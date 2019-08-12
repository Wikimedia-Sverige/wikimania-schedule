#!/usr/bin/python3

import subprocess
import os

for d in 'pages', 'extracts':
    if not os.path.exists(d):
        os.mkdir(d)

subprocess.run(['python3', 'get_schedule.py'], check=True)
subprocess.run(['python3', 'get_titles.py'], check=True)
p = subprocess.run(['python3', 'parse_schedule.py'], check=True, capture_output=True)

open('schedule.xml', 'wb').write(p.stdout)
