"""High-quality Cycles renders of the wire grid. Run:
   blender -b -P render_blender.py -- <shot> [samples]   shot = full | macro | top2x2 | tag | all
Units: 1 Blender unit = 1 mm. Row r (1..32) at y=(32-r)*P, column c at x=(c-1)*P; columns lie on the rows."""
import bpy, bmesh, math, sys, os
from mathutils import Vector, Matrix
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from params import N, PITCH as P, RAIL_GAP, FRAME_W, ROW_WIRE_D, COL_WIRE_D
argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else ['all']
SHOT = argv[0]; SPP = int(argv[1]) if len(argv) > 1 else 96
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'renders', 'hq')
RR, RC = ROW_WIRE_D / 2, COL_WIRE_D / 2
ZR = RR; ZC = 2 * RR + 0.05 + RC                 # column centre: on the row + kapton
L0, L1 = -RAIL_GAP, (N - 1) * P + RAIL_GAP

def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene; sc.unit_settings.scale_length = 0.001
    return sc

def mat(name, base, metal=0.0, rough=0.4, coat=0.0, coat_tint=(1, 1, 1, 1), trans=0.0, emit=None, estr=0.0, alpha=1.0, sss=0.0):
    m = bpy.data.materials.new(name); m.use_nodes = True; b = m.node_tree.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value = base; b.inputs['Metallic'].default_value = metal; b.inputs['Roughness'].default_value = rough
    b.inputs['Coat Weight'].default_value = coat; b.inputs['Coat Tint'].default_value = coat_tint; b.inputs['Coat Roughness'].default_value = 0.08
    b.inputs['Transmission Weight'].default_value = trans; b.inputs['Alpha'].default_value = alpha
    b.inputs['Subsurface Weight'].default_value = sss
    if emit: b.inputs['Emission Color'].default_value = emit; b.inputs['Emission Strength'].default_value = estr
    if alpha < 1: m.blend_method = 'BLEND' if hasattr(m, 'blend_method') else None
    return m

def materials():
    M = {}
    M['row'] = mat('enamel_row', (0.95, 0.45, 0.22, 1), metal=1.0, rough=0.22, coat=1.0, coat_tint=(1.0, 0.55, 0.30, 1))
    M['col'] = mat('enamel_col', (0.80, 0.32, 0.14, 1), metal=1.0, rough=0.25, coat=1.0, coat_tint=(0.75, 0.30, 0.15, 1))
    M['kapton'] = mat('kapton', (0.85, 0.38, 0.03, 1), rough=0.12, trans=0.55, alpha=0.9)
    M['body'] = mat('led_body', (0.93, 0.93, 0.90, 1), rough=0.45, sss=0.15)
    M['phos_off'] = mat('phosphor_off', (0.98, 0.88, 0.35, 1), rough=0.25, sss=0.3)
    M['phos_on'] = mat('phosphor_on', (1.0, 0.95, 0.80, 1), rough=0.3, emit=(1.0, 0.93, 0.78, 1), estr=60.0)
    M['term'] = mat('terminal', (0.85, 0.85, 0.82, 1), metal=1.0, rough=0.25)
    M['solder'] = mat('solder', (0.78, 0.79, 0.80, 1), metal=1.0, rough=0.32)
    M['wood'] = mat('frame_ply', (0.62, 0.45, 0.28, 1), rough=0.7)
    M['fr4'] = mat('fr4_green', (0.05, 0.28, 0.10, 1), rough=0.35, coat=0.6, coat_tint=(0.6, 1, 0.6, 1))
    M['black'] = mat('plastic_black', (0.02, 0.02, 0.02, 1), rough=0.35)
    M['ribbon'] = mat('ribbon_grey', (0.22, 0.23, 0.25, 1), rough=0.45)
    M['red'] = mat('ribbon_red', (0.6, 0.05, 0.04, 1), rough=0.5)
    M['gold'] = mat('pin_gold', (1.0, 0.78, 0.35, 1), metal=1.0, rough=0.2)
    M['chip'] = mat('ic', (0.04, 0.04, 0.045, 1), rough=0.5)
    M['bench'] = mat('bench', (0.06, 0.065, 0.07, 1), rough=0.6)
    return M

