#!/usr/bin/env python3
"""Frame-exact offline video of a stack run, rendered from the simulator's JSONL log (no screen capture).
   render_video.py LOG OUT.mp4 [--t0 S] [--t1 S] [--size 1920x1080] [--fps 60] [--crf 18]"""
import argparse, json, os, subprocess, sys
os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
import pygame
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from logstate import LogState
from stack_view import Renderer

ap = argparse.ArgumentParser()
ap.add_argument('log'); ap.add_argument('out')
ap.add_argument('--t0', type=float, default=0); ap.add_argument('--t1', type=float, default=1e9)
ap.add_argument('--size', default='1920x1080'); ap.add_argument('--fps', type=int, default=60)
ap.add_argument('--crf', type=int, default=18); ap.add_argument('--png', nargs='*', type=float, default=[])
ap.add_argument('--pngdir', default='.')
a = ap.parse_args()
W, H = map(int, a.size.split('x'))
pygame.init()
recs = [json.loads(l) for l in open(a.log) if l.strip().startswith('{')]
recs = [r for r in recs if 't' in r]
t_end = min(a.t1, recs[-1]['t'])
st = LogState(); R = None; k = 0
ff = subprocess.Popen(['ffmpeg', '-loglevel', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', '%dx%d' % (W, H),
                       '-r', str(a.fps), '-i', '-', '-c:v', 'libx264', '-preset', 'slow', '-crf', str(a.crf),
                       '-pix_fmt', 'yuv420p', '-movflags', '+faststart', a.out], stdin=subprocess.PIPE)
n = int((t_end - a.t0) * a.fps)
pngs = sorted(a.png)
for i in range(n):
    t = a.t0 + i / a.fps
    while k < len(recs) and recs[k]['t'] <= t:
        st.feed(recs[k]); k += 1
    st.t = t
    if R is None and st.boards:
        R = Renderer(W, H, st.layout, st.boards)
    if R is None:
        continue
    S = R.draw(st.view())
    ff.stdin.write(pygame.image.tostring(S, 'RGB'))
    while pngs and t >= pngs[0]:
        pygame.image.save(S, os.path.join(a.pngdir, '%s_t%05.1f.png' % (os.path.splitext(os.path.basename(a.out))[0], pngs[0])))
        pngs.pop(0)
    if i % 300 == 0: print('frame %d/%d' % (i, n), flush=True)
ff.stdin.close(); ff.wait()
print('done', a.out, os.path.getsize(a.out))
