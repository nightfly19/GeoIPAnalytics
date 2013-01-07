from twisted.internet.protocol import DatagramProtocol
from twisted.internet.protocol import Factory
from twisted.internet import reactor
from twisted.web import server, resource

import pygeoip

class LocationStats(object):

    def __init__(self, geoip_db):
        self.geoip_db = geoip_db
        self.locs_seen = {}

    def saw_addr(self, addr):
        rec = self.geoip_db.record_by_addr(addr)
        try:
            self.locs_seen[(rec['latitude'], rec['longitude'])] += 1
        except KeyError:
            self.locs_seen[(rec['latitude'], rec['longitude'])] = 1

    def get_stats(self):
        return self.locs_seen


class StatsSite(resource.Resource):

    isLeaf = True

    def __init__(self, loc_stats):
        self.loc_stats = loc_stats

    def render_GET(self, request):
        for loc, value in self.loc_stats.get_stats().items():
            print loc, value


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

    reactor.listenTCP(8880, server.Site(StatsSite(loc_stats)))
    reactor.listenUDP(8999, IpReceiver(loc_stats))
    reactor.run()


if __name__ == '__main__':
    main()

