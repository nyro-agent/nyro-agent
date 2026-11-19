"""Nyro banner: gold chain coins mined out of dark ore, streaming on light trails into one big USDC coin.

    blender -b -P banner.py -- og      # 2400x1260 -> og-raw.png
    blender -b -P banner.py -- x       # 3000x1000 -> x-raw.png
    PREVIEW=1 for a quick half-size, low-sample render.
Reuses the struck-gold coin builder from superswap-section/blender/coins_ring.py (medal lettering replaced by dots).
"""
import bpy, bmesh, math, os, re, sys, random
from mathutils import Vector, Matrix

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
OUT = argv[0] if argv else "og"
BDIR = os.path.dirname(os.path.abspath(__file__))
RING_PY = os.path.expanduser("~/Documents/projek-token/superswap-section/blender/coins_ring.py")
PREVIEW = os.environ.get("PREVIEW") == "1"

# ---- coin builder (materials + detailed_coin_mesh) from coins_ring.py, without its ring scene
src = open(RING_PY).read()
src = src[:src.index('if COIN == "gold":\n    RELIEF')]
src = src.replace('"usdc": 1.0}', '"usdc": 1.0, "nyro": 1.18}')
src = re.sub(r'td\.body = "SUPERSWAP[^"]*"', lambda m_: 'td.body = "\u00b7      " * 34', src)
os.environ["COIN"] = "gold"
g = globals()
g["__file__"] = RING_PY
exec(compile(src, RING_PY, "exec"), g)
MARKS = os.path.join(BDIR, "marks")      # mono marks incl. kaspa + polygon
g["MARKS"] = MARKS

RELIEF = gold("gold_relief", 0.05, 0.14, 1.2, patina=0.2)
MARK_FACE = gold("gold_mark_face", 0.25, 0.4, 2.0, guilloche=True, patina=0.4)
CHAINS = ["btc", "kaspa", "sol", "eth", "base", "arbitrum", "matic"]
MESH = {c: detailed_coin_mesh(FACE, EDGE, RELIEF, MARK_FACE, c) for c in CHAINS + ["usdc"]}

scene = bpy.context.scene
FACE_CAM = Matrix.Rotation(math.radians(90), 4, "X")     # coin face (local +Z) -> toward the camera (-Y)

def coin(chain, loc, s, yaw, pitch, roll=0):
    ob = bpy.data.objects.new("coin_" + chain, MESH[chain])
    scene.collection.objects.link(ob)
    ob.matrix_world = (Matrix.Translation(loc) @ Matrix.Rotation(math.radians(yaw), 4, "Z")
                       @ Matrix.Rotation(math.radians(pitch), 4, "X") @ FACE_CAM
                       @ Matrix.Rotation(math.radians(roll), 4, "Z") @ Matrix.Scale(s, 4))
    return ob

HERO = Vector((2.15, 0.0, 0.3))
coin("usdc", HERO, 1.6, -16, 6, 0)

# chain coins: (chain, location, scale, yaw, pitch, roll)
FLOW = [
    ("btc",      (-2.55, -0.4,  0.95), 0.66,  44,  24,  8),
    ("eth",      (-0.55, -0.9, -0.55), 0.56, -24,  12, -6),
    ("sol",      (-1.15,  0.3,  1.75), 0.48,  36,  22,  0),
    ("kaspa",    (-3.55,  0.9, -0.85), 0.60,  -8, -26, 12),
    ("base",     ( 0.15,  1.6,  1.55), 0.44, -40,  -8,  0),
    ("arbitrum", (-2.0,   1.8, -1.85), 0.50,  48,  18, -10),
    ("matic",    (-4.45,  2.6,  0.75), 0.52, -30,  10,  6),
]
for c, loc, s, yaw, pitch, roll in FLOW:
    coin(c, Vector(loc), s, yaw, pitch, roll)

# far coins: soft out-of-focus depth
rnd = random.Random(11)
for i in range(9):
    c = CHAINS[i % len(CHAINS)]
    loc = Vector((rnd.uniform(-4.8, 1.0), rnd.uniform(5.0, 9.0), rnd.uniform(-2.2, 2.4)))
    coin(c, loc, rnd.uniform(0.4, 0.6), rnd.uniform(-70, 70), rnd.uniform(-50, 50), rnd.uniform(0, 360))

