from pathlib import Path
import argparse
from collections import deque
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
CELL, GAP, MARGIN = 11, 3, 26
PITCH = CELL + GAP
WIDTH = 2*MARGIN + COLS*PITCH-GAP
HEIGHT = 2*MARGIN + ROWS*PITCH-GAP
GRID_COLOR, SNAKE_COLOR = '#39d353', '#ef4444'
EATEN_COLOR = '#ebedf0'
# Segment sizes from the head to the tail, in pixels.
SEGMENT_SIZES = (14, 11, 9, 7, 5, 3)
STEP = 0.15
HOLD = 1.5

# List calendar cells in a serpentine order.
cells = [(x,y) for x in range(COLS) for y in (range(ROWS) if x%2==0 else range(ROWS-1,-1,-1))]
# Skip padding outside the dates returned by GitHub.
cells = [(x,y) for x,y in cells if start_day+timedelta(days=x*7+y) in calendar.days]
targets = {cell for cell in cells if calendar.days[start_day+timedelta(days=cell[0]*7+cell[1])] == 0}
blocked = set(cells)-targets


def route_to_food(position, food):
    """Find the nearest food via adjacent cells, allowing an outside border."""
    queue = deque([position])
    parents = {position: None}
    while queue:
        current = queue.popleft()
        if current in food:
            route = []
            while current != position:
                route.append(current)
                current = parents[current]
            return route[::-1]
        x, y = current
        for neighbor in ((x+1,y), (x,y+1), (x,y-1), (x-1,y)):
            nx, ny = neighbor
            if (-1 <= nx <= COLS and -1 <= ny <= ROWS
                    and neighbor not in blocked and neighbor not in parents):
                parents[neighbor] = current
                queue.append(neighbor)
    return None


# Start outside the grid and choose food by distance rather than date order.
path = [(-1,0)] if targets else []
remaining = set(targets)
while remaining:
    route = route_to_food(path[-1], remaining)
    if route is None:
        break  # Fully enclosed cells cannot be reached without crossing activity.
    path.extend(route)
    remaining.difference_update(route)
arrival_indices = {}
for index, cell in enumerate(path):
    if cell in targets:
        arrival_indices.setdefault(cell, index)
N=len(path)
DURATION=N*STEP+HOLD

def times_and_values(index):
    # Empty days turn gray on the first visit and stay gray on revisits.
    t=index*STEP/DURATION
    return f'0;{t:.6f};1', f'{GRID_COLOR};{EATEN_COLOR};{EATEN_COLOR}'

parts=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}" role="img" aria-label="Red snake eats only days with zero GitHub contributions">',
       '<title>iamhieu213 contribution snake</title>',
       f'<rect width="{WIDTH}" height="{HEIGHT}" fill="white"/>']
for x,y in cells:
    px=MARGIN+x*PITCH; py=MARGIN+y*PITCH
    day = start_day+timedelta(days=x*7+y)
    level = calendar.days[day]
    animation = ''
    if (x,y) in arrival_indices:
        kt,vs=times_and_values(arrival_indices[(x,y)])
        animation = f'<animate attributeName="fill" values="{vs}" keyTimes="{kt}" dur="{DURATION:.3f}s" repeatCount="indefinite" calcMode="discrete"/>'
    parts.append(f'<rect x="{px}" y="{py}" width="{CELL}" height="{CELL}" rx="2" fill="{GRID_COLOR}" data-date="{day}" data-level="{level}"><title>{day}: {"0 contributions" if level == 0 else "contribution level " + str(level)}</title>{animation}</rect>')
# Draw the tail first so the larger head appears on top.
# Each segment tracks prior head position; hides when beyond the grid.
for segment in (range(len(SEGMENT_SIZES)-1,-1,-1) if path else ()):
    size = SEGMENT_SIZES[segment]
    offset = (CELL-size)/2
    coords=[path[max(0,i-segment)] for i in range(N)]
    xs=';'.join(str(MARGIN+x*PITCH+offset) for x,y in coords+[coords[-1]])
    ys=';'.join(str(MARGIN+y*PITCH+offset) for x,y in coords+[coords[-1]])
    keys=';'.join(f'{(i*STEP)/DURATION:.6f}' for i in range(N))+ ';1'
    opacity='1' if segment==0 else '0.92'
    parts.append(f'<rect x="{MARGIN+coords[0][0]*PITCH+offset}" y="{MARGIN+coords[0][1]*PITCH+offset}" width="{size}" height="{size}" rx="{min(3, size/2)}" fill="{SNAKE_COLOR}" opacity="{opacity}"><animate attributeName="x" values="{xs}" keyTimes="{keys}" dur="{DURATION:.3f}s" repeatCount="indefinite" calcMode="discrete"/><animate attributeName="y" values="{ys}" keyTimes="{keys}" dur="{DURATION:.3f}s" repeatCount="indefinite" calcMode="discrete"/><animate attributeName="opacity" values="1;1;0" keyTimes="0;{N*STEP/DURATION:.6f};1" dur="{DURATION:.3f}s" repeatCount="indefinite" calcMode="discrete"/></rect>')
parts.append('</svg>')
Path('snake.svg').write_text('\n'.join(parts),encoding='utf-8')
print(f'Generated snake.svg ({len(cells)} days, {len(arrival_indices)} empty days eaten, {N} steps, {DURATION:.1f}s loop)')
if remaining:
    print(f'{len(remaining)} empty days are enclosed by active cells and stay green.')
