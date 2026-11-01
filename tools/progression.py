"""RetroRemake progression stage. Runs after build_world.py.

- Imports the 2007-08 era items from the Project Insanity cache into this cache at id + 10000.
- Writes generated items (the Rainbow set) and custom NPCs (recoloured / rescaled bosses and monsters)
  straight into the cache's obj.dat / npc.dat, so the client needs no code for them.
- Builds an 8-tier ladder: each tier has a zone, three monster types, a miniboss and a boss.
- Every custom or imported item gets a tier, a source NPC and stats scaled from that source's HP,
  anchored on the stats the custom items had on their original servers.
- Writes drop tables (including rare drops from two or three tiers higher), the mystery box pool,
  a starter shop, zones, spawns, and the server data files RetroContent reads.

Usage: python3 progression.py <config.json>
"""
import collections, json, math, os, re, shutil, struct, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_world as bw
import merge_customs as mc
from cache317 import (Cache, CacheWriter, World, archive, archive_names, decode_npc, decode_obj, encode_obj,
                      hsl, join_defs, mkhsl, model_colors, name_hash, pack_archive, split_defs)
import cache317

cache317.SUPPORTED_OBJ |= {114, 115}
SHIFT = 10000                     # PI item id -> our id
PI_FIRST, PI_LAST = 7956, 11790
NPC_FIRST = 3852                   # first free npc id; the client sends npc types in 12 bits (max 4095)

# --------------------------------------------------------------------------- tiers
TIERS = [
    # name,       palette (hue, sat, light shift), zone candidates
    ("Novice",     (22, 4, 0),   [(3255, 3285, "Lumbridge Fields"), (3082, 3420, "Barbarian Village")]),
    ("Apprentice", (42, 5, 0),   [(3082, 3420, "Barbarian Village"), (2960, 3500, "Goblin Village")]),
    ("Adept",      (32, 6, 4),   [(3100, 9890, "Edgeville Dungeon"), (3115, 9845, "Training Dungeon")]),
    ("Veteran",    (0, 6, -4),   [(2884, 9800, "Taverley Dungeon"), (2910, 9780, "Taverley Depths")]),
    ("Elite",      (9, 6, 8),    [(2713, 9564, "Brimhaven Dungeon"), (2580, 9490, "Yanille Dungeon")]),
    ("Champion",   (4, 7, -8),   [(2445, 5170, "TzHaar Crater"), (2400, 5150, "Fight Pits")]),
    ("Mythic",     (50, 6, 0),   [(2272, 4698, "Dragon Lair"), (2271, 4690, "Dragon Lair")]),
    ("Divine",     ("rainbow", 7, 10), [(3485, 9495, "Kalphite Hive"), (3490, 9510, "Kalphite Hive")]),
]
HP_ANCHOR = 1200.0                 # first guess for the tier-5 boss; the ladder is solved below

NPC_PLAN = [
    (["Goblin", "Giant rat", "Skeleton"], "Hill giant", "Ogre",
     ["Mossback Goblin", "Bog Rat", "Moss Skeleton"], "Mossjaw the Hill Giant", "Grubnash the Ogre Chief"),
    (["Hobgoblin", "Ice warrior", "Giant spider"], "Moss giant", "Black knight titan",
     ["Frost Hobgoblin", "Glacial Warrior", "Frost Spider"], "Rimeheart Giant", "Cobalt Titan"),
    (["Lesser demon", "Blue dragon", "Ice giant"], "Greater demon", "Jungle demon",
     ["Tidal Imp", "Azure Wyrmling", "Tidecaller Giant"], "Abyssal Warden", "Leviathan Demon"),
    (["Black dragon", "Hellhound", "Dagannoth"], "Dagannoth Supreme", "King black dragon",
     ["Crimson Drake", "Bloodhound", "Blood Dagannoth"], "Crimson Supreme", "Vermilion King"),
    (["Abyssal demon", "Dark beast", "Gargoyle"], "Skeletal wyvern", "Steel dragon",
     ["Gilded Fiend", "Gold Beast", "Gilded Gargoyle"], "Gilded Wyvern", "Sunforged Dragon"),
    (["Fire giant", "TzHaar-Ket", "Ket-Zek"], "TzHaar-Mej", "TzTok-Jad",
     ["Magma Giant", "Cinder Guard", "Lava Zek"], "Pyroclast Mage", "Inferno Jad"),
    (["Nechryael", "Abyssal demon", "Bloodveld"], "Dagannoth Prime", "King black dragon",
     ["Voidspawn", "Umbral Demon", "Nether Fiend"], "Void Harbinger", "Eclipse Dragon"),
    (["Red dragon", "Black demon", "Dark beast"], "Dagannoth Rex", "King black dragon",
     ["Prism Drake", "Spectrum Fiend", "Chroma Beast"], "Prism Sentinel", "The Rainbow Dragon"),
]
BOSS_HITS = [22, 28, 34, 40, 46, 52, 58, 64]     # hits to kill the boss in the previous tier's best gear
BOSS_AVG_HIT = [7, 8, 9, 10, 11, 12, 13, 14]     # average boss hit after the previous tier's armour
SKILLS = ["attack", "strength", "defence", "ranging", "range", "prayer", "magic", "runecraft", "runecrafting", "hitpoint",
          "hitpoints", "agility", "herblore", "thieving", "crafting", "fletching", "slayer", "construct", "const",
          "mining", "smithing", "fishing", "cooking", "firemaking", "woodcut", "woodcutting", "farming", "hunter", "quest"]
MOB_HP = [0.12, 0.16, 0.22]
BOSS_SCALE = [150, 165, 180, 195, 210, 230, 250, 280]   # model scale (128 = normal) per tier for the boss
MINI_SCALE = 140

# weapon animation templates (ids GodzHell's code already animates)
WEAPON_TEMPLATE = [("godsword|balmung|ultimanum|legionary", 15334), ("whip", 4151), ("claw", 3101),
                   ("c'bow|crossbow", 837), ("dark bow|plasma bow|comp bow|shortbow|longbow|\\bbow\\b", 861),
                   ("staff|crozier|wand|sceptre", 4675), ("halberd|hasta|scythe", 3204), ("2h|two-hand", 7158),
                   ("maul|hammer", 4153), ("anchor", 14915), ("dagger|keris", 5698), ("scimitar|sabre|blade", 4587),
                   ("longsword|sword", 1305), ("battleaxe|axe", 6739)]