# ---- light trails from each coin into the USDC coin (end just behind it)
def emit(name, color, strength):
    m = bpy.data.materials.new(name); m.use_nodes = True
    nt = m.node_tree; nt.nodes.clear()
    e = nt.nodes.new("ShaderNodeEmission"); e.inputs["Color"].default_value = (*color, 1); e.inputs["Strength"].default_value = strength
    nt.links.new(e.outputs[0], nt.nodes.new("ShaderNodeOutputMaterial").inputs[0])
    return m

TRAIL = emit("trail", (1.0, 0.62, 0.24), 5.0)
TRAIL_SOFT = emit("trail_soft", (1.0, 0.55, 0.2), 0.9)
DUST = emit("dust", (1.0, 0.72, 0.35), 14.0)

def bezier(p0, p3, lift, name, mat, depth):
    cu = bpy.data.curves.new(name, "CURVE"); cu.dimensions = "3D"
    cu.bevel_depth = depth; cu.bevel_resolution = 2; cu.use_fill_caps = True
    sp = cu.splines.new("BEZIER"); sp.bezier_points.add(1)
    a, b = sp.bezier_points
    d = p3 - p0
    a.co = p0; a.handle_left = p0 - d * 0.2; a.handle_right = p0 + d * 0.35 + lift
    b.co = p3; b.handle_left = p3 - d * 0.4 + lift * 0.4; b.handle_right = p3 + d * 0.2
    # taper: thin at the coin, fuller near the payout
    a.radius = 0.25; b.radius = 1.0
    ob = bpy.data.objects.new(name, cu); scene.collection.objects.link(ob)
    cu.materials.append(mat)
    return ob, sp

END = HERO + Vector((-0.15, 0.55, 0))
dust_bm = bmesh.new()
for i, (c, loc, s, *_ ) in enumerate(FLOW):
    p0 = Vector(loc)
    lift = Vector((0, 0, rnd.uniform(-0.9, 0.9)))
    bezier(p0, END, lift, f"trail_{c}", TRAIL, 0.007)
    bezier(p0, END, lift, f"trail_soft_{c}", TRAIL_SOFT, 0.03)
    # dust motes along the same path (evaluate the cubic)
    q0, q1, q2, q3 = p0, p0 + (END - p0) * 0.35 + lift, END - (END - p0) * 0.4 + lift * 0.4, END
    for _ in range(26):
        t = rnd.random() ** 0.8
        p = (1 - t) ** 3 * q0 + 3 * (1 - t) ** 2 * t * q1 + 3 * (1 - t) * t ** 2 * q2 + t ** 3 * q3
        p += Vector((rnd.gauss(0, 0.06), rnd.gauss(0, 0.06), rnd.gauss(0, 0.06)))
        sph = bmesh.ops.create_icosphere(dust_bm, subdivisions=1, radius=rnd.uniform(0.006, 0.02))
        bmesh.ops.translate(dust_bm, verts=sph["verts"], vec=p)
me = bpy.data.meshes.new("dust"); dust_bm.to_mesh(me); dust_bm.free(); me.materials.append(DUST)
scene.collection.objects.link(bpy.data.objects.new("dust", me))

# ---- ore: dark faceted rock with glowing gold seams, bottom left (where the coins are mined from)
def rock_mat():
    m = bpy.data.materials.new("ore"); m.use_nodes = True
    nt = m.node_tree; N = nt.nodes; L = nt.links; b = N["Principled BSDF"]
    b.inputs["Base Color"].default_value = (0.008, 0.007, 0.007, 1)
    b.inputs["Roughness"].default_value = 0.6
    b.inputs["Metallic"].default_value = 0.0
    tc = N.new("ShaderNodeTexCoord")
    vo = N.new("ShaderNodeTexVoronoi"); vo.feature = "DISTANCE_TO_EDGE"; vo.inputs["Scale"].default_value = 2.4
    L.new(tc.outputs["Object"], vo.inputs["Vector"])
    cr = N.new("ShaderNodeMapRange"); cr.inputs["From Min"].default_value = 0.0; cr.inputs["From Max"].default_value = 0.035
    cr.inputs["To Min"].default_value = 1.0; cr.inputs["To Max"].default_value = 0.0
    L.new(vo.outputs["Distance"], cr.inputs["Value"])
    nz = N.new("ShaderNodeTexNoise"); nz.inputs["Scale"].default_value = 1.6
    L.new(tc.outputs["Object"], nz.inputs["Vector"])
    gate = N.new("ShaderNodeMapRange"); gate.inputs["From Min"].default_value = 0.5; gate.inputs["From Max"].default_value = 0.62
    L.new(nz.outputs["Fac"], gate.inputs["Value"])
    mul = N.new("ShaderNodeMath"); mul.operation = "MULTIPLY"
    L.new(cr.outputs["Result"], mul.inputs[0]); L.new(gate.outputs["Result"], mul.inputs[1])
    b.inputs["Emission Color"].default_value = (1.0, 0.55, 0.18, 1)
    st = N.new("ShaderNodeMath"); st.operation = "MULTIPLY"; st.inputs[1].default_value = 7.0
    L.new(mul.outputs[0], st.inputs[0]); L.new(st.outputs[0], b.inputs["Emission Strength"])
    return m