COLL = None
def link(ob):
    (COLL or bpy.context.scene.collection).objects.link(ob); return ob
def mesh_obj(name, bm, m):
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free(); me.materials.append(m)
    for p in me.polygons: p.use_smooth = True
    return link(bpy.data.objects.new(name, me))
def cube(name, size, loc, m, rotz=0.0, bevel=0.0):
    bm = bmesh.new(); bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=Vector(size), verts=bm.verts)
    if bevel: bmesh.ops.bevel(bm, geom=bm.edges[:] + bm.verts[:], offset=bevel, segments=2, affect='EDGES')
    bmesh.ops.rotate(bm, cent=Vector((0, 0, 0)), matrix=Matrix.Rotation(rotz, 3, 'Z'), verts=bm.verts)
    bmesh.ops.translate(bm, vec=Vector(loc), verts=bm.verts)
    o = mesh_obj(name, bm, m)
    for p in o.data.polygons: p.use_smooth = False
    return o
def cyl(name, r, p0, p1, m, seg=24):
    p0, p1 = Vector(p0), Vector(p1); d = p1 - p0
    bm = bmesh.new(); bmesh.ops.create_cone(bm, cap_ends=True, segments=seg, radius1=r, radius2=r, depth=d.length)
    rot = d.to_track_quat('Z', 'Y').to_matrix()
    bmesh.ops.rotate(bm, cent=Vector((0, 0, 0)), matrix=rot, verts=bm.verts); bmesh.ops.translate(bm, vec=(p0 + p1) / 2, verts=bm.verts)
    return mesh_obj(name, bm, m)
def blob(name, loc, sc, m):
    bm = bmesh.new(); bmesh.ops.create_uvsphere(bm, u_segments=24, v_segments=12, radius=1.0)
    bmesh.ops.scale(bm, vec=Vector(sc), verts=bm.verts); bmesh.ops.translate(bm, vec=Vector(loc), verts=bm.verts)
    return mesh_obj(name, bm, m)

def led_parts(M, lit):
    """one LED + fillets + kapton at origin = crossing; returns list of objects (to be instanced)"""
    a = -math.pi / 4; c = Vector((0.55, 0.55, 0))
    zb = ZC + RC + 0.01                                  # LED rests on the column top; the anode fillet bridges down to the row
    u = Vector((math.cos(a), math.sin(a), 0))
    obs = [cube('body', (1.1, 0.8, 0.55), (c.x, c.y, zb + 0.3), M['body'], a, 0.04),
           cube('phos', (0.9, 0.6, 0.04), (c.x, c.y, zb + 0.58), M['phos_on' if lit else 'phos_off'], a, 0.01)]
    for s in (1, -1):
        e = c + u * s * 0.68
        obs.append(cube('term', (0.26, 0.8, 0.6), (e.x, e.y, zb + 0.3), M['term'], a, 0.04))
    # fillets: anode on the row at (1.1, 0); cathode on the column at (0, 1.1)
    obs.append(blob('fil_a', (1.10, 0.0, 2 * RR + 0.08), (0.42, 0.34, 0.33), M['solder']))
    obs.append(blob('fil_k', (0.0, 1.12, ZC + 0.02), (0.32, 0.45, 0.20), M['solder']))
    obs.append(cube('kapton', (1.5, 1.5, 0.05), (0, 0, 2 * RR + 0.025), M['kapton']))
    return obs

