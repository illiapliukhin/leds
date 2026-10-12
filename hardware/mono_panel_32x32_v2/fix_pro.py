#!/usr/bin/env python3
"""Re-apply the project design rules after pcbnew SaveBoard (which rewrites .kicad_pro with its defaults)."""
import json, os
H = os.path.dirname(os.path.abspath(__file__)); F = os.path.join(H, 'mono_panel_32x32_v2.kicad_pro')
d = json.load(open(F)); ds = d['board']['design_settings']
ds['rules'].update({'min_clearance': 0.127, 'min_track_width': 0.15, 'min_via_diameter': 0.5, 'min_via_annular_width': 0.1,
                    'min_through_hole_diameter': 0.25, 'min_copper_edge_clearance': 0.3, 'min_hole_clearance': 0.25,
                    'min_hole_to_hole': 0.25, 'min_silk_clearance': 0.15, 'min_text_height': 0.8, 'min_text_thickness': 0.15})
ds['track_widths'] = [0.0, 0.2, 0.25, 0.3, 0.6, 1.0]
ds['via_dimensions'] = [{'diameter': 0.0, 'drill': 0.0}, {'diameter': 0.6, 'drill': 0.3}]
for c in d['net_settings']['classes']:
    if c['name'] == 'Default': c.update({'clearance': 0.127, 'track_width': 0.2, 'via_diameter': 0.6, 'via_drill': 0.3})
json.dump(d, open(F, 'w'), indent=2)
print('pro rules: min_clearance 0.127, Default class 0.127 / 0.2 / via 0.6/0.3')