ORE = rock_mat()
def rock(name, loc, s, seed):
    r_ = random.Random(seed)
    bm = bmesh.new(); bmesh.ops.create_icosphere(bm, subdivisions=3, radius=1.0)
    from mathutils import noise as _nz
    off = Vector((r_.uniform(0, 50), r_.uniform(0, 50), r_.uniform(0, 50)))
    for v in bm.verts:
        v.co *= 1 + 0.32 * _nz.fractal(v.co * 1.3 + off, 0.6, 2.2, 4) + r_.uniform(-0.03, 0.03)
    bmesh.ops.scale(bm, vec=(1.25, 1.0, 0.8), verts=bm.verts)
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free(); me.materials.append(ORE)
    for p in me.polygons: p.use_smooth = False
    ob = bpy.data.objects.new(name, me); scene.collection.objects.link(ob)
    ob.location = loc; ob.scale = (s, s, s)
    ob.rotation_euler = (r_.uniform(0, 3), r_.uniform(0, 3), r_.uniform(0, 3))
    return ob

rock("ore_a", (-4.1, 1.2, -2.85), 1.35, 1)
rock("ore_b", (-2.35, 2.4, -3.15), 1.05, 2)
rock("ore_c", (-5.5, 0.4, -1.35), 0.95, 3)
rock("ore_d", (-0.9, 3.6, -3.1), 0.8, 4)
for i in range(7):                     # shards breaking off, floating up with the coins
    rock(f"shard_{i}", (rnd.uniform(-4.8, -1.4), rnd.uniform(-0.6, 1.8), rnd.uniform(-2.0, -0.6)), rnd.uniform(0.07, 0.16), 10 + i)

# ---- warm halo behind the USDC coin
halo = bpy.data.materials.new("halo"); halo.use_nodes = True
nt = halo.node_tree; nt.nodes.clear()
tc = nt.nodes.new("ShaderNodeTexCoord"); gr = nt.nodes.new("ShaderNodeTexGradient"); gr.gradient_type = "SPHERICAL"
nt.links.new(tc.outputs["Object"], gr.inputs["Vector"])
pw = nt.nodes.new("ShaderNodeMath"); pw.operation = "POWER"; pw.inputs[1].default_value = 2.4
nt.links.new(gr.outputs["Fac"], pw.inputs[0])
em = nt.nodes.new("ShaderNodeEmission"); em.inputs["Color"].default_value = (1.0, 0.5, 0.16, 1)
st = nt.nodes.new("ShaderNodeMath"); st.operation = "MULTIPLY"; st.inputs[1].default_value = 0.8
nt.links.new(pw.outputs[0], st.inputs[0]); nt.links.new(st.outputs[0], em.inputs["Strength"])
tr = nt.nodes.new("ShaderNodeBsdfTransparent"); ad = nt.nodes.new("ShaderNodeAddShader")
nt.links.new(em.outputs[0], ad.inputs[0]); nt.links.new(tr.outputs[0], ad.inputs[1])
out = nt.nodes.new("ShaderNodeOutputMaterial"); nt.links.new(ad.outputs[0], out.inputs[0])
bm = bmesh.new(); bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=1)
me = bpy.data.meshes.new("halo"); bm.to_mesh(me); bm.free(); me.materials.append(halo)
h = bpy.data.objects.new("halo", me); scene.collection.objects.link(h)
h.location = HERO + Vector((0.1, 4.0, 0)); h.rotation_euler = (math.radians(90), 0, 0); h.scale = (4.2, 4.2, 1)

