GeoIP Analtics
==============

A server for collecting and visualising data based on geoip lookups.


Setup
=====

    pip install -r requirements.txt


    wget -O- -N http://geolite.maxmind.com/download/geoip/database/GeoLiteCity.dat.gz | gunzip > GeoIP.dat



Run
===

    python server.py


    echo "131.252.208.38" | nc -q1 -u4 servername 8999

