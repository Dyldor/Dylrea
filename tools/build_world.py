"""Build the RetroRemake retro world: GodzHell base + content from other 2007-2012 era servers.

Every output is regenerated from the pristine GodzHell source plus donor servers, so the script is
repeatable. It writes data files only; the Java hooks that read them live in RetroContent.java.

Usage: python3 build_world.py <config.json>
"""
import json, math, os, re, shutil, sys, collections, random, difflib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import merge_customs as mc
from cache317 import World, config_counts

random.seed(317)
NUM = r"-?\d+"


# ------------------------------------------------------------------ generic helpers
def norm(s):
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def read(p):
    return open(p, encoding="latin-1").read().replace("\r\n", "\n").replace("\r", "\n")


def write(p, text):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    open(p, "w", encoding="latin-1", newline="").write(text.replace("\n", "\r\n"))


def cfg_rows(text, key):
    """Rows of `key = a<tab>b...` as token lists (tabs or runs of whitespace)."""
    out = []
    for line in text.split("\n"):
        m = re.match(r"\s*%s\s*=\s*(.*)$" % re.escape(key), line)
        if m:
            out.append(re.split(r"\t+|\s{2,}", m.group(1).strip()) if "\t" in m.group(1) else m.group(1).split())
    return out


def ints(tokens, n):
    try:
        return [int(t) for t in tokens[:n]]
    except ValueError:
        return None


def find_files(root, name):
    hits = []
    for d, _, fs in os.walk(root):
        for f in fs:
            if f.lower() == name.lower():
                hits.append(os.path.join(d, f))
    return hits


def richest(root, name, key):
    """The copy of a config file with the most `key =` rows (servers ship several stale copies)."""
    best, n = None, -1
    for p in find_files(root, name):
        c = len(cfg_rows(read(p), key))
        if c > n:
            best, n = p, c
    return best


# ------------------------------------------------------------------ item names / ids
class Items:
    def __init__(self, item_cfg_text, custom_names):
        self.name = {}
        for row in cfg_rows(item_cfg_text, "item"):
            if row and row[0].isdigit() and len(row) > 1:
                self.name.setdefault(int(row[0]), row[1].replace("_", " "))
        self.name.update(custom_names)
        self.by_name = {}
        for i, n in sorted(self.name.items()):
            self.by_name.setdefault(norm(n), i)

    def map_foreign(self, fid, fname, max_stock):
        """Map a donor item id to ours: same id+name, else by name, else None."""
        if fid in self.name and (fname is None or norm(self.name[fid]) == norm(fname)):
            return fid
        if fname and norm(fname) in self.by_name:
            return self.by_name[norm(fname)]
        if fname is None and fid < max_stock:
            return fid
        return None


# ------------------------------------------------------------------ area naming
LANDMARKS = [("Lumbridge", 3222, 3218), ("Varrock", 3212, 3424), ("Falador", 2965, 3380), ("Edgeville", 3087, 3496),
             ("Draynor", 3093, 3244), ("Al Kharid", 3293, 3174), ("Port Sarim", 3011, 3215), ("Rimmington", 2957, 3214),
             ("Karamja", 2918, 3176), ("Brimhaven", 2760, 3178), ("Shilo Village", 2852, 2955), ("Yanille", 2606, 3093),
             ("Ardougne", 2662, 3305), ("Catherby", 2808, 3435), ("Camelot", 2757, 3477), ("Seers' Village", 2726, 3485),
             ("Taverley", 2894, 3448), ("Burthorpe", 2899, 3544), ("Rellekka", 2660, 3657), ("Canifis", 3493, 3488),
             ("Morytania", 3600, 3400), ("Barrows", 3565, 3289), ("Port Phasmatys", 3687, 3502), ("Duel Arena", 3360, 3240),
             ("Kharidian Desert", 3300, 3000), ("Pollnivneach", 3359, 2972), ("Gnome Stronghold", 2462, 3444),
             ("Tree Gnome Village", 2526, 3165), ("Castle Wars", 2442, 3090), ("Feldip Hills", 2550, 2950),
             ("Tirannwn", 2240, 3260), ("Entrana", 2834, 3335), ("Crandor", 2840, 3260), ("Wizards' Tower", 3109, 3162),
             ("Barbarian Village", 3082, 3420), ("Ice Mountain", 3008, 3477), ("Goblin Village", 2956, 3505),
             ("Trollheim", 2890, 3680), ("Digsite", 3360, 3400), ("Mort'ton", 3490, 3290), ("Ape Atoll", 2760, 2780),
             ("Lletya", 2340, 3170), ("Waterbirth Island", 2530, 3740), ("Fremennik Isles", 2330, 3810),
             ("Mage Arena", 3105, 3934), ("Lighthouse", 2510, 3640), ("Piscatoris", 2340, 3650)]
SPECIAL = [("TzHaar City", 2370, 2560, 5050, 5240), ("God Wars Dungeon", 2820, 2950, 5250, 5370),
           ("The Abyss", 3010, 3070, 4800, 4870), ("Fight Pits", 2370, 2430, 5130, 5180)]


