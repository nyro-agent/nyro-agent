"""Animated ring of 10 BTC coins (gold like the thrive coins by default; COIN=silver for chrome) (from the 720w reference video), rendered as a seamless loop.

    python3 -I blender/icons.py                               # needs assets/tex/btc-outline.png
    blender -b -P blender/coins_ring.py -- still              # one 640px test frame -> assets/ring-still.png
    blender -b -P blender/coins_ring.py -- anim               # 1080px RGBA PNG frames -> assets/ring/####.png

Motion: the coins orbit the ring, and each coin's spin around its own radial axis is tied to where it is on the
ring (spin = ring angle + offset). So the "face-on" spots stay put on screen (upper right / lower left, like the
video) and the coins roll through them. All coins are identical, so one slot step (36 degrees) loops seamlessly.
"""
import bpy, bmesh, math, os, sys
from mathutils import Vector, Matrix

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
MODE = argv[0] if argv else "still"
HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.expanduser("~/Documents/projek-token/superswap-section/assets")   # marks + textures
OUTDIR = os.environ.get("OUTDIR", HERE)
env = lambda k, d: float(os.environ.get(k, d))

N = 10
RING = env("RING", 1.6)          # ring radius
R = env("COIN_R", 0.74)            # coin radius
THICK = 0.16 * R
SLOT_SECONDS = env("SLOT_S", 1.0) # time for the ring to advance one coin slot (= loop length)
FPS = int(env("FPS", 60))
# gold coins carry one chain mark each, repeating every len(CHAINS) slots, so the loop has to cover that many slots
CHAINS = os.environ.get("CHAINS", "eth,sol,base,arbitrum,usdc").split(",") if os.environ.get("COIN", "gold") == "gold" else ["btc"]
PERIOD = len(CHAINS)
FRAMES = round(SLOT_SECONDS * FPS * PERIOD)
SPIN_OFFSET = math.radians(env("SPIN_OFFSET", -40))   # where the coins face the camera (ring angle + offset = 0)
TILT = math.radians(env("TILT", -16))                  # ring plane tilted back a little

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene

# ---------- materials
def chrome_face():
    m = bpy.data.materials.new("chrome_face")
    m.use_nodes = True
    nt = m.node_tree
    p = nt.nodes["Principled BSDF"]
    p.inputs["Base Color"].default_value = (0.92, 0.92, 0.93, 1)
    p.inputs["Metallic"].default_value = 1.0
    img = nt.nodes.new("ShaderNodeTexImage")
    img.image = bpy.data.images.load(os.path.join(ASSETS, "tex", "btc-outline.png"))
    img.image.colorspace_settings.name = "Non-Color"
    img.interpolation = "Cubic"
    rough = nt.nodes.new("ShaderNodeMapRange")        # polished face, slightly satin inside the outline
    rough.inputs["To Min"].default_value = env("ROUGH", 0.17)
    rough.inputs["To Max"].default_value = 0.3
    nt.links.new(img.outputs["Color"], rough.inputs["Value"])
    nt.links.new(rough.outputs["Result"], p.inputs["Roughness"])
    bump = nt.nodes.new("ShaderNodeBump")             # outline embossed (raised)
    bump.inputs["Strength"].default_value = 1.0
    bump.inputs["Distance"].default_value = 0.03
    nt.links.new(img.outputs["Color"], bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], p.inputs["Normal"])
    return m

def chrome(name, rough):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    p = m.node_tree.nodes["Principled BSDF"]
    p.inputs["Base Color"].default_value = (0.92, 0.92, 0.93, 1)
    p.inputs["Metallic"].default_value = 1.0
    p.inputs["Roughness"].default_value = rough
    return m


# ---------- gold (COIN=gold, the default): the struck-gold material from projek-token/thrive/blender/scene.py
# (noisy roughness, dark bronze in the recesses, patina, brushed grain, guilloche rings on the face, reeded side wall)
COIN = os.environ.get("COIN", "gold")

