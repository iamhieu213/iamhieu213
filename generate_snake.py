from pathlib import Path
import argparse
from datetime import date, timedelta
from html.parser import HTMLParser
from urllib.request import Request, urlopen


class ContributionParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.days = {}

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'td' and 'data-date' in attrs and 'data-level' in attrs:
            day = date.fromisoformat(attrs['data-date'])
            level = int(attrs['data-level'])
            if level not in range(5):
                raise ValueError('Unexpected contribution level')
            self.days[day] = level


args_parser = argparse.ArgumentParser()
args_parser.add_argument('--username', default='iamhieu213')
args_parser.add_argument('--calendar-html', type=Path,
                         help='Use a downloaded GitHub contribution calendar')
args = args_parser.parse_args()
if args.calendar_html:
    calendar_html = args.calendar_html.read_text(encoding='utf-8')
else:
    request = Request(f'https://github.com/users/{args.username}/contributions',
                      headers={'User-Agent': 'contribution-snake'})
    with urlopen(request, timeout=30) as response:
        calendar_html = response.read().decode('utf-8')
calendar = ContributionParser()
calendar.feed(calendar_html)
if not calendar.days:
    raise ValueError('GitHub returned no contribution cells; refusing to generate a fake grid')
first_day = min(calendar.days)
last_day = max(calendar.days)
# GitHub contribution weeks start on Sunday.
start_day = first_day - timedelta(days=(first_day.weekday()+1) % 7)

COLS, ROWS = (last_day-start_day).days//7+1, 7
CELL, GAP, MARGIN = 11, 3, 10
PITCH = CELL + GAP
WIDTH = 2*MARGIN + COLS*PITCH-GAP
HEIGHT = 2*MARGIN + ROWS*PITCH-GAP
GRAY, SNAKE_COLOR = '#ebedf0', '#ef4444'
LEVEL_COLORS = (GRAY, '#9be9a8', '#40c463', '#30a14e', '#216e39')
# Segment sizes from the head to the tail, in pixels.
SEGMENT_SIZES = (14, 11, 9, 7, 5, 3)
STEP = 0.15
HOLD = 1.5

# Serpentine Hamiltonian path visits each cell exactly once.
path = [(x,y) for x in range(COLS) for y in (range(ROWS) if x%2==0 else range(ROWS-1,-1,-1))]
# Skip padding outside the dates returned by GitHub.
path = [(x,y) for x,y in path if start_day+timedelta(days=x*7+y) in calendar.days]
N=len(path)
DURATION=N*STEP+HOLD

def times_and_values(index):
    # Only empty days disappear when the snake head arrives.
    t=(index+1)*STEP/DURATION
    return f'0;{t:.6f};1', '1;0;0'

parts=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}" role="img" aria-label="Red snake eats only days with zero GitHub contributions">',
       '<title>iamhieu213 contribution snake</title>',
       f'<rect width="{WIDTH}" height="{HEIGHT}" fill="white"/>']
for i,(x,y) in enumerate(path):
    px=MARGIN+x*PITCH; py=MARGIN+y*PITCH
    day = start_day+timedelta(days=x*7+y)
    level = calendar.days[day]
    animation = ''
    if level == 0:
        kt,vs=times_and_values(i)
        animation = f'<animate attributeName="opacity" values="{vs}" keyTimes="{kt}" dur="{DURATION:.3f}s" repeatCount="indefinite" calcMode="discrete"/>'
    parts.append(f'<rect x="{px}" y="{py}" width="{CELL}" height="{CELL}" rx="2" fill="{LEVEL_COLORS[level]}" data-date="{day}" data-level="{level}"><title>{day}: {"0 contributions" if level == 0 else "contribution level " + str(level)}</title>{animation}</rect>')
# Draw the tail first so the larger head appears on top.
# Each segment tracks prior head position; hides when beyond the grid.
for segment in range(len(SEGMENT_SIZES)-1,-1,-1):
    size = SEGMENT_SIZES[segment]
    offset = (CELL-size)/2
    coords=[path[max(0,i-segment)] for i in range(N)]
    xs=';'.join(str(MARGIN+x*PITCH+offset) for x,y in coords+[coords[-1]])
    ys=';'.join(str(MARGIN+y*PITCH+offset) for x,y in coords+[coords[-1]])
    keys=';'.join(f'{(i*STEP)/DURATION:.6f}' for i in range(N))+ ';1'
    opacity='1' if segment==0 else '0.92'
    parts.append(f'<rect x="{MARGIN+offset}" y="{MARGIN+offset}" width="{size}" height="{size}" rx="{min(3, size/2)}" fill="{SNAKE_COLOR}" opacity="{opacity}"><animate attributeName="x" values="{xs}" keyTimes="{keys}" dur="{DURATION:.3f}s" repeatCount="indefinite" calcMode="discrete"/><animate attributeName="y" values="{ys}" keyTimes="{keys}" dur="{DURATION:.3f}s" repeatCount="indefinite" calcMode="discrete"/><animate attributeName="opacity" values="1;1;0" keyTimes="0;{N*STEP/DURATION:.6f};1" dur="{DURATION:.3f}s" repeatCount="indefinite" calcMode="discrete"/></rect>')
parts.append('</svg>')
Path('snake.svg').write_text('\n'.join(parts),encoding='utf-8')
print(f'Generated snake.svg ({N} cells, {DURATION:.1f}s loop)')
