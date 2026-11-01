"""Extract command-based teleports (::name -> x,y,h) from Delta-era server client.java files."""
import re, sys, glob, os, json
CMD = re.compile(r'command\.(?:equalsIgnoreCase|equals|startsWith)\(\s*"([^"]+)"\s*\)')
TX = re.compile(r'\bteleportToX\s*=\s*(\d+)\s*;'); TY = re.compile(r'\bteleportToY\s*=\s*(\d+)\s*;')
TH = re.compile(r'\bheightLevel\s*=\s*(\d+)\s*;')
def extract(path):
    src = open(path, encoding="latin-1").read().replace("\r", "")
    out = []
    for m in CMD.finditer(src):
        seg = src[m.end(): m.end() + 900]
        nxt = CMD.search(seg)
        if nxt: seg = seg[:nxt.start()]
        x, y = TX.search(seg), TY.search(seg)
        if not (x and y): continue
        h = TH.search(seg)
        rights = re.search(r'playerRights\s*>=?\s*(\d)', src[max(0, m.start()-120): m.end()+60])
        out.append({"cmd": m.group(1).strip().lower(), "x": int(x.group(1)), "y": int(y.group(1)),
                    "h": int(h.group(1)) if h else 0, "staff": bool(rights and int(rights.group(1)) >= 1)})
    return out
if __name__ == "__main__":
    res = {}
    for s in sorted(os.listdir(sys.argv[1])):
        ps = sorted(glob.glob(os.path.join(sys.argv[1], s, "Server", "**", "client.java"), recursive=True), key=os.path.getsize)
        if ps: res[s] = extract(ps[-1])
    json.dump(res, open(sys.argv[2], "w"), indent=1)
    for s, t in res.items(): print(f"{s:<22} {len(t):>3}  " + " ".join(sorted({x['cmd'] for x in t if not x['staff']}))[:230])