def gold(name, rough_lo, rough_hi, dirt, guilloche=False, patina=0.0, reed=None, icon=None):
    m = bpy.data.materials.new(name); m.use_nodes = True
    nt = m.node_tree; N = nt.nodes; L = nt.links; b = N["Principled BSDF"]
    b.inputs["Metallic"].default_value = 1.0
    tc = N.new("ShaderNodeTexCoord")
    nz = N.new("ShaderNodeTexNoise"); nz.inputs["Scale"].default_value = 9; nz.inputs["Detail"].default_value = 8
    L.new(tc.outputs["Object"], nz.inputs["Vector"])
    rr = N.new("ShaderNodeMapRange"); rr.inputs["To Min"].default_value = rough_lo; rr.inputs["To Max"].default_value = rough_hi
    L.new(nz.outputs["Fac"], rr.inputs["Value"]); rough_out = rr.outputs["Result"]
    ao = N.new("ShaderNodeAmbientOcclusion"); ao.inputs["Distance"].default_value = 0.02
    mix = N.new("ShaderNodeMix"); mix.data_type = "RGBA"
    mix.inputs["A"].default_value = (0.16, 0.08, 0.025, 1); mix.inputs["B"].default_value = (1.0, 0.7, 0.3, 1)
    pw = N.new("ShaderNodeMath"); pw.operation = "POWER"; pw.inputs[1].default_value = dirt
    L.new(ao.outputs["AO"], pw.inputs[0]); L.new(pw.outputs[0], mix.inputs["Factor"])
    pn = N.new("ShaderNodeTexNoise"); pn.inputs["Scale"].default_value = 3.5; pn.inputs["Detail"].default_value = 10; pn.inputs["Roughness"].default_value = 0.65
    L.new(tc.outputs["Object"], pn.inputs["Vector"])
    pr = N.new("ShaderNodeMapRange"); pr.inputs["From Min"].default_value = 0.45; pr.inputs["From Max"].default_value = 0.62
    pr.inputs["To Min"].default_value = 0; pr.inputs["To Max"].default_value = patina
    L.new(pn.outputs["Fac"], pr.inputs["Value"])
    pm = N.new("ShaderNodeMix"); pm.data_type = "RGBA"; pm.inputs["B"].default_value = (0.09, 0.05, 0.02, 1)
    L.new(mix.outputs["Result"], pm.inputs["A"]); L.new(pr.outputs["Result"], pm.inputs["Factor"])
    L.new(pm.outputs["Result"], b.inputs["Base Color"])
    gr = N.new("ShaderNodeTexNoise"); gr.inputs["Scale"].default_value = 900; gr.inputs["Detail"].default_value = 2
    L.new(tc.outputs["Object"], gr.inputs["Vector"])
    bump = N.new("ShaderNodeBump"); bump.inputs["Strength"].default_value = 0.06; bump.inputs["Distance"].default_value = 0.0005
    L.new(gr.outputs["Fac"], bump.inputs["Height"]); last = bump
    if guilloche:
        wv = N.new("ShaderNodeTexWave"); wv.wave_type = "RINGS"; wv.rings_direction = "Z"; wv.inputs["Scale"].default_value = 60
        wv.inputs["Distortion"].default_value = 3; wv.inputs["Detail"].default_value = 2
        L.new(tc.outputs["Object"], wv.inputs["Vector"])
        b2 = N.new("ShaderNodeBump"); b2.inputs["Strength"].default_value = env("GUIL", 0.35); b2.inputs["Distance"].default_value = 0.0008
        L.new(wv.outputs["Fac"], b2.inputs["Height"]); L.new(last.outputs["Normal"], b2.inputs["Normal"]); last = b2
    if reed:
        n, r = reed
        sx = N.new("ShaderNodeSeparateXYZ"); L.new(tc.outputs["Object"], sx.inputs[0])
        at = N.new("ShaderNodeMath"); at.operation = "ARCTAN2"; L.new(sx.outputs["Y"], at.inputs[0]); L.new(sx.outputs["X"], at.inputs[1])
        ml = N.new("ShaderNodeMath"); ml.operation = "MULTIPLY"; ml.inputs[1].default_value = n / 2; L.new(at.outputs[0], ml.inputs[0])
        sn = N.new("ShaderNodeMath"); sn.operation = "SINE"; L.new(ml.outputs[0], sn.inputs[0])
        cx = N.new("ShaderNodeCombineXYZ"); L.new(sx.outputs["X"], cx.inputs[0]); L.new(sx.outputs["Y"], cx.inputs[1])
        ln = N.new("ShaderNodeVectorMath"); ln.operation = "LENGTH"; L.new(cx.outputs[0], ln.inputs[0])
        gt = N.new("ShaderNodeMath"); gt.operation = "GREATER_THAN"; gt.inputs[1].default_value = r * 0.985; L.new(ln.outputs["Value"], gt.inputs[0])
        mk = N.new("ShaderNodeMath"); mk.operation = "MULTIPLY"; L.new(sn.outputs[0], mk.inputs[0]); L.new(gt.outputs[0], mk.inputs[1])
        b3 = N.new("ShaderNodeBump"); b3.inputs["Strength"].default_value = 1.0; b3.inputs["Distance"].default_value = 0.004
        L.new(mk.outputs[0], b3.inputs["Height"]); L.new(last.outputs["Normal"], b3.inputs["Normal"]); last = b3
    if icon:
        # the raised BTC outline: polished (low roughness) and embossed on top of the grain
        img = N.new("ShaderNodeTexImage"); img.image = bpy.data.images.load(icon)
        img.image.colorspace_settings.name = "Non-Color"; img.interpolation = "Cubic"
        rm = N.new("ShaderNodeMix"); rm.data_type = "FLOAT"; rm.inputs["B"].default_value = 0.06
        L.new(img.outputs["Color"], rm.inputs["Factor"]); L.new(rough_out, rm.inputs["A"]); rough_out = rm.outputs["Result"]
        b4 = N.new("ShaderNodeBump"); b4.inputs["Strength"].default_value = 1.0; b4.inputs["Distance"].default_value = 0.05
        L.new(img.outputs["Color"], b4.inputs["Height"]); L.new(last.outputs["Normal"], b4.inputs["Normal"]); last = b4
    L.new(rough_out, b.inputs["Roughness"])
    L.new(last.outputs["Normal"], b.inputs["Normal"])
    return m