TWO_HANDED = r"godsword|balmung|2h|halberd|hasta|maul|anchor|scythe|(?<!')\bbow\b|shortbow|longbow|comp bow|dark bow|plasma bow|ultimanum|legionary"

JUNK = (r"barrel|crate|dossier|sketch|bucket|vial|\bsaw\b|torch|flag|banner|\bshot\b|\brum\b|\bstick\b|icon|seal\(|commorb|"
        r"chime|rope|logs|pie\b|decapitated|severed|tea flask|satchel|\brod\b|butterfly net|sandbag|thingy|lantern|"
        r"potion|limbs|stock|\(u\)|teasing|harpoon|rabbit foot|salamander|lizard|noose|egg|destabiliser|ghost buster|"
        r"bell|prayer book|training|bone dagger \(|\(p\+*\)|\(kp\)|\(\d+\)$|\(h\d\)|ham shirt|zombie shirt|shrink|"
        r"clean necklace|digsite|chicken|bob shirt|rubber chicken|mime|frog mask|easter|pharaoh|queen's secateurs|"
        r"emerald lantern|skull sceptre|castlewar|inoculation|abyssal brace|combat bracelet\(|skills necklace\(|"
        r"glory\(t\d\)|void seal|elvarg's head|crabclaw|hook|wig|pantaloons|sleeping cap|flared|bunny ears|"
        r"cutthroat|guilded smile|bronze fist|lucky shot|treasure flag|phasmatys flag|hat eyepatch|bandana eyepatch")


# --------------------------------------------------------------------------- helpers
def norm(s):
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def bonuses_of(line):
    parts = re.split(r"\t+", line.strip())
    try:
        b = [int(float(x)) for x in parts[-12:]]
        return b if len(b) == 12 else None
    except ValueError:
        return None


def power(b):
    return sum(max(0, v) for v in b) if b else 0


def scale_vec(shape, target):
    p = power(shape)
    if p <= 0:
        return [0] * 12
    f = target / float(p)
    return [int(round(v * f)) if v > 0 else max(-40, int(round(v * min(f, 1.5)))) for v in shape]


def recolor_pairs(colors, palette, k):
    """Map a model's most used colours onto a tier palette, keeping each colour's lightness."""
    pairs = []
    hue, sat, lshift = palette
    rainbow = [0, 9, 14, 22, 32, 42, 50, 58]
    for n, (c, _) in enumerate(colors.most_common(12)):
        h, s, l = hsl(c)
        nh = rainbow[n % len(rainbow)] if hue == "rainbow" else hue
        nl = max(8, min(120, l + lshift))
        pairs.append((c, mkhsl(nh, sat, nl)))
    return pairs


def encode_npc(d):
    out = bytearray()
    w = lambda v: out.extend(struct.pack(">H", v & 0xFFFF))
    def s(op, v):
        out.append(op); out.extend(v.encode("latin-1") + b"\n")
    out.append(1); out.append(len(d["models"]))
    for m in d["models"]:
        w(m)
    s(2, d["name"])
    if d.get("examine"):
        s(3, d["examine"])
    out.append(12); out.append(max(1, min(10, d.get("size", 1))))
    if "stand" in d:
        out.append(13); w(d["stand"])
    if "walk" in d:
        out.append(17); w(d["walk"]); w(d.get("turn180", d["walk"])); w(d.get("turn90cw", d["walk"])); w(d.get("turn90ccw", d["walk"]))
    for k, v in sorted(d.get("actions", {}).items()):
        if v:
            s(30 + k, v)
    if d.get("recolor"):
        out.append(40); out.append(len(d["recolor"]))
        for a, b in d["recolor"]:
            w(a); w(b)
    if d.get("heads"):
        out.append(60); out.append(len(d["heads"]))
        for m in d["heads"]:
            w(m)
    out.append(95); w(d.get("combat", 1))
    out.append(97); w(d.get("scaleXZ", 128))
    out.append(98); w(d.get("scaleY", 128))
    out.append(0)
    return bytes(out)


