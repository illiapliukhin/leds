"""BOM values of the current electronics board, read from data/bom_v15.json (exported by tools/refresh_data.py
from the .kicad_pcb footprint values), so the Lab model uses exactly what is placed on the board."""
import json, re
from . import host

def _load():
    try:
        with open(host.data_path('bom_v15.json'), encoding='utf-8') as f: return json.load(f)
    except Exception: return {}
BOM = _load()

def ohms(ref, default):
    v = BOM.get(ref)
    m = re.match(r'\s*([0-9.]+)\s*([kKmMR]?)([0-9]*)', v or '')
    if not m: return default
    x = float(m.group(1)); u = m.group(2)
    if m.group(3): x = float('%s.%s' % (m.group(1), m.group(3)))         # 2k7 / 4R7 style
    return x * {'k': 1e3, 'K': 1e3, 'M': 1e6, 'm': 1e-3}.get(u, 1.0)

def amps(ref, default):
    m = re.search(r'([0-9.]+)\s*A\b', BOM.get(ref) or '')
    return float(m.group(1)) if m else default

R_ILIM1 = ohms('R_ILIM1', 18e3)      # BQ25185 ILIM/VSET -> table 6-1
R_ILM1 = ohms('R_ILM1', 2.7e3)       # TPS259531 current limit = 2156 / R
R_ISET1 = ohms('R_ISET1', 600.0)     # BQ25185 ICHG = 300 AΩ / R
F_BAT1_A = amps('F_BAT1', 2.0)
J_BAT1 = BOM.get('J_BAT1', 'S3B-PH-SM4-TB')
