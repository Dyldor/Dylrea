"""RetroRemake v4 progression. Runs after build_world.py (replaces progression.py).

Builds a custom-only progression path:
- 8 tiers; each has 4 monster types, 2 guardians and a boss, all with newly generated models
  (per-face two-tone "bands" or rainbow gradients on the base meshes), plus 4 event bosses and 2 home NPCs.
- Each tier has a "bands" item set (melee, ranged and magic armour, cape, amulet, ring, weapons for every
  style) with generated models; tier whips are the servers' own coloured whips.
- Every other custom or imported item is assigned to a tier and a source NPC; cosmetics drop from event
  bosses; utility customs are sold in a shop. Nothing custom is left unobtainable.
- Melee, ranged and magic get the same damage budget per tier (the server uses one max-hit formula for all three).
- Regular monsters stay low HP, so you one-hit them as you outgear them.
- Removes vanilla monster spawns, vanilla teleports (keeps skilling, home, market) and vanilla gear from shops.
Writes the data files RetroContent reads (customnpcs, extradrops, zones, menu, slayer, events, mystery box).
"""
import collections, gzip, json, os, re, shutil, struct, sys, zlib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_world as bw
import merge_customs as mc
import progression as pg
import cache317
from cache317 import (Cache, CacheWriter, World, archive, archive_names, decode_npc, decode_obj, encode_obj,
                      join_defs, name_hash, pack_archive, split_defs, gunzip, recolor_model, Model)

cache317.SUPPORTED_OBJ |= {114, 115}
SHIFT, PI_FIRST, PI_LAST, NPC_FIRST, TABLE = 10000, 7956, 11790, 3852, 14927
RAINBOW = [0, 5, 9, 14, 22, 32, 42, 50, 58]

# ------------------------------------------------------------------------------------------- tiers
T = [
    dict(name="Novice", set="Verdant", bands=[(22, 5), (8, 3)], light=[4, -14], L=40, D=70, DEF=250,
         whip="green whip",
         zones=[(3255, 3285, "Lumbridge Fields"), (3082, 3420, "Barbarian Village")],
         mobs=[("Goblin", "Moss Goblin"), ("Giant rat", "Bog Rat"), ("Skeleton", "Moss Skeleton"), ("Giant spider", "Thorn Spider")],
         guards=[("Hill giant", "Mossjaw the Hill Giant"), ("Ogre", "Thornhide Ogre")],
         boss=("Troll general", "Verdant Troll King")),
    dict(name="Apprentice", set="Jett", bands=[(42, 6), (0, 0)], light=[-6, 34], L=55, D=105, DEF=340,
         whip="blue whip",
         zones=[(3082, 3420, "Barbarian Village"), (2960, 3500, "Goblin Village")],
         mobs=[("Ice warrior", "Jett Warrior"), ("Hobgoblin", "Jett Hobgoblin"), ("Ice giant", "Jett Giant"), ("Moss giant", "Jett Brute")],
         guards=[("Ice queen", "Jett Matriarch"), ("Black knight titan", "Jett Titan")],
         boss=("Blue dragon", "Jett Wyrm")),
    dict(name="Adept", set="Tidal", bands=[(32, 6), (42, 5)], light=[12, -22], L=70, D=150, DEF=440,
         whip="white whip",
         zones=[(3100, 9890, "Edgeville Dungeon"), (3115, 9845, "Training Dungeon")],
         mobs=[("Lesser demon", "Tide Imp"), ("Rock lobster", "Reef Crusher"), ("Dagannoth", "Tidal Dagannoth"), ("Blue dragon", "Azure Wyrmling")],
         guards=[("Greater demon", "Abyssal Warden"), ("Dagannoth supreme", "Tide Supreme")],
         boss=("Jungle demon", "Leviathan Demon")),
    dict(name="Toxic", set="Toxic", bands=[(15, 7), (0, 0)], light=[14, -44], L=85, D=205, DEF=550,
         whip="unknown color whip",
         zones=[(3420, 3545, "Slayer Tower Grounds"), (2600, 3150, "Yanille Swamp"), (3180, 3020, "Desert Ruins"), (2480, 3170, "Gnome Swamp")],
         mobs=[("Giant spider", "Venom Spider"), ("Bloodveld", "Toxic Bloodveld"), ("Hobgoblin", "Plague Hobgoblin"), ("Rock lobster", "Sludge Crab")],
         guards=[("Greater demon", "Blight Demon"), ("Troll general", "Rot Troll")],
         boss=("Jungle demon", "Toxic Behemoth")),
    dict(name="Veteran", set="Infernal", bands=[(0, 7), (0, 0)], light=[0, -44], L=99, D=275, DEF=680,
         whip="red whip",
         zones=[(2884, 9800, "Taverley Dungeon"), (2910, 9780, "Taverley Depths")],
         mobs=[("Hellhound", "Infernal Hound"), ("Black demon", "Infernal Demon"), ("Red dragon", "Infernal Drake"), ("Bloodveld", "Infernal Bloodveld")],
         guards=[("Dagannoth prime", "Infernal Prime"), ("Ket-Zek", "Infernal Zek")],
         boss=("King black dragon", "Infernal King")),
    dict(name="Elite", set="Gilded", bands=[(9, 6), (0, 0)], light=[10, 38], L=110, D=360, DEF=820,
         whip="gold whip",
         zones=[(2713, 9564, "Brimhaven Dungeon"), (2580, 9490, "Yanille Dungeon")],
         mobs=[("Gargoyle", "Gilded Gargoyle"), ("Dark beast", "Gold Beast"), ("Abyssal demon", "Gilded Fiend"), ("Iron dragon", "Gilded Drake")],
         guards=[("Skeletal wyvern", "Gilded Wyvern"), ("Kalphite guardian", "Gilded Sentinel")],
         boss=("Steel dragon", "Sunforged Dragon")),
    dict(name="Royal", set="Royal", bands=[(50, 6), (9, 6)], light=[0, 24], L=120, D=460, DEF=970,
         whip="orange whip",
         zones=[(2760, 3480, "Camelot Fields"), (2650, 3300, "Ardougne Market"), (2970, 3340, "Falador Gardens")],
         mobs=[("Ice warrior", "Royal Guard"), ("Lesser demon", "Court Imp"), ("Gargoyle", "Royal Gargoyle"), ("Black dragon", "Royal Drake")],
         guards=[("Black knight titan", "Crown Titan"), ("Ice queen", "The Duchess")],
         boss=("Iron dragon", "Regal Dragon")),
    dict(name="Champion", set="Molten", bands=[(5, 7), (0, 0)], light=[6, -44], L=130, D=580, DEF=1130,
         whip="lava whip",
         zones=[(2445, 5170, "TzHaar Crater"), (2400, 5150, "Fight Pits")],
         mobs=[("Fire giant", "Magma Giant"), ("TzHaar-Ket", "Cinder Guard"), ("TzHaar-Mej", "Ember Mage"), ("Bronze dragon", "Molten Drake")],
         guards=[("Ket-Zek", "Magma Zek"), ("Giant mole", "Molten Burrower")],
         boss=("TzTok-Jad", "Inferno Jad")),
    dict(name="Mythic", set="Void", bands=[(50, 6), (0, 0)], light=[4, -44], L=140, D=720, DEF=1300,
         whip="purple whip",
         zones=[(2272, 4698, "Dragon Lair"), (2271, 4690, "Dragon Lair")],
         mobs=[("Nechryael", "Voidspawn"), ("Abyssal demon", "Umbral Demon"), ("Dark beast", "Nether Beast"), ("Black dragon", "Void Drake")],
         guards=[("Dagannoth rex", "Void Rex"), ("Jungle demon", "Void Fiend")],
         boss=("King black dragon", "Eclipse Dragon")),
    dict(name="Divine", set="Rainbow", bands=None, light=[10, 10], L=150, D=900, DEF=1520,
         whip=None,
         zones=[(3485, 9495, "Kalphite Hive"), (3490, 9510, "Kalphite Hive")],
         mobs=[("Red dragon", "Prism Drake"), ("Black demon", "Spectrum Fiend"), ("Gargoyle", "Chroma Gargoyle"), ("Steel dragon", "Prism Wyrm")],
         guards=[("Dagannoth supreme", "Prism Sentinel"), ("Ket-Zek", "Chroma Zek")],
         boss=("King black dragon", "The Rainbow Dragon")),
]
EVENTS = [
    dict(base="Black knight titan", name="Jett Colossus", scheme=dict(type="bands", colors=[(42, 7), (0, 0)], bands=8, band_light=[0, 40]), cosmetic=r"party ?hat|santa", scale=260),
    dict(base="Jungle demon", name="Pumpkin King", scheme=dict(type="bands", colors=[(5, 7), (0, 0)], bands=6, band_light=[10, -40]), cosmetic=r"h'ween|2008|mask|jester", scale=240),
    dict(base="Ice queen", name="Frostfather", scheme=dict(type="bands", colors=[(32, 4), (0, 0)], bands=5, band_light=[20, 50]), cosmetic=r"santa|candy|bobble|white", scale=240),
    dict(base="Blue dragon", name="Party Wyrm", scheme=dict(type="gradient", hues=RAINBOW, sat=7, light=12), cosmetic=r"party|boater|beret|cavalier|tricorn|headband|halo|car$|briefcase", scale=280),
]
HOME_NPCS = [("Rift Guide", ["Wizard", "Man"], dict(type="gradient", hues=RAINBOW, sat=6, light=8), "teleport"),
             ("Slayer Sage", ["Monk", "Man"], dict(type="bands", colors=[(0, 7), (0, 0)], bands=4, band_light=[0, -40]), "slayer")]