# --------------------------------------------------------------------------- main
def main(conf_path):
    C = json.load(open(conf_path))
    proj, base = C["project"], C["base"]
    srv, cli = os.path.join(proj, "server"), os.path.join(proj, "client")
    rep = collections.OrderedDict()

    # 0. pristine cache (this stage rewrites the config archive)
    cdir = os.path.join(cli, "cache")
    for f in os.listdir(os.path.join(base, "Client", "cache")):
        if f.startswith("main_file_cache"):
            shutil.copy(os.path.join(base, "Client", "cache", f), os.path.join(cdir, f))
    ours = Cache(cdir)
    pi = Cache(C["pi_cache"])
    cfg_raw = ours.file(0, 2)
    cfg = archive(cfg_raw)
    order = archive_names(cfg_raw)
    pcfg = archive(pi.file(0, 2))
    obj = split_defs(cfg[name_hash("obj.dat")], cfg[name_hash("obj.idx")])
    pobj = split_defs(pcfg[name_hash("obj.dat")], pcfg[name_hash("obj.idx")])
    npcs = split_defs(cfg[name_hash("npc.dat")], cfg[name_hash("npc.idx")])
    n_stock = len(obj)

    # 1. custom items already in the client (hardcoded Class8 blocks) and server item.cfg
    class8_path = os.path.join(cli, "Class8.java")
    class8 = bw.read(class8_path)
    custom = {}
    for i, _, _, body in mc.find_blocks(class8):
        n = mc.block_name(body)
        if n and i not in custom:
            custom[i] = n.strip()
    # relocate hardcoded customs that sit inside the imported range
    clash = [i for i in custom if PI_FIRST + SHIFT <= i <= PI_LAST + SHIFT]
    free_ids = [i for i in range(16000, 16999) if i not in custom]
    item_cfg_path = os.path.join(srv, "item.cfg")
    item_text = bw.read(item_cfg_path)
    for i in clash:
        new = free_ids.pop(0)
        class8 = re.sub(r"if\s*\(\s*i\s*==\s*%d\s*\)" % i, "if(i == %d)" % new, class8)
        item_text = re.sub(r"(?m)^(\s*item\s*=\s*)%d(\s)" % i, r"\g<1>%d\2" % new, item_text)
        custom[new] = custom.pop(i)
    rep["hardcoded customs moved out of the imported id range"] = clash
    bw.write(class8_path, class8)

    # donor stats for custom items (the reference: what the source servers gave them)
    donor_stats = {}
    donor_cfgs = [mc.load_cfg(p) for d in C["classic"] for p in bw.find_files(d, "item.cfg")]
    for i, n in custom.items():
        for dc in donor_cfgs:
            ln = dc.get(i)
            if ln and norm(mc.cfg_name(ln)) == norm(n):
                b = bonuses_of(ln)
                if b and 0 < power(b) < 1500:
                    donor_stats[i] = b; break
    rep["custom items with original stats (reference set)"] = len(donor_stats)

    # 2. import PI items at id + SHIFT
    def remap(v):
        return v + SHIFT if PI_FIRST <= v <= PI_LAST else v
    rm = {97: remap, 98: remap}
    for op in range(100, 110):
        rm[op] = lambda v: (remap(v[0]), v[1])
    filler = b"\x00"
    new_obj = list(obj) + [filler] * (PI_FIRST + SHIFT - n_stock)
    pi_names = {}
    for pid in range(PI_FIRST, PI_LAST + 1):
        ops = decode_obj(pobj[pid])
        new_obj.append(encode_obj(ops, rm))
        nm = dict(ops).get(2)
        if nm:
            pi_names[pid + SHIFT] = (nm, dict(ops))
    rep["items imported from the PI cache"] = len(pi_names)

    # PI server stats for imported items (shape + original power)
    pi_cfg = mc.load_cfg(C["pi_item_cfg"])
    stock_cfg = mc.load_cfg(item_cfg_path)

    # 2b. models: PI ships ~600 extra models in cache/models.dat; add the ones this cache lacks, and let the
    #     client load every model above its original table (RetroModels.java + Class42_Sub1 patch)
    import gzip as _gz
    TABLE = 14927
    model_slots = len(ours.idx[1]) // 6
    have_model = lambda m: m < model_slots and bool(ours.file(1, m))
    pm_idx = open(os.path.join(C["pi_models"], "models.idx"), "rb").read()
    pm_dat = open(os.path.join(C["pi_models"], "models.dat"), "rb").read()
    n_pm = struct.unpack(">i", pm_idx[:4])[0]
    off, added = 0, []
    w = CacheWriter(cdir)
    for k in range(n_pm):
        mid, ln = struct.unpack(">ii", pm_idx[4 + 8 * k: 12 + 8 * k])
        raw = pm_dat[off:off + ln]; off += ln
        if raw[-2:] == b"\xff\xff" or have_model(mid):
            continue
        w.put(1, mid, _gz.compress(raw, 9) + b"\x00\x01")
        added.append(mid)
    high = sorted({m for m in range(TABLE, model_slots) if ours.file(1, m)} | {m for m in added if m >= TABLE})
    loadable = lambda m: (m < TABLE and have_model(m)) or m in set(high) or m in added
    high_set, added_set = set(high), set(added)
    loadable = lambda m: (m < TABLE and have_model(m)) or m in high_set or m in added_set
    rep["extra models added from PI"] = len(added)
    rep["models loadable above the original table"] = len(high)
    open(os.path.join(cli, "RetroModels.java"), "w").write(
        "/** Generated by tools/progression.py: model ids above the cache's original model table that the client may load. */\n"
        "final class RetroModels {\n\tstatic final int MAX = %d;\n\tstatic final int[] IDS = {%s};\n}\n"
        % (max(high) if high else 0, ",".join(map(str, high))))

    def def_models(ops):
        d = dict(ops) if not isinstance(ops, dict) else ops
        out = []
        for op in (1, 23, 24, 25, 26, 78, 79, 90, 91, 92, 93):
            v = d.get(op)
            if v is not None:
                out.append(v[0] if isinstance(v, tuple) else v)
        return [m for m in out if m != 65535]

    # 3. choose which imported items are game items
    custom_norm = {norm(n) for n in custom.values()}
    stock_norm = {norm(mc.cfg_name(l)) for l in stock_cfg.values() if mc.cfg_name(l)}
    seen = set()
    imported = {}
    for iid, (nm, ops) in sorted(pi_names.items()):
        key = norm(nm)
        wearable = 23 in ops or 25 in ops or any(isinstance(v, str) and v.lower() in ("wear", "wield") for op, v in ops.items() if 30 <= op < 40)
        if not wearable or 97 in ops or key in seen or key in custom_norm or key in stock_norm:
            continue
        if not all(loadable(m) for m in def_models(ops)):
            rep["imported items skipped (missing models)"] = rep.get("imported items skipped (missing models)", 0) + 1
            continue
        if re.search(JUNK, nm.lower()):
            continue
        if bw.item_slot(nm) is None and not re.search(r"bracelet|vamb|brace", nm.lower()):
            continue
        seen.add(key)
        imported[iid] = nm
    rep["imported items used as gear"] = len(imported)

    # 4. generated Rainbow set: copy a base item's def, rename, rainbow recolour
    gen_specs = C["generated_items"]
    gen_items = {}
    next_gen = PI_LAST + SHIFT + 1 + 9
    while len(new_obj) < next_gen:
        new_obj.append(filler)
    lookup = {}
    for iid, (nm, _) in pi_names.items():
        lookup.setdefault(norm(nm), iid)
    for k, l in mc.load_cfg(item_cfg_path).items():
        if k < n_stock and mc.cfg_name(l):
            lookup.setdefault(norm(mc.cfg_name(l)), k)
    for spec in gen_specs:
        src = spec.get("from") or lookup.get(norm(spec.get("from_name", "")))
        if src is None:
            rep.setdefault("generated items skipped (base not found)", []).append(spec["name"]); continue
        b = new_obj[src] if src < len(new_obj) else None
        if not b or b == filler:
            continue
        ops = decode_obj(b)
        d = dict(ops)
        if not all(loadable(m) for m in def_models(ops)):
            rep.setdefault("generated items skipped (missing models)", []).append(spec["name"]); continue
        models = [m for m in (d.get(1), (d.get(23) or (None,))[0], (d.get(25) or (None,))[0]) if m]
        cols = collections.Counter()
        for m in models:
            mcnt = model_colors(ours, m)
            if mcnt:
                cols.update(mcnt)
        pal = tuple(spec.get("palette", ["rainbow", 7, 10]))
        pairs = recolor_pairs(cols, pal, 12)
        ops = [(op, v) for op, v in ops if op not in (2, 3, 40, 97, 98) and not (100 <= op < 110)]
        ops.insert(0, (2, spec["name"]))
        ops.insert(1, (3, spec["examine"]))
        if pairs:
            ops.append((40, pairs))
        gid = len(new_obj)
        new_obj.append(encode_obj(ops))
        gen_items[gid] = spec
    # signature set for every tier, recoloured in the tier palette
    ADJ = ["Verdant", "Frostforged", "Tidal", "Crimson", "Gilded", "Molten", "Umbral", "Prismatic"]
    SIG = [("full helm", 1163, "head"), ("platebody", 1127, "body"), ("platelegs", 1079, "legs"),
           ("kiteshield", 1201, "shield"), ("boots", 4131, "feet"), ("gloves", 7462, "hands"), ("cape", 1052, "cape"),
           ("scimitar", 1333, "weapon"), ("shortbow", 861, "weapon"), ("staff", 4675, "weapon")]
    have = {(s["tier"], s["slot"], bw.weapon_style(s["name"]) if s["slot"] == "weapon" else s["slot"]) for s in gen_items.values()}
    for t, (tname, pal, _) in enumerate(TIERS, 1):
        for noun, src, slot in SIG:
            nm = "%s %s" % (ADJ[t - 1], noun)
            key = (t, slot, bw.weapon_style(nm) if slot == "weapon" else slot)
            if key in have:
                continue
            ops = decode_obj(new_obj[src])
            d = dict(ops)
            cols = collections.Counter()
            for m in [m for m in (d.get(1), (d.get(23) or (None,))[0], (d.get(25) or (None,))[0]) if m]:
                mcnt = model_colors(ours, m)
                if mcnt:
                    cols.update(mcnt)
            ops = [(op, v) for op, v in ops if op not in (2, 3, 40, 97, 98) and not (100 <= op < 110)]
            ops[:0] = [(2, nm), (3, "Forged in the %s tier." % tname)]
            pairs = recolor_pairs(cols, pal, 12)
            if pairs:
                ops.append((40, pairs))
            gid = len(new_obj)
            new_obj.append(encode_obj(ops))
            gen_items[gid] = {"name": nm, "tier": t, "slot": slot, "examine": "", "signature": True}
    rep["generated items"] = {i: s["name"] for i, s in gen_items.items()}

    # 5. tiers for every item -------------------------------------------------
    names = dict(custom)
    names.update(imported)
    names.update({i: s["name"] for i, s in gen_items.items()})
    theme = C["theme"]
    rune_power = {s: power(v) for s, v in theme["ref"].items()}
    tier_of, kind = {}, {}
    skill_rx = re.compile(r"^(%s)\.? ?(cape|cape\(t\)|hood)$" % "|".join(SKILLS))
    for i, n in names.items():
        low = n.lower()
        if i in gen_items:
            tier_of[i] = gen_items[i]["tier"]; kind[i] = gen_items[i]["slot"]; continue
        t_custom = bw.item_tier(n, theme)
        if t_custom == "utility":
            continue
        slot = bw.item_slot(n)
        if slot is None:
            continue
        kind[i] = slot
        m = skill_rx.match(low.replace("woodcut.", "woodcut").replace("construct.", "construct"))
        if m:
            tier_of[i] = 2 + (SKILLS.index(m.group(1)) % 4); continue
        if t_custom == "cosmetic" or re.search(C["cosmetic_regex"], low):
            tier_of[i] = "cosmetic"; continue
        forced = next((t for rx, t in C["tier_overrides"] if re.search(rx, low)), None)
        if forced:
            tier_of[i] = forced; continue
        if i in custom:
            tier_of[i] = {"t1": 1, "t2": 2, "t3": 3, "t4": 4, "t5": 6, "staff": 8}.get(t_custom, 3); continue
        line = pi_cfg.get(i - SHIFT)
        b = bonuses_of(line) if line else None
        ref = rune_power[bw.weapon_style(n) if slot == "weapon" else slot]
        r = power(b) / float(ref or 1) if b else 0
        tier_of[i] = "cosmetic" if r <= 0.05 else (1 if r < 0.45 else 2 if r < 0.75 else 3 if r < 1.1 else 4 if r < 1.4 else 5 if r < 1.8 else 6)
    tiers = collections.defaultdict(list)
    for i, t in tier_of.items():
        tiers[t].append(i)
    rep["items per tier"] = {str(k): len(v) for k, v in sorted(tiers.items(), key=lambda kv: str(kv[0]))}

    # 6. anchors (median power of the custom items' original stats, per slot) and stat shapes
    by_slot = collections.defaultdict(list)
    for i, b in donor_stats.items():
        if kind.get(i):
            by_slot[kind[i]].append(power(b))
    anchor = {}
    for s in ("head", "body", "legs", "shield", "feet", "hands", "cape", "ring", "amulet", "weapon"):
        vals = sorted(by_slot.get(s, []))
        anchor[s] = vals[len(vals) // 2] if len(vals) >= 3 else power(theme["ref"]["slash" if s == "weapon" else s]) * 1.6
    rep["stat anchors (median power of custom items per slot)"] = anchor

    def shape_of(i):
        s = kind[i]
        ref = theme["ref"][bw.weapon_style(names[i]) if s == "weapon" else s]
        if i in gen_items:
            return ref
        if i in donor_stats:
            return donor_stats[i]
        b = bonuses_of(pi_cfg[i - SHIFT]) if (i - SHIFT) in pi_cfg else None
        return b if b and power(b) > 0 else ref

    shapes = {i: shape_of(i) for i in tier_of if tier_of[i] != "cosmetic"}
    MINI_SLOTS = {"head", "hands", "feet", "ring", "amulet", "cape"}

    def tier_gear(t, hp_boss, hp_mini):
        """Best strength and melee defence a player gets from tier t gear."""
        best_str, best_def = collections.defaultdict(int), collections.defaultdict(int)
        for i in tiers.get(t, []):
            hp = hp_mini if kind[i] in MINI_SLOTS else hp_boss
            v = scale_vec(shapes[i], anchor[kind[i]] * (hp / HP_ANCHOR) ** 0.55)
            best_str[kind[i]] = max(best_str[kind[i]], v[10])
            best_def[kind[i]] = max(best_def[kind[i]], (v[5] + v[6] + v[7]) // 3)
        return sum(best_str.values()), sum(best_def.values())

    # 7. solve the boss ladder from the gear: HP so the previous tier needs BOSS_HITS hits,
    #    max hit so the previous tier's armour takes it down to BOSS_AVG_HIT on average
    STR_LEVEL, prev_str, prev_def = 99, C["starting_gear"]["str"], C["starting_gear"]["def"]
    ladder = []
    carried_str, carried_def = collections.defaultdict(int), collections.defaultdict(int)
    for t in range(1, 9):
        maxhit_player = (prev_str + STR_LEVEL) / 6.76
        hp = int(round(BOSS_HITS[t - 1] * maxhit_player / 2.0 / 10.0) * 10)
        hp = max(hp, ladder[-1][0] + 60) if ladder else hp
        mini = int(round(hp * 0.6 / 10.0) * 10)
        reduce = 1.0 / (1.0 + prev_def / 600.0)
        bmax = int(round(BOSS_AVG_HIT[t - 1] * 2 / reduce))
        ladder.append((hp, mini, bmax, int(maxhit_player), prev_str, prev_def))
        for i in tiers.get(t, []):
            v = scale_vec(shapes[i], anchor[kind[i]] * ((mini if kind[i] in MINI_SLOTS else hp) / HP_ANCHOR) ** 0.55)
            carried_str[kind[i]] = max(carried_str[kind[i]], v[10])
            carried_def[kind[i]] = max(carried_def[kind[i]], (v[5] + v[6] + v[7]) // 3)
        prev_str, prev_def = sum(carried_str.values()), sum(carried_def.values())
    rep["boss ladder (hp, mini hp, raw max hit, player max hit arriving, str bonus, melee def)"] = ladder

    # 8. custom NPCs written into npc.dat ----------------------------------------
    npc_by_name = {}
    for i, e in enumerate(npcs):
        d = decode_npc(e)
        if d.get("name") and d.get("models") and d.get("combat", 0) > 0:
            npc_by_name.setdefault(d["name"].lower(), (i, d))
    custom_npcs = []
    next_npc = NPC_FIRST
    for t, ((tname, pal, zones), plan, (bhp, mhp, bmax, _, _, _)) in enumerate(zip(TIERS, NPC_PLAN, ladder), 1):
        mobs, mini, boss, mob_names, mini_name, boss_name = plan
        roles = [(m, mn, "mob", int(bhp * MOB_HP[k]), max(2, int(bmax * (0.35 + 0.1 * k))), 128)
                 for k, (m, mn) in enumerate(zip(mobs, mob_names))]
        roles += [(mini, mini_name, "miniboss", mhp, int(bmax * 0.75), MINI_SCALE),
                  (boss, boss_name, "boss", bhp, bmax, BOSS_SCALE[t - 1])]
        for basename, newname, role, hp, mx, scale in roles:
            hit = npc_by_name.get(basename.lower())
            if not hit:
                raise SystemExit("base npc not found: " + basename)
            bid, bd = hit
            cols = collections.Counter()
            for m in bd["models"]:
                mcnt = model_colors(ours, m)
                if mcnt:
                    cols.update(mcnt)
            nd = dict(bd)
            nd["name"] = newname
            nd["examine"] = "%s of the %s tier." % ({"boss": "The boss", "miniboss": "The guardian"}.get(role, "A creature"), tname)
            nd["combat"] = min(999, int(round(hp / 4.0 + mx * 3)))
            nd["scaleXZ"] = nd["scaleY"] = int(scale)
            nd["size"] = max(1, min(8, int(round((bd.get("size") or 1) * (scale / 128.0)))))
            nd["recolor"] = recolor_pairs(cols, pal, 12)
            nd["actions"] = {1: "Attack"}
            nid = next_npc; next_npc += 1
            if nid > 4095:
                raise SystemExit("too many custom npcs for the 12-bit npc id")
            npcs.append(encode_npc(nd))
            custom_npcs.append((nid, bid, hp, mx, newname, t, role, nd["combat"]))
    rep["custom NPCs"] = len(custom_npcs)

    # 9. write the config archive back into the cache
    cfg[name_hash("obj.dat")], cfg[name_hash("obj.idx")] = join_defs(new_obj)
    cfg[name_hash("npc.dat")], cfg[name_hash("npc.idx")] = join_defs(npcs)
    CacheWriter(cdir).put(0, 2, pack_archive([(h, cfg[h]) for h in order]))
    chk = archive(Cache(cdir).file(0, 2))
    assert split_defs(chk[name_hash("obj.dat")], chk[name_hash("obj.idx")]) == new_obj
    assert split_defs(chk[name_hash("npc.dat")], chk[name_hash("npc.idx")]) == npcs
    for nid, *_ in custom_npcs:
        decode_npc(npcs[nid])
    rep["cache item count"] = len(new_obj)
    rep["cache npc count"] = len(npcs)

    # 10. stats from the source NPC's HP ---------------------------------------------
    boss_of = {}
    for nid, bid, hp, mx, nm, t, role, cb in custom_npcs:
        boss_of.setdefault(t, {}).setdefault(role, (nid, hp, nm))
    source, stats = {}, {}
    for i, t in tier_of.items():
        if t == "cosmetic":
            s = kind[i]
            stats[i] = scale_vec(theme["ref"][bw.weapon_style(names[i]) if s == "weapon" else s], anchor[s] * 0.12)
            continue
        role = "miniboss" if kind[i] in MINI_SLOTS else "boss"
        nid, hp, nm = boss_of[t][role]
        source[i] = (nid, nm, t, role)
        ranged = kind[i] == "weapon" and bw.weapon_style(names[i]) == "ranged"
        stats[i] = scale_vec(shapes[i], anchor[kind[i]] * (hp / HP_ANCHOR) ** 0.55 * (0.5 if ranged else 1.0))


    # 11. item.cfg ---------------------------------------------------------------
    TV = C["tier_value"]
    lines = item_text.split("\n")
    have = {}
    for k, l in enumerate(lines):
        m = re.match(r"\s*item\s*=\s*(\d+)\s", l)
        if m:
            have[int(m.group(1))] = k
    def cfg_line(i):
        t = tier_of.get(i)
        val = TV[str(t)] if t is not None else 1000
        nm = names[i].replace(" ", "_")
        if t is None:
            ex = "%s." % nm
        elif t == "cosmetic":
            ex = "%s_(cosmetic)." % nm
        else:
            ex = "%s_(Tier_%d_%s)." % (nm, t, TIERS[t - 1][0])
        b = stats.get(i, [0] * 12)
        return "item = %d\t%s\t%s\t%d\t%d\t%d\t%s" % (i, nm, ex, val, val * 4 // 10, val * 6 // 10, "\t".join(map(str, b)))
    new_lines = []
    for i in sorted(names):
        if i in have:
            lines[have[i]] = cfg_line(i)
        else:
            new_lines.append(cfg_line(i))
    item_text = "\n".join(lines)
    end = item_text.rindex("[ENDOFITEMLIST]")
    item_text = item_text[:end].rstrip("\n") + "\n" + "\n".join(new_lines) + "\n" + item_text[end:]
    # mystery box price
    item_text = re.sub(r"(?m)^(item = %d\t[^\t]+\t[^\t]+\t)[^\t]+\t[^\t]+\t[^\t]+" % C["mystery_box_item"],
                       lambda m: m.group(1) + "%d\t%d\t%d" % (C["mystery_box_price"], C["mystery_box_price"] * 4 // 10, C["mystery_box_price"] * 6 // 10), item_text)
    bw.write(item_cfg_path, item_text)

    # 11. equipment slots, two-handed, weapon animation templates ---------------
    slots = {i: kind[i] for i in tier_of}
    bw.patch_item4(os.path.join(srv, "Item4.java"), slots, rep)
    item_java = bw.read(os.path.join(srv, "Item.java"))
    item_java = re.sub(r"new boolean\[20000\]", "new boolean[32768]", item_java)
    two = [i for i in tier_of if kind[i] == "weapon" and re.search(TWO_HANDED, names[i].lower())]
    anchor_line = "itemTwoHanded[15336] = true;"
    if "// RetroRemake two-handed" not in item_java:
        item_java = item_java.replace(anchor_line, anchor_line + "\n// RetroRemake two-handed\n" + "\n".join("itemTwoHanded[%d] = true;" % i for i in sorted(two)), 1)
    bw.write(os.path.join(srv, "Item.java"), item_java)
    wl = ["// weapon = itemId<TAB>templateItemId  (animations borrowed from a weapon the server already animates)"]
    for i in sorted(tier_of):
        if kind[i] != "weapon":
            continue
        low = names[i].lower()
        for rx, tpl in WEAPON_TEMPLATE:
            if re.search(rx, low):
                wl.append("weapon = %d\t%d\t// %s" % (i, tpl, names[i])); break
    bw.write(os.path.join(srv, "weapons.cfg"), "\n".join(wl) + "\n")
    rep["two-handed weapons"] = len(two)

    # 12. tier zones, spawns -----------------------------------------------------
    world = World(cdir)
    spawn_text = bw.read(os.path.join(srv, "autospawn.cfg"))
    spawn_lines = [l for l in spawn_text.split("\n") if l.strip().startswith("spawn")]
    zone_rows = [l for l in bw.read(os.path.join(srv, "zones.cfg")).split("\n") if l.startswith("zone")]
    chosen = []
    used = []
    for t, (tname, pal, cands) in enumerate(TIERS, 1):
        best = None
        for cx, cy, label in cands:
            if any(abs(cx - ux) < 40 and abs(cy - uy) < 40 for ux, uy in used):
                continue
            free = [(x, y) for x in range(cx - 12, cx + 13) for y in range(cy - 12, cy + 13) if world.free(x, y)]
            if len(free) >= 120:
                best = (cx, cy, label, free); break
        if not best:
            raise SystemExit("no free area for tier %d" % t)
        used.append(best[:2])
        chosen.append(best)
    R = C["tier_zone_clear_radius"]
    def in_tier_area(x, y):
        return any(abs(x - cx) <= R and abs(y - cy) <= R for cx, cy, _, _ in chosen)
    kept, removed = [], 0
    for l in spawn_lines:
        v = bw.ints(re.split(r"\s+", l.split("=", 1)[1].strip()), 4)
        if v and v[3] == 0 and in_tier_area(v[1], v[2]):
            removed += 1; continue
        kept.append(l)
    rep["vanilla spawns cleared from tier zones"] = removed
    new_spawns = []
    tier_zones = []
    for t, (cx, cy, label, free) in enumerate(chosen, 1):
        free.sort(key=lambda p: (p[0] - cx) ** 2 + (p[1] - cy) ** 2)
        far = [p for p in free if (p[0] - cx) ** 2 + (p[1] - cy) ** 2 >= 81]
        tele = far[0] if far else free[-1]
        boss = next(p for p in free if (p[0] - cx) ** 2 + (p[1] - cy) ** 2 >= 4)
        taken = {tele, boss}
        def pick(mind, maxd):
            for p in free:
                d2 = (p[0] - cx) ** 2 + (p[1] - cy) ** 2
                if mind * mind <= d2 <= maxd * maxd and p not in taken and all(abs(p[0] - q[0]) + abs(p[1] - q[1]) >= 2 for q in taken):
                    taken.add(p); return p
            return None
        tier_n = [n for n in custom_npcs if n[5] == t]
        for nid, bid, hp, mx, nm, tt, role, cb in tier_n:
            if role == "boss":
                pts = [boss]
            elif role == "miniboss":
                pts = [pick(4, 7)]
            else:
                pts = [pick(5, 11) for _ in range(C["mobs_per_type"])]
            for p in pts:
                if not p:
                    continue
                r = 2 if role != "mob" else 3
                new_spawns.append("spawn = %d\t%d\t%d\t0\t%d\t%d\t%d\t%d\t2\t// Tier %d %s" % (nid, p[0], p[1], p[0] + r, p[1] + r, p[0] - r, p[1] - r, t, nm))
        tier_zones.append((t, "Tier %d: %s (%s)" % (t, TIERS[t - 1][0], label), tele))
    bw.write(os.path.join(srv, "autospawn.cfg"), "\n".join(kept + new_spawns) + "\n[ENDOFSPAWNLIST]\n")
    rep["tier spawns"] = len(new_spawns)
    # zones: progression first, drop old zones inside tier areas, renumber
    old = []
    for l in zone_rows:
        p = l.split("=", 1)[1].strip().split("\t")
        x, y = int(p[2]), int(p[3])
        if in_tier_area(x, y):
            continue
        old.append(p[1:])
    out = ["// zone = id<TAB>category<TAB>x<TAB>y<TAB>height<TAB>name  (generated by tools/build_world.py + progression.py)"]
    zid = 1
    for t, nm, (x, y) in tier_zones:
        out.append("zone = %d\tProgression\t%d\t%d\t0\t%s" % (zid, x, y, nm)); zid += 1
    for p in old:
        out.append("zone = %d\t%s" % (zid, "\t".join(p))); zid += 1
    bw.write(os.path.join(srv, "zones.cfg"), "\n".join(out) + "\n")
    rep["zones"] = zid - 1

    # 13. NPC definitions for the server (npc.cfg) + custom NPC table -------------
    npc_cfg = bw.read(os.path.join(srv, "npc.cfg"))
    npc_cfg = re.sub(r"(?m)^npc = (%s)\t.*\n" % "|".join(str(n[0]) for n in custom_npcs), "", npc_cfg)
    add = ["npc = %d\t%s\t%d\t%d" % (nid, nm.replace(" ", "_"), cb, hp) for nid, bid, hp, mx, nm, t, role, cb in custom_npcs]
    end = npc_cfg.rindex("[ENDOFNPCLIST]") if "[ENDOFNPCLIST]" in npc_cfg else len(npc_cfg)
    bw.write(os.path.join(srv, "npc.cfg"), npc_cfg[:end].rstrip("\n") + "\n" + "\n".join(add) + "\n" + npc_cfg[end:])
    cl = ["// customnpc = id<TAB>baseNpc<TAB>hp<TAB>maxHit<TAB>tier<TAB>role<TAB>name"]
    cl += ["customnpc = %d\t%d\t%d\t%d\t%d\t%s\t%s" % (nid, bid, hp, mx, t, role, nm) for nid, bid, hp, mx, nm, t, role, cb in custom_npcs]
    bw.write(os.path.join(srv, "customnpcs.cfg"), "\n".join(cl) + "\n")

    # 14. drops: tier gear from bosses, guardians and monsters, plus jackpots ------
    D = C["drops"]
    dl = [l for l in bw.read(os.path.join(srv, "extradrops.cfg")).split("\n") if l.strip()]
    dl.append("// ---- RetroRemake progression drops (progression.py) ----")
    def pool(ids):
        return ",".join("%d:1" % i for i in sorted(ids))
    for t in range(1, 9):
        ids = tiers.get(t, [])
        mini_ids = [i for i in ids if source[i][3] == "miniboss"]
        boss_ids = [i for i in ids if source[i][3] == "boss"]
        up2 = tiers.get(t + 2, []) or tiers.get(8, [])
        up3 = tiers.get(t + 3, []) or tiers.get(8, [])
        for nid, bid, hp, mx, nm, tt, role, cb in [n for n in custom_npcs if n[5] == t]:
            dl.append("table = %d\t1\t995:%d\t// coins, %s" % (nid, max(50, hp * (3 if role == "boss" else 1)), nm))
            if role == "boss" and boss_ids:
                dl.append("table = %d\t%d\t%s\t// tier %d gear" % (nid, D["boss_gear"], pool(boss_ids), t))
                if up2:
                    dl.append("table = %d\t%d\t%s\t// jackpot: tier %d+" % (nid, D["boss_jackpot2"], pool(up2), t + 2))
                if up3:
                    dl.append("table = %d\t%d\t%s\t// jackpot: tier %d+" % (nid, D["boss_jackpot3"], pool(up3), t + 3))
                dl.append("table = %d\t%d\t%d:1\t// mystery box" % (nid, D["boss_box"], C["mystery_box_item"]))
            elif role == "miniboss" and mini_ids:
                dl.append("table = %d\t%d\t%s\t// tier %d gear" % (nid, D["mini_gear"], pool(mini_ids), t))
                if up2:
                    dl.append("table = %d\t%d\t%s\t// jackpot: tier %d+" % (nid, D["mini_jackpot2"], pool(up2), t + 2))
            elif role == "mob" and ids:
                dl.append("table = %d\t%d\t%s\t// tier %d gear" % (nid, D["mob_gear"], pool(ids), t))
                if up2:
                    dl.append("table = %d\t%d\t%s\t// jackpot: tier %d+" % (nid, D["mob_jackpot2"], pool(up2), t + 2))
    bw.write(os.path.join(srv, "extradrops.cfg"), "\n".join(dl) + "\n")

    # 15. mystery box: cosmetics + every tier (weighted), and starter shop -----------
    W = C["box_tier_weight"]
    bl = ["// reward = itemId<TAB>weight<TAB>name   (higher weight = more common)", "box = %d" % C["mystery_box_item"]]
    for t, ids in sorted(tiers.items(), key=lambda kv: str(kv[0])):
        for i in sorted(ids):
            bl.append("reward = %d\t%d\t%s" % (i, W[str(t)], names[i]))
    bw.write(os.path.join(srv, "mysterybox.cfg"), "\n".join(bl) + "\n")
    shops = bw.read(os.path.join(srv, "shops.cfg"))
    sid = max(int(x) for x in re.findall(r"(?m)^shop = (\d+)", shops)) + 1
    starter = sorted(tiers.get(1, []))[:38]
    line = "shop = %d\tNovice_Outfitter\t1\t1\t%s" % (sid, "\t".join("%d\t20" % i for i in starter))
    end = shops.rindex("[ENDOFSHOPLIST]") if "[ENDOFSHOPLIST]" in shops else len(shops)
    bw.write(os.path.join(srv, "shops.cfg"), shops[:end].rstrip("\n") + "\n" + line + "\n" + shops[end:])
    # starter shopkeeper at the novice zone teleport
    t1x, t1y = tier_zones[0][2]
    sn = bw.read(os.path.join(srv, "shopnpcs.cfg")).rstrip("\n")
    kx, ky = None, None
    for dx, dy in ((2, 0), (-2, 0), (0, 2), (0, -2), (2, 2), (-2, -2)):
        if world.free(t1x + dx, t1y + dy):
            kx, ky = t1x + dx, t1y + dy; break
    if kx:
        bw.write(os.path.join(srv, "shopnpcs.cfg"), sn + "\nshopnpc = %d\t%d\t0\t%d\tNovice_Outfitter\n" % (kx, ky, sid))
        at = bw.read(os.path.join(srv, "autospawn.cfg"))
        at = at.replace("[ENDOFSPAWNLIST]", "spawn = 528\t%d\t%d\t0\t%d\t%d\t%d\t%d\t2\t// Novice Outfitter\n[ENDOFSPAWNLIST]" % (kx, ky, kx, ky, kx, ky))
        bw.write(os.path.join(srv, "autospawn.cfg"), at)
    rep["starter shop id"] = sid

    # 16. obtainability check -----------------------------------------------------
    drop_ids = set(int(x) for x in re.findall(r"(\d+):\d+", "\n".join(dl)))
    box_ids = set(int(x) for x in re.findall(r"(?m)^reward = (\d+)", "\n".join(bl)))
    missing = [i for i in tier_of if i not in drop_ids and i not in box_ids]
    rep["gear items not obtainable"] = missing
    write_docs(proj, names, tier_of, kind, stats, source, custom_npcs, tier_zones, gen_items, imported, custom, rep)
    print(json.dumps(rep, indent=1, default=str))


def write_docs(proj, names, tier_of, kind, stats, source, custom_npcs, tier_zones, gen_items, imported, custom, rep):
    L = ["# Progression", "", "Eight tiers. Teleport with `::tp 1` ... `::tp 8` (or `::zones progression`). Each tier zone has",
         "three monster types, a guardian (miniboss) and a boss. Gear from a tier drops there; very rarely you get gear",
         "from two or three tiers higher. `::tiers` shows this list in game.", ""]
    for t, nm, (x, y) in tier_zones:
        L.append("## %s" % nm)
        L.append("")
        L.append("| NPC | Role | HP | Max hit | Combat |")
        L.append("|---|---|---:|---:|---:|")
        for nid, bid, hp, mx, n, tt, role, cb in custom_npcs:
            if tt == t:
                L.append("| %s (%d) | %s | %d | %d | %d |" % (n, nid, role, hp, mx, cb))
        ids = [i for i, tt in tier_of.items() if tt == t]
        L.append("")
        L.append("%d items drop in this tier." % len(ids))
        L.append("")
    open(os.path.join(proj, "PROGRESSION.md"), "w").write("\n".join(L) + "\n")
    I = ["# Items", "", "Every custom, imported (2007-08 era, from the Project Insanity cache) and generated item, with its tier,",
         "slot, where it drops and the main bonuses. Stats are scaled from the HP of the NPC that drops it, anchored on",
         "the stats the custom items had on their original servers.", "",
         "| ID | Item | Origin | Tier | Slot | Drops from | Att | Def | Str |", "|---:|---|---|---|---|---|---:|---:|---:|"]
    for i in sorted(tier_of, key=lambda i: (str(tier_of[i]), names[i].lower())):
        b = stats.get(i, [0] * 12)
        origin = "generated" if i in gen_items else ("custom" if i in custom else "2007-08 import")
        src = source.get(i)
        I.append("| %d | %s | %s | %s | %s | %s | %d | %d | %d |" % (
            i, names[i].replace("|", "/"), origin, tier_of[i], kind.get(i, "-"),
            ("%s (%s)" % (src[1], src[3])) if src else "mystery box", max(b[0:5]), max(b[5:10]), b[10]))
    open(os.path.join(proj, "ITEMS.md"), "w").write("\n".join(I) + "\n")
    box = ["# Mystery box", "", "Open a Mystery box (item 6199) for one random item. Every tier can come out of it; higher tiers are",
           "rarer (weights: cosmetic 30, tier 1 24, tier 2 18, tier 3 12, tier 4 8, tier 5 5, tier 6 3, tier 7 2, tier 8 1).", "",
           "Boxes: Mystery Box Store in the Market (1M), 1 in 10 from every tier boss, 1 in 300 from any monster of combat 50+.", "",
           "| Tier | Items |", "|---|---:|"]
    for t in ["cosmetic"] + list(range(1, 9)):
        box.append("| %s | %d |" % (t, sum(1 for v in tier_of.values() if v == t)))
    open(os.path.join(proj, "MYSTERY_BOX.md"), "w").write("\n".join(box) + "\n")
    old = os.path.join(proj, "CUSTOM_ITEMS.md")
    if os.path.exists(old):
        os.remove(old)
    open(os.path.join(proj, "BUILD_REPORT_PROGRESSION.json"), "w").write(json.dumps(rep, indent=1, default=str))


if __name__ == "__main__":
    main(sys.argv[1])
