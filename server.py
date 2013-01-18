from twisted.internet.protocol import DatagramProtocol
from twisted.internet.protocol import Factory
from twisted.internet import reactor
from twisted.web import server, resource, static
from twisted.names.client import Resolver, createResolver

import pygeoip

import demjson
from collections import deque, Counter


class MultiIntervalCounter(object):

    def __init__(self, interval=60, multiples=(1,5,10,60)):
        self.counter = Counter()
        self.interval = interval
        self.multiples = multiples
        self.multi_counters = {}
        self.counter_backlogs = {}
        for i in multiples:
            self.multi_counters[i] = Counter()
            self.counter_backlogs[i] = deque()
        reactor.callLater(interval, self.next_interval)

    def next_interval(self):
        for i, c in self.counter_backlogs.items():
            if len(c) >= i:
                self.multi_counters[i] -= c[i-1]
            self.multi_counters[i] += self.counter
            c.appendleft(self.counter)
        self.counter = Counter()
        reactor.callLater(self.interval, self.next_interval)

    def most_common(self, count):
        return [(i, self.multi_counters[i].most_common(count)) for i in self.multiples]


class IPStats(object):

    def __init__(self, loc_stats, minute_breakdowns=(1, 5, 15, 60)):
        self.loc_stats = loc_stats
        self.seen_ips = Counter()
        self.bot_ips = Counter()
        self.non_bot_ips = MultiIntervalCounter(multiples=minute_breakdowns)
        self.rdns = MultiIntervalCounter(multiples=minute_breakdowns)
        self.resolver = createResolver()

    def saw_ip(self, ip):
        if ip not in self.seen_ips:
            self.seen_ips[ip] = True
            d = self.resolver.lookupPointer('.'.join(ip.split('.')[::-1]) + '.in-addr.arpa')
            d.addCallback(self.ptr_response, ip)
            d.addErrback(self.ptr_error, ip)
        if not self.is_bot(ip):
            self.non_bot_ips.counter[ip] += 1

    def is_bot(self, addr):
        return self.bot_ips[addr] > 0
    
    def ptr_error(self, err, ip):
        if ip in self.seen_ips:
            del self.seen_ips[ip]

    def ptr_response(self, resp, ip):
        res = str(resp[0][0].payload.name)

        if res.endswith('.googlebot.com') or res.endswith('.search.msn.com')\
                or res.endswith('.crawl.yahoo.net') or res.endswith('.crawl.baidu.com.')\
                or res.endswith('.google.com') or res.endswith('.yandex.com'):
            self.bot_ips[ip] += 1
            self.loc_stats.decrement_addr(ip)
            self.non_bot_ips.counter[ip] -= 1
        else:
            postfixes = res.split('.')
            if len(postfixes) > 3:
                postfixes = postfixes[-3:]
            for i, postfix in enumerate(postfixes):
                pf = '.'.join([x for x in postfixes[-i:]])
                self.rdns.counter[pf] += 1


class LocationStats(object):

    def __init__(self, geoip_db, minute_breakdowns=(1, 5, 15, 60)):
        self.geoip_db = geoip_db
        self.ip_stats = IPStats(self, minute_breakdowns=minute_breakdowns)
        self.stats = MultiIntervalCounter(multiples=minute_breakdowns)

    def saw_addr(self, addr):
        rec = self.geoip_db.record_by_addr(addr)
        if rec == None:
            return

        self.ip_stats.saw_ip(addr)
        if self.ip_stats.is_bot(addr):
            return

        self.stats.counter[(rec['latitude'], rec['longitude'])] += 1

    def decrement_addr(self, addr):
        rec = self.geoip_db.record_by_addr(addr)
        if rec == None:
            print 'This shouldnt happen, inval dec addr'
            return

        self.stats.counter[(rec['latitude'], rec['longitude'])] -= 1


class GlobeStats(resource.Resource):

    isLeaf = True

    def __init__(self, loc_stats):
        self.loc_stats = loc_stats

    def render_GET(self, request):
        request.setHeader("content-type", "application/json")
        data = []
        for i in self.loc_stats.stats.multiples:
            c = self.loc_stats.stats.multi_counters[i]
            vals = deque()
            maxval = 0
            try:
                maxval = float(c.most_common(1)[0][1])
            except IndexError:
                pass
            for loc, val in c.items():
                vals.extend((loc[0], loc[1], val / maxval))
            data.append((str(i), vals))
        return str(demjson.encode(data))


class TopRdns(resource.Resource):

    isLeaf = True

    def __init__(self, ip_stats):
        self.ip_stats = ip_stats

    def render_GET(self, request):
        request.setHeader("content-type", "application/json")
        return str(demjson.encode(self.ip_stats.rdns.most_common(100)))


class TopIps(resource.Resource):

    isLeaf = True

    def __init__(self, ip_stats):
        self.ip_stats = ip_stats

    def render_GET(self, request):
        request.setHeader("content-type", "application/json")
        return str(demjson.encode(self.ip_stats.non_bot_ips.most_common(100)))


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
    root_site.putChild("globe_stats.json", GlobeStats(loc_stats))
    root_site.putChild("top_ips.json", TopIps(loc_stats.ip_stats))
    root_site.putChild("top_rdns.json", TopRdns(loc_stats.ip_stats))

    reactor.listenTCP(8880, server.Site(root_site))
    reactor.listenUDP(8999, IpReceiver(loc_stats))
    reactor.run()


if __name__ == '__main__':
    main()
