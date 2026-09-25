#!/usr/bin/env python3
"""usage: tap.py SERIAL 'label regex' [timeout]  -- find a UI node by text/content-desc (case-insensitive, full match) and tap it."""
import os, re, subprocess, sys, time
adb = os.environ.get('ADB', 'adb')
serial, label = sys.argv[1], sys.argv[2]
timeout = float(sys.argv[3]) if len(sys.argv) > 3 else 60
rx = re.compile(label, re.I)
deadline = time.time() + timeout
while True:
    xml = subprocess.run([adb, '-s', serial, 'exec-out', 'uiautomator', 'dump', '/dev/tty'], capture_output=True, text=True, errors='replace').stdout
    for node in re.finditer(r'<node [^>]*>', xml):
        n = node.group(0)
        text = (re.search(r' text="([^"]*)"', n) or [None, ''])[1]
        desc = (re.search(r' content-desc="([^"]*)"', n) or [None, ''])[1]
        if rx.fullmatch(text.strip()) or rx.fullmatch(desc.strip()):
            if 'enabled="false"' in n:
                continue
            x1, y1, x2, y2 = map(int, re.search(r'bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"', n).groups())
            subprocess.run([adb, '-s', serial, 'shell', 'input', 'tap', str((x1 + x2) // 2), str((y1 + y2) // 2)], check=True)
            print(f'tapped "{text or desc}" at {(x1 + x2) // 2},{(y1 + y2) // 2}')
            sys.exit(0)
    if time.time() > deadline:
        sys.exit(f'No enabled node matching /{label}/ found.\n' + xml[-3000:])
    time.sleep(2)
