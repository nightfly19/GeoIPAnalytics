from twisted.internet.protocol import DatagramProtocol
from twisted.internet.protocol import Factory
from twisted.internet import reactor
from twisted.web import server, resource, static

import pygeoip

import json
import collections

class LocationStats(object):

    def __init__(self, geoip_db, minute_breakdowns=(1, 5, 15, 60)):
        self.geoip_db = geoip_db
        self.cur_stats = collections.Counter()

        self.minute_breakdowns = minute_breakdowns
        self.stats_by_minute = {}
        for i in minute_breakdowns:
            self.stats_by_minute[i] = collections.Counter()
        self.old_stats_queue = collections.deque()
        self.max_minute_breakdown = int(max(minute_breakdowns))

        # Normalization factor
        self.max_cnt = 0

        self.min_count = 0
        reactor.callLater(60, self.next_minute)

    def next_minute(self):
        self.min_count += 1
        for i in self.minute_breakdowns:
            self.stats_by_minute[i] = self.stats_by_minute[i] + self.cur_stats
            if self.min_count >= i:
                try:
                    sub_stats = self.old_stats_queue[i-1]
                except IndexError:
                    continue
                else:
                    self.stats_by_minute[i] = self.stats_by_minute[i] - self.old_stats_queue[i-1]

        # Flip stats buffers
        self.old_stats_queue.appendleft(self.cur_stats)
        self.cur_stats = collections.Counter()
        if self.min_count >= self.max_minute_breakdown:
            self.old_stats_queue.pop()

        reactor.callLater(60, self.next_minute)

    def saw_addr(self, addr):
        rec = self.geoip_db.record_by_addr(addr)
        self.cur_stats[(rec['latitude'], rec['longitude'])] += 1

        # set normalization factor
        cnt = self.cur_stats[(rec['latitude'], rec['longitude'])]
        if cnt > self.max_cnt:
            self.max_cnt = cnt

    def get_stats(self, min_breakdown=None):
        if min_breakdown == None:
            return self.cur_stats
        else:
            return self.stats_by_minute[min_breakdown]


class JsonStats(resource.Resource):

    isLeaf = True

    def __init__(self, loc_stats):
        self.loc_stats = loc_stats

    def render_GET(self, request):
        request.setHeader("content-type", "application/json")
        ret_data = []
        for min_bd in self.loc_stats.minute_breakdowns:
            set_data = []
            for loc, value in self.loc_stats.get_stats(min_bd).items():
                set_data.append(loc[0])
                set_data.append(loc[1])
                set_data.append(value / float(self.loc_stats.max_cnt))
            ret_data.append([str(min_bd), set_data])
        return json.dumps(ret_data)


class IpReceiver(DatagramProtocol):

    def __init__(self, loc_stats):
        self.loc_stats = loc_stats

    def datagramReceived(self, data, (host, port)):
        ips = data.split('\n')
        for ip in ips:
            try:
                vals = [int(x) for x in ip.split('.')]
            except ValueError:
                pass
            else:
                self.loc_stats.saw_addr(ip)


def main():
    db = pygeoip.GeoIP('GeoIP.dat')
    loc_stats = LocationStats(db)
    root_site = static.File("static")
    root_site.putChild("stats.json", JsonStats(loc_stats))

    reactor.listenTCP(8880, server.Site(root_site))
    reactor.listenUDP(8999, IpReceiver(loc_stats))
    reactor.run()


if __name__ == '__main__':
    main()

