import re
import os
import urllib.parse
import json
from lxml import etree
from defaultlist import defaultlist

re_heading = re.compile(r'==\s*(.*August)\s*==')
re_row_class = re.compile(r'^\|- class="([^"]+)"')
re_room_name = re.compile(r'^(.+)<br>(?:<[^>]*>)*\'+([A-Z]\d+)\'+')
re_colspan = re.compile(r'^\s*colspan="(\d)"\s*\|\s*')
re_col = re.compile(r'(?:!!|\|\|)')
re_day = re.compile(r'^[A-Z][a-z]+ (\d+) August')
re_attribs = re.compile(r' *([a-z]+)="([^"]*)"')
re_link = re.compile(r' *\[\[[^|]*\|(.*)\]\]')

def tidy_room_name(room):
    if room.startswith("'''") and room.endswith("'''"):
        return room[3:-3]
    if '<br>' not in room:
        return room
    m = re_room_name.match(room)
    return f'{m.group(1)} ({m.group(2)})'

def get_abstract(content):
    if '=== Description ===' not in content:
        return

    lines = []
    capture = False
    for line in content.splitlines():
        if '=== Description ===' in line:
            capture = True
            continue
        if capture:
            if line.startswith('==='):
                break
            if line.startswith('<!--'):
                continue
            if line.startswith('[[File:'):
                continue
            lines.append(line)

    return '\n'.join(lines).strip()

def track_from_title(title):
    track = title[5:title.find('/')]
    return urllib.parse.unquote(track.replace('_', ' '))

def iter_schedule():
    in_table = False
    day = None
    tables = []
    filename = max(f for f in os.listdir('.') if f[0].isdigit())
    for line in open(filename):
        m = re_heading.match(line.strip())
        if m:
            if day:
                yield(day, tables)
            day = m.group(1)
            cur_table = []
            tables = [cur_table]
        if not in_table and day and 'wikitable schedule' in line:
            in_table = True
        if in_table:
            cur_table.append(line[:-1])
        if in_table and '|}' in line:
            in_table = False
            cur_table = []
            tables.append(cur_table)

    yield(day, tables)

def extend_grid(grid, rows, cols):
    if len(grid) <= rows:
        grid += [None] * (rows - len(grid))

def set_grid(grid, row, col, value):
    if '|' in value:
        attribs = dict(re_attribs.findall(value))
        if attribs:
            value = value[value.find('|') + 1:].strip()
        for key in 'colspan', 'rowspan':
            if key in attribs:
                attribs[key] = int(attribs[key])
    else:
        attribs = {}

    attribs.setdefault('colspan', 1)
    attribs.setdefault('rowspan', 1)

    attribs['text'] = value
    while grid[row][col] is not None:
        col += 1
    assert '{{Program item' not in value or col != 0
    attribs['row'] = row
    attribs['col'] = row
    for xrow in range(row, row + attribs['rowspan']):
        for xcol in range(col, col + attribs['colspan']):
            grid[xrow][xcol] = attribs

def parse_table(table):
    grid = defaultlist(defaultlist)
    row_class = defaultlist()
    cur_row = 0
    cur_col = 0
    seen_cols = False
    for line in table:
        xline = line.rstrip()
        if xline.startswith('|}'):
            break
        if xline.startswith('|-'):
            cur_col = 0
            if seen_cols:
                cur_row += 1
            seen_cols = False
            m = re_attribs.search(line)
            if m:
                assert m.group(1) == 'class'
                row_class[cur_row] = m.group(2)
        elif xline.startswith('|') or xline.startswith('!'):
            seen_cols = True
            if '||' in line or '!!' in line:
                cols = re_col.split(xline[1:])
                # if len(grid) <= cur_row:
                #     grid += [None] * ((cur_row - len(grid)) + 1)

                for num, i in enumerate(cols):
                    set_grid(grid, cur_row, cur_col + num, i)
                cur_col += num
            else:
                # if len(grid) <= cur_row:
                #     grid += [None] * ((cur_row - len(grid)))

                set_grid(grid, cur_row, cur_col, line[1:])
                cur_col += 1

    return (row_class, grid)

    for i, row in enumerate(grid):
        print(len(row))
        print('grid:', i, row)

def cell_text(cell):
    return cell.get('text') if cell else None

def parse_program_item(text):
    start = '{{Program item|'
    assert text.startswith(start)
    parts = {}
    for pair in text[len(start):-2].split('|'):
        key, _, value = pair.partition('=')
        if value:
            parts[key] = value
    return parts

