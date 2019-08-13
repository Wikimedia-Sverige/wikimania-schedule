import urllib.parse
import requests
import json
import os
from itertools import islice
from pprint import pprint

user_agent = 'Program converter/0.1'
query_url = 'https://wikimania.wikimedia.org/w/api.php'

start = '{{Program item|'
start2 = start + 'title='
page_size = 50

def main():
    filename = max(f for f in os.listdir('.') if f[0].isdigit())
    titles = [
        '2019:Program/Free Knowledge and the Global Goals Spotlight Session'
    ]
    for line in open(filename):
        if start not in line or '}}' not in line:
            continue
        item = line[line.find(start):line.rfind('}}') + 2]
        if not item.startswith(start2):
            print(line)
        assert item.startswith(start2)
        title = item[len(start2):item.find('|', len(start2))].strip()
        if not title or title == 'Test':
            continue
        title = tidy_title(title)
        titles.append(title)
    get_pages(titles)
    extracts(titles)

def tidy_title(title):
    return urllib.parse.unquote(title.replace('_', ' '))

def chunk(it, size):
    it = iter(it)
    return iter(lambda: tuple(islice(it, size)), ())

def run_query(titles, params):
    base = {
        'format': 'json',
        'formatversion': 2,
        'action': 'query',
        'continue': '',
        'titles': '|'.join(titles),
    }
    p = base.copy()
    p.update(params)

    r = requests.get(query_url, params=p, headers={'User-Agent': user_agent})
    json_reply = r.json()
    if 'query' not in json_reply:
        pprint(json_reply)
    return json_reply['query']['pages']

def extracts_query(titles):
    params = {
        'prop': 'extracts',
        'exlimit': 'max',
        # 'exintro': '1',
        'explaintext': '1',
    }
    return run_query(titles, params)

def get_extracts(titles):
    for cur in chunk(titles, page_size):
        for page in extracts_query(cur):
            yield page

def get_page_iter(titles):
    for cur in chunk(titles, page_size):
        params = {'prop': 'revisions', 'rvprop': 'ids|content'}
        pages = run_query(cur, params)
        for page in pages:
            yield page

def get_pages(titles):
    for page in get_page_iter(titles):
        if 'missing' in page:
            continue
        if 'pageid' not in page:
            print(json.dumps(page, indent=2))
        pageid = page['pageid']
        out = open(f'pages/{pageid:05d}.json', 'w')
        json.dump(page, out)
        out.close()

def extracts(titles):
    for page in get_extracts(titles):
        print(page)
        if 'missing' in page:
            continue
        pageid = page['pageid']
        out = open(f'extracts/{pageid:05d}.json', 'w')
        json.dump(page, out)
        out.close()
