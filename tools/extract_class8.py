"""Extract hardcoded custom item blocks (if(i == N){...}) from Delta-era Class8.java clients."""
import re, sys, json, hashlib
FIELD = {"aString170":"name","aByteArray178":"examine","anInt174":"model","anInt181":"zoom2d","anInt190":"rotX","anInt198":"rotY",
 "anInt204":"rotZ","anInt169":"offX","anInt194":"offY","anInt165":"maleWield","anInt200":"femaleWield","anInt188":"maleWield2",
 "anInt164":"femaleWield2","anInt175":"maleHead","anInt197":"femaleHead","anInt185":"maleEquipOffset","anInt162":"femaleEquipOffset",
 "anInt179":"certTemplate","anInt163":"certID","anInt155":"value","aBoolean176":"members","anInt161":"stackable"}
def blocks(src):
    src = src.replace("\r","")
    # only look inside forID-style method: after "aClass8Array172[j].anInt157 == i" region we find if(i == N) blocks
    for m in re.finditer(r"if\s*\(\s*i\s*==\s*(\d+)\s*\)\s*\{", src):
        start = m.end(); depth = 1; k = start
        while depth and k < len(src):
            if src[k] == "{": depth += 1
            elif src[k] == "}": depth -= 1
            k += 1
        body = src[start:k-1]
        if "class8." not in body: continue
        yield int(m.group(1)), body
def parse(body):
    d = {}
    for f, key in FIELD.items():
        mm = re.findall(r"class8\.%s\s*=\s*([^;]+);" % f, body)
        if mm: d[key] = mm[-1].strip()
    for key, arr in (("name", "aString170"), ("examine", "aByteArray178")):
        if key in d: d[key] = re.sub(r'^"|"(\.getBytes\(\))?$', "", d[key])
    o = dict(re.findall(r"class8\.anIntArray156\[(\d+)\]\s*=\s*(-?\d+);", body))
    n = dict(re.findall(r"class8\.anIntArray160\[(\d+)\]\s*=\s*(-?\d+);", body))
    if o: d["recolor"] = [[int(o[i]), int(n.get(i, 0))] for i in sorted(o, key=int)]
    acts = re.findall(r"class8\.aStringArray189\[(\d)\]\s*=\s*\"([^\"]*)\"", body)
    if acts: d["actions"] = {int(a): b for a, b in acts}
    d["_hash"] = hashlib.md5(re.sub(r"\s+", "", body).encode()).hexdigest()[:10]
    return d
if __name__ == "__main__":
    out = {}
    for path in sys.argv[1:]:
        out[path] = {i: parse(b) for i, b in blocks(open(path, errors="ignore").read())}
    json.dump(out, sys.stdout, indent=1)