if COIN == "gold":
    # softer highlights than the first render: the face-on coin no longer blows out to white
    FACE = gold("gold_face", env("FACE_LO", 0.3), env("FACE_HI", 0.46), 2.6, guilloche=True, patina=0.4)
    EDGE = gold("gold_edge", 0.2, 0.36, 2.6, patina=0.45, reed=(320, R))
else:
    FACE, EDGE = chrome_face(), chrome("edge", 0.08)

# ---------- one coin mesh (shared by all 10): smooth edge, thick raised rim, outline icon on both faces
def coin_mesh():
    bm = bmesh.new()
    uv = bm.loops.layers.uv.new("UVMap")
    S = 128
    top = [bm.verts.new((R * math.cos(2 * math.pi * i / S), R * math.sin(2 * math.pi * i / S), THICK / 2)) for i in range(S)]
    bot = [bm.verts.new((v.co.x, v.co.y, -THICK / 2)) for v in top]
    for i in range(S):
        j = (i + 1) % S
        bm.faces.new((bot[i], bot[j], top[j], top[i])).material_index = 1
    front = bm.faces.new(top)
    back = bm.faces.new(list(reversed(bot)))
    for f in (front, back):
        rim = bmesh.ops.inset_region(bm, faces=[f], thickness=0.1 * R, depth=0)["faces"]
        for rf in rim:
            rf.material_index = 1
        rim2 = bmesh.ops.inset_region(bm, faces=[f], thickness=0.03 * R, depth=-0.035 * R)["faces"]
        for rf in rim2:
            rf.material_index = 1
    bmesh.ops.poke(bm, faces=[front, back])          # fan from the center: no long thin triangles across the face
    for f in bm.faces:
        for loop in f.loops:
            x, y, _ = loop.vert.co
            u, v = (x / R + 1) / 2, (y / R + 1) / 2
            if f.normal.z < -0.5:
                u = 1 - u                       # back face reads the right way round from behind
            loop[uv].uv = (u, v)
    me = bpy.data.meshes.new("coin")
    bm.to_mesh(me)
    bm.free()
    me.materials.append(FACE)
    me.materials.append(EDGE)
    for p in me.polygons:
        p.use_smooth = True
    return me


# ---------- detailed gold coin (thrive's coin + medal face, with a raised BTC mark), both faces, joined into one mesh
def _link(o):
    scene.collection.objects.link(o); return o

def _mesh_obj(name, bm, mat, smooth=False):
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    me.materials.append(mat)
    for f in me.polygons: f.use_smooth = smooth
    return _link(bpy.data.objects.new(name, me))