# ---- camera
cam_d = bpy.data.cameras.new("cam"); cam_d.lens = float(os.environ.get("LENS", 36 if OUT == "x" else 50))
cam_d.dof.use_dof = True; cam_d.dof.focus_distance = 14.0; cam_d.dof.aperture_fstop = float(os.environ.get("FSTOP", 2.0))
cam = bpy.data.objects.new("cam", cam_d); scene.collection.objects.link(cam)
cam.location = (0, -14, 0); cam.rotation_euler = (math.radians(90), 0, 0)
scene.camera = cam

# ---- lights: softboxes seen only in reflections + a key and a violet rim
def softbox(name, loc, size, strength, rot, color=(1, 1, 1)):
    bm = bmesh.new(); bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=1)
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    ob = bpy.data.objects.new(name, me); scene.collection.objects.link(ob)
    ob.location, ob.scale, ob.rotation_euler = loc, size, rot
    me.materials.append(emit(name, color, strength)); ob.visible_camera = False
    return ob

softbox("key", (6, -10, 6), (7, 3, 1), 5.0, (math.radians(62), 0, math.radians(28)))
softbox("strip_left", (-8, -7, 1), (1.2, 8, 1), 3.0, (math.radians(90), math.radians(-50), 0))
softbox("top", (0, -3, 10), (9, 4, 1), 2.4, (0, 0, 0))
softbox("front", (1.5, -18, 1.5), (10, 6, 1), 0.35, (math.radians(90), 0, 0))
softbox("rim_violet", (7, 6, 2), (2, 7, 1), 5.0, (math.radians(90), math.radians(60), 0), (0.48, 0.44, 0.94))

def area(name, loc, energy, size, color=(1, 1, 1)):
    d = bpy.data.lights.new(name, "AREA"); d.size = size; d.energy = energy; d.color = color
    o = bpy.data.objects.new(name, d); scene.collection.objects.link(o)
    o.location = loc; o.rotation_euler = (Vector((0, 0, 0)) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
area("key_l", (7, -9, 7), 1100, 6)
area("rim_l", (6, 7, 3), 700, 4, (0.5, 0.45, 1.0))
area("ore_l", (-4, -5, -5), 160, 4, (1.0, 0.7, 0.4))

w = bpy.data.worlds.new("w"); w.use_nodes = True
w.node_tree.nodes["Background"].inputs["Color"].default_value = (0.0025, 0.0025, 0.0035, 1)
scene.world = w

# ---- MIRROR=1: mirror the whole layout left-right without mirroring any geometry (logos stay readable)
if os.environ.get("MIRROR") == "1":
    M = Matrix.Scale(-1, 4, Vector((1, 0, 0)))
    bpy.context.view_layer.update()            # matrix_world must reflect location/rotation/scale set above
    MW = {ob.name: ob.matrix_world.copy() for ob in scene.objects}
    for ob in scene.objects:
        if ob.type == "CURVE":                    # trails: points are in world space
            for sp in ob.data.splines:
                for bp in sp.bezier_points:
                    for attr in ("co", "handle_left", "handle_right"):
                        v = getattr(bp, attr); setattr(bp, attr, Vector((-v.x, v.y, v.z)))
        elif ob.name == "dust":                   # dust motes: vertices are in world space
            for v in ob.data.vertices:
                v.co.x = -v.co.x
        elif ob.name != "cam":
            ob.matrix_world = M @ MW[ob.name] @ M

# ---- render
r = scene.render
r.engine = "CYCLES"; scene.cycles.device = "GPU"
prefs = bpy.context.preferences.addons["cycles"].preferences
try:
    prefs.compute_device_type = "METAL"; prefs.get_devices()
    for dv in prefs.devices: dv.use = True
except Exception as ex:
    print("GPU setup failed:", ex); scene.cycles.device = "CPU"
scene.cycles.samples = 40 if PREVIEW else int(os.environ.get("SAMPLES", 256))
scene.cycles.use_denoising = True
r.film_transparent = False
r.resolution_x, r.resolution_y = {"og": (2400, 1260), "x": (3000, 1000)}[OUT]
r.resolution_percentage = 40 if PREVIEW else 100
r.image_settings.file_format = "PNG"; r.image_settings.color_mode = "RGB"; r.image_settings.color_depth = "16"
scene.view_settings.view_transform = "Standard"; scene.view_settings.look = "None"
r.filepath = os.path.join(BDIR, f"{OUT}{'-mirror' if os.environ.get('MIRROR') == '1' else ''}-raw{'-prev' if PREVIEW else ''}.png")
bpy.ops.render.render(write_still=True)
print("DONE", r.filepath)
