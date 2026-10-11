"""Embedded data provenance: data/versions.json (written by tools/refresh_data.py) + the firmware SHA compiled
into the host library. check() compares everything against a repo checkout (when one is reachable)."""
import hashlib, json, os, subprocess
from . import host

def load():
    try:
        with open(host.data_path('versions.json')) as f: return json.load(f)
    except Exception: return {}
V = load()

def lib_fw():
    try: return host.L.sim_fw_sha().decode()
    except Exception: return '?'

def short():
    """one line for the status bar / About"""
    pcb = V.get('pcb', {}).get('board_v15', {})
    return 'FW %s (DLL %s) · HW %s · board v15 %s · panel_full %s' % (V.get('firmware_commit', '?')[:7], lib_fw()[:7], V.get('hardware_commit', '?')[:7],
                                                                    pcb.get('git', '?')[:7], V.get('pcb', {}).get('panel_full', {}).get('git', '?')[:7])

def find_repo():
    for c in (os.environ.get('LEDS_REPO'), os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..')):
        if c and os.path.isdir(os.path.join(c, '.git')) and os.path.isdir(os.path.join(c, 'firmware', 'mono_split')): return os.path.abspath(c)

def _sha(p):
    with open(p, 'rb') as f: return hashlib.sha256(f.read()).hexdigest()

def check(repo=None):
    """-> (ok_lines, bad_lines). Compares embedded hashes with the repo files and the DLL's firmware SHA."""
    ok, bad = [], []
    fw = V.get('firmware_commit', '')
    (ok if lib_fw()[:7] == fw[:7] else bad).append('host library built from firmware %s, data says %s' % (lib_fw()[:7], fw[:7]))
    repo = repo or find_repo()
    if not repo: ok.append('repo not reachable (installed exe): embedded versions only'); return ok, bad
    def git(*a): return subprocess.run(['git', '-C', repo] + list(a), capture_output=True, text=True).stdout.strip()
    for key, e in V.get('pcb', {}).items():
        p = os.path.join(repo, e['src'])
        if not os.path.exists(p): bad.append('%s: %s missing in repo' % (key, e['src'])); continue
        (ok if _sha(p) == e['src_sha256'] else bad).append('%s: %s %s' % (key, e['src'], 'matches HEAD' if _sha(p) == e['src_sha256'] else 'CHANGED since export (%s -> %s)' % (e['git'][:7], git('log', '-1', '--format=%h', '--', e['src']))))
    for key, e in V.get('sch', {}).items():
        p = os.path.join(repo, e['src'])
        (ok if os.path.exists(p) and _sha(p) == e['src_sha256'] else bad).append('schematic %s: %s' % (key, 'matches HEAD' if os.path.exists(p) and _sha(p) == e['src_sha256'] else 'CHANGED since export'))
    for rel, e in V.get('firmware', {}).items():
        p = os.path.join(repo, rel)
        (ok if os.path.exists(p) and _sha(p) == e['sha256'] else bad).append('firmware %s: %s' % (rel, 'matches HEAD' if os.path.exists(p) and _sha(p) == e['sha256'] else 'CHANGED since build'))
    return ok, bad
