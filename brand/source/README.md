Render sources. Put the Satoshi TTFs (fontshare.com, free) in `font/` and the scripts next to `marks/`, then:

    blender -b -P banner.py -- og && python3 post.py og-raw.png og.jpg 1200 630
    MIRROR=1 blender -b -P banner.py -- x && python3 post.py x-mirror-raw.png x-header.jpg 1500 500   # mirrored, clear of the profile photo
    blender -b -P logo.py                      # logo-raw.png (2000px)
    python3 wordmark.py ../logo                # flat mark + wordmark PNGs

The coin builder comes from superswap-section/blender/coins_ring.py.

    FPS=30 SAMPLES=56 RES=1200 KEY=2.8 KEYL=420 REL_LO=0.2 REL_HI=0.32 OUTDIR=out blender -b -P coins_ring.py -- anim   # hero coin ring (site/assets/ring.*)