def rowspan_to_duration(rowspan):
    mins = rowspan * 15
    return f'{mins // 60:02d}:{mins % 60:02d}'

def is_program_item(text):
    return text.startswith('{{Program item|') and text.endswith('}}')

def table_to_items(table):
    row_class, grid = parse_table(table)

    rooms = defaultlist()

    start_cell = cell_text(grid[0][0])

    if not start_cell or 'Building' not in start_cell:
        return None, None
    room_row = next(row for row in range(len(row_class)) if row_class[row] == 'room')
    for i in range(1, len(grid[room_row]) - 1):
        text = tidy_room_name(cell_text(grid[room_row][i]))
        rooms[i] = text

    seen = set()

    if False:
        for row in range(0, len(grid)):
            cls = row_class[row]
            print(cls)

    items = []
    last_time = None
    spaces = {}
    for row in range(2, len(grid)):
        cls = row_class[row]
        if cls == 'space':
            for column in range(len(grid[row])):
                if column > 0 and column < len(grid[row]):
                    # First and last cell says "Space".
                    cell = grid[row][column]
                    if cell['rowspan'] == 1:
                        match = re_link.match(cell['text'])
                        if match:
                            space = match[1].lower()
                            spaces[column] = space
        if cls != 'items':
            continue

        row_time = cell_text(grid[row][0])
        time_rows = grid[row][0]['rowspan']
        if last_time and time_rows > 1:
            for item in items:
                if item['start'] == last_time:
                    item['duration'] = \
                        rowspan_to_duration(item['rows'] - (time_rows - 1))
        assert len(row_time) == 5

        for col in range(1, len(grid[row])):
            cell = grid[row][col]
            text = cell_text(cell)
            if text is None:
                continue
            if not is_program_item(text) or text in seen:
                continue
            seen.add(text)
            item = parse_program_item(text)
            if '/' not in item['title']:
                continue
            assert item['title'].startswith('2019:')
            if row != cell['row']:
                assert cell_text(grid[cell['row']][col]) == text
            item['start'] = row_time
            last_time = row_time
            item['rows'] = cell['rowspan']
            item['duration'] = rowspan_to_duration(cell['rowspan'])
            item['room'] = rooms[col]
            item['identifiers'] = []
            for k, v in item.items():
                if v == 'yes':
                    item['identifiers'].append(k)
            item['space'] = spaces[col]
            items.append(item)

    return rooms, items

def get_presenters(item):
    if 'presenters' not in item:
        return
    text = item['presenters'].strip()
    if not text:
        return
    bad = {'TBD', 'Documentation and quality process workshop', 'quality process workshop'}
    text = text.replace(' and ', ', ')
    text = text.replace(', M.D.', ' M.D.')
    values = [i.strip() for i in text.split(', ')]
    values = [i for i in values if i and i not in bad]
    return values or None

def build_event(room, item, title, event_id, presenters):
    display = item['displayname']
    event_data = [
        ('start', item['start']),
        ('duration', item['duration']),
        ('room', item['room']),
        ('title', display),
        ('subtitle', ''),
        # ('slug', slugify(display)),
        ('track', item.get('track') or track_from_title(item['title'])),
        # ('type', 'maintrack'),
        ('language', ''),
        ('abstract', item['abstract']),
        ('description', ''),
    ]
    if 'space' in item:
        event_data.append(('space', item['space']))

    # event_id = page_ids.get(title)
    event = etree.SubElement(room, 'event', id=str(event_id))
    for key, value in event_data:
        etree.SubElement(event, key).text = str(value)

    # url_title = title.replace(' ', '_')
    url_title = urllib.parse.quote(title.replace(' ', '_'))
    url = 'https://wikimania.wikimedia.org/wiki/' + url_title

    if presenters:
        persons = etree.SubElement(event, 'persons')
        for person_id, name in presenters:
            etree.SubElement(persons,
                             'person',
                             id=str(person_id)).text = name

    links = etree.SubElement(event, 'links')
    etree.SubElement(links, 'link', href=url).text = 'detail'
    identifiers = etree.SubElement(event, 'identifiers')
    if 'identifiers' in item:
        for identifier in item['identifiers']:
            identifiers.set(identifier, 'yes')

