#!/bin/bash
# Unplug/replug regression: every board position, 3x2 and 6x1, headless (own ports, the live sim on :4 is untouched).
# usage: regress_stack.sh [rounds]   -> results in regress/<layout>_<round>.json, summary on stdout
cd "$(dirname "$0")"; mkdir -p regress
R=${1:-1}; fail=0
for r in $(seq 1 $R); do for L in 3x2 6x1; do
  timeout 900 /workspace/sim/venv/bin/python stack_sim.py --layout $L --headless --regress --base 6800 \
     --log regress/${L}_$r.jsonl --result regress/${L}_$r.json > regress/${L}_$r.log 2>&1
  python3 -c "
import json,sys; r=json.load(open('regress/${L}_$r.json'))
print('$L round $r:', 'PASS' if r['pass'] else 'FAIL', 'form %.1fs'%(r['form'] or -1), ' '.join('b%d:%s(%s/%s)'%(s['victim'],'ok' if s['ok'] else 'FAIL', '%.1f'%s['unplug_s'] if s['unplug_s'] else s['unplug_why'], '%.1f'%s['replug_s'] if s['replug_s'] else s['replug_why']) for s in r['steps']))
sys.exit(0 if r['pass'] else 1)" || fail=1
done; done
exit $fail