def _to_mesh(o):
    bpy.ops.object.select_all(action="DESELECT"); o.select_set(True); bpy.context.view_layer.objects.active = o
    bpy.ops.object.convert(target="MESH")
    return bpy.context.view_layer.objects.active

import addon_utils
addon_utils.enable("io_curve_svg")
MARKS = os.path.join(ASSETS, "tex", "marks")

def svg_mark(name, path, size, h, mat, z0):
    """import a flat logo SVG, normalise it to `size` (largest side), extrude it h*THICK and bevel the top edges"""
    before = set(bpy.data.objects)
    bpy.ops.import_curve.svg(filepath=path)
    new = [o for o in bpy.data.objects if o not in before]
    bpy.ops.object.select_all(action="DESELECT")
    for o in new:
        o.select_set(True)
    bpy.context.view_layer.objects.active = new[0]
    bpy.ops.object.convert(target="MESH")
    if len(new) > 1:
        bpy.ops.object.join()
    o = bpy.context.view_layer.objects.active
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    o.name = name
    bm = bmesh.new(); bm.from_mesh(o.data)
    bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=1e-6)
    xs = [v.co.x for v in bm.verts]; ys = [v.co.y for v in bm.verts]
    cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
    sc_ = size / max(max(xs) - min(xs), max(ys) - min(ys))
    for v in bm.verts:
        v.co = Vector(((v.co.x - cx) * sc_, (v.co.y - cy) * sc_, 0))
    for f in bm.faces:
        if f.normal.z < 0:
            f.normal_flip()
    top = THICK * h
    ext = bmesh.ops.extrude_face_region(bm, geom=bm.faces[:])
    bmesh.ops.translate(bm, verts=[g for g in ext["geom"] if isinstance(g, bmesh.types.BMVert)], vec=(0, 0, top))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    bmesh.ops.bevel(bm, geom=[e for e in bm.edges if all(abs(v.co.z - top) < 1e-7 for v in e.verts)],
                    offset=THICK * 0.025, segments=3, affect="EDGES", profile=0.5, clamp_overlap=True)
    bm.to_mesh(o.data); bm.free()
    o.data.materials.clear(); o.data.materials.append(mat)
    for f in o.data.polygons: f.use_smooth = False
    o.location = (0, 0, z0)
    return o

