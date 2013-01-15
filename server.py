from twisted.internet.protocol import DatagramProtocol
from twisted.internet.protocol import Factory
from twisted.internet import reactor
from twisted.web import server, resource, static
from twisted.names.client import Resolver, createResolver

import pygeoip

import demjson
from collections import deque, Counter

class IPStats(object):

    def __init__(self):
        self.seen_ips = Counter()
        self.bot_ips = Counter()
        self.resolver = createResolver()

    def saw_ip(self, ip):
        if ip not in self.seen_ips:
            self.seen_ips[ip] = True
            print ip
            d = self.resolver.lookupPointer('.'.join(ip.split('.')[::-1]) + '.in-addr.arpa')
            d.addCallback(self.ptr_response, ip)
            d.addErrback(self.ptr_error, ip)

    def is_bot(self, addr):
        return self.bot_ips[addr] > 0
    
    def ptr_error(self, err, ip):
        print 'Error looking up reverse dns for %s' % ip
        if ip in self.seen_ips:
            del self.seen_ips[ip]

    def ptr_response(self, resp, ip):
        res = str(resp[0][0].payload.name)
        if res.endswith('.googlebot.com') or res.endswith('.search.msn.com')\
            or res.endswith('.crawl.yahoo.net') or res.endswith('.crawl.baidu.com.'):
            self.bot_ips[ip] += 1
            print 'found bot %s with addr %s' % (res, ip)


class LocationStats(object):

    def __init__(self, geoip_db, minute_breakdowns=(1, 5, 15, 60)):
        self.geoip_db = geoip_db
        self.ip_stats = IPStats()
        self.cur_stats = Counter()

        self.minute_breakdowns = minute_breakdowns
        self.stats_by_minute = {}
        for i in minute_breakdowns:
            self.stats_by_minute[i] = Counter()
        self.old_stats_queue = deque()
        self.max_minute_breakdown = int(max(minute_breakdowns))
        reactor.callLater(60, self.next_minute)
        self.min_count = 0

    def next_minute(self):
        self.min_count += 1
        for i in self.minute_breakdowns:
            if self.min_count >= i:
                try:
                    sub_stats = self.old_stats_queue[i-1]
                except IndexError:
                    pass
                else:
                    self.stats_by_minute[i] = self.stats_by_minute[i] - sub_stats
            self.stats_by_minute[i] = self.stats_by_minute[i] + self.cur_stats

        # Flip stats buffers
        self.old_stats_queue.appendleft(self.cur_stats)
        self.cur_stats = Counter()
        if self.min_count > self.max_minute_breakdown:
            self.old_stats_queue.pop()

        try:
            del self.json_stats_cached
        except AttributeError:
            pass
        reactor.callLater(60, self.next_minute)

    def saw_addr(self, addr):
        rec = self.geoip_db.record_by_addr(addr)
        if rec == None:
            return

        self.ip_stats.saw_ip(addr)
        if self.ip_stats.is_bot(addr):
            return

        self.cur_stats[(rec['latitude'], rec['longitude'])] += 1

        # set normalization factor
        cnt = self.cur_stats[(rec['latitude'], rec['longitude'])]

    def get_stats(self, min_breakdown=None):
        if min_breakdown == None:
            return self.cur_stats
        else:
            return self.stats_by_minute[min_breakdown]

    def get_json_stats(self):
        try:
            return self.json_stats_cached
        except AttributeError:
            pass

        ret_data = deque()
        for min_bd in self.minute_breakdowns:
            set_data = deque()
            try:
                max_cnt = self.get_stats(min_bd).most_common(1)[0][1] * 1.0001
            except IndexError:
                ret_data.append([str(min_bd), set_data])
                continue
            for loc, value in self.get_stats(min_bd).items():
                set_data.extend((loc[0], loc[1], value / max_cnt))
            ret_data.append([str(min_bd), set_data])
        self.json_stats_cached = demjson.encode(ret_data, encoding='ascii')
        return self.json_stats_cached


class JsonStats(resource.Resource):

    isLeaf = True

    def __init__(self, loc_stats):
        self.loc_stats = loc_stats

    def render_GET(self, request):
        request.setHeader("content-type", "application/json")
        return self.loc_stats.get_json_stats()


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
