#!/usr/bin/env python3
import re
import sys

sys.path.insert(0, '.')

from dashboard.tui import TUIDashboard

# ANSI to HTML converter
ANSI_RE = re.compile(r'\x1b\[([0-9;]*)m')

def ansi_to_html(text):
    result = []
    stack = []
    
    def flush():
        pass
    
    i = 0
    while i < len(text):
        if text[i] == '\x1b' and i + 1 < len(text) and text[i+1] == '[':
            end = text.find('m', i+2)
            if end == -1:
                result.append(text[i])
                i += 1
                continue
            code = text[i+2:end]
            i = end + 1
            
            if code == '0':
                while stack:
                    result.append('</span>')
                    stack.pop()
            elif code == '1':
                result.append('<span style="font-weight:bold">')
                stack.append('bold')
            elif code == '2':
                result.append('<span style="opacity:0.6">')
                stack.append('dim')
            elif code == '7':
                result.append('<span style="background:#fafafa;color:#09090b">')
                stack.append('inverse')
            elif code.startswith('38;5;'):
                color256 = int(code.split(';')[2])
                # Approximate 256 colors
                if color256 >= 232:
                    gray = (color256 - 232) * 10 + 8
                    hexcolor = f"#{gray:02x}{gray:02x}{gray:02x}"
                elif color256 >= 16:
                    idx = color256 - 16
                    r = [0, 95, 135, 175, 215, 255][idx // 36]
                    g = [0, 95, 135, 175, 215, 255][(idx // 6) % 6]
                    b = [0, 95, 135, 175, 215, 255][idx % 6]
                    hexcolor = f"#{r:02x}{g:02x}{b:02x}"
                else:
                    hexcolor = {
                        0: '#000', 1: '#800', 2: '#080', 3: '#880',
                        4: '#008', 5: '#808', 6: '#088', 7: '#ccc',
                        8: '#888', 9: '#f00', 10: '#0f0', 11: '#ff0',
                        12: '#00f', 13: '#f0f', 14: '#0ff', 15: '#fff',
                    }.get(color256, '#ccc')
                result.append(f'<span style="color:{hexcolor}">')
                stack.append('fg')
            elif code.startswith('48;5;'):
                color256 = int(code.split(';')[2])
                if color256 >= 232:
                    gray = (color256 - 232) * 10 + 8
                    hexcolor = f"#{gray:02x}{gray:02x}{gray:02x}"
                elif color256 >= 16:
                    idx = color256 - 16
                    r = [0, 95, 135, 175, 215, 255][idx // 36]
                    g = [0, 95, 135, 175, 215, 255][(idx // 6) % 6]
                    b = [0, 95, 135, 175, 215, 255][idx % 6]
                    hexcolor = f"#{r:02x}{g:02x}{b:02x}"
                else:
                    hexcolor = {
                        0: '#000', 1: '#800', 2: '#080', 3: '#880',
                        4: '#008', 5: '#808', 6: '#088', 7: '#ccc',
                        8: '#888', 9: '#f00', 10: '#0f0', 11: '#ff0',
                        12: '#00f', 13: '#f0f', 14: '#0ff', 15: '#fff',
                    }.get(color256, '#ccc')
                result.append(f'<span style="background:{hexcolor}">')
                stack.append('bg')
            else:
                # Ignore unknown codes
                pass
        elif text[i] == '\n':
            while stack:
                result.append('</span>')
                stack.pop()
            result.append('<br>')
            i += 1
        elif text[i] == ' ':
            result.append('&nbsp;')
            i += 1
        else:
            result.append(text[i])
            i += 1
    
    while stack:
        result.append('</span>')
        stack.pop()
    
    return ''.join(result)


def main():
    tui = TUIDashboard(max_events=8)
    
    grid = []
    for y in range(10):
        row = []
        for x in range(10):
            certainty = 0.5
            if (x, y) in [(2,3), (4,5), (7,1), (5,5), (1,8)]:
                certainty = 0.92
            elif (x, y) in [(3,3), (2,4), (5,4), (6,1), (8,1)]:
                certainty = 0.75
            elif (x, y) in [(0,0), (9,0), (0,9), (9,9)]:
                certainty = 0.35
            row.append({'x': x, 'y': y, 'entropy': certainty, 'certainty': certainty})
        grid.append(row)
    
    drones = [
        {'id': 'drone_1', 'alive': True, 'reachable': True, 'position': [2, 3], 'target': [4, 5], 'status': 'searching', 'current_entropy': 0.12, 'role': 'scout', 'battery': 87.0, 'searched_cells': 12, 'subzone': 'A1'},
        {'id': 'drone_2', 'alive': True, 'reachable': True, 'position': [7, 1], 'target': [7, 2], 'status': 'transiting', 'current_entropy': 0.45, 'role': 'scout', 'battery': 62.0, 'searched_cells': 8, 'subzone': 'A2'},
        {'id': 'drone_3', 'alive': True, 'reachable': True, 'position': [1, 8], 'target': [2, 8], 'status': 'claiming', 'current_entropy': 0.38, 'role': 'scout', 'battery': 45.0, 'searched_cells': 15, 'subzone': 'B1'},
        {'id': 'drone_4', 'alive': True, 'reachable': True, 'position': [5, 5], 'target': [5, 5], 'status': 'searching', 'current_entropy': 0.15, 'role': 'scout', 'battery': 91.0, 'searched_cells': 9, 'subzone': 'B2'},
        {'id': 'drone_5', 'alive': False, 'reachable': False, 'position': [9, 9], 'target': [8, 8], 'status': 'stale', 'current_entropy': 0.0, 'role': 'scout', 'battery': 0.0, 'searched_cells': 3, 'subzone': 'C1'},
    ]
    
    events = [
        {'type': 'survivor', 'message': 'Survivor confirmed at [7,3] by drone_4', 't': 128},
        {'type': 'consensus', 'message': 'Auction at [5,5] winner: drone_4', 't': 95},
        {'type': 'failure', 'message': 'drone_5 heartbeat timeout', 't': 45},
        {'type': 'claim', 'message': 'drone_3 claimed [2,8]', 't': 38},
        {'type': 'mesh', 'message': 'Peer drone_2 joined mesh', 't': 12},
        {'type': 'info', 'message': 'Simulation started with 5 drones', 't': 0},
    ]
    
    mesh_peers = [
        {'peer_id': 'drone_1', 'stale': False, 'last_seen_ms': 120},
        {'peer_id': 'drone_2', 'stale': False, 'last_seen_ms': 340},
        {'peer_id': 'drone_3', 'stale': False, 'last_seen_ms': 180},
        {'peer_id': 'drone_4', 'stale': False, 'last_seen_ms': 90},
        {'peer_id': 'drone_5', 'stale': True, 'last_seen_ms': 45000},
    ]
    
    sim_state = {
        'grid': grid,
        'drones': drones,
        'events': events,
        'target': (7, 3),
        'flash_target': True,
        'stale_message': '',
        'paused': False,
        'frame_counter': 4,
        'elapsed': 128,
        'coverage': 42,
        'coverage_completed': 0.35,
        'coverage_visited': 0.42,
        'avg_entropy': 0.68,
        'auctions': 8,
        'dropouts': 1,
        'consensus_rounds': 12,
        'survivor_found': True,
        'survivor_receipts': 1,
        'mesh': 'local',
        'mesh_peers': mesh_peers,
        'mesh_messages': 156,
        'pending_claims': [{'zone': [2, 8], 'owner': 'drone_3'}],
        'consensus': [
            {'cell': [5, 5], 'status': 'resolved', 'vote_count': 4},
            {'cell': [3, 2], 'status': 'resolved', 'vote_count': 3},
            {'cell': [7, 1], 'status': 'resolved', 'vote_count': 4},
        ],
        'failures': [
            {'drone_id': 'drone_5', 'failure_type': 'heartbeat_timeout', 't': 45, 'recovered': False},
        ],
        'tick_delay_seconds': 0.5,
    }
    
    frame = tui.build_frame(sim_state)
    # Remove clear sequence
    frame = frame.replace('\033[H\033[J', '')
    html_body = ansi_to_html(frame)
    
    html = f'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<title>Entropy Hunt — TUI Monitor</title>
<style>
  body {{
    background: #09090b;
    color: #fafafa;
    font-family: "JetBrains Mono", ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
    font-size: 13px;
    line-height: 1.35;
    margin: 0;
    padding: 24px;
    min-height: 100vh;
    display: flex;
    align-items: flex-start;
    justify-content: center;
  }}
  .terminal {{
    background: #0f0f11;
    border: 1px solid #27272a;
    border-radius: 8px;
    padding: 16px 20px;
    box-shadow: 0 8px 32px rgba(0,0,0,0.5);
    white-space: nowrap;
  }}
</style>
</head>
<body>
<div class="terminal">
{html_body}
</div>
</body>
</html>'''
    
    with open('frontend/tui_preview.html', 'w') as f:
        f.write(html)
    print('Generated frontend/tui_preview.html')


if __name__ == '__main__':
    main()
