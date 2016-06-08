import os
import sys
import re
import schedule
import time
import urllib.request
import xmlrpc.client

################################################################################
# Gandi.net API (Production) key
apikey = os.environ.get('API_KEY')

# Gandi.net API (Production) URL
apiurl = os.environ.get('API_URL', 'https://rpc.gandi.net/xmlrpc/')

# Domain
domain = os.environ.get('DOMAIN')

# A-record name
a_name = os.environ.get('RECORD', '@')

# TTL Default 15 minutes
ttl = os.environ.get('TTL', 900)

# Production API
api = xmlrpc.client.ServerProxy(apiurl, verbose=False)

# Used to cache the zone_id for future calls
zone_id = None

# Used to get current public IP
ipapiurl = 'http://ipv4.myexternalip.com/raw'

################################################################################

def get_ip():
    """ Get external IP """

    try:
        ip = urllib.request.urlopen(ipapiurl, timeout=3).read()
    except Exception:
        sys.stderr.write('Error: Unable to external IP address.\n')
        sys.exit(2);

    return re.sub(r'[^0-9\.]', '', str(ip))

def get_zone_id():
    """ Get the gandi.net ID for the current zone version"""

    global zone_id

    if zone_id is None:
        try:
            domain_info = api.domain.info(apikey, domain)
            current_zone_id = domain_info['zone_id']

            if current_zone_id == 'None':
                sys.stderr.write('No zone - make sure domain is set to use gandi.net name servers.\n')
                sys.exit(1)

            zone_id = current_zone_id
        except Exception:
            sys.stderr.write('Error: Unable to read domain info.\n')
            sys.stderr.write('Please check your API URL (%s) API Key (%s) and domain (%s).\n' % (apiurl, apikey, domain))
            sys.exit(2)

    return zone_id

def get_zone_ip():
    """Get the current IP from the A record in the DNS zone """

    ip = '0.0.0.0'

    current_zone = api.domain.zone.record.list(apikey, get_zone_id(), 0)

    # There may be more than one A record - we're interested in one with
    # the specific name (typically @ but could be sub domain)
    for d in current_zone:
      if d['type'] == 'A'and d['name'] == a_name:
        ip = d['value']

    return ip.strip()

def change_zone_ip(new_ip):
    """ Change the zone record to the new IP """

    # Define record zone
    zone_record = {'name': a_name, 'value': new_ip, 'ttl': ttl, 'type': 'A'}

    # Get a new zone version
    new_zone_ver = api.domain.zone.version.new(apikey, get_zone_id())

    # Clear old A record (defaults to previous verison's
    api.domain.zone.record.delete(apikey, get_zone_id(), new_zone_ver,{'type':'A', 'name': a_name})

    # Add in new A record
    api.domain.zone.record.add(apikey, get_zone_id(), new_zone_ver, zone_record)

    # Set new zone version as the active zone
    api.domain.zone.version.set(apikey, get_zone_id(), new_zone_ver)

def job():
    """ Execute the change if necessary """
    zone_ip = get_zone_ip()
    current_ip = get_ip()

    if (zone_ip == current_ip):
        print('No change detected.')
    else:
        print('DNS Mistmatch detected: A-record: ', zone_ip, ' WAN IP: ', current_ip)
        change_zone_ip(current_ip)
        zone_id = None
        zone_ip = get_zone_ip();
        print('DNS A record update complete - set to ', zone_ip)

################################################################################

# Setup de schedule
schedule.every().day.at('00:00').do(job)

# Execute job for the first time
# Useful to test the configuration
print('----------------------')
print(' Application launched ')
print('----------------------')
job()

# Run the magic loop
while True:
    schedule.run_pending()
    time.sleep(1)

################################################################################
