from twisted.internet.protocol import DatagramProtocol
from twisted.internet.protocol import Factory
from twisted.internet import reactor
from twisted.web import server, resource, static

import pygeoip

import json

class LocationStats(object):

    def __init__(self, geoip_db):
        self.geoip_db = geoip_db
        self.locs_seen = {}
        self.max_cnt = 0

    def saw_addr(self, addr):
        rec = self.geoip_db.record_by_addr(addr)
        try:
            self.locs_seen[(rec['latitude'], rec['longitude'])] += 1
        except KeyError:
            self.locs_seen[(rec['latitude'], rec['longitude'])] = 1
        cnt = self.locs_seen[(rec['latitude'], rec['longitude'])]
        if cnt > self.max_cnt:
            self.max_cnt = cnt

    def get_stats(self):
        return self.locs_seen


class JsonStats(resource.Resource):

    isLeaf = True

    def __init__(self, loc_stats):
        self.loc_stats = loc_stats

    def render_GET(self, request):
        request.setHeader("content-type", "application/json")
        ret_data = []
        for loc, value in self.loc_stats.get_stats().items():
            ret_data.append(loc[0])
            ret_data.append(loc[1])
            ret_data.append(value / float(self.loc_stats.max_cnt))
        return json.dumps([["10min", ret_data]])


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

