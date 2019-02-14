#!/usr/bin/env python3
__author__ = "h5vx"
__version__ = '1.0.0'

import sys
import asyncio
import argparse
import requests

from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from db import DBThread

# Sometimes, when threads count is big, there is proxy error happens
# constant below is number of retries on proxy error, before give up
MAX_PROXY_ERR_COUNT = 5
PROXY = {
    'http': 'http://127.0.0.1:4444'
}


def to_url(hostname):
    if 0 in (hostname.find('http://'), hostname.find('https://')):
        return hostname
    return 'http://' + hostname


def hostname(url):
    return urlparse(url).hostname


def check(session, url, timeout):
    try:
        r = session.get(url, timeout=timeout)
    except requests.ReadTimeout:
        r = False

    return r


def get_and_check_args():
    p = argparse.ArgumentParser()
    p.add_argument('file', type=str, help="File with hostnames")
    p.add_argument('-t', '--threads', type=int, 
                    help="Number of threads (5 default)", default=5)
    p.add_argument('-n', '--timeout', type=float, 
                    help="Timeout, seconds (60 default)", default=60)
    p.add_argument('-p', '--proxy', type=str, 
                    help="HTTP Proxy address (default %s)" % PROXY['http'])
    p.add_argument('-np', '--no-proxy', action='store_true',
                    help="Proceed without proxy")
    args = p.parse_args()

    try:
        f = open(args.file, 'tr')
    except:
        print('Cannot open file "%s"' % args.file, file=sys.stderr)
        exit(1)
    f.close()

    if args.threads < 1:
        print("Cannot use %d threads" % args.threads, file=sys.stderr)
        exit(2)

    if args.proxy:
        if 'http://' not in args.proxy:
            args.proxy = 'http://' + args.proxy
        PROXY['http'] = args.proxy

    return args


def read_hostnames(filename):
    f = open(filename, 'tr')
    hostnames = f.read().split()
    f.close()

    return hostnames


async def main(db_thread):
    args = get_and_check_args()

    def proceed_result(hostname, r):
        updated = datetime.now()  # .strftime('%d %b %H:%M:%S')

        if r and r.status_code == 200:
            print("%15s UP (%.3f seconds)" % (
                hostname, 
                r.elapsed.total_seconds()
            ))
            db_thread.q.put_nowait({
                'host': hostname,
                'type': 'UP',
                'latency': r.elapsed.total_seconds(),   
                'updated': updated
            })
        else:
            if r == False:
                reason = "TIMEOUT" 
            else: 
                reason = "DOWN (%d)" % r.status_code

            print("%15s %s" % (hostname, reason))
            db_thread.q.put_nowait({
                'host': hostname,
                'type': 'DOWN',
                'reason': reason,
                'latency': float(args.timeout), 
                'updated': updated
            })

    def proceed_error(hostname, exc):
        updated = datetime.now()

        print("%r generated an exception: %s" % (hostname, exc))
        db_thread.q.put_nowait({
            'host': hostname,
            'type': 'ERROR',
            'reason': str(exc),
            'updated': updated
        })
    
    hostnames = read_hostnames(args.file)
    sess = requests.session()
    sess.proxies = PROXY if not args.no_proxy else None

    db_thread.start()
    with ThreadPoolExecutor(max_workers=args.threads) as executor:
        future_to_hostname = {
            executor.submit(check, sess, to_url(hostname), args.timeout): hostname 
            for hostname in hostnames
        }
        proxyerrs = dict()

        for future in as_completed(future_to_hostname):
            hostname = future_to_hostname[future]
            try:
                r = future.result()
            except requests.exceptions.ProxyError as exc:
                proxyerrs[hostname] = proxyerrs.get(hostname, 0) + 1
                if proxyerrs[hostname] > MAX_PROXY_ERR_COUNT:
                    proceed_error(hostname, exc)
                else:
                    ft = executor.submit(check, sess, to_url(hostname), args.timeout)
                    future_to_hostname[ft] = hostname
            except Exception as exc:
                proceed_error(hostname, exc)
            else:
                proceed_result(hostname, r)
    db_thread.stop()


if __name__ == "__main__":
    db_thread = DBThread("hosts.db")

    try:
        if 'run' in dir(asyncio):  # Python>=3.7
            asyncio.run(main(db_thread))
        else:
            loop = asyncio.get_event_loop()
            loop.run_until_complete(asyncio.wait([main(db_thread)]))
            loop.close()
    except KeyboardInterrupt:
        if db_thread.is_alive():
            db_thread.stop()