def detailed_coin_mesh(field_m, edge_m, relief_m, mark_face_m, chain="btc"):
    r, th, n = R, THICK, 320
    k = r / 0.62; z0 = th / 2 - th * 0.1
    parts = []
    # body: rim, recessed field, chamfered rim edge, reeded side wall (geometry + bump)
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=n, radius1=r, radius2=r, depth=th)
    for f in [f for f in bm.faces if len(f.verts) > 4]:
        bmesh.ops.inset_individual(bm, faces=[f], thickness=r * 0.035, depth=0)
        bmesh.ops.inset_individual(bm, faces=[f], thickness=r * 0.02, depth=-th * 0.1)
        bmesh.ops.inset_individual(bm, faces=[f], thickness=r * 0.01, depth=0)
    bmesh.ops.bevel(bm, geom=[e for e in bm.edges if all(math.hypot(v.co.x, v.co.y) > r * 0.999 for v in e.verts)
                              and abs(e.verts[0].co.z - e.verts[1].co.z) < 1e-6],
                    offset=th * 0.12, segments=2, affect="EDGES", profile=0.5)
    for v in bm.verts:
        if math.hypot(v.co.x, v.co.y) > r * 0.9995:
            a = math.atan2(v.co.y, v.co.x); q = 1 - 0.007 * (1 if int(round(a / (2 * math.pi) * n)) % 2 else 0)
            v.co.x *= q; v.co.y *= q
    for f in [f for f in bm.faces if len(f.verts) > 4]:
        bmesh.ops.poke(bm, faces=[f])
    me = bpy.data.meshes.new("body"); bm.to_mesh(me); bm.free()
    me.materials.append(field_m); me.materials.append(edge_m)
    for f in me.polygons:
        side = abs(f.normal.z) < 0.9
        f.material_index = 1 if side else 0
        f.use_smooth = side
    parts.append(_link(bpy.data.objects.new("body", me)))

    def face_parts():
        out = []
        def ring(nm, ro, ri, h, segs=256):
            bm = bmesh.new()
            outer = [bm.verts.new((ro * math.cos(a), ro * math.sin(a), h)) for a in (2 * math.pi * i / segs for i in range(segs))]
            inner = [bm.verts.new((ri * math.cos(a), ri * math.sin(a), h)) for a in (2 * math.pi * i / segs for i in range(segs))]
            for i in range(segs):
                j = (i + 1) % segs; bm.faces.new((outer[i], outer[j], inner[j], inner[i]))
            ext = bmesh.ops.extrude_face_region(bm, geom=bm.faces[:])
            bmesh.ops.translate(bm, verts=[g for g in ext["geom"] if isinstance(g, bmesh.types.BMVert)], vec=(0, 0, -h - 0.002 * k))
            bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
            out.append(_mesh_obj(nm, bm, relief_m))
        ring("ring", 0.432 * k, 0.42 * k, 0.007 * k)
        for i, rr_ in enumerate((0.515, 0.505)):
            ring(f"line{i}", (rr_ + 0.002) * k, (rr_ - 0.002) * k, 0.004 * k)
        bm = bmesh.new()
        for i in range(96):
            a = 2 * math.pi * i / 96
            g = bmesh.ops.create_uvsphere(bm, u_segments=10, v_segments=6, radius=0.0055 * k)
            bmesh.ops.translate(bm, verts=g["verts"], vec=(0.562 * k * math.cos(a), 0.562 * k * math.sin(a), 0.0))
        out.append(_mesh_obj("beads", bm, relief_m, smooth=True))
        bm = bmesh.new()
        for i in range(72):
            a = 2 * math.pi * (i + 0.5) / 72
            r0, r1, w = 0.435 * k, (0.495 if i % 2 else 0.47) * k, 0.004 * k
            t = Vector((math.cos(a), math.sin(a), 0)); nn = Vector((-t.y, t.x, 0))
            pp = [t * r0 + nn * w, t * r1, t * r0 - nn * w]
            vs = [bm.verts.new((v.x, v.y, 0.0)) for v in pp] + [bm.verts.new((v.x, v.y, 0.004 * k)) for v in pp]
            bm.faces.new((vs[0], vs[1], vs[2])); bm.faces.new((vs[5], vs[4], vs[3]))
            for q in range(3):
                j = (q + 1) % 3; bm.faces.new((vs[q], vs[3 + q], vs[3 + j], vs[j]))
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
        out.append(_mesh_obj("rays", bm, relief_m))
        # lettering around the medal
        path = bpy.data.curves.new("txt_path", "CURVE"); path.dimensions = "2D"
        sp = path.splines.new("POLY"); npt = 180; sp.points.add(npt - 1); sp.use_cyclic_u = True
        for i in range(npt):
            a = math.pi / 2 + 2.62 - 2 * math.pi * i / npt
            sp.points[i].co = (0.531 * k * math.cos(a), 0.531 * k * math.sin(a), 0, 1)
        path_o = _link(bpy.data.objects.new("txt_path", path))
        td = bpy.data.curves.new("ring_text", "FONT")
        td.body = "SUPERSWAP  ·  BITCOIN  ·  ANY COIN, ANY CHAIN  ·  ONE CLICK  ·  WORKS REALLY EVERYWHERE  ·"
        td.size = 0.026 * k; td.space_character = 1.35; td.extrude = 0.0018 * k; td.follow_curve = path_o
        t = _to_mesh(_link(bpy.data.objects.new("ring_text", td)))
        t.data.materials.append(relief_m); bpy.data.objects.remove(path_o)
        out.append(t)
        for o in out:
            o.location = (0, 0, z0)
        # the BTC mark: bold B + the four bars, tilted like the video coins; polished bevelled frame over a brushed inner face
        font = bpy.data.fonts.load("/System/Library/Fonts/Supplemental/Arial Bold.ttf")
        def mark(name, h, mat, inset):
            td = bpy.data.curves.new(name, "FONT"); td.body = "B"; td.font = font
            td.size = 1.0; td.align_x = "CENTER"; td.align_y = "CENTER"
            td.extrude = th * h / 2; td.bevel_depth = th * 0.025 if not inset else 0; td.bevel_resolution = 3
            td.offset = -inset
            o = _to_mesh(_link(bpy.data.objects.new(name, td)))
            bm = bmesh.new(); bm.from_mesh(o.data)
            for x in (-0.09, 0.09):        # bars above and below, in units of the B's cap height (~0.72)
                for y0, y1 in ((0.25, 0.47), (-0.47, -0.25)):
                    g = bmesh.ops.create_cube(bm, size=1)
                    bmesh.ops.scale(bm, vec=(0.075 - 2 * inset, y1 - y0 - 2 * inset, th * h), verts=g["verts"])
                    bmesh.ops.translate(bm, vec=(x, (y0 + y1) / 2, 0), verts=g["verts"])
            bm.to_mesh(o.data); bm.free()
            o.data.materials.clear(); o.data.materials.append(mat)
            s_ = env("MARK", 1.2) * r            # glyph scale: fits inside the raised ring like the thrive mark
            o.scale = (s_, s_, 1)
            o.rotation_euler = (0, 0, math.radians(-14))
            o.location = (0.02 * r, 0, z0 + th * h / 2)
            return o
        if chain == "btc":
            out.append(mark("mark_frame", 0.14, relief_m, 0))
            out.append(mark("mark_face", 0.14 * 0.4 + 0.02, mark_face_m, 0.035))
        else:
            size = {"eth": 1.08, "bnb": 1.02, "matic": 1.05, "sol": 0.98, "base": 0.82, "arbitrum": 1.08, "usdc": 1.0}.get(chain, 1.0) * r
            out.append(svg_mark("mark_" + chain, os.path.join(MARKS, chain + ".svg"), size, 0.14, relief_m, z0))
        return out

    front = face_parts()
    back = face_parts()
    bpy.context.view_layer.update()      # matrix_world must reflect the locations set above before flipping
    for o in back:                       # same medal on the back, reading the right way round from behind
        o.matrix_world = Matrix.Rotation(math.pi, 4, "Y") @ o.matrix_world
    parts += front + back
    bpy.ops.object.select_all(action="DESELECT")
    for o in parts:
        o.select_set(True)
    bpy.context.view_layer.objects.active = parts[0]
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    bpy.ops.object.join()
    master = bpy.context.view_layer.objects.active
    me = master.data
    bpy.data.objects.remove(master)
    return me