# base items for the generated sets (stock 317 meshes) -- (noun, base id, slot, style, source role)
SET_ITEMS = [
    # Bandos-style melee set (Gandorx-style tiers: same meshes, a different name and colour scheme per tier)
    ("bandos helm", 20350, "head", "melee", "guard"), ("bandos chestplate", 21724, "body", "melee", "boss"),
    ("bandos tassets", 21726, "legs", "melee", "boss"), ("bandos shield", 21283, "shield", "melee", "guard"),
    ("bandos boots", 21728, "feet", "all", "guard"), ("bandos gloves", 7462, "hands", "all", "guard"),
    # ranged and magic sets on the 3rd age meshes
    ("range coif", 20334, "head", "ranged", "guard2"), ("range top", 20330, "body", "ranged", "boss"),
    ("range legs", 20332, "legs", "ranged", "boss"), ("vambraces", 20336, "hands", "ranged", "guard2"),
    ("mage hat", 20342, "head", "magic", "guard2"), ("robe top", 20338, "body", "magic", "boss"),
    ("robe bottom", 20340, "legs", "magic", "boss"),
    ("cape", 1052, "cape", "all", "guard2"), ("amulet", 1704, "amulet", "all", "guard2"), ("ring", 6737, "ring", "all", "guard2"),
    # weapons for every style
    ("whip", 4151, "weapon", "melee", "boss"), ("godsword", 21694, "weapon2h", "melee", "boss"),
    ("bow", 21235, "weapon2h", "ranged", "boss"), ("crossbow", 19185, "weapon", "ranged", "guard2"),
    ("staff", 4675, "weapon2h", "magic", "boss"), ("wand", 6914, "weapon", "magic", "guard2"),
]
DMG_SHARE = {"weapon": 0.45, "weapon2h": 0.60, "head": 0.07, "body": 0.10, "legs": 0.08, "hands": 0.06, "feet": 0.04,
             "amulet": 0.08, "ring": 0.05, "cape": 0.05, "shield": 0.02}
DEF_SHARE = {"head": 0.14, "body": 0.28, "legs": 0.22, "shield": 0.16, "hands": 0.06, "feet": 0.06, "cape": 0.04,
             "amulet": 0.02, "ring": 0.02, "weapon": 0.0, "weapon2h": 0.0}
SOURCE_MULT = {"boss": 1.10, "guard": 1.0, "guard2": 1.0, "mob": 0.95}
WEAPON_TEMPLATE = pg.WEAPON_TEMPLATE
UTILITY_NPC = (r"bank|shop|store|assistant|fishing spot|rod fishing|clerk|tanner|merchant|trader|leprechaun|tool|"
               r"smith$|tutor|guide|gardener|farmer$|^cook$|spinning|apothecary|sawmill|hairdresser|staff of armour")
STYLE_IDX = {"melee": [10], "ranged": [4], "magic": [3], "all": [10, 4, 3]}


def norm(s):
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def scheme_for(tier, kind="item"):
    t = T[tier - 1]
    if t["bands"] is None:
        return dict(type="gradient", hues=RAINBOW, sat=7, light=10)
    if kind == "item":
        return dict(type="duo", colors=t["bands"], band_light=t["light"])
    return dict(type="bands", colors=t["bands"], bands=7, band_light=t["light"])


def vec(style, slot, D, DEF, mult):
    """Bonus vector: equal damage budget per style, same defence for every style."""
    b = [0] * 12
    dmg = D * DMG_SHARE[slot] * mult
    for k in STYLE_IDX[style]:
        b[k] = int(round(dmg if style != "all" else dmg))
    if slot.startswith("weapon"):
        acc = int(round(dmg))
        if style == "melee":
            b[0], b[1], b[2] = acc // 2, acc, acc // 2
    d = DEF * DEF_SHARE[slot] * mult
    for k in (5, 6, 7, 8, 9):
        b[k] = int(round(d))
    if slot == "amulet":
        b[11] = 2 + int(D / 80)
    return b


