#!/usr/bin/env python3
"""
Build a distinct image prompt for every build in the catalogue.

Prints one compact line per build:

    <n>|<id>|<scene phrase>

Compose the final prompt as:

    "<scene phrase>, retro pixel-art voxel game screenshot, crisp 16-bit
     pixels, vibrant saturated colours, cinematic lighting, 16:10 composition.
     Absolutely no text, no letters, no words, no UI, no logos."

Usage:
    python3 tools/make_cover_prompts.py              # all
    python3 tools/make_cover_prompts.py 1 10         # a range
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# --------------------------------------------------------------------------
# hand-written scenes for the builds people look at most (releases, clients)
# --------------------------------------------------------------------------
EXACT = {
    # ---- full releases -------------------------------------------------
    "Eaglercraft 1.0.0": "a blocky snowy taiga village at dawn with smoke rising from chimneys",
    "Eaglercraft 1.1": "a grassy plains biome with a wooden windmill and grazing sheep",
    "Eaglercraft 1.2.3": "a jungle temple half-swallowed by vines under a bright blue sky",
    "Eaglercraft 1.2.5": "a desert village with sandstone houses and a flowing river",
    "Eaglercraft 1.3.2": "a swamp biome with lily pads, vines and a small witch hut",
    "Eaglercraft 1.4.7": "a snow-covered mountain ridge at night under a starry sky",
    "Eaglercraft 1.5.2": "a quartz nether fortress bridge over a lava sea",
    "Eaglercraft 1.6.4": "a mushroom island biome with giant red mushrooms at sunset",
    "Eaglercraft 1.7": "a flower forest biome bursting with colourful blooms",
    "Eaglercraft 1.7.10": "a dark oak roofed forest with dense canopy and mist",
    "Eaglercraft 1.8": "an ocean monument silhouette deep under blue water",
    "EaglercraftX 1.8.8": "a stone-brick stronghold library with bookshelves and torches",
    "EaglercraftX 1.8 (Mobile)": "a compact grassy island with a small dirt hut seen from above",
    "EaglercraftX 1.9 (b194)": "an end island with obsidian pillars and a dragon silhouette",
    "Eaglercraft 1.11.2": "an ice plains spikes biome with sharp frozen towers",
    "Eaglercraft 1.12": "a savanna plateau with acacia trees and a watering hole",
    "EaglercraftX 1.12.2": "a birch forest at golden hour with long shadows",
    "Eaglercraft 1.13.2": "a coral reef under the ocean with tropical fish and shipwreck",
    "EaglercraftX 1.14.4": "a pale snowy village with lanterns glowing at dusk",
    "EaglercraftX 1.14.4 (U1)": "a bamboo jungle with pandas and a winding river",
    "Eaglercraft 1.16.5": "a crimson nether forest with glowing fungi and lava",
    "Eaglercraft 1.17": "a lush cave with glow berries and dripping water",
    "Eaglercraft 1.20.6": "a cherry blossom grove with pink petals on still water",
    "Eaglercraft 1.21.11": "a towering pale garden with hanging moss and pale oak",
    "EaglercraftX 1.21.11": "a deep dark biome with sculk veins glowing faintly",
    "Eaglercraft 26.1.2": "a futuristic voxel skyline of glass towers at night",
    "Eaglercraft 26.2": "a vast windswept savanna under a dramatic purple storm sky",
    "Eaglercraft 1.6.4 Forge": "a cobblestone workshop filled with furnaces and anvils",
    # ---- clients --------------------------------------------------------
    "Aero Client": "a neon cyan voxel duel arena floating in a dark void",
    "EaglyMC": "a glowing magenta voxel hub island with floating platforms",
    "EB Client Nextgen CU4": "a purple-lit voxel battle arena with particle storms",
    "Eclipse Client": "an obsidian PvP arena lit by orange lava and moonlight",
    "EaglercraftZ": "a chrome and glass voxel citadel at night",
    "Huzzium Client": "a glowing lime-green voxel parkour course in the sky",
    "Kone Client": "a compact neon arena with glowing edge lighting",
    "Mega Client": "a futuristic voxel training ground with holographic rings",
    "Myven Client": "a sleek white and cyan voxel arena with energy pillars",
    "N0VA Client": "a starfield voxel arena with drifting asteroids",
    "Novix 26.1.2": "a high-tech voxel city rooftop at night with neon signs",
    "PixelClient": "a pixel-art voxel colosseum lit by bright spotlights",
    "Precision Client": "a clean quartz arena with precise grid markings",
    "Prism Client": "a prismatic crystal voxel arena refracting rainbow light",
    "Tuff Client": "a deepslate and tuff fortress arena under storm clouds",
    "Wispcraft Eaglercraft 1.8.8": "a misty emerald voxel arena with floating ruins",
    "Wispcraft EaglercraftX 1.8": "a glowing teal void arena with ancient stone rings",
    "Wispcraft Eaglercraft 1.12": "a wisp-lit blue voxel arena over a misty lake",
    "Wispcraft Eaglercraft 1.12.2": "a frozen cyan voxel arena with aurora overhead",
    "Water Client": "an underwater voxel arena with coral and light shafts",
    "WurstX": "a dark industrial voxel arena with red warning lights",
    # ---- extras ---------------------------------------------------------
    "Minicraft": "a top-down pixel-art adventure map with a tiny hero sprite and slimes",
    "Eaglercraft Scratch": "a bright flat cartoon voxel playground with a cat mascot",
    "Wispcraft Injector": "a glowing cyan wrench over a grid of code and gears",
}

# --------------------------------------------------------------------------
# rotation pools, used for the long Classic / Alpha / Beta / rd- families so
# that no two neighbouring builds get the same scene
# --------------------------------------------------------------------------
POOLS = {
    "preclassic": [
        "flat brown dirt plains with stubby sparse grass and thick grey fog",
        "crude cobblestone blocks stacked into a rough wall on bare dirt",
        "primitive dirt terrain with a small square pond under a flat grey sky",
        "a rough grey stone mound standing alone on empty brown plains",
        "an early prototype world with odd floating dirt cubes",
        "barren dirt hills under a washed-out white sky",
        "blocky brown terrain with a crude tree made of grey leaves",
        "a flat world of dirt and gravel fading into heavy distance fog",
        "early voxel cliffs of dirt surrounding a tiny grass patch",
        "a crude dirt plateau with a single torch of flickering light",
    ],
    "classic": [
        "a bright checkerboard grass and cobblestone platform floating in blue sky",
        "a brick pyramid rising from a flat green creative world",
        "a cobblestone castle with tall towers and crenellations",
        "a glass and quartz tower sparkling in midday sun",
        "a floating rainbow wool sculpture over a cheerful green field",
        "an obsidian platform surrounded by pixel clouds",
        "a stone brick maze viewed from a high angle",
        "a cosy oak plank house with a cobblestone path",
        "a grand fountain of stone and water in a creative plaza",
        "a giant pixel-art mural wall of coloured wool blocks",
        "a sandy beach next to a calm creative-mode ocean",
        "a snowy creative landscape dotted with spruce trees",
        "a mushroom-shaped structure built from red and white wool",
        "a long suspension bridge of planks over a green valley",
        "a tiered garden of flower beds and hedges",
        "a floating island with a waterfall spilling into the void",
    ],
    "indev": [
        "a tiny foggy voxel island at dusk with a wooden shack and torch",
        "a small finite world surrounded by endless grey fog",
        "a cobblestone shelter glowing with firelight on a misty island",
        "a cramped voxel valley walled in by invisible limits",
        "a torch-lit mineshaft entrance cut into a foggy hillside",
        "a lone plank cabin on a grass island under heavy overcast",
        "a fog-veiled island with a small wheat farm and fence",
        "a dim underground cavern lit by a single placed torch",
        "a misty island shoreline with gentle grey waves",
    ],
    "infdev": [
        "endless rolling voxel hills fading into heavy distance fog with a cave mouth",
    ],
    "alpha": [
        "a cobblestone shelter at night with a campfire and lurking zombies",
        "a survival base carved into a cliffside at sunrise",
        "a torch-lit mine tunnel with exposed coal and iron ore",
        "a dark oak forest at night with a small wooden outpost",
        "a dirt hovel under a storm with lightning over the plains",
        "a walled courtyard of cobble defending against the night",
        "a glowing lava pit inside a cramped stone shelter",
        "a foggy survival camp beside a wide rushing river",
    ],
    "beta": [
        "a golden sunrise over a grassy savanna with acacia trees",
        "a small village of oak and cobblestone houses around a well",
        "a snowy taiga village with chimneys smoking at dawn",
        "a desert with cacti and a distant sandstone ruin",
        "a birch hillside overlooking a wide calm lake at noon",
        "a dense swamp with vines, lily pads and misty water",
        "a plains biome with tall grass and a herd of cows",
        "a cliffside overlook above a fog-filled valley",
        "a rainy forest canopy dripping over mossy stone",
        "a mesa of layered red sand under a bright blue sky",
        "a beach at sunset with palm trees and gentle surf",
        "a frozen river winding through snow-covered pines",
        "a jungle river with waterfalls and dense green canopy",
        "a mushroom island shore glowing at twilight",
        "a canyon of red rock sliced by a thin river",
        "a wheat farm on rolling hills at harvest time",
        "a stone bridge arching over a deep ravine",
        "a mountaintop camp under a clear starry sky",
    ],
    "release": [
        "a cherry blossom grove reflected in still water",
        "a deep dark cavern glowing with sculk sensors",
        "a nether fortress bridge spanning a sea of lava",
        "a windswept savanna plateau at golden hour",
        "an ancient city of deepslate bricks in the dark",
        "a lush cave with waterfalls and glowing berries",
        "a snowy ice-spikes biome under aurora light",
        "a coral reef teeming with tropical fish",
        "a bamboo forest with mist and a winding path",
        "a village under siege by a thunderstorm at night",
    ],
    "client": [
        "a neon-lit voxel duel arena with glowing trim",
        "a dark void platform arena with energy rings",
        "a futuristic voxel training facility with holograms",
        "a crystal voxel arena refracting coloured light",
        "a cyberpunk voxel rooftop arena at night",
    ],
    "extras": [
        "a tiny glowing retro game cartridge on a dark grid",
        "a pocket handheld showing a top-down pixel hero",
        "a chunky 16-bit voxel sprite sheet of blocks and tools",
        "a neon workshop bench scattered with pixel tools",
    ],
}

# time-of-day twist so the JS and WASM twin of the same version differ
TWINS = {
    "js": "bright midday light",
    "wasm": "warm sunset light",
    "wasm-gc": "dramatic dusk lighting with long shadows",
    "unknown": "soft overcast light",
}


def main() -> int:
    cat = json.load(open(os.path.join(ROOT, "data", "versions.json"), encoding="utf-8"))
    versions = cat["versions"]

    start = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    end = int(sys.argv[2]) if len(sys.argv) > 2 else len(versions)

    used = {}
    lines = []
    for i, v in enumerate(versions, 1):
        name = v["name"]
        if name in EXACT:
            scene = EXACT[name]
        else:
            pool = POOLS.get(v["category"], POOLS["release"])
            n = used.get(v["category"], 0)
            used[v["category"]] = n + 1
            scene = pool[n % len(pool)]
            # keep the JS / WASM twins of one version visually distinct
            scene += ", " + TWINS.get(v["runtime"], "soft overcast light")
        lines.append("%d|%s|%s" % (i, v["id"], scene))

    for line in lines[start - 1:end]:
        print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