if COIN == "gold":
    RELIEF = gold("gold_relief", env("REL_LO", 0.12), env("REL_HI", 0.24), 1.6, patina=0.2)
    MARK_FACE = gold("gold_mark_face", 0.25, 0.4, 2.0, guilloche=True, patina=0.4)
    MESHES = [detailed_coin_mesh(FACE, EDGE, RELIEF, MARK_FACE, c) for c in CHAINS]
else:
    MESHES = [coin_mesh()]
rig = bpy.data.objects.new("ring", None)            # ring plane, tilted back
scene.collection.objects.link(rig)
rig.rotation_euler = (TILT, 0, 0)

coins = []
for i in range(N):
    ob = bpy.data.objects.new(f"coin_{i}", MESHES[i % len(MESHES)])
    scene.collection.objects.link(ob)
    ob.parent = rig
    if COIN != "gold":
        bev = ob.modifiers.new("bevel", "BEVEL")
        bev.width = 0.012 * R
        bev.segments = 3
        bev.limit_method = "ANGLE"
        bev.angle_limit = math.radians(40)
        bev.harden_normals = True
    coins.append(ob)

def place(frame):
    """Clockwise orbit by PERIOD slots over FRAMES; spin locked to ring angle."""
    t = (frame - 1) / FRAMES
    for i, ob in enumerate(coins):
        theta = 2 * math.pi * i / N - (2 * math.pi / N) * PERIOD * t
        radial = Vector((math.cos(theta), 0, math.sin(theta)))
        spin = theta + SPIN_OFFSET
        face = Matrix.Rotation(math.radians(90), 4, "X")
        ob.matrix_basis = Matrix.Translation(radial * RING) @ Matrix.Rotation(spin, 4, radial) @ face

for f in range(1, FRAMES + 1):
    place(f)
    for ob in coins:
        ob.keyframe_insert("location", frame=f)
        ob.rotation_mode = "QUATERNION"
        ob.rotation_quaternion = ob.matrix_basis.to_quaternion()
        ob.keyframe_insert("rotation_quaternion", frame=f)
