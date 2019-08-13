import os

import get_schedule
import get_titles
import parse_schedule

for d in 'pages', 'extracts':
    if not os.path.exists(d):
        os.mkdir(d)

get_schedule.main()
get_titles.main()
xml = parse_schedule.main()
open('schedule.xml', 'w').write(xml)