def build(M, nodes=None, frame=True, tag=True, lit_fn=lambda r, c: False):
    """nodes: (r0, r1, c0, c1) 0-based inclusive-exclusive window, default whole grid"""
    global COLL
    r0, r1, c0, c1 = nodes or (0, N, 0, N)
    full = nodes is None
    xa, xb = (L0 - 10, L1 + 10) if full else (c0 * P - 7, (c1 - 1) * P + 7)
    ya, yb = (L0 - 10, L1 + 10) if full else ((N - r1) * P - 7, (N - 1 - r0) * P + 7)
    for r in range(r0, r1):
        y = (N - 1 - r) * P; cyl('row%d' % r, RR, (xa, y, ZR), (xb, y, ZR), M['row'], 20)
    for c in range(c0, c1):
        x = c * P; cyl('col%d' % c, RC, (x, ya, ZC), (x, yb, ZC), M['col'], 14)
    proto = {k: led_parts(M, k) for k in (False, True)}
    hidden = bpy.data.collections.new('protos')
    for k, obs in proto.items():
        for o in obs: bpy.context.scene.collection.objects.unlink(o); hidden.objects.link(o)
    for r in range(r0, r1):
        for c in range(c0, c1):
            for o in proto[bool(lit_fn(r, c))]:
                d = o.copy(); d.location = (c * P, (N - 1 - r) * P, 0); link(d)
    if full and frame:
        W0, W1 = L0 - 8 - FRAME_W, L1 + 8 + FRAME_W
        for (x, y, sx, sy) in [((W0 + W1) / 2, W0 + FRAME_W / 2, W1 - W0, FRAME_W), ((W0 + W1) / 2, W1 - FRAME_W / 2, W1 - W0, FRAME_W),
                               (W0 + FRAME_W / 2, (W0 + W1) / 2, FRAME_W, W1 - W0 - 2 * FRAME_W), (W1 - FRAME_W / 2, (W0 + W1) / 2, FRAME_W, W1 - W0 - 2 * FRAME_W)]:
            cube('frame', (sx, sy, 12), (x, y, -1.6 - 6), M['wood'], 0, 0.8)
        for (x, y, sx, sy) in [(L0 - 4, (L0 + L1) / 2, 8, L1 - L0 + 16), (L1 + 4, (L0 + L1) / 2, 8, L1 - L0 + 16),
                               ((L0 + L1) / 2, L0 - 4, L1 - L0, 8), ((L0 + L1) / 2, L1 + 4, L1 - L0, 8)]:
            cube('rail', (sx, sy, 1.6), (x, y, -0.8), M['fr4'], 0, 0.1)
        for i in range(N):                                   # rail solder joints
            y = (N - 1 - i) * P; x = i * P
            for (px, py, z) in [(L0 - 4, y, ZR), (L1 + 4, y, ZR), (x, L0 - 4, ZC), (x, L1 + 4, ZC)]:
                blob('rj', (px, py, max(z - 0.3, 0.2)), (1.1, 1.1, 0.55), M['solder'])
        cyl('bench', 1, (0, 0, 0), (0, 0, 0.1), M['bench'])
        bpy.data.objects['bench'].scale = (2000, 2000, 1); bpy.data.objects['bench'].location = (155, 155, -14)
    if full and tag: build_tag(M)

def bez(name, pts, r, m):
    cu = bpy.data.curves.new(name, 'CURVE'); cu.dimensions = '3D'; cu.bevel_depth = r; cu.bevel_resolution = 3
    sp = cu.splines.new('BEZIER'); sp.bezier_points.add(len(pts) - 1)
    for bp, p in zip(sp.bezier_points, pts): bp.co = p; bp.handle_left_type = bp.handle_right_type = 'AUTO'
    o = link(bpy.data.objects.new(name, cu)); o.data.materials.append(m); return o