for ob in coins:
    for fc in ob.animation_data.action.fcurves if hasattr(ob.animation_data.action, "fcurves") else []:
        for k in fc.keyframe_points:
            k.interpolation = "LINEAR"

scene.frame_start, scene.frame_end = 1, FRAMES
scene.render.fps = FPS

# ---------- camera (perspective like the video)
cam_data = bpy.data.cameras.new("cam")
cam_data.lens = env("LENS", 45)
cam = bpy.data.objects.new("cam", cam_data)
scene.collection.objects.link(cam)
dist = env("DIST", 8.4)
cam.location = (0, -dist, 0)
cam.rotation_euler = (math.radians(90), 0, 0)
scene.camera = cam

# ---------- studio: black world, softboxes only seen in reflections (chrome needs something to reflect)
def softbox(name, loc, size, strength, rot):
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=1)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    scene.collection.objects.link(ob)
    ob.location, ob.scale, ob.rotation_euler = loc, size, rot
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    e = nt.nodes.new("ShaderNodeEmission")
    e.inputs["Strength"].default_value = strength
    nt.links.new(e.outputs[0], nt.nodes.new("ShaderNodeOutputMaterial").inputs[0])
    me.materials.append(m)
    ob.visible_camera = False
    return ob

k = env("LIGHT", 0.75 if COIN == "gold" else 1.0)
softbox("key", (5, -9, 5), (7, 3, 1), env("KEY", 3.6) * k, (math.radians(65), 0, math.radians(25)))
softbox("strip_left", (-7, -6, 0), (1.2, 8, 1), 4 * k, (math.radians(90), math.radians(-50), 0))
softbox("top", (0, -2, 9), (8, 4, 1), 3 * k, (0, 0, 0))
softbox("front", (1.5, -14, 1.5), (9, 6, 1), env("FRONT", 0.5 if COIN == "gold" else 1.1) * k, (math.radians(90), 0, 0))
softbox("bottom", (2, -6, -7), (6, 2, 1), 1.2 * k, (math.radians(140), 0, 0))
d = bpy.data.lights.new("keylight", "AREA")
d.size, d.energy = 6, env("KEYL", 600) * k
kl = bpy.data.objects.new("keylight", d)
scene.collection.objects.link(kl)
kl.location = (6, -8, 6)
kl.rotation_euler = (Vector((0, 0, 0)) - kl.location).to_track_quat("-Z", "Y").to_euler()

world = bpy.data.worlds.new("w")
world.use_nodes = True
g = env("WORLD", 0.07)
world.node_tree.nodes["Background"].inputs["Color"].default_value = (g, g, g, 1)
scene.world = world

# ---------- render
r = scene.render
r.engine = "CYCLES"
scene.cycles.device = "GPU"
prefs = bpy.context.preferences.addons["cycles"].preferences
try:
    prefs.compute_device_type = "METAL"
    prefs.get_devices()
    for dv in prefs.devices:
        dv.use = True
except Exception as ex:
    print("GPU setup failed, using CPU:", ex)
    scene.cycles.device = "CPU"
scene.cycles.samples = int(env("SAMPLES", 48 if MODE == "still" else 64))
scene.cycles.use_denoising = True
scene.cycles.seed = 7                    # fixed seed: stable noise across frames
r.film_transparent = True
r.resolution_x = r.resolution_y = int(env("RES", 640 if MODE == "still" else 1080))
r.resolution_percentage = 100
r.image_settings.file_format = "PNG"
r.image_settings.color_mode = "RGBA"
if COIN == "gold":                       # Standard keeps the gold saturated (AgX washes it toward cream), like thrive
    scene.view_settings.view_transform = "Standard"
    scene.view_settings.look = "None"
else:
    scene.view_settings.view_transform = "AgX"
    scene.view_settings.look = "AgX - High Contrast"
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUTDIR, "coins_ring.blend"))

if MODE == "still":
    scene.frame_set(int(env("FRAME", 1)))
    r.filepath = os.path.join(OUTDIR, "ring-still.png")
    bpy.ops.render.render(write_still=True)
else:
    os.makedirs(os.path.join(OUTDIR, "ring"), exist_ok=True)
    r.filepath = os.path.join(OUTDIR, "ring", "####")
    bpy.ops.render.render(animation=True)
print("DONE", MODE, FRAMES, "frames")
