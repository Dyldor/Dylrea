"""Static checks of the generated cache: every used item/NPC definition decodes and its models exist."""
import sys, os, re, struct, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cache317 import Cache, archive, name_hash, split_defs, decode_obj, decode_npc, gunzip

proj = sys.argv[1]
c = Cache(os.path.join(proj, "client", "cache"))
cfg = archive(c.file(0, 2))
objs = split_defs(cfg[name_hash("obj.dat")], cfg[name_hash("obj.idx")])
npcs = split_defs(cfg[name_hash("npc.dat")], cfg[name_hash("npc.idx")])
seq_count = struct.unpack(">H", cfg[name_hash("seq.dat")][0:2])[0]
model_slots = len(c.idx[1]) // 6
VER = archive(c.file(0, 5))
model_version_len = len(VER[name_hash("model_version")]) // 2

_rm = open(os.path.join(proj, "client", "RetroModels.java")).read()
extra_ok = set(int(x) for x in re.search(r"IDS = \{([^}]*)\}", _rm).group(1).split(",") if x.strip())


def model_ok(m):
    if m >= model_version_len and m in extra_ok and c.file(1, m):
        return None
    if m < 0 or m >= model_version_len:
        return "id %d beyond the client's model table (%d)" % (m, model_version_len)
    raw = c.file(1, m)
    if not raw:
        return "model %d missing" % m
    d = gunzip(raw)
    if d[-2:] == b"\xff\xff":
        return "model %d is new-format" % m
    return None

problems = []
srv = os.path.join(proj, "server")
used_items = [int(x) for x in re.findall(r"(?m)^item = (\d+)", open(os.path.join(srv, "item.cfg"), encoding="latin-1").read())]
checked = 0
for i in used_items:
    if i < 7956 or i >= len(objs) or objs[i] == b"\x00":
        continue
    ops = dict(decode_obj(objs[i]))
    for op in (1, 23, 24, 25, 26, 78, 79, 90, 91, 92, 93):
        v = ops.get(op)
        if v is None:
            continue
        m = v[0] if isinstance(v, tuple) else v
        err = model_ok(m)
        if err:
            problems.append("item %d %s: %s" % (i, ops.get(2), err))
    checked += 1
custom = [l.split("\t") for l in open(os.path.join(srv, "customnpcs.cfg")) if l.startswith("customnpc")]
for row in custom:
    nid = int(row[0].split("=")[1])
    d = decode_npc(npcs[nid])
    for m in d.get("models", []) + d.get("heads", []):
        err = model_ok(m)
        if err:
            problems.append("npc %d %s: %s" % (nid, d.get("name"), err))
    for k in ("stand", "walk"):
        if d.get(k, 0) >= seq_count and d.get(k, 0) != 65535:
            problems.append("npc %d anim %s=%d beyond %d" % (nid, k, d[k], seq_count))
    if nid > 4095:
        problems.append("npc %d does not fit in 12 bits" % nid)
# config files against what GodzHell's loaders read
def rows_of(fname, key):
    for l in open(os.path.join(srv, fname), encoding="latin-1"):
        l = l.strip()
        m = re.match(r"%s\s*=\s*(.*)$" % key, l)
        if m:
            yield re.sub(r"\t+", "\t", m.group(1)).split("\t")
def ints_ok(p, n):
    try:
        [int(x) for x in p[:n]]; return True
    except ValueError:
        return False
for p in rows_of(os.path.join("Config", "objects.cfg"), "object"):
    if len(p) < 7 or not ints_ok(p, 6) or p[6] not in ("true", "false"):
        problems.append("objects.cfg line needs 7 fields: " + "\t".join(p)[:60])
for p in rows_of("WorldObjects.cfg", "object"):
    if len(p) < 6 or not ints_ok(p, 6):
        problems.append("WorldObjects.cfg line: " + "\t".join(p)[:60])
for p in rows_of("autospawn.cfg", "spawn"):
    if len(p) < 9 or not ints_ok(p, 9):
        problems.append("autospawn.cfg line: " + "\t".join(p)[:60])
for p in rows_of("npc.cfg", "npc"):
    if len(p) < 4 or not ints_ok([p[0], p[2], p[3]], 3):
        problems.append("npc.cfg line: " + "\t".join(p)[:60])
for p in rows_of("shops.cfg", "shop"):
    if len(p) < 6 or not ints_ok([p[0], p[2], p[3]] + p[4:], 3 + len(p[4:])):
        problems.append("shops.cfg line: " + "\t".join(p)[:60])
for p in rows_of("item.cfg", "item"):
    try:
        int(p[0]); [float(x) for x in p[-15:]]
    except (ValueError, IndexError):
        problems.append("item.cfg line: " + "\t".join(p)[:60])

print(json.dumps({"item defs checked": checked, "custom npcs checked": len(custom), "objs": len(objs), "npcs": len(npcs),
                  "seq count": seq_count, "model table": model_version_len, "problems": problems[:40], "problem count": len(problems)}, indent=1))
