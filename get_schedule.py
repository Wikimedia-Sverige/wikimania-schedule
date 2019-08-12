#!/usr/bin/python3
import requests
from datetime import datetime
from pprint import pprint

user_agent = 'Program converter/0.1'
query_url = 'https://wikimania.wikimedia.org/w/api.php'


def run_query(title, params):
    base = {
        'format': 'json',
        'formatversion': 2,
        'action': 'query',
        'continue': '',
        'titles': title,
    }
    p = base.copy()
    p.update(params)

    r = requests.get(query_url, params=p, headers={'User-Agent': user_agent})
    json_reply = r.json()
    if 'query' not in json_reply:
        pprint(json_reply)
    return json_reply['query']['pages']


params = {'prop': 'revisions', 'rvprop': 'ids|content'}
page = run_query('2019:Program', params)[0]['revisions'][0]['content']

now = datetime.now().strftime('%Y%m%d%H%M') + '.mediawiki'
out = open(now, 'w')
out.write(page)
out.close()
# pprint(page, stream=open(now, 'w'))