def main(conf_path):
    C = json.load(open(conf_path))
    proj, base = C["project"], C["base"]
    srv, cli = os.path.join(proj, "server"), os.path.join(proj, "client")
    rep = collections.OrderedDict()

    # 0. pristine cache
    cdir = os.path.join(cli, "cache")
    for f in os.listdir(os.path.join(base, "Client", "cache")):
        if f.startswith("main_file_cache"):
            shutil.copy(os.path.join(base, "Client", "cache", f), os.path.join(cdir, f))
    ours, pi = Cache(cdir), Cache(C["pi_cache"])
    cfg_raw = ours.file(0, 2)
    cfg, order = archive(cfg_raw), archive_names(cfg_raw)
    pcfg = archive(pi.file(0, 2))
    obj = split_defs(cfg[name_hash("obj.dat")], cfg[name_hash("obj.idx")])
    pobj = split_defs(pcfg[name_hash("obj.dat")], pcfg[name_hash("obj.idx")])
    npcs = split_defs(cfg[name_hash("npc.dat")], cfg[name_hash("npc.idx")])
    n_stock = len(obj)
    writer = CacheWriter(cdir)
    model_slots = len(ours.idx[1]) // 6

    # 1. custom items (client hardcoded) -- move any inside the imported id range
    class8_path = os.path.join(cli, "Class8.java")
    class8 = bw.read(class8_path)
    custom = {}
    for i, _, _, body in mc.find_blocks(class8):
        n = mc.block_name(body)
        if n and i not in custom:
            custom[i] = n.strip()
    item_cfg_path = os.path.join(srv, "item.cfg")
    item_text = bw.read(item_cfg_path)
    for old, new in C["item_line_fixes"]:
        # GodzHell's item.cfg defines a few ids twice; fix the stray line (matched by its exact name)
        item_text = re.sub(r"(?m)^item = %s\t%s\t" % (old[0], re.escape(old[1])),
                           ("item = %s\t%s\t" % (new, old[1])) if new else "item = DELETE\t", item_text, count=1)
    item_text = "\n".join(l for l in item_text.split("\n") if not l.startswith("item = DELETE\t"))
    free_ids = [i for i in range(16000, 16999) if i not in custom]
    for i in [i for i in custom if PI_FIRST + SHIFT <= i <= PI_LAST + SHIFT]:
        new = free_ids.pop(0)
        class8 = re.sub(r"if\s*\(\s*i\s*==\s*%d\s*\)" % i, "if(i == %d)" % new, class8)
        item_text = re.sub(r"(?m)^(\s*item\s*=\s*)%d(\s)" % i, r"\g<1>%d\2" % new, item_text)
        custom[new] = custom.pop(i)
    bw.write(class8_path, class8)
    donor_stats = {}
    donor_cfgs = [mc.load_cfg(p) for d in C["classic"] for p in bw.find_files(d, "item.cfg")]
    for i, n in custom.items():
        for dc in donor_cfgs:
            ln = dc.get(i)
            if ln and norm(mc.cfg_name(ln)) == norm(n):
                b = pg.bonuses_of(ln)
                if b and 0 < pg.power(b) < 1500:
                    donor_stats[i] = b; break

    # 2. models: PI extras + loader list ------------------------------------------------------
    have_model = lambda m: m < model_slots and bool(ours.file(1, m))
    pm_idx = open(os.path.join(C["pi_models"], "models.idx"), "rb").read()
    pm_dat = open(os.path.join(C["pi_models"], "models.dat"), "rb").read()
    off, added = 0, set()
    for k in range(struct.unpack(">i", pm_idx[:4])[0]):
        mid, ln = struct.unpack(">ii", pm_idx[4 + 8 * k: 12 + 8 * k])
        raw = pm_dat[off:off + ln]; off += ln
        if raw[-2:] == b"\xff\xff" or have_model(mid):
            continue
        writer.put(1, mid, gzip.compress(raw, 9) + b"\x00\x01")
        added.add(mid)
    high = {m for m in range(TABLE, model_slots) if ours.file(1, m)} | {m for m in added if m >= TABLE}
    loadable = lambda m: m == 65535 or (m < TABLE and have_model(m)) or m in high or m in added
    pi_models = {}
    off = 0
    for k in range(struct.unpack(">i", pm_idx[:4])[0]):
        mid, ln = struct.unpack(">ii", pm_idx[4 + 8 * k: 12 + 8 * k])
        pi_models[mid] = pm_dat[off:off + ln]; off += ln

    def model_bytes(m):
        if m < model_slots and ours.file(1, m):
            return gunzip(ours.file(1, m))
        return pi_models.get(m)

    next_model = [max([model_slots] + list(added)) + 10]
    generated_models = {}

    def gen_model(m, scheme):
        key = (m, json.dumps(scheme, sort_keys=True))
        if key in generated_models:
            return generated_models[key]
        data = model_bytes(m)
        new = recolor_model(data, scheme)
        Model(new)  # must still decode
        mid = next_model[0]; next_model[0] += 1
        writer.put(1, mid, gzip.compress(new, 9) + b"\x00\x01")
        high.add(mid)
        generated_models[key] = mid
        return mid

    def def_models(d):
        out = []
        for op in (1, 23, 24, 25, 26, 78, 79, 90, 91, 92, 93):
            v = d.get(op)
            if v is not None:
                m = v[0] if isinstance(v, tuple) else v
                if m != 65535:
                    out.append(m)
        return out

    def remodel_obj(ops, scheme):
        out = []
        for op, v in ops:
            if op in (1, 24, 26, 78, 79, 90, 91, 92, 93) and v != 65535:
                v = gen_model(v, scheme)
            elif op in (23, 25) and v[0] != 65535:
                v = (gen_model(v[0], scheme), v[1])
            out.append((op, v))
        return out

    # 3. PI items at id + SHIFT ------------------------------------------------------------------
    def remap(v):
        return v + SHIFT if PI_FIRST <= v <= PI_LAST else v
    rm = {97: remap, 98: remap}
    for op in range(100, 110):
        rm[op] = lambda v: (remap(v[0]), v[1])
    new_obj = list(obj) + [b"\x00"] * (PI_FIRST + SHIFT - n_stock)
    pi_names = {}
    for pid in range(PI_FIRST, PI_LAST + 1):
        ops = decode_obj(pobj[pid])
        new_obj.append(encode_obj(ops, rm))
        d = dict(ops)
        if d.get(2):
            pi_names[pid + SHIFT] = (d[2], d)
    pi_cfg = mc.load_cfg(C["pi_item_cfg"])
    stock_cfg = mc.load_cfg(item_cfg_path)
    custom_norm = {norm(n) for n in custom.values()}
    stock_norm = {norm(mc.cfg_name(l)) for l in stock_cfg.values() if mc.cfg_name(l)}
    imported, seen = {}, set()
    for iid, (nm, d) in sorted(pi_names.items()):
        key = norm(nm)
        wearable = 23 in d or 25 in d
        if not wearable or 97 in d or key in seen or key in custom_norm or key in stock_norm:
            continue
        if re.search(pg.JUNK, nm.lower()) or bw.item_slot(nm) is None or re.search(C["import_exclude"], nm.lower()):
            continue
        if not all(loadable(m) for m in def_models(d)):
            continue
        seen.add(key)
        imported[iid] = nm
    rep["imported 2007-08 items"] = len(imported)

    # 4. generated band sets -------------------------------------------------------------------
    while len(new_obj) < 21800:
        new_obj.append(b"\x00")
    gen = {}       # id -> dict(name, tier, slot, style, role)
    whips = {norm(n): i for i, n in custom.items() if "whip" in n.lower()}
    tier_whip = {}
    for t, tt in enumerate(T, 1):
        sch = scheme_for(t)
        for noun, src, slot, style, role in SET_ITEMS:
            if noun == "whip" and tt["whip"] and norm(tt["whip"]) in whips:
                tier_whip[t] = whips[norm(tt["whip"])]
                continue
            if tt["set"] == "Rainbow" and noun == "bandos helm":
                name = "Rainbow full helm"
            else:
                name = "%s %s" % (tt["set"], noun)
            ops = decode_obj(new_obj[src])
            d = dict(ops)
            if not all(loadable(m) for m in def_models(d)):
                rep.setdefault("set items skipped (base models missing)", []).append(name); continue
            ops = [(op, v) for op, v in ops if op not in (2, 3, 40, 97, 98) and not (100 <= op < 110)]
            ops = remodel_obj(ops, sch)
            ops[:0] = [(2, name), (3, "%s gear of the %s tier." % (tt["set"], tt["name"]))]
            gid = len(new_obj)
            new_obj.append(encode_obj(ops))
            gen[gid] = dict(name=name, tier=t, slot=slot, style=style, role=role)
    # specials (jackpot/event weapons from earlier builds)
    for sp in C["special_items"]:
        src = sp.get("from") or next((i for i, (n, _) in pi_names.items() if norm(n) == norm(sp.get("from_name", ""))), None)
        if src is None:
            continue
        ops = decode_obj(new_obj[src])
        if not all(loadable(m) for m in def_models(dict(ops))):
            continue
        sch = sp["scheme"]
        ops = [(op, v) for op, v in ops if op not in (2, 3, 40, 97, 98) and not (100 <= op < 110)]
        ops = remodel_obj(ops, sch)
        ops[:0] = [(2, sp["name"]), (3, sp["examine"])]
        gid = len(new_obj)
        new_obj.append(encode_obj(ops))
        gen[gid] = dict(name=sp["name"], tier=sp["tier"], slot=sp["slot"], style=sp["style"], role="boss", special=True)
    rep["generated items"] = len(gen)

    # 5. NPCs with generated models --------------------------------------------------------------
    by_name = {}
    for i, e in enumerate(npcs):
        dd = decode_npc(e)
        if dd.get("name") and dd.get("models"):
            by_name.setdefault(dd["name"].lower(), (i, dd))

    def make_npc(base_names, name, scheme, combat, scale, actions, examine):
        if isinstance(base_names, str):
            base_names = [base_names]
        hit = next((by_name[b.lower()] for b in base_names if b.lower() in by_name), None)
        if not hit:
            raise SystemExit("no base npc among " + str(base_names))
        bid, bd = hit
        nd = dict(bd)
        nd["models"] = [gen_model(m, scheme) for m in bd["models"]]
        if bd.get("heads"):
            nd["heads"] = [gen_model(m, scheme) for m in bd["heads"]]
        nd.pop("recolor", None)
        nd.update(name=name, examine=examine, combat=min(999, combat), scaleXZ=scale, scaleY=scale,
                  size=max(1, min(8, int(round((bd.get("size") or 1) * scale / 128.0)))), actions=actions)
        nid = len(npcs)
        if nid > 4095:
            raise SystemExit("npc ids exhausted")
        npcs.append(pg.encode_npc(nd))
        return nid, bid

    roster = []   # dict(id, base, name, tier, role, hp, maxhit, combat)
    D_prev = C["starting_damage"]
    DEF_prev = C["starting_def"]
    for t, tt in enumerate(T, 1):
        arrive = (D_prev + tt["L"]) / 6.76
        red = (1.0 + DEF_prev / 1500.0) / 0.6
        sch = scheme_for(t, "npc")
        entries = [(b, n, "mob", int(round(arrive * 1.5)), int(round((3 + t) * 2 * red)), 128) for b, n in tt["mobs"]]
        entries += [(b, n, "guardian", int(round(arrive * 10)), int(round((6 + t) * 2 * red)), 150) for b, n in tt["guards"]]
        b, n = tt["boss"]
        entries.append((b, n, "boss", int(round(arrive * 25)), int(round((8 + 1.5 * t) * 2 * red)), 170 + 14 * t))
        for b, n, role, hp, mx, scale in entries:
            cb = int(round(hp / 4.0 + mx * 3))
            nid, bid = make_npc(b, n, sch, cb, scale, {1: "Attack"}, "%s of the %s tier." % (role.capitalize(), tt["name"]))
            roster.append(dict(id=nid, base=bid, name=n, tier=t, role=role, hp=hp, maxhit=mx, combat=cb))
        D_prev, DEF_prev = tt["D"], tt["DEF"]
    for ev in EVENTS:
        nid, bid = make_npc(ev["base"], ev["name"], ev["scheme"], 600, ev["scale"], {1: "Attack"}, "An event boss.")
        roster.append(dict(id=nid, base=bid, name=ev["name"], tier=99, role="event", hp=C["event_hp"],
                           maxhit=int(round(22 * 2 * (1 + T[-2]["DEF"] / 600.0))), combat=600, cosmetic=ev["cosmetic"]))
    for name, bases, sch, role in HOME_NPCS:
        nid, bid = make_npc(bases, name, sch, 0, 128, {0: "Talk-to"}, "Here to help.")
        roster.append(dict(id=nid, base=bid, name=name, tier=0, role=role, hp=100, maxhit=0, combat=0))
    rep["custom NPCs"] = len(roster)

    # 6. write config archive + loader list
    cfg[name_hash("obj.dat")], cfg[name_hash("obj.idx")] = join_defs(new_obj)
    cfg[name_hash("npc.dat")], cfg[name_hash("npc.idx")] = join_defs(npcs)
    writer.put(0, 2, pack_archive([(h, cfg[h]) for h in order]))
    chk = archive(Cache(cdir).file(0, 2))
    assert split_defs(chk[name_hash("obj.dat")], chk[name_hash("obj.idx")]) == new_obj
    assert split_defs(chk[name_hash("npc.dat")], chk[name_hash("npc.idx")]) == npcs
    hs = sorted(high)
    open(os.path.join(cli, "RetroModels.java"), "w").write(
        "/** Generated by tools/progression4.py: model ids above the cache's original model table that the client may load. */\n"
        "final class RetroModels {\n\tstatic final int MAX = %d;\n\tstatic final int[] IDS = {%s};\n}\n" % (max(hs), ",".join(map(str, hs))))
    rep["generated models"] = len(generated_models)
    rep["cache items"], rep["cache npcs"] = len(new_obj), len(npcs)

    # 7. tier every custom/imported item ----------------------------------------------------------
    names = dict(custom); names.update(imported); names.update({i: g["name"] for i, g in gen.items()})
    theme = C["theme"]
    tier_of, slot_of, style_of, role_of = {}, {}, {}, {}
    utility = []
    skill_rx = re.compile(r"^(%s)\.? ?(cape|cape\(t\)|hood)$" % "|".join(pg.SKILLS))
    rune_power = {s: pg.power(v) for s, v in theme["ref"].items()}
    for i, n in names.items():
        low = n.lower()
        if i in gen:
            g = gen[i]
            tier_of[i], slot_of[i], style_of[i], role_of[i] = g["tier"], g["slot"], g["style"], g["role"]
            continue
        if bw.item_tier(n, theme) == "utility":
            utility.append(i); continue
        if re.search(C["custom_exclude"], low):
            continue
        s = bw.item_slot(n)
        if s is None:
            continue
        if s == "weapon" and re.search(pg.TWO_HANDED, low):
            s = "weapon2h"
        slot_of[i] = s
        ws = bw.weapon_style(n) if s.startswith("weapon") else None
        style_of[i] = {"ranged": "ranged", "magic": "magic"}.get(ws, "melee") if ws else (
            "ranged" if re.search(r"coif|d'hide|chaps|vamb|bracers|range|ranger", low) else
            "magic" if re.search(r"robe|mystic|infinity|lunar|wizard|mage|hood|hat$|splitbark|skeletal|enchanted", low) else
            "all" if s in ("cape", "amulet", "ring", "feet", "hands") else "melee")
        for k, w in sorted(tier_whip.items()):
            if w == i:
                tier_of[i] = k
        if i in tier_of:
            role_of[i] = "boss"; continue
        m = skill_rx.match(low.replace("woodcut.", "woodcut").replace("construct.", "construct"))
        if m:
            tier_of[i] = 2 + (pg.SKILLS.index(m.group(1)) % 6)
        elif bw.item_tier(n, theme) == "cosmetic" or re.search(C["cosmetic_regex"], low):
            if i in imported:
                continue          # imported cosmetics are vanilla-looking; custom cosmetics only
            tier_of[i] = "cosmetic"
        else:
            forced = next((t for rx, t in C["tier_overrides"] if re.search(rx, low)), None)
            if forced:
                tier_of[i] = forced
            elif i in custom:
                tier_of[i] = {"t1": 1, "t2": 2, "t3": 3, "t4": 5, "t5": 8, "staff": len(T)}.get(bw.item_tier(n, theme), 3)
            else:
                b = pg.bonuses_of(pi_cfg[i - SHIFT]) if (i - SHIFT) in pi_cfg else None
                ref = rune_power[bw.weapon_style(n) if s.startswith("weapon") else s.replace("weapon2h", "weapon")] if not s.startswith("weapon") else rune_power[bw.weapon_style(n)]
                r = pg.power(b) / float(ref or 1) if b else 0
                if r <= 0.05:
                    continue
                tier_of[i] = 1 if r < 0.5 else 2 if r < 0.8 else 3 if r < 1.1 else 5 if r < 1.4 else 6 if r < 1.8 else 7
        role_of[i] = "boss" if s in ("body", "legs", "weapon", "weapon2h") else ("guard" if s in ("head", "shield", "feet", "hands") else "guard2")
    tiers = collections.defaultdict(list)
    for i, t in tier_of.items():
        tiers[t].append(i)
    rep["items per tier"] = {str(k): len(v) for k, v in sorted(tiers.items(), key=lambda kv: str(kv[0]))}

    # 8. stats: same budget per style; customs keep their own stat mix ---------------------------
    stats = {}
    for i, t in tier_of.items():
        s, st = slot_of[i], style_of[i]
        if t == "cosmetic":
            # rare and overpowered: above tier 8, and armour pieces boost every combat style
            cs = "melee" if s.startswith("weapon") else "all"
            v = vec(cs, s, T[-1]["D"] * C["cosmetic_power"], T[-1]["DEF"] * C["cosmetic_power"], 1.0)
        else:
            mult = SOURCE_MULT[role_of[i]] * (1.0 + ((i * 2654435761) % 11 - 5) / 100.0 if i not in gen else 1.0)
            v = vec(st, s, T[t - 1]["D"], T[t - 1]["DEF"], mult)
            shape = donor_stats.get(i) or (pg.bonuses_of(pi_cfg[i - SHIFT]) if (i - SHIFT) in pi_cfg else None)
            if shape and pg.power(shape) > 0 and i not in gen:
                v = pg.scale_vec(shape, pg.power(v))
                # keep the damage stat of its style at least at the set level
                ref = vec(st, s, T[t - 1]["D"], T[t - 1]["DEF"], mult)
                for k in STYLE_IDX[st]:
                    v[k] = max(v[k], ref[k])
        stats[i] = v

    # 9. item.cfg ---------------------------------------------------------------------------------
    TV = C["tier_value"]
    lines = item_text.split("\n")
    at = {}
    for k, l in enumerate(lines):
        m = re.match(r"\s*item\s*=\s*(\d+)\s", l)
        if m:
            at[int(m.group(1))] = k
    out_new = []
    for i in sorted(set(tier_of) | set(utility)):
        t = tier_of.get(i)
        val = TV[str(t)] if t is not None else 2000
        nm = names[i].replace(" ", "_")
        ex = ("%s_(cosmetic)." % nm) if t == "cosmetic" else ("%s_(Tier_%d_%s)." % (nm, t, T[t - 1]["name"]) if t else nm + ".")
        b = stats.get(i, [0] * 12)
        line = "item = %d\t%s\t%s\t%d\t%d\t%d\t%s" % (i, nm, ex, val, val * 4 // 10, val * 6 // 10, "\t".join(map(str, b)))
        if i in at:
            lines[at[i]] = line
        else:
            out_new.append(line)
    item_text = "\n".join(lines)
    end = item_text.rindex("[ENDOFITEMLIST]")
    item_text = item_text[:end].rstrip("\n") + "\n" + "\n".join(out_new) + "\n" + item_text[end:]
    item_text = re.sub(r"(?m)^(item = %d\t[^\t]+\t[^\t]+\t)[^\t]+\t[^\t]+\t[^\t]+" % C["mystery_box_item"],
                       lambda m: m.group(1) + "%d\t%d\t%d" % (C["mystery_box_price"], C["mystery_box_price"] * 4 // 10, C["mystery_box_price"] * 6 // 10), item_text)
    bw.write(item_cfg_path, item_text)

    # 10. slots, two-handed, weapon animation templates
    eq = {i: ("weapon" if s.startswith("weapon") else s) for i, s in slot_of.items() if i in tier_of}
    bw.patch_item4(os.path.join(srv, "Item4.java"), eq, rep)
    ij = bw.read(os.path.join(srv, "Item.java")).replace("new boolean[20000]", "new boolean[32768]")
    two = sorted(i for i in tier_of if slot_of[i] == "weapon2h")
    if "// RetroRemake two-handed" not in ij:
        ij = ij.replace("itemTwoHanded[15336] = true;", "itemTwoHanded[15336] = true;\n// RetroRemake two-handed\n" +
                        "\n".join("itemTwoHanded[%d] = true;" % i for i in two), 1)
    bw.write(os.path.join(srv, "Item.java"), ij)
    wl = ["// weapon = itemId<TAB>templateItemId"]
    for i in sorted(tier_of):
        if not slot_of[i].startswith("weapon"):
            continue
        low = names[i].lower()
        tpl = next((tp for rx, tp in WEAPON_TEMPLATE if re.search(rx, low)), None)
        if tpl is None:
            tpl = {"ranged": 861, "magic": 4675}.get(style_of[i], 4587 if slot_of[i] == "weapon" else 7158)
        wl.append("weapon = %d\t%d\t// %s" % (i, tpl, names[i]))
    bw.write(os.path.join(srv, "weapons.cfg"), "\n".join(wl) + "\n")

    # 11. zones + spawns: remove vanilla, lay out tier areas ------------------------------------
    world = World(cdir)
    npc_cfg_text = bw.read(os.path.join(srv, "npc.cfg"))
    npc_names = {int(m.group(1)): m.group(2).replace("_", " ") for m in re.finditer(r"(?m)^npc\s*=\s*(\d+)\s+(\S+)", npc_cfg_text)}
    sp_lines = [l for l in bw.read(os.path.join(srv, "autospawn.cfg")).split("\n") if l.strip().startswith("spawn")]
    kept, dropped = [], 0
    for l in sp_lines:
        v = bw.ints(re.split(r"\s+", l.split("=", 1)[1].strip()), 4)
        if not v:
            continue
        if "// Market" in l or re.search(UTILITY_NPC, npc_names.get(v[0], "").lower()):
            kept.append(l)
        else:
            dropped += 1
    rep["vanilla spawns removed"] = dropped
    used = []
    areas = []
    for t, tt in enumerate(T, 1):
        pick = None
        for cx, cy, label in tt["zones"]:
            if any(abs(cx - ux) < 40 and abs(cy - uy) < 40 for ux, uy in used):
                continue
            free = [(x, y) for x in range(cx - 14, cx + 15) for y in range(cy - 14, cy + 15) if world.free(x, y)]
            if len(free) >= 160:
                pick = (cx, cy, label, free); break
        if not pick:
            raise SystemExit("no area for tier %d" % t)
        used.append(pick[:2]); areas.append(pick)
    ev_area = None
    for cx, cy, label in C["event_areas"]:
        free = [(x, y) for x in range(cx - 10, cx + 11) for y in range(cy - 10, cy + 11) if world.free(x, y)]
        if len(free) >= 100 and not any(abs(cx - ux) < 40 and abs(cy - uy) < 40 for ux, uy in used):
            ev_area = (cx, cy, label, free); break
    if not ev_area:
        raise SystemExit("no event area")
    new_spawns, menu = [], []
    # every NPC that stays keeps its tile: new spawns may not land on one
    taken = set()
    for l in kept:
        v = bw.ints(re.split(r"\s+", l.split("=", 1)[1].strip()), 3)
        if v:
            taken.add((v[1], v[2]))

    def near(free, ax, ay, rmin=0, rmax=3, gap=2):
        cands = sorted(free, key=lambda p: (p[0] - ax) ** 2 + (p[1] - ay) ** 2)
        for p in cands:
            d2 = (p[0] - ax) ** 2 + (p[1] - ay) ** 2
            if rmin * rmin <= d2 <= rmax * rmax and p not in taken and all(abs(p[0] - q[0]) + abs(p[1] - q[1]) >= gap for q in taken):
                taken.add(p); return p
        return None
    import math
    for t, (cx, cy, label, free) in enumerate(areas, 1):
        group = [r for r in roster if r["tier"] == t]
        anchors = {"boss": (cx, cy)}
        gi = mi = 0
        for r in group:
            if r["role"] == "guardian":
                ang = math.pi * (0.25 + gi); gi += 1
                anchors[r["id"]] = (cx + int(6 * math.cos(ang)), cy + int(6 * math.sin(ang)))
            elif r["role"] == "mob":
                ang = math.pi * (0.75 + 0.5 * mi); mi += 1
                anchors[r["id"]] = (cx + int(10 * math.cos(ang)), cy + int(10 * math.sin(ang)))
        for r in group:
            ax, ay = anchors["boss"] if r["role"] == "boss" else anchors[r["id"]]
            n = C["mobs_per_group"] if r["role"] == "mob" else 1
            placed = []
            for _ in range(n):
                p = None
                for rmax in ((4, 7, 10, 14) if r["role"] == "mob" else (2, 4, 7, 10)):
                    p = near(free, ax, ay, 0, rmax) or near(free, ax, ay, 0, rmax, 1)
                    if p:
                        break
                if p:
                    placed.append(p)
            if not placed:
                raise SystemExit("could not place %s" % r["name"])
            rng = 3 if r["role"] == "mob" else 2
            for x, y in placed:
                new_spawns.append("spawn = %d\t%d\t%d\t0\t%d\t%d\t%d\t%d\t2\t// T%d %s" % (r["id"], x, y, x + rng, y + rng, x - rng, y - rng, t, r["name"]))
            tp = near(free, placed[0][0], placed[0][1], 2, 5, 1) or placed[0]
            r["tele"] = tp
            menu.append((t, r["role"], r["name"], tp))
    # event + home
    ecx, ecy, elabel, efree = ev_area
    etele = near(efree, ecx, ecy, 4, 8, 1)
    hx, hy = C["home"]
    home_free = [(x, y) for x in range(hx - 6, hx + 7) for y in range(hy - 6, hy + 7) if world.free(x, y)]
    home_spots = {}
    for r in roster:
        if r["tier"] == 0:
            p = near(home_free, hx, hy, 2, 6)
            if not p:
                raise SystemExit("no room for %s at home" % r["name"])
            new_spawns.append("spawn = %d\t%d\t%d\t0\t%d\t%d\t%d\t%d\t2\t// %s" % (r["id"], p[0], p[1], p[0], p[1], p[0], p[1], r["name"]))
            home_spots[r["role"]] = p
    def near_area(x, y):
        return any(abs(x - cx) <= 16 and abs(y - cy) <= 16 for cx, cy, _, _ in areas) or (abs(x - ecx) <= 12 and abs(y - ecy) <= 12)
    clean, tiles, clash = [], set(), 0
    for l in kept + new_spawns:
        v = bw.ints(re.split(r"\s+", l.split("=", 1)[1].strip()), 4)
        custom_line = v[0] >= NPC_FIRST
        if (not custom_line and near_area(v[1], v[2])) or (v[1], v[2], v[3]) in tiles:
            clash += 1; continue
        tiles.add((v[1], v[2], v[3]))
        clean.append(l)
    rep["spawn clashes removed"] = clash
    kept, new_spawns = [l for l in clean if l in kept], [l for l in clean if l in new_spawns]
    sp_text = "\n".join(kept + new_spawns) + "\n[ENDOFSPAWNLIST]\n"
    bw.write(os.path.join(srv, "autospawn.cfg"), sp_text)
    rep["spawns"] = len(kept) + len(new_spawns)

    # zones.cfg: progression entries in order, then event, skilling, home/market
    zrows = [l.split("=", 1)[1].strip().split("\t") for l in bw.read(os.path.join(srv, "zones.cfg")).split("\n") if l.startswith("zone")]
    out = ["// zone = id<TAB>category<TAB>x<TAB>y<TAB>height<TAB>name  (generated by build_world.py + progression4.py)"]
    zid = 1
    ROLE_ORDER = {"mob": 0, "guardian": 1, "boss": 2}
    for t in range(1, len(T) + 1):
        for tt, role, nm, (x, y) in sorted([m for m in menu if m[0] == t], key=lambda m: ROLE_ORDER[m[1]]):
            label = {"mob": "", "guardian": " (guardian)", "boss": " (BOSS)"}[role]
            out.append("zone = %d\tTier %d\t%d\t%d\t0\tT%d %s%s" % (zid, t, x, y, t, nm, label)); zid += 1
    out.append("zone = %d\tEvent\t%d\t%d\t0\tEvent arena (%s)" % (zid, etele[0], etele[1], elabel)); zid += 1
    seen_skill = set()
    for z in zrows:
        if z[1] == "Skilling" or z[5].split(" (")[0] in ("Home", "Market"):
            if z[5].startswith("Market (") or z[5].startswith("Home ("):
                continue
            base_name = z[5].split(" (")[0].strip().lower()
            if base_name in seen_skill or near_area(int(z[2]), int(z[3])) or z[5].startswith("Hidden area"):
                continue
            seen_skill.add(base_name)
            out.append("zone = %d\t%s\t%s" % (zid, "Skilling" if z[1] == "Skilling" else "Home", "\t".join(z[2:]))); zid += 1
    bw.write(os.path.join(srv, "zones.cfg"), "\n".join(out) + "\n")
    rep["zones"] = zid - 1

    # 12. shops: strip vanilla gear, add tablets shop + starter + box store ----------------------
    shops_text = bw.read(os.path.join(srv, "shops.cfg"))
    sl, removed_items, dropped_shops = [], 0, []
    for l in shops_text.split("\n"):
        if not l.startswith("shop"):
            sl.append(l); continue
        p = l.split("=", 1)[1].strip().split("\t")
        p = [x for x in p if x != ""]
        sid, head, items = int(p[0]), p[:4], p[4:]
        keep = []
        for a, b in zip(items[0::2], items[1::2]):
            it = int(a)
            nm = names.get(it) or (mc.cfg_name(stock_cfg[it]) if it in stock_cfg else "")
            if it not in tier_of and it != C["mystery_box_item"] and bw.item_slot(nm or "") is not None and it < PI_FIRST:
                removed_items += 1; continue
            keep.append((a, b))
        if len(keep) < 2 and sid > 20 and not any(int(a) == C["mystery_box_item"] for a, _ in keep):
            dropped_shops.append(sid); continue
        if len(keep) < 2:
            # a GodzHell shopkeeper opens this shop by NPC type, so it must not end up empty
            low = head[1].lower()
            fill = C["refill_shops"].get(next((k for k in C["refill_shops"] if k in low), "default"))
            if fill == "tier1":
                fill_ids = [i for i in sorted(tiers[1]) if i in gen][:38]
            elif fill == "tablets":
                fill_ids = [C["mystery_box_item"]] + sorted(utility)
            else:
                fill_ids = fill
            keep = [(str(i), "100") for i in fill_ids]
            rep.setdefault("emptied GodzHell shops refilled", []).append(head[1])
        sl.append("shop = %s\t%s" % ("\t".join(head), "\t".join("%s\t%s" % kv for kv in keep)))
    sid_next = max(int(re.match(r"shop = (\d+)", l).group(1)) for l in sl if l.startswith("shop")) + 1
    starter = [i for i in sorted(tiers[1]) if i in gen]
    tabs = sorted(utility)
    extra_shops = [("Novice_Outfitter", starter), ("Rainbow_Tablets", tabs)]
    shop_ids = {}
    endmark = "[ENDOFSHOPLIST]"
    body = [l for l in sl if l.strip() != endmark]
    for nm, its in extra_shops:
        if its:
            body.append("shop = %d\t%s\t1\t1\t%s" % (sid_next, nm, "\t".join("%d\t50" % i for i in its[:40])))
            shop_ids[nm] = sid_next; sid_next += 1
    body.append(endmark)
    bw.write(os.path.join(srv, "shops.cfg"), "\n".join(body) + "\n")
    rep["vanilla gear removed from shops"] = removed_items
    rep["shops dropped (nothing left)"] = len(dropped_shops)
    sn = [l for l in bw.read(os.path.join(srv, "shopnpcs.cfg")).split("\n") if l.strip()]
    sn2 = []
    for l in sn:
        if l.startswith("shopnpc"):
            p = l.split("=", 1)[1].strip().split("\t")
            if int(p[3]) in dropped_shops:
                # also remove that keeper's spawn
                sp_text = re.sub(r"(?m)^spawn = \d+\t%s\t%s\t0\t.*// Market\n" % (p[0], p[1]), "", sp_text)
                continue
        sn2.append(l)
    for nm, sid in shop_ids.items():
        p = near(home_free, hx, hy, 2, 6)
        if p:
            sn2.append("shopnpc = %d\t%d\t0\t%d\t%s" % (p[0], p[1], sid, nm))
            sp_text = sp_text.replace("[ENDOFSPAWNLIST]", "spawn = 528\t%d\t%d\t0\t%d\t%d\t%d\t%d\t2\t// %s\n[ENDOFSPAWNLIST]" % (p[0], p[1], p[0], p[1], p[0], p[1], nm))
    bw.write(os.path.join(srv, "shopnpcs.cfg"), "\n".join(sn2) + "\n")
    bw.write(os.path.join(srv, "autospawn.cfg"), sp_text)

    # 13. npc.cfg + customnpcs.cfg + home npc roles
    nt = re.sub(r"(?m)^npc = (%s)\t.*\n" % "|".join(str(r["id"]) for r in roster), "", npc_cfg_text)
    add = ["npc = %d\t%s\t%d\t%d" % (r["id"], r["name"].replace(" ", "_"), r["combat"], r["hp"]) for r in roster]
    end = nt.rindex("[ENDOFNPCLIST]") if "[ENDOFNPCLIST]" in nt else len(nt)
    bw.write(os.path.join(srv, "npc.cfg"), nt[:end].rstrip("\n") + "\n" + "\n".join(add) + "\n" + nt[end:])
    cl = ["// customnpc = id<TAB>baseNpc<TAB>hp<TAB>maxHit<TAB>tier<TAB>role<TAB>name"]
    cl += ["customnpc = %d\t%d\t%d\t%d\t%d\t%s\t%s" % (r["id"], r["base"], r["hp"], r["maxhit"], r["tier"], r["role"], r["name"]) for r in roster]
    cl += ["eventarea = %d\t%d\t0\t%s" % (ecx, ecy, elabel)]
    cl += ["tiername = %d\t%s\t%s" % (k, tt["name"], tt["set"]) for k, tt in enumerate(T, 1)]
    cl += ["tierstat = %d\t%d\t%d\t%d" % (k, tt["D"], tt["DEF"], tt["L"]) for k, tt in enumerate(T, 1)]
    bw.write(os.path.join(srv, "customnpcs.cfg"), "\n".join(cl) + "\n")

    # 14. drops ------------------------------------------------------------------------------------
    D = C["drops"]
    box = C["mystery_box_item"]
    pool = lambda ids: ",".join("%d:1" % i for i in sorted(ids))
    dl = ["// table = npcId<TAB>chance(1 in N)<TAB>item:amount,...   one entry is picked when the roll hits",
          "// global = minCombat<TAB>chance<TAB>item:amount"]
    bones = {t: (526 if t <= 2 else 532 if t <= 4 else 536) for t in range(1, len(T) + 1)}
    events = [r for r in roster if r["role"] == "event"]
    ev_cos = {r["id"]: [i for i in tiers["cosmetic"] if re.search(r["cosmetic"], names[i].lower())] for r in events}
    claimed = set(i for v in ev_cos.values() for i in v)
    for k, i in enumerate(sorted(i for i in tiers["cosmetic"] if i not in claimed)):
        ev_cos[events[k % len(events)]["id"]].append(i)
    for r in roster:
        t, role, nid = r["tier"], r["role"], r["id"]
        if t == 0:
            continue
        if role == "event":
            cos = ev_cos[nid]
            hi = [i for k in range(len(T) - 2, len(T) + 1) for i in tiers.get(k, [])]
            dl.append("table = %d\t1\t%d:2\t// %s: mystery boxes" % (nid, box, r["name"]))
            dl.append("table = %d\t%d\t%s\t// cosmetics (rare, overpowered)" % (nid, D["event_cosmetic"], pool(cos)))
            dl.append("table = %d\t3\t%s\t// tier 6-8 gear" % (nid, pool(hi)))
            dl.append("table = %d\t1\t995:%d" % (nid, 250000))
            continue
        ids = tiers.get(t, [])
        mine = [i for i in ids if role_of.get(i) == ("boss" if role == "boss" else role_of.get(i))]
        up2 = [i for i in (tiers.get(t + 2, []) or tiers.get(len(T), [])) if i not in imported]
        up3 = [i for i in (tiers.get(t + 3, []) or tiers.get(len(T), [])) if i not in imported]
        dl.append("table = %d\t1\t995:%d\t// %s" % (nid, max(20, r["hp"] * (6 if role == "boss" else 2)), r["name"]))
        dl.append("table = %d\t1\t%d:1" % (nid, bones[t]))
        if role == "boss":
            mine = [i for i in ids if role_of.get(i) == "boss" and i not in imported]
            dl.append("table = %d\t%d\t%s\t// tier %d boss gear" % (nid, D["boss_gear"], pool(mine), t))
            dl.append("table = %d\t%d\t%s\t// jackpot tier %d" % (nid, D["boss_jackpot2"], pool(up2), min(len(T), t + 2)))
            dl.append("table = %d\t%d\t%s\t// jackpot tier %d" % (nid, D["boss_jackpot3"], pool(up3), min(len(T), t + 3)))
            dl.append("table = %d\t%d\t%d:1" % (nid, D["boss_box"], box))
        elif role == "guardian":
            g = [r2 for r2 in roster if r2["tier"] == t and r2["role"] == "guardian"]
            want = "guard" if g.index(r) == 0 else "guard2"
            mine = [i for i in ids if role_of.get(i) == want and i not in imported]
            dl.append("table = %d\t%d\t%s\t// tier %d guardian gear" % (nid, D["guard_gear"], pool(mine), t))
            dl.append("table = %d\t%d\t%s\t// jackpot" % (nid, D["guard_jackpot2"], pool(up2)))
        else:
            dl.append("table = %d\t%d\t%s\t// tier %d gear" % (nid, D["mob_gear"], pool(ids), t))
            dl.append("table = %d\t%d\t%s\t// jackpot" % (nid, D["mob_jackpot2"], pool(up2)))
    g = C["global_box_drop"]
    dl.append("global = %d\t%d\t%d:1" % (g["min_combat"], g["chance"], box))
    bw.write(os.path.join(srv, "extradrops.cfg"), "\n".join(dl) + "\n")

    # 15. mystery box, slayer, event config
    W = C["box_tier_weight"]
    bl = ["// reward = itemId<TAB>weight<TAB>name", "box = %d" % box]
    for t, ids in sorted(tiers.items(), key=lambda kv: str(kv[0])):
        bl += ["reward = %d\t%d\t%s" % (i, W[str(t)], names[i]) for i in sorted(ids)]
    bw.write(os.path.join(srv, "mysterybox.cfg"), "\n".join(bl) + "\n")
    sl = ["// tierpool = tier<TAB>item,item,...   (slayer reward crates)"]
    for t in range(1, len(T) + 1):
        sl.append("tierpool = %d\t%s" % (t, ",".join(str(i) for i in sorted(tiers.get(t, [])))))
    sl.append("tierpool = 0\t%s" % ",".join(str(i) for i in sorted(tiers.get("cosmetic", []))))
    bw.write(os.path.join(srv, "slayer.cfg"), "\n".join(sl) + "\n")

    # 16. checks: nothing may be defined twice or share a tile
    def dupes(path, key):
        ids = re.findall(r"(?m)^%s\s*=\s*(\d+)" % key, bw.read(path))
        return sorted({i for i in ids if ids.count(i) > 1})
    clashes = {"item ids": dupes(os.path.join(srv, "item.cfg"), "item"),
               "npc ids": dupes(os.path.join(srv, "npc.cfg"), "npc"),
               "shop ids": dupes(os.path.join(srv, "shops.cfg"), "shop")}
    sn_tiles = re.findall(r"(?m)^shopnpc = (\d+)\t(\d+)\t(\d+)", bw.read(os.path.join(srv, "shopnpcs.cfg")))
    clashes["shopkeeper tiles"] = sorted({t for t in sn_tiles if sn_tiles.count(t) > 1})
    sp_tiles = [tuple(m) for m in re.findall(r"(?m)^spawn = \d+\t(\d+)\t(\d+)\t(\d+)", bw.read(os.path.join(srv, "autospawn.cfg")))]
    clashes["spawn tiles"] = sorted({t for t in sp_tiles if sp_tiles.count(t) > 1})
    rep["clashes"] = clashes
    if any(clashes.values()):
        raise SystemExit("clashes found: %s" % clashes)
    drop_ids = set(int(x) for x in re.findall(r"(\d+):\d+", "\n".join(dl)))
    missing = [i for i in tier_of if i not in drop_ids]
    rep["tiered items not in any drop table"] = missing
    rep["utility customs sold in Rainbow_Tablets"] = len(tabs)
    write_docs(proj, roster, tier_of, slot_of, style_of, role_of, stats, names, gen, custom, imported, rep, menu, T, D_ladder(C))
    print(json.dumps(rep, indent=1, default=str))
    return rep


def D_ladder(C):
    rows, D_prev = [], C["starting_damage"]
    for tt in T:
        rows.append((tt["name"], tt["L"], int((D_prev + tt["L"]) / 6.76), int((tt["D"] + tt["L"]) / 6.76)))
        D_prev = tt["D"]
    return rows


def write_docs(proj, roster, tier_of, slot_of, style_of, role_of, stats, names, gen, custom, imported, rep, menu, T, ladder):
    L = ["# Progression", "", "Talk to the **Rift Guide** at home (or type `::teleports`) for the teleport menu, in progression order.",
         "Every tier has four monster types, two guardians and a boss. Monsters drop the whole tier's gear rarely; the",
         "first guardian drops helms, shields, gloves and boots; the second drops capes, jewellery, ranged/magic accessories;",
         "the boss drops bodies, legs and weapons. Bosses and guardians can also drop gear two or three tiers higher.", "",
         "| Tier | Set | Max hit arriving | Max hit in full set | Boss |", "|---|---|---:|---:|---|"]
    for k, (nm, lv, arrive, full) in enumerate(ladder, 1):
        boss = next(r for r in roster if r["tier"] == k and r["role"] == "boss")
        L.append("| %d %s | %s | %d | %d | %s (%d hp) |" % (k, nm, T[k - 1]["set"], arrive, full, boss["name"], boss["hp"]))
    L += ["", "Max hit uses one formula for melee, ranged and magic: (damage bonus + level) / 6.76. The table assumes these",
          "levels per tier: %s. Skills go to 150." % ", ".join(str(tt["L"]) for tt in T), ""]
    for t in range(1, len(T) + 1):
        L += ["## Tier %d: %s (%s bands)" % (t, T[t - 1]["name"], T[t - 1]["set"]), "", "| NPC | Role | HP | Max hit |", "|---|---|---:|---:|"]
        for r in roster:
            if r["tier"] == t:
                L.append("| %s | %s | %d | %d |" % (r["name"], r["role"], r["hp"], r["maxhit"]))
        L.append("")
    L += ["## Event bosses", "", "One spawns in the event arena 10 minutes after start-up, then every 40 minutes after the last one dies",
          "(announced in chat; `::event` or the menu to get there). They drop 2 mystery boxes, 250K coins, gear from the top",
          "three tiers (1 in 3) and rare overpowered cosmetics (1 in 20).", ""]
    for r in roster:
        if r["role"] == "event":
            L.append("- %s (%d hp)" % (r["name"], r["hp"]))
    open(os.path.join(proj, "PROGRESSION.md"), "w").write("\n".join(L) + "\n")
    I = ["# Items", "", "| ID | Item | Origin | Tier | Slot | Style | Source | Melee str | Range | Magic | Avg def |", "|---:|---|---|---|---|---|---|---:|---:|---:|---:|"]
    for i in sorted(tier_of, key=lambda i: (str(tier_of[i]), names[i].lower())):
        b = stats.get(i, [0] * 12)
        origin = "generated" if i in gen else ("custom" if i in custom else "2007-08 import")
        I.append("| %d | %s | %s | %s | %s | %s | %s | %d | %d | %d | %d |" % (
            i, names[i].replace("|", "/"), origin, tier_of[i], slot_of[i], style_of[i], role_of.get(i, "-") if tier_of[i] != "cosmetic" else "events/box",
            b[10], b[4], b[3], sum(b[5:10]) // 5))
    open(os.path.join(proj, "ITEMS.md"), "w").write("\n".join(I) + "\n")
    open(os.path.join(proj, "BUILD_REPORT_PROGRESSION.json"), "w").write(json.dumps(rep, indent=1, default=str))
    old = os.path.join(proj, "CUSTOM_ITEMS.md")
    if os.path.exists(old):
        os.remove(old)


if __name__ == "__main__":
    main(sys.argv[1])
