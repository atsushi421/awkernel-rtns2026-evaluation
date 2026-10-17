#!/usr/bin/env python3
"""Receives the UDP report of a measurement image and appends it to a log file.

Usage: udp_receive.py <tu10.log> [--port 26099] [--timeout 600]

It prints the #HELLO, #DAGS, #BEGIN, and #END lines as they arrive, and it
stops after the last round or at the timeout. aw_log_to_csv.py converts the
log file into the CSV that plot_comparison.py reads.
"""
import argparse
import re
import socket
import time

ap = argparse.ArgumentParser()
ap.add_argument("out")
ap.add_argument("--port", type=int, default=26099)
ap.add_argument("--timeout", type=int, default=600)
ap.add_argument("--rounds", type=int, default=3)
a = ap.parse_args()

s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
s.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 4 << 20)
s.bind(("", a.port))
s.settimeout(1.0)
print(f"listening on UDP {a.port}, writing {a.out}", flush=True)

SEQ = re.compile(r"#SEQ (\d+)/(\d+)")
END = re.compile(r"#END .*round=(\d+)")
seen = {}
total = 0
end = time.time() + a.timeout
with open(a.out, "a") as f:
    while time.time() < end:
        try:
            data, addr = s.recvfrom(65535)
        except socket.timeout:
            continue
        text = data.decode(errors="replace")
        f.write(text if text.endswith("\n") else text + "\n")
        f.flush()
        first = text.split("\n", 1)[0]
        m = SEQ.match(first)
        if m:
            seen.setdefault(int(m.group(1)), 0)
            seen[int(m.group(1))] += 1
            total = int(m.group(2))
            continue
        print(f"{time.strftime('%H:%M:%S')} {addr[0]} {first}", flush=True)
        m = END.match(first)
        if m:
            print(f"  datagrams received so far: {len(seen)}/{total}", flush=True)
            if int(m.group(1)) == a.rounds - 1:
                break
missing = [i for i in range(total) if i not in seen]
print(f"done: {len(seen)}/{total} datagrams, missing {missing[:20]}", flush=True)
