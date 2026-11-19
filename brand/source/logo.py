"""Nyro profile logo (3D gold coin with the N mark). blender -b -P logo.py
From the banner script: gold chain coins mined out of dark ore, streaming on light trails into one big USDC coin.

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

RELIEF = gold("gold_relief", 0.1, 0.2, 1.6, patina=0.2)
FACE = gold("gold_face_matte", 0.38, 0.55, 3.0, guilloche=True, patina=0.35)
MARK_FACE = gold("gold_mark_face", 0.32, 0.48, 2.4, guilloche=True, patina=0.45)
MESH = {"nyro": detailed_coin_mesh(FACE, EDGE, RELIEF, MARK_FACE, "nyro")}


scene = bpy.context.scene
FACE_CAM = Matrix.Rotation(math.radians(90), 4, "X")
ob = bpy.data.objects.new("coin_nyro", MESH["nyro"]); scene.collection.objects.link(ob)
ob.matrix_world = Matrix.Rotation(math.radians(-20), 4, "Z") @ Matrix.Rotation(math.radians(10), 4, "X") @ FACE_CAM @ Matrix.Scale(2.0, 4)

def emit(name, color, strength):
    m = bpy.data.materials.new(name); m.use_nodes = True
    nt = m.node_tree; nt.nodes.clear()
    e = nt.nodes.new("ShaderNodeEmission"); e.inputs["Color"].default_value = (*color, 1); e.inputs["Strength"].default_value = strength
    nt.links.new(e.outputs[0], nt.nodes.new("ShaderNodeOutputMaterial").inputs[0])
    return m

# warm halo behind the coin (emission + transparent, so it never blocks)
halo = bpy.data.materials.new("halo"); halo.use_nodes = True
nt = halo.node_tree; nt.nodes.clear()
tc = nt.nodes.new("ShaderNodeTexCoord"); gr = nt.nodes.new("ShaderNodeTexGradient"); gr.gradient_type = "SPHERICAL"
nt.links.new(tc.outputs["Object"], gr.inputs["Vector"])
pw = nt.nodes.new("ShaderNodeMath"); pw.operation = "POWER"; pw.inputs[1].default_value = 2.2
nt.links.new(gr.outputs["Fac"], pw.inputs[0])
em = nt.nodes.new("ShaderNodeEmission"); em.inputs["Color"].default_value = (1.0, 0.5, 0.16, 1)
st = nt.nodes.new("ShaderNodeMath"); st.operation = "MULTIPLY"; st.inputs[1].default_value = 0.6
nt.links.new(pw.outputs[0], st.inputs[0]); nt.links.new(st.outputs[0], em.inputs["Strength"])
tr = nt.nodes.new("ShaderNodeBsdfTransparent"); ad = nt.nodes.new("ShaderNodeAddShader")
nt.links.new(em.outputs[0], ad.inputs[0]); nt.links.new(tr.outputs[0], ad.inputs[1])
out = nt.nodes.new("ShaderNodeOutputMaterial"); nt.links.new(ad.outputs[0], out.inputs[0])
bm = bmesh.new(); bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=1)
me = bpy.data.meshes.new("halo"); bm.to_mesh(me); bm.free(); me.materials.append(halo)
h = bpy.data.objects.new("halo", me); scene.collection.objects.link(h)
h.location = (0, 4.0, 0); h.rotation_euler = (math.radians(90), 0, 0); h.scale = (3.6, 3.6, 1)

cam_d = bpy.data.cameras.new("cam"); cam_d.lens = 128
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

softbox("key", (6, -10, 6), (7, 3, 1), 2.3, (math.radians(62), 0, math.radians(28)))
softbox("strip_left", (-8, -7, 1), (1.2, 8, 1), 3.0, (math.radians(90), math.radians(-50), 0))
softbox("top", (0, -3, 10), (9, 4, 1), 1.1, (0, 0, 0))
softbox("front", (1.5, -18, 1.5), (10, 6, 1), 0.35, (math.radians(90), 0, 0))
softbox("rim_violet", (7, 6, 2), (2, 7, 1), 5.0, (math.radians(90), math.radians(60), 0), (0.48, 0.44, 0.94))

def area(name, loc, energy, size, color=(1, 1, 1)):
    d = bpy.data.lights.new(name, "AREA"); d.size = size; d.energy = energy; d.color = color
    o = bpy.data.objects.new(name, d); scene.collection.objects.link(o)
    o.location = loc; o.rotation_euler = (Vector((0, 0, 0)) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
area("key_l", (7, -9, 7), 300, 6)
area("rim_l", (6, 7, 3), 700, 4, (0.5, 0.45, 1.0))
area("ore_l", (-4, -5, -5), 160, 4, (1.0, 0.7, 0.4))

w = bpy.data.worlds.new("w"); w.use_nodes = True
w.node_tree.nodes["Background"].inputs["Color"].default_value = (0.0025, 0.0025, 0.0035, 1)
scene.world = w

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
r.film_transparent = os.environ.get("CUT") == "1"
if os.environ.get("CUT") == "1":
    bpy.data.objects["halo"].hide_render = True
    cam_d.lens = 112
r.resolution_x = r.resolution_y = 2000
r.resolution_percentage = 40 if PREVIEW else 100
r.image_settings.file_format = "PNG"; r.image_settings.color_mode = "RGBA" if os.environ.get("CUT") == "1" else "RGB"; r.image_settings.color_depth = "16"
scene.view_settings.view_transform = "Standard"; scene.view_settings.look = "None"
r.filepath = os.path.join(BDIR, f"logo{'-cut' if os.environ.get('CUT') == '1' else ''}-raw{'-prev' if PREVIEW else ''}.png")
bpy.ops.render.render(write_still=True)
print("DONE", r.filepath)