def area_name(x, y):
    for n, x1, x2, y1, y2 in SPECIAL:
        if x1 <= x <= x2 and y1 <= y <= y2:
            return n
    if 2944 <= x <= 3392 and 3520 <= y <= 3970:
        return "Wilderness level %d" % ((y - 3520) // 8 + 1)
    if 2944 <= x <= 3392 and 10112 <= y <= 10370:
        return "Wilderness Dungeon"
    under = y >= 9000
    sy = y - 6400 if under else y
    if sy > 4200 or sy < 2400:
        return "Hidden area (%d, %d)" % (x, y)
    best = min(LANDMARKS, key=lambda l: (l[1] - x) ** 2 + (l[2] - sy) ** 2)
    return best[0] + (" Dungeon" if under else "")


def wild(x, y):
    return (2944 <= x <= 3392 and 3520 <= y <= 3970) or (2944 <= x <= 3392 and 10112 <= y <= 10370)


# ------------------------------------------------------------------ teleport names
TELE_ALIAS = {
    "kq": "Kalphite Queen", "kqueen": "Kalphite Queen", "kalph": "Kalphite Queen", "kalphite": "Kalphite Lair",
    "kalphitequeen": "Kalphite Queen", "kalphqueen": "Kalphite Queen", "kbd": "King Black Dragon",
    "kbdcave": "King Black Dragon", "kingbd": "King Black Dragon", "kingblackdragon": "King Black Dragon",
    "jad": "TzTok-Jad", "tzhaar": "TzHaar City", "tzar": "TzHaar City", "fightpits": "Fight Pits", "pits": "Fight Pits",
    "barrows": "Barrows", "barrw": "Barrows Crypts", "gotobarrows": "Barrows", "teletobarrows": "Barrows",
    "godwars": "God Wars Dungeon", "armadyl": "Armadyl Boss", "sara": "Saradomin Boss", "zammy": "Zamorak Boss",
    "zamm": "Zamorak Boss", "cw": "Castle Wars", "cwars": "Castle Wars", "clanwar": "Clan Wars", "clanwars": "Clan Wars",
    "duel": "Duel Arena", "duelarena2": "Duel Arena", "stake": "Duel Arena", "pest": "Pest Control",
    "mb": "Mage Bank", "edge": "Edgeville", "edgvil": "Edgeville", "edge2": "Edgeville Wilderness",
    "home": "Home", "home2": "Home (alt)", "shops": "Market", "fish": "Fishing", "fish2": "Fishing Guild",
    "mine": "Mining", "mining": "Mining", "minerune": "Rune Mine", "wildmine": "Wilderness Mine", "smelt": "Smelting",
    "smith": "Smithing", "wc": "Woodcutting", "wc2": "Woodcutting (gnome)", "thieve": "Thieving", "thiev": "Thieving",
    "rc": "Runecrafting", "runecraft": "Runecrafting", "farm": "Farming", "farm1": "Farming",
    "agility": "Agility", "prayguild": "Prayer Guild", "prayer": "Prayer Altar", "range": "Ranging Guild",
    "train": "Training Grounds", "train2": "Training Grounds 2", "training": "Training Grounds", "hightrain": "High Training",
    "lowtrain": "Low Training", "protrain": "Pro Training", "slayer": "Slayer Tower", "ghosts": "Ectofuntus Ghosts",
    "portals": "Portals", "dungeon": "Dungeon", "taverly": "Taverley Dungeon", "tar": "Taverley Dungeon",
    "tcave": "Taverley Cave", "tcave2": "Taverley Cave 2", "brimhavendungeon": "Brimhaven Dungeon",
    "travlerydungeon": "Taverley Dungeon", "abby": "Abyssal Demons", "abbydemons": "Abyssal Demons",
    "chaoselem": "Chaos Elemental", "chaoselemental": "Chaos Elemental", "crystalchest": "Crystal Chest",
    "druidcircle": "Druid Circle", "druidtrain": "Druids", "spiderhill": "Spider Hill", "cather": "Catherby",
    "relleka": "Rellekka", "frem": "Fremennik", "canfis": "Canifis", "eastvarrock": "East Varrock",
    "varrok": "Varrock", "varrocksmith": "Varrock Smithy", "alkharid": "Al Kharid", "draynor": "Draynor",
    "karamja": "Karamja", "entrana": "Entrana", "falador": "Falador", "zoo": "Zoo", "concert": "Concert",
    "meleeisland": "Melee Island", "islandofskill": "Skill Island", "gopk": "PK Zone", "pk": "PK Zone",
    "newpk": "New PK Zone", "epk": "East PK", "rpk": "Red PK", "icepk": "Ice PK", "purepk": "Pure PK",
    "pkbox": "PK Box", "playerkill": "PK Zone", "multi": "Multi PK", "1v1": "1v1 Arena", "war": "War Zone",
    "drags": "Dragons", "drags2": "Dragons 2", "beast": "Beasts", "kbd2": "King Black Dragon",
    "3rdage": "3rd Age Monsters", "capes": "Capes Area", "elfs": "Elves", "guilds": "Guilds", "skills": "Skills Area",
    "skillz": "Skills Area", "gs": "Godsword Area", "mimenme1": "Mime Area", "icequeen12123": "Ice Queen",
    "wootplacek": "Hidden Spot", "mining2": "Mining 2", "con": "Construction", "kqtrip": "Kalphite Queen",
    "cwars2": "Castle Wars", "hang": "Hangout", "west": "West Falador", "stupid": "Fun Room",
    "medieval": "Medieval Area", "dungeongate": "Dungeon Gate", "getout": "Exit Area", "saveme": "Safe Spot",
}
TELE_SKIP = {"jail", "unjail", "secret", "xteleallpk", "testminigame", "getout", "saveme", "stupid", "wootplacek",
             "mimenme1", "icequeen12123", "concert"}

CATEGORY_RULES = [
    ("Bosses", r"queen|dragon|jad|boss|elemental|god ?wars|armadyl|saradomin|zamorak|bandos|ice queen|dagannoth|barrelchest|tztok|tzhaar|king|godsword"),
    ("PvP", r"pk|wilderness|clan|castle wars|duel|1v1|multi|war zone|mage bank|edgeville wild|fight pits"),
    ("Minigames", r"pest|barrows|crystal|portals|fight|guild|zoo"),
    ("Skilling", r"fish|min(e|ing)|smelt|smith|wood|thiev|runecraft|farm|agility|prayer|rang|construction|skill|druid circle"),
    ("Cities", r"home|varrock|falador|lumbridge|edgeville|catherby|ardougne|canifis|rellekka|draynor|al kharid|karamja|entrana|shops|market|hangout"),
]


def category(name, x, y):
    n = name.lower()
    for cat, rx in CATEGORY_RULES:
        if re.search(rx, n):
            return cat
    if wild(x, y):
        return "PvP"
    return "Training"


# ------------------------------------------------------------------ main build
def main(conf_path):
    C = json.load(open(conf_path))
    base, proj, donors_classic, donors_pi = C["base"], C["project"], C["classic"], C["pi"]
    srv, cli = os.path.join(proj, "server"), os.path.join(proj, "client")
    report = collections.OrderedDict()

    # 0. restore pristine data files that this script owns
    for rel in ("Client/Class8.java",):
        shutil.copy(os.path.join(base, rel), os.path.join(cli, "Class8.java"))
    for rel in ("item.cfg", "autospawn.cfg", "npc.cfg", "WorldObjects.cfg", "drops.cfg", "shops.cfg",
                "Item4.java", "Item.java"):
        shutil.copy(os.path.join(base, "Server", rel), os.path.join(srv, rel))
    shutil.copy(os.path.join(base, "Server", "Config", "objects.cfg"), os.path.join(srv, "Config", "objects.cfg"))

    limits = config_counts(os.path.join(cli, "cache"))
    MAX_ITEM, MAX_NPC, MAX_LOC = limits["obj.idx"], limits["npc.idx"], limits["loc.idx"]
    world = World(os.path.join(cli, "cache"))

    # 1. custom item merge (client Class8 + server item.cfg)
    mc.NEW_ID_START = C["new_item_id_start"]
    mcfg = dict(C["customs"])
    mcfg.update(base_client=os.path.join(cli, "Class8.java"), base_item_cfg=os.path.join(srv, "item.cfg"),
                out_client=os.path.join(cli, "Class8.java"), out_item_cfg=os.path.join(srv, "item.cfg"),
                report=os.path.join(proj, "MERGED_ITEMS.tsv"))
    tmp = os.path.join(proj, ".merge.json"); json.dump(mcfg, open(tmp, "w")); mc.main(tmp); os.remove(tmp)

    class8 = read(os.path.join(cli, "Class8.java"))
    custom = {}
    for i, _, _, body in mc.find_blocks(class8):
        n = mc.block_name(body)
        if n and i not in custom:
            custom[i] = n.strip()
    item_text = read(os.path.join(srv, "item.cfg"))
    items = Items(item_text, custom)

    # 2. item.cfg entries for custom items without one (stats from any donor that has the same item)
    donor_item_cfgs = []
    for d in donors_classic + [p["root"] for p in donors_pi]:
        for p in find_files(d, "item.cfg"):
            donor_item_cfgs.append(mc.load_cfg(p))
    cfg = mc.load_cfg(os.path.join(srv, "item.cfg"))
    add = []
    for i, n in sorted(custom.items()):
        if i in cfg:
            continue
        line = None
        for dc in donor_item_cfgs:
            l = dc.get(i)
            if l and norm(mc.cfg_name(l)) == norm(n):
                line = re.sub(r"^\s*item\s*=\s*\d+", "item = %d" % i, l); break
        add.append(line or "item = %d\t%s\tA_custom_item.\t10000\t10000\t10000\t0\t0\t0\t0\t0\t0\t0\t0\t0\t0\t0\t0"
                   % (i, n.replace(" ", "_")))
    end = item_text.rindex("[ENDOFITEMLIST]")
    item_text = item_text[:end].rstrip("\n") + "\n" + "\n".join(add) + "\n" + item_text[end:]
    report["item.cfg entries added for custom items"] = len(add)

    # 3. NPC definitions (server-side names/combat/hp), base first
    npc_text = read(os.path.join(srv, "npc.cfg"))
    npc_rows = {}
    for r in cfg_rows(npc_text, "npc"):
        if r and r[0].isdigit():
            npc_rows.setdefault(int(r[0]), r)
    base_npc_ids = set(npc_rows)
    npc_name = {i: r[1].replace("_", " ") for i, r in npc_rows.items() if len(r) > 1}

    def donor_npc_names(root, fname="npc.cfg"):
        p = richest(root, fname, "npc")
        d = {}
        if p:
            for r in cfg_rows(read(p), "npc"):
                if r and r[0].isdigit() and len(r) > 1:
                    d.setdefault(int(r[0]), r)
        return d

    added_npc_defs = 0
    donor_names = {}
    for d in donors_classic + [p["root"] for p in donors_pi]:
        dn = donor_npc_names(d)
        donor_names[d] = {i: r[1].replace("_", " ") for i, r in dn.items()}
        for i, r in dn.items():
            if i < MAX_NPC and i not in npc_rows and len(r) >= 4 and ints(r[2:4], 2):
                npc_rows[i] = r; npc_name[i] = r[1].replace("_", " "); added_npc_defs += 1
    report["NPC definitions added"] = added_npc_defs

    def npc_ok(nid, donor_root):
        if nid < 0 or nid >= MAX_NPC or nid not in npc_rows:
            return False
        dn = donor_names.get(donor_root, {})
        return nid not in dn or nid not in npc_name or norm(dn[nid]) == norm(npc_name[nid])

    # 4. NPC spawns
    spawns, seen, cell = [], set(), collections.Counter()
    def add_spawn(row, src):
        nid, x, y, h = row[:4]
        k = (nid, x, y, h)
        if k in seen or not (1000 < x < 4600 and 1000 < y < 11000 and 0 <= h <= 3):
            return False
        c = (nid, x // 16, y // 16, h)
        if src != "GodzHell" and cell[c] >= 6:
            return False
        seen.add(k); cell[c] += 1
        spawns.append((row, src)); return True

    for r in cfg_rows(read(os.path.join(srv, "autospawn.cfg")), "spawn"):
        v = ints(r, 9)
        if v:
            add_spawn(v, "GodzHell")
    base_spawn_count = len(spawns)
    per_src = collections.Counter()
    for d in donors_classic:
        p = richest(d, "autospawn.cfg", "spawn")
        if not p:
            continue
        src = os.path.basename(d.rstrip("/"))
        for r in cfg_rows(read(p), "spawn"):
            v = ints(r, 9)
            if v and npc_ok(v[0], d) and add_spawn(v, src):
                per_src[src] += 1
    for pi in donors_pi:
        p = richest(pi["root"], "spawn-config.cfg", "spawn")
        if not p:
            continue
        for r in cfg_rows(read(p), "spawn"):
            v = ints(r, 5)
            if not v or not npc_ok(v[0], pi["root"]):
                continue
            nid, x, y, h, walk = v
            rng = 3 if walk else 0
            if add_spawn([nid, x, y, h, x + rng, y + rng, x - rng, y - rng, 2], pi["name"]):
                per_src[pi["name"]] += 1
    report["NPC spawns (GodzHell)"] = base_spawn_count
    report["NPC spawns imported"] = dict(per_src)

    # 5. ground items (drops.cfg) and objects
    def merge_simple(name, key, n_int, valid, base_path, donor_name, keyfn, label):
        text = read(base_path)
        rows = [r for r in cfg_rows(text, key)]
        keys = {keyfn(ints(r, n_int)) for r in rows if ints(r, n_int)}
        extra = []
        for d in donors_classic:
            p = richest(d, donor_name, key)
            if not p:
                continue
            for r in cfg_rows(read(p), key):
                v = ints(r, n_int)
                if key == "object" and name == "objects.cfg" and (len(r) < 7 or r[6] not in ("true", "false")):
                    continue
                if v and valid(v) and keyfn(v) not in keys:
                    keys.add(keyfn(v)); extra.append(r)
        report[label] = len(extra)
        return text, extra

    gi_text, gi_extra = merge_simple("drops.cfg", "drop", 5, lambda v: 0 <= v[0] < MAX_ITEM and v[3] > 0,
                                     os.path.join(srv, "drops.cfg"), "drops.cfg", lambda v: (v[1], v[2], v[4]),
                                     "ground item spawns imported")
    # GodzHell's object loader reads id x y height face type open-flag; servers with another layout are skipped
    ob_text, ob_extra = merge_simple("objects.cfg", "object", 6, lambda v: 0 <= v[0] < MAX_LOC and 0 <= v[5] <= 22,
                                     os.path.join(srv, "Config", "objects.cfg"), "objects.cfg",
                                     lambda v: (v[1], v[2], v[3]), "world objects imported")
    wo_text, wo_extra = merge_simple("WorldObjects.cfg", "object", 5, lambda v: -1 <= v[2] < MAX_LOC,
                                     os.path.join(srv, "WorldObjects.cfg"), "WorldObjects.cfg",
                                     lambda v: (v[0], v[1], v[3]), "world object overrides imported")

    def insert_rows(text, key, rows, endmark):
        lines = "\n".join("%s = %s" % (key, "\t".join(r)) for r in rows)
        if endmark in text:
            i = text.rindex(endmark)
            return text[:i].rstrip("\n") + "\n" + lines + "\n" + text[i:]
        return text.rstrip("\n") + "\n" + lines + "\n"

    write(os.path.join(srv, "drops.cfg"), insert_rows(gi_text, "drop", gi_extra, "[ENDOFDROPLIST]"))
    write(os.path.join(srv, "Config", "objects.cfg"), insert_rows(ob_text, "object", ob_extra, "[ENDOFOBJECTLIST]"))
    write(os.path.join(srv, "WorldObjects.cfg"), insert_rows(wo_text, "object", wo_extra, "[ENDOFOBJECTLIST]"))

    # 6. shops
    shop_text = read(os.path.join(srv, "shops.cfg"))
    shops = {}
    for r in cfg_rows(shop_text, "shop"):
        v = ints(r, 1)
        if v:
            shops[v[0]] = r
    base_shop_ids = set(shops)
    item_sets = [set(int(t) for t in r[4::2] if t.lstrip("-").isdigit()) for r in shops.values()]
    imported_shops = []

    def donor_item_names(root):
        p = richest(root, "item.cfg", "item")
        d = {}
        if p:
            for r in cfg_rows(read(p), "item"):
                if r and r[0].isdigit() and len(r) > 1:
                    d.setdefault(int(r[0]), r[1].replace("_", " "))
        return d

    for d, label in [(x, os.path.basename(x.rstrip("/"))) for x in donors_classic] + \
                    [(p["root"], p["name"]) for p in donors_pi]:
        p = richest(d, "shops.cfg", "shop")
        if not p:
            continue
        dnames = donor_item_names(d)
        for r in cfg_rows(read(p), "shop"):
            if len(r) < 6 or not r[0].isdigit():
                continue
            name = re.sub(r"@\w\w\w@", "", r[1]).strip("_ .") or "Shop"
            pairs = []
            for a, b in zip(r[4::2], r[5::2]):
                if not (a.lstrip("-").isdigit() and b.lstrip("-").isdigit()):
                    continue
                mid = items.map_foreign(int(a), dnames.get(int(a)), MAX_ITEM)
                if mid is not None and (mid < MAX_ITEM or mid in custom) and mid not in [x for x, _ in pairs]:
                    pairs.append((mid, max(1, min(int(b), 100000))))
            pairs = pairs[:40]
            if len(pairs) < 3:
                continue
            imported_shops.append((label, name, r[2] if r[2].isdigit() else "1", r[3] if r[3].isdigit() else "1", pairs))
    # greedy: keep the shop that adds the most items nobody sells yet, until a shop adds fewer than min_new
    sold = set().union(*item_sets) if item_sets else set()
    kept, pool_shops = [], list(imported_shops)
    while pool_shops and len(kept) < C["max_imported_shops"]:
        best = max(pool_shops, key=lambda sh: len({x for x, _ in sh[4]} - sold))
        gain = len({x for x, _ in best[4]} - sold)
        if gain < C["shop_min_new_items"]:
            break
        kept.append(best); sold |= {x for x, _ in best[4]}; pool_shops.remove(best)
    report["shop candidates"] = len(imported_shops)
    imported_shops = kept
    next_shop = max(shops) + 1
    shop_lines, shop_meta = [], []
    for label, name, sm, bm, pairs in imported_shops:
        sid = next_shop; next_shop += 1
        nm = "%s_(%s)" % (name.replace(" ", "_"), label.replace(" ", ""))
        shop_lines.append("shop = %d\t%s\t%s\t%s\t%s" % (sid, nm, sm, bm, "\t".join("%d\t%d" % pr for pr in pairs)))
        shop_meta.append((sid, nm.replace("_", " "), label, len(pairs)))

    # mystery box shop is added later once the pool exists; reserve its id
    box_shop_id = next_shop; next_shop += 1
    report["shops imported"] = len(shop_meta)

    # market stalls: free tiles around the GodzHell shop area
    mk = C["market"]
    taken = {(r[1], r[2]) for r, _ in spawns}
    stalls = []
    cand = [(x, y) for y in range(mk["y2"], mk["y1"] - 1, -1) for x in range(mk["x1"], mk["x2"] + 1)]
    for x, y in cand:
        if len(stalls) >= len(shop_meta) + 1:
            break
        if not world.free(x, y) or (x, y) in taken:
            continue
        if any(abs(x - a) < 2 and abs(y - b) < 2 for a, b in stalls) or any(abs(x - a) < 2 and abs(y - b) < 2 for a, b in taken):
            continue
        stalls.append((x, y))
    if len(stalls) < len(shop_meta) + 1:
        raise SystemExit("not enough free market tiles: %d for %d shops" % (len(stalls), len(shop_meta) + 1))
    shopnpc_lines = []
    keepers = mk["keeper_npcs"]
    for k, ((sid, nm, label, n), (x, y)) in enumerate(zip(shop_meta + [(box_shop_id, "Mystery Box Store", "RetroRemake", 1)], stalls)):
        nid = keepers[k % len(keepers)]
        spawns.append(([nid, x, y, 0, x, y, x, y, 2], "Market"))
        shopnpc_lines.append("shopnpc = %d\t%d\t0\t%d\t%s" % (x, y, sid, nm.replace(" ", "_")))

    # 7. NPC drops -> extradrops.cfg (only for NPCs GodzHell does not already drop for in Java)
    npch = read(os.path.join(srv, "NPCHandler.java"))
    md = npch[npch.index("public void MonsterDropItem(int NPCID)"):]
    hard_dropped = {int(x) for x in re.findall(r"npcType\s*==\s*(\d+)", md[:60000])}
    tables = collections.defaultdict(list)

    def add_table(nid, chance, entries, src):
        if nid in hard_dropped or not entries:
            return
        key = tuple(sorted(entries))
        if any(t[2] == key for t in tables[nid]) or len(tables[nid]) >= 4:
            return
        tables[nid].append((chance, src, key))

    RARITY = {1: 1, 2: 8, 3: 32}
    for d in donors_classic:
        p = richest(d, "npcdrops.cfg", "npcdrop")
        if not p:
            continue
        src = os.path.basename(d.rstrip("/"))
        dnames = donor_item_names(d)
        for r in cfg_rows(read(p), "npcdrop"):
            v = ints(r, 2)
            if not v or not npc_ok(v[0], d):
                continue
            ent = []
            for a, b in zip(r[2::2], r[3::2]):
                if a.lstrip("-").isdigit() and b.lstrip("-").isdigit() and int(b) > 0:
                    mid = items.map_foreign(int(a), dnames.get(int(a)), MAX_ITEM)
                    if mid is not None and (mid < MAX_ITEM or mid in custom):
                        ent.append((mid, int(b)))
            add_table(v[0], RARITY.get(v[1], 128), ent, src)
    for pi in donors_pi:
        p = None
        for f in find_files(pi["root"], "NPCDrops.cfg"):
            p = f; break
        if not p:
            continue
        dnames = donor_item_names(pi["root"])
        for line in read(p).split("\n"):
            t = line.split()
            if len(t) < 2 or not all(x.isdigit() for x in t):
                continue
            nid = int(t[0])
            if not npc_ok(nid, pi["root"]):
                continue
            ent = []
            for a in t[1:]:
                mid = items.map_foreign(int(a), dnames.get(int(a)), MAX_ITEM)
                if mid is not None and (mid < MAX_ITEM or mid in custom):
                    ent.append((mid, 1000 if mid == 995 else 1))
            add_table(nid, 3, ent, pi["name"])
    report["NPC drop tables imported"] = sum(len(v) for v in tables.values())

    # 8. zones (teleports)
    zones = []

    def add_zone(name, x, y, h, src, kind):
        if not world.known(x, y):
            return False
        for z in zones:
            if z["h"] == h and abs(z["x"] - x) <= 12 and abs(z["y"] - y) <= 12:
                return False
        if h == 0 and not world.free(x, y):
            nf = world.nearest_free(x, y, 0, 3)
            if not nf:
                return False
            x, y = nf
        zones.append({"name": name, "x": x, "y": y, "h": h, "src": src, "kind": kind}); return True

    teles = json.load(open(C["teleports_json"]))
    order = ["GodzHell"] + [k for k in teles if k != "GodzHell"]
    for s in order:
        for t in teles.get(s, []):
            if t["staff"] or t["cmd"] in TELE_SKIP or not (1000 < t["x"] < 4600 and 1000 < t["y"] < 11000):
                continue
            nm = TELE_ALIAS.get(t["cmd"], t["cmd"].capitalize())
            add_zone(nm, t["x"], t["y"], t["h"], s, "named")
    # spawn clusters added by donors that have no teleport nearby
    def combat(nid):
        r = npc_rows.get(nid)
        try:
            return int(r[2])
        except (TypeError, ValueError, IndexError):
            return 0

    clusters = collections.defaultdict(list)
    for r, src in spawns:
        if src in ("GodzHell", "Market") or combat(r[0]) < C["cluster_min_combat"]:
            continue
        clusters[(r[1] // 24, r[2] // 24, r[3])].append(r)
    named_per_area = set()
    for key, rs in sorted(clusters.items(), key=lambda kv: -len(kv[1])):
        if len(rs) < C["cluster_min_spawns"]:
            continue
        cx = sum(r[1] for r in rs) / len(rs); cy = sum(r[2] for r in rs) / len(rs)
        r0 = min(rs, key=lambda r: (r[1] - cx) ** 2 + (r[2] - cy) ** 2)
        topid = collections.Counter(r[0] for r in rs).most_common(1)[0][0]
        top = npc_name.get(topid, "Monster").strip().title()
        area = area_name(r0[1], r0[2])
        if (norm(top), area) in named_per_area:
            continue
        if add_zone("%s (%s)" % (top, area), r0[1], r0[2], r0[3], "spawns", "cluster"):
            named_per_area.add((norm(top), area))
            zones[-1]["cat"] = "PvP" if wild(r0[1], r0[2]) else ("Bosses" if combat(topid) >= 200 else "Training")
    for z in zones:
        if "cat" not in z:
            z["cat"] = "PvP" if wild(z["x"], z["y"]) else category(z["name"], z["x"], z["y"])
        z["area"] = area_name(z["x"], z["y"])
    # unique names: the first (GodzHell) keeps the plain name, later ones say where they came from
    count = collections.Counter(z["name"].lower() for z in zones)
    seen_names = set()
    for z in zones:
        key = z["name"].lower()
        if count[key] > 1 and key in seen_names:
            z["name"] = "%s (%s)" % (z["name"], z["src"] if z["kind"] == "named" else z["area"])
        seen_names.add(key)
    catorder = ["Cities", "Skilling", "Training", "Bosses", "Minigames", "PvP"]
    zones.sort(key=lambda z: (catorder.index(z["cat"]), z["name"].lower()))
    for i, z in enumerate(zones, 1):
        z["id"] = i
    report["zones"] = collections.Counter(z["cat"] for z in zones)

    # 8b. keep teleport targets off tiles that now hold an imported object
    obj_tiles = set()
    for r in cfg_rows(read(os.path.join(srv, "Config", "objects.cfg")), "object"):
        v = ints(r, 4)
        if v:
            obj_tiles.add((v[1], v[2], v[3]))
    for z in zones:
        if (z["x"], z["y"], z["h"]) in obj_tiles:
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (-1, -1), (2, 0), (0, 2)):
                t = (z["x"] + dx, z["y"] + dy, z["h"])
                if t not in obj_tiles and (z["h"] or world.free(t[0], t[1])):
                    z["x"], z["y"] = t[0], t[1]; report["zones moved off imported objects"] = report.get("zones moved off imported objects", 0) + 1
                    break

    # 9. stats theme + slots
    theme = C["theme"]
    box_price = C["mystery_box_price"]
    item_text = re.sub(r"(?m)^(item = %d\t[^\t]+\t[^\t]+\t)[^\t]+\t[^\t]+\t[^\t]+" % C["mystery_box_item"],
                       lambda m: m.group(1) + "%d\t%d\t%d" % (box_price, box_price * 4 // 10, box_price * 6 // 10), item_text)
    item_text = apply_theme(item_text, custom, theme, report)
    write(os.path.join(srv, "item.cfg"), item_text)
    slots = classify_slots(custom, theme)
    patch_item4(os.path.join(srv, "Item4.java"), slots, report)
    patch_twohanded(os.path.join(srv, "Item.java"), slots)

    # 10. mystery box pool = custom items not sold in any shop and not in any drop table
    obtainable = set()
    for r in list(shops.values()):
        obtainable |= {int(t) for t in r[4::2] if t.isdigit()}
    for line in shop_lines:
        obtainable |= {int(t) for t in line.split("\t")[4::2]}
    for t in tables.values():
        for _, _, ent in t:
            obtainable |= {i for i, _ in ent}
    obtainable |= {int(x) for x in re.findall(r"\b(1[0-9]{4})\b", read(os.path.join(srv, "Item2.java")) + read(os.path.join(srv, "Item3.java")) + md[:60000])}
    pool = []
    for i, n in sorted(custom.items()):
        if i in obtainable:
            continue
        tier, slot = item_tier(n, theme), slots.get(i)
        if tier in ("staff", "utility") or slot is None:
            continue
        pool.append((i, n, theme["box_weight"][tier]))
    report["mystery box rewards"] = len(pool)

    # mystery box store + drops
    shop_lines.append("shop = %d\tMystery_Box_Store\t1\t1\t%d\t100" % (box_shop_id, C["mystery_box_item"]))
    end = shop_text.rindex("[ENDOFSHOPLIST]") if "[ENDOFSHOPLIST]" in shop_text else len(shop_text)
    shop_text = shop_text[:end].rstrip("\n") + "\n" + "\n".join(shop_lines) + "\n" + shop_text[end:]
    write(os.path.join(srv, "shops.cfg"), shop_text)
    report["max shop id"] = box_shop_id

    # spawns file
    sp = read(os.path.join(srv, "autospawn.cfg"))
    end = sp.rindex("[ENDOFSPAWNLIST]") if "[ENDOFSPAWNLIST]" in sp else len(sp)
    head = sp[:end]
    extra = ["spawn = %s\t// %s" % ("\t".join(str(v) for v in r[:9]), src) for r, src in spawns if src != "GodzHell"]
    write(os.path.join(srv, "autospawn.cfg"), head.rstrip("\n") + "\n" + "\n".join(extra) + "\n[ENDOFSPAWNLIST]\n")
    report["NPC spawns total"] = len(spawns)

    # npc.cfg
    nt = read(os.path.join(srv, "npc.cfg"))
    end = nt.rindex("[ENDOFNPCLIST]") if "[ENDOFNPCLIST]" in nt else len(nt)
    newdefs = ["npc = %s" % "\t".join(r) for i, r in sorted(npc_rows.items()) if i not in base_npc_ids]
    write(os.path.join(srv, "npc.cfg"), nt[:end].rstrip("\n") + "\n" + "\n".join(newdefs) + "\n" + nt[end:])

    # RetroContent data files
    out = ["// zone = id<TAB>category<TAB>x<TAB>y<TAB>height<TAB>name  (generated by tools/build_world.py)"]
    out += ["zone = %d\t%s\t%d\t%d\t%d\t%s" % (z["id"], z["cat"], z["x"], z["y"], z["h"], z["name"].replace("\t", " ")) for z in zones]
    write(os.path.join(srv, "zones.cfg"), "\n".join(out) + "\n")
    write(os.path.join(srv, "shopnpcs.cfg"), "// shopnpc = spawnX<TAB>spawnY<TAB>height<TAB>shopId<TAB>name\n" + "\n".join(shopnpc_lines) + "\n")
    dl = ["// table = npcId<TAB>chanceDenominator<TAB>item:amount,item:amount,...  (one entry is picked when the 1/N roll hits)",
          "// global = minCombat<TAB>chanceDenominator<TAB>item:amount   (any NPC with at least that combat level)"]
    for nid in sorted(tables):
        for ch, src, ent in tables[nid]:
            dl.append("table = %d\t%d\t%s\t// %s %s" % (nid, ch, ",".join("%d:%d" % e for e in ent), npc_name.get(nid, ""), src))
    for b in C["boss_box_drops"]:
        if b[0] not in npc_rows:
            continue
        dl.append("table = %d\t%d\t%d:1\t// mystery box from %s" % (b[0], b[1], C["mystery_box_item"], npc_name.get(b[0], "?")))
    g = C["global_box_drop"]
    dl.append("global = %d\t%d\t%d:1" % (g["min_combat"], g["chance"], C["mystery_box_item"]))
    write(os.path.join(srv, "extradrops.cfg"), "\n".join(dl) + "\n")
    bl = ["// reward = itemId<TAB>weight<TAB>name   (higher weight = more common)", "box = %d" % C["mystery_box_item"]]
    bl += ["reward = %d\t%d\t%s" % (i, w, n.replace("\t", " ")) for i, n, w in pool]
    write(os.path.join(srv, "mysterybox.cfg"), "\n".join(bl) + "\n")

    write_docs(proj, zones, shop_meta, box_shop_id, pool, report, custom, slots, theme, item_text)
    print(json.dumps(report, indent=1, default=str))


# ------------------------------------------------------------------ theme
SLOT_RULES = [
    ("ring", r"\bring\b"), ("amulet", r"amulet|necklace|stole|pendant|scarf"),
    ("cape", r"cape|cloak|tail\b"),
    ("hands", r"glove|gauntlet|hands|bracelet|brace\b|vamb|bracers"), ("feet", r"boot|feet|shoes"),
    ("shield", r"shield|defender|kiteshield|visage|book|ward\b"),
    ("legs", r"leg|chaps|skirt|bottom|tights|trousers|slacks|cuisse|tasset|pantaloons|robe$|robe bottom"),
    ("body", r"body|chainmail|platebody|top\b|torso|shirt|blouse|chest|plate\b|jacket|robe top|hauberk|d'hide$|dragonhide|armour$|tunic"),
    ("head", r"helm|hat|hood|mask|horn|head|coif|mitre|halo|crown|partyhat|party hat|santa|sallet|tiara|headdress|beret|boater|headband|cavalier|goggles"),
    ("weapon", r"whip|sword|blade|scimitar|claw|\bbow\b|shortbow|longbow|c'bow|crossbow|staff|crozier|anchor|mace|stick|spear|axe|maul|dagger|"
               r"godsword|balmung|halberd|hammer|chinchompa|wand|cane|hasta|sceptre|scythe|flail|sabre|keris|^car$|briefcase|dildo"),
]


def item_slot(name):
    n = name.lower()
    for slot, rx in SLOT_RULES:
        if re.search(rx, n):
            return slot
    return None


def item_tier(name, theme):
    n = name.lower()
    for tier, rx in theme["tier_rules"]:
        if re.search(rx, n):
            return tier
    return theme["default_tier"]


def weapon_style(name):
    n = name.lower()
    if re.search(r"\bbow\b|shortbow|longbow|comp bow|c'bow|crossbow|chinchompa", n):
        return "ranged"
    if re.search(r"staff|crozier|wand", n):
        return "magic"
    if re.search(r"mace|anchor|maul|hammer|stick|cane", n):
        return "crush"
    if re.search(r"godsword|balmung|halberd", n):
        return "twohand"
    if re.search(r"claw", n):
        return "claws"
    if re.search(r"whip", n):
        return "whip"
    return "slash"


def classify_slots(custom, theme):
    out = {}
    for i, n in custom.items():
        if item_tier(n, theme) == "utility":
            continue
        s = item_slot(n)
        if s:
            out[i] = s
    return out


def apply_theme(item_text, custom, theme, report):
    lines = item_text.split("\n")
    changed = 0
    for k, line in enumerate(lines):
        m = re.match(r"\s*item\s*=\s*(\d+)\s", line)
        if not m:
            continue
        i = int(m.group(1))
        if i not in custom:
            continue
        name = custom[i]
        tier, slot = item_tier(name, theme), item_slot(name)
        if tier == "utility" or slot is None:
            continue
        ref = theme["ref"][weapon_style(name) if slot == "weapon" else slot]
        mult = theme["tier_mult"][tier]
        bonus = [int(round(b * mult)) if b > 0 else b for b in ref]
        value = theme["tier_value"][tier]
        examine = "%s_(%s_tier)." % (name.replace(" ", "_"), tier.capitalize())
        lines[k] = "item = %d\t%s\t%s\t%d\t%d\t%d\t%s" % (i, name.replace(" ", "_"), examine, value, value * 4 // 10,
                                                          value * 6 // 10, "\t".join(str(b) for b in bonus))
        changed += 1
    report["custom items given themed stats"] = changed
    return "\n".join(lines)


SLOT_ARRAYS = {"cape": "capes", "feet": "boots", "hands": "gloves", "shield": "shields", "head": "hats",
               "amulet": "amulets", "ring": "rings", "body": "body", "legs": "legs"}


def patch_item4(path, slots, report):
    src = read(path)
    added = collections.Counter()
    for slot, arr in SLOT_ARRAYS.items():
        ids = sorted(i for i, s in slots.items() if s == slot)
        m = re.search(r"(public static int %s\[\]\s*=\s*\{)([^}]*)\}" % re.escape(arr), src)
        have = {int(x) for x in re.findall(r"\d+", m.group(2))}
        new = [i for i in ids if i not in have]
        if new:
            src = src[:m.end(2)] + "," + ",".join(map(str, new)) + src[m.end(2):]
            added[arr] += len(new)
        if slot == "body":
            m = re.search(r"(public static int platebody\[\]\s*=\s*\{)([^}]*)\}", src)
            have = {int(x) for x in re.findall(r"\d+", m.group(2))}
            new = [i for i in ids if i not in have]
            if new:
                src = src[:m.end(2)] + "," + ",".join(map(str, new)) + src[m.end(2):]
    write(path, src)
    report["Item4 slot entries added"] = dict(added)


def patch_twohanded(path, slots):
    pass  # godswords already marked two-handed in Item.java; other customs stay one-handed


# ------------------------------------------------------------------ docs
def write_docs(proj, zones, shop_meta, box_shop_id, pool, report, custom, slots, theme, item_text):
    z = ["# Zones", "", "Every teleport in RetroRemake. In game: `::zones` lists categories, `::zones <category>` lists",
         "a category, and `::tp <number>` or `::tp <name>` teleports. Coordinates were checked against the cache map",
         "so you do not land inside a wall, but the zones have not been visited in game yet.", "",
         "| # | Name | Category | Area | x, y, h | Source |", "|---:|---|---|---|---|---|"]
    for q in zones:
        z.append("| %d | %s | %s | %s | %d, %d, %d | %s |" % (q["id"], q["name"], q["cat"], q["area"], q["x"], q["y"], q["h"], q["src"]))
    open(os.path.join(proj, "ZONES.md"), "w").write("\n".join(z) + "\n")
    s = ["# Imported shops", "", "Shopkeepers stand in the Market (`::tp market`). Each one opens the shop below.", "",
         "| Shop id | Name | From | Items |", "|---:|---|---|---:|"]
    s += ["| %d | %s | %s | %d |" % m for m in shop_meta]
    s += ["| %d | Mystery Box Store | RetroRemake | 1 |" % box_shop_id]
    open(os.path.join(proj, "SHOPS.md"), "w").write("\n".join(s) + "\n")
    b = ["# Mystery box", "", "Custom items that are not sold in a shop or dropped by an NPC. Open a Mystery box (item 6199)",
         "to get one. Higher weight means more common.", "", "| ID | Item | Weight |", "|---:|---|---:|"]
    b += ["| %d | %s | %d |" % (i, n, w) for i, n, w in pool]
    open(os.path.join(proj, "MYSTERY_BOX.md"), "w").write("\n".join(b) + "\n")
    cfg = mc.load_cfg(os.path.join(proj, "server", "item.cfg"))
    c = ["# Custom items", "", "All %d custom items. Tier and slot are assigned by `tools/build_world.py` from the item name." % len(custom),
         "", "| ID | Name | Tier | Slot | Attack/Def/Str summary |", "|---:|---|---|---|---|"]
    for i, n in sorted(custom.items()):
        parts = re.split(r"\t+", cfg.get(i, ""))
        bon = [int(x) for x in parts[-12:]] if len(parts) >= 15 else [0] * 12
        c.append("| %d | %s | %s | %s | att %d / def %d / str %d |" % (i, n.replace("|", "/"), item_tier(n, theme), slots.get(i, "-"),
                                                                         max(bon[0:5]), max(bon[5:10]), bon[10]))
    open(os.path.join(proj, "CUSTOM_ITEMS.md"), "w").write("\n".join(c) + "\n")
    open(os.path.join(proj, "BUILD_REPORT.json"), "w").write(json.dumps(report, indent=1, default=str))


if __name__ == "__main__":
    main(sys.argv[1])