spotlight_abstract = '''How does Free Knowledge relate to Sustainable Development? Can the Wikimedia movement contribute to a better world? What role can free knowledge play in the work to fulfill Agenda 2030 – the world's shared vision for a sustainable future?

Welcome to a full day's session addressing these questions, opening up the floor for international leaders to give their view on Free Knowledge and the Global Goals. The session will be recorded by the national Swedish broadcaster Utbildningsradion and eventually aired on Kunskapskanalen!'''

def main():
    person_ids = {}
    max_person_id = 0

    page_ids = {}
    abstracts = {}
    for f in os.scandir('pages'):
        page = json.load(open(f.path))
        title = page['title']
        assert title not in page_ids
        page_ids[title] = page['pageid']
        # print(page['pageid'], title)
        content = page['revisions'][0]['content']
        abstract = get_abstract(content)
        if abstract:
            abstracts[title] = abstract
        # print((page['pageid'], page['title']))

    page_ids['2019:Diversity/Lightning talks#Sunday'] = 90001
    page_ids['2019:Libraries/Ideation sessions#Part 2'] = 90002
    page_ids['2019:Libraries/Ideation sessions#Part 3'] = 90003
    page_ids['2019:Hackathon/program#Sunday, August 18: WIKIMANIA HACKATHON CLOSING / SHOWCASE'] = 90004

    meta = [
        ('title', 'Wikimania 2019'),
        ('subtitle', 'Stronger Together: Wikimedia, Free Knowledge and the Sustainable Development Goals'),
        ('venue', 'Aula Magna, Stockholm University'),
        ('city', 'Stockholm'),
        ('start', '2019-08-16'),
        ('end', '2019-08-18'),
        ('days', 3),
        ('day_change', '09:00:00'),
        ('timeslot_duration', '00:15:00'),
    ]

    root = etree.Element('schedule')
    conf = etree.SubElement(root, 'conference')
    for key, value in meta:
        etree.SubElement(conf, key).text = str(value)

    index = 0
    event_id = 0
    for day_heading, tables in iter_schedule():
        index += 1
        m = re_day.match(day_heading)
        d = f'2019-08-{m.group(1)}'

        day = etree.SubElement(root, 'day')
        day.set('index', str(index))
        day.set('date', d)

        rooms = None
        items = []

        if d == '2019-08-16':  # Friday
            room_name = 'Plenary sessions'
            room = etree.SubElement(day, 'room', name=room_name)
            title = '2019:Program/Free Knowledge and the Global Goals Spotlight Session'

            item = {
                'abstract': spotlight_abstract,
                'displayname': 'Free Knowledge and the Sustainable Development Goals',
                'start': '13:00',
                'duration': '01:30',
                'room': room_name,
                'track': 'Spotlight session',
            }

            build_event(room, item, title, 90005, [])

            item = {
                'abstract': spotlight_abstract,
                'displayname': 'Free Knowledge and the Sustainable Development Goals (Continued)',
                'start': '15:00',
                'duration': '02:00',
                'room': room_name,
                'track': 'Spotlight session',
            }

            build_event(room, item, title, 90006, [])

        for table in tables:
            xrooms, xitems = table_to_items(table)
            if xrooms is None:
                continue
            if rooms is None:
                rooms = xrooms
            items += xitems

        added_items = []
        for room_name in rooms:
            if not room_name:
                continue

            room_items = [item for item in items if item['room'] == room_name]
            if not room_items:
                continue
            room = etree.SubElement(day, 'room', name=room_name)
            for item in room_items:
                if item in added_items:
                    # HACK: Don't add multiple events for rooms that
                    # span several columns.
                    continue
                title = urllib.parse.unquote(item['title'].replace('_', ' ')).strip()
                item['abstract'] = abstracts.get(title, '')
                event_id = page_ids[title]

                presenter_names = get_presenters(item) or []
                presenters = []
                for name in presenter_names:
                    if name in person_ids:
                        person_id = person_ids[name]
                    else:
                        max_person_id += 1
                        person_id = person_ids[name] = max_person_id
                    presenters.append((person_id, name))

                build_event(room, item, title, event_id, presenters)
                added_items.append(item)

    as_xml = etree.tostring(root,
                            xml_declaration=True,
                            encoding='utf-8',
                            pretty_print=True)
    return as_xml.decode('utf-8')

def test_rowspan_to_duration():
    for rowspan in range(1, 10):
        print(rowspan, rowspan_to_duration(rowspan))