def build_tag(M):
    tx, ty, tz = L0 - 8 - FRAME_W - 80, L0 - 8 - FRAME_W - 60, -13.0
    cube('tag_pcb', (60, 40, 1.6), (tx + 30, ty + 20, tz), M['fr4'], 0, 0.3)
    for k in range(2):                                         # 2x20 1.27 box headers
        cube('hdr40', (31.75, 6.0, 4.9), (tx + 20, ty + 6 + k * 10, tz + 3.25), M['black'], 0, 0.2)
    for k in range(4):                                         # 2x8 2.54 box headers (fan inputs)
        cube('hdr16', (8.8, 25.0, 9.0), (tx + 41 + (k % 2) * 10.5, ty + 20 if k < 2 else ty + 20, tz + 5.3), M['black'], 0, 0.3) if k < 2 else None
    cube('u_id', (2.9, 1.6, 1.1), (tx + 8, ty + 32, tz + 1.35), M['chip'], 0, 0.1)
    cube('c_id', (1.6, 0.8, 0.8), (tx + 13, ty + 32, tz + 1.2), M['body'], 0, 0.05)
    # outgoing 40-way ribbons (to v15)
    for k in range(2):
        y = ty + 6 + k * 10
        cube('ribbon40', (120, 25.4, 0.9), (tx - 60, y, tz + 6), M['ribbon'], 0, 0.2)
        cube('idc40', (34, 7, 6), (tx + 20, y, tz + 8.5), M['black'], 0, 0.3)
    # fan-outs: row fans (J_R1 rows 1-16, J_R2 rows 17-32) from the IDC on the tag to the left rail pads
    for f in range(2):
        hx, hy = tx + 41 + f * 10.5, ty + 32
        for j in range(16):
            r = f * 16 + j; y = (N - 1 - r) * P
            m = M['red'] if j == 0 else M['ribbon']
            bez('fanR', [(hx - 3.2 + (j // 8) * 6.4 * 0 + (j % 8) * 0.0, hy + (j % 8) * 2.54 - 9, tz + 10), (hx - 20, hy + 40 + j * 0.6, tz + 4),
                         (L0 - 25, y * 0.6 + 20, -4), (L0 - 4, y, 0.4)], 0.42, m)
    for f in range(2):
        hx, hy = tx + 52, ty + 10
        for j in range(16):
            c = f * 16 + j; x = c * P
            m = M['red'] if j == 0 else M['ribbon']
            bez('fanC', [(hx + 4, hy + j * 0.3, tz + 10), (hx + 40 + j, ty - 10 + f * 6, tz + 2),
                         (x * 0.6 + 20, L0 - 28, -4), (x, L0 - 4, 0.6)], 0.42, m)

def world(sc, strength=0.6, dark=False):
    w = bpy.data.worlds.new('W'); sc.world = w; w.use_nodes = True
    nt = w.node_tree; bg = nt.nodes['Background']
    sky = nt.nodes.new('ShaderNodeTexSky'); sky.sky_type = 'NISHITA'; sky.sun_elevation = math.radians(35); sky.sun_rotation = math.radians(-40)
    nt.links.new(sky.outputs[0], bg.inputs[0]); bg.inputs[1].default_value = 0.08 if dark else strength * 0.25

def area(name, loc, target, size, energy, color=(1, 1, 1)):
    l = bpy.data.lights.new(name, 'AREA'); l.size = size; l.energy = energy; l.color = color
    o = link(bpy.data.objects.new(name, l)); o.location = loc
    o.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler(); return o

def camera(loc, target, lens=50, ortho=None, dof=None, fstop=2.8):
    c = bpy.data.cameras.new('cam'); c.lens = lens; c.clip_start = 0.5; c.clip_end = 20000
    if ortho: c.type = 'ORTHO'; c.ortho_scale = ortho
    if dof: c.dof.use_dof = True; c.dof.focus_distance = dof; c.dof.aperture_fstop = fstop
    o = link(bpy.data.objects.new('cam', c)); o.location = loc
    o.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
    bpy.context.scene.camera = o; return o

def render(sc, fn, w=2560, h=1600, glare=True):
    sc.render.engine = 'CYCLES'; sc.cycles.device = 'CPU'; sc.cycles.samples = SPP; sc.cycles.use_denoising = True
    sc.cycles.max_bounces = 8; sc.cycles.transmission_bounces = 8
    sc.render.resolution_x, sc.render.resolution_y = w, h; sc.render.resolution_percentage = 100
    sc.render.filter_size = 1.5; sc.view_settings.view_transform = 'AgX'; sc.view_settings.look = 'AgX - Medium High Contrast'
    sc.render.image_settings.file_format = 'PNG'; sc.render.image_settings.color_depth = '8'
    if glare:
        sc.use_nodes = True; nt = sc.node_tree; rl = nt.nodes['Render Layers']; comp = nt.nodes['Composite']
        g = nt.nodes.new('CompositorNodeGlare'); g.glare_type = 'FOG_GLOW'; g.quality = 'HIGH'; g.threshold = 1.0; g.size = 9; g.mix = 0.0
        nt.links.new(rl.outputs['Image'], g.inputs['Image']); nt.links.new(g.outputs['Image'], comp.inputs['Image'])
    sc.render.filepath = os.path.join(OUT, fn); bpy.ops.render.render(write_still=True); print('WROTE', sc.render.filepath)

def lit_pattern(r, c):
    # ring + diagonal sparkle: radius 9..13 around the centre plus a "W" of the cross diagonals
    d = math.hypot(r - 15.5, c - 15.5)
    return (9.0 < d < 12.5) or (abs(r - c) <= 0 and d < 7) or (abs(r + c - 31) == 0 and d < 7) or d < 2.2

def shot_full():
    sc = reset(); M = materials()
    M['phos_on'].node_tree.nodes['Principled BSDF'].inputs['Emission Strength'].default_value = 900.0
    build(M, lit_fn=lit_pattern)
    world(sc, dark=True); sc.world.node_tree.nodes['Background'].inputs[1].default_value = 0.012
    area('key', (-250, -450, 520), (155, 155, 0), 400, 1.2e6, (1.0, 0.96, 0.9))
    area('rim', (650, 600, 250), (155, 155, 0), 300, 6e5, (0.8, 0.88, 1.0))
    camera((-230, -330, 360), (165, 150, -10), lens=40)
    render(sc, 'grid_full_34.png', 2560, 1600)

def shot_macro():
    sc = reset(); M = materials(); build(M, nodes=(15, 17, 15, 17), lit_fn=lambda r, c: r == 15 and c == 15)
    world(sc, strength=0.8)
    cube('bg', (200, 200, 1), (160, 155, -6), M['bench'])
    ox, oy = 15 * P, (N - 1 - 15) * P                         # node (r=15, c=15) crossing
    area('key', (ox - 25, oy - 30, 40), (ox, oy, 0), 30, 4000, (1, 0.97, 0.92))
    area('fill', (ox + 30, oy + 10, 25), (ox, oy, 0), 30, 1200, (0.85, 0.9, 1.0))
    t = (ox + 0.45, oy + 0.45, 0.7); cam = (ox - 8.0, oy - 10.0, 8.0)
    camera(cam, t, lens=100, dof=(Vector(cam) - Vector(t)).length, fstop=5.6)
    render(sc, 'node_macro.png', 2560, 1700)

def shot_top():
    sc = reset(); M = materials(); build(M, nodes=(14, 16, 14, 16), lit_fn=lambda r, c: (r + c) % 2 == 0)
    world(sc, strength=0.8)
    cube('bg', (200, 200, 1), (150, 165, -6), M['bench'])
    cx, cy = 14.5 * P, (N - 1 - 14.5) * P
    area('key', (cx - 30, cy - 20, 60), (cx, cy, 0), 40, 9000); area('fill', (cx + 40, cy + 30, 50), (cx, cy, 0), 40, 3000, (0.85, 0.9, 1))
    camera((cx + 0.3, cy + 0.3, 80), (cx + 0.3, cy + 0.3, 0), ortho=19.0)
    render(sc, 'nodes_2x2_top.png', 2560, 2560)

def shot_tag():
    sc = reset(); M = materials(); build(M, lit_fn=lambda r, c: c < 3 or r > 28)
    world(sc, strength=0.8)
    tx, ty = L0 - 8 - FRAME_W - 80, L0 - 8 - FRAME_W - 60
    area('key', (tx - 60, ty - 150, 260), (tx + 60, ty + 60, -10), 250, 1.2e6, (1, 0.96, 0.9))
    area('fill', (200, -50, 200), (tx + 60, ty + 60, -10), 200, 4e5, (0.85, 0.9, 1))
    camera((tx - 70, ty - 110, 150), (tx + 75, ty + 75, -8), lens=35, dof=None)
    render(sc, 'leadin_tag.png', 2560, 1600)

shots = {'full': shot_full, 'macro': shot_macro, 'top2x2': shot_top, 'tag': shot_tag}
for k in (shots if SHOT == 'all' else [SHOT]): shots[k]()
