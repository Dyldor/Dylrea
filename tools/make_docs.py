"""ZONES.md and SHOPS.md from the final server config files."""
import os, re, sys
proj = sys.argv[1]
srv = os.path.join(proj, "server")
names = {}
for l in open(os.path.join(srv, "item.cfg"), encoding="latin-1"):
    m = re.match(r"item = (\d+)\t(\S+)", l)
    if m:
        names[int(m.group(1))] = m.group(2).replace("_", " ")
Z = ["# Teleports", "", "Open the menu with the Rift Guide at home or `::teleports`. `::tp <number>` and `::tp <name>` also work.", "",
     "| # | Menu section | Destination |", "|---:|---|---|"]
for l in open(os.path.join(srv, "zones.cfg")):
    if l.startswith("zone"):
        p = l.split("=", 1)[1].strip().split("\t")
        Z.append("| %s | %s | %s |" % (p[0], p[1], p[5]))
open(os.path.join(proj, "ZONES.md"), "w").write("\n".join(Z) + "\n")
S = ["# Shops", "", "Vanilla weapons and armour were taken out of every shop; the progression gear comes from custom NPCs.", "",
     "| Shop | Items |", "|---|---|"]
for l in open(os.path.join(srv, "shops.cfg"), encoding="latin-1"):
    if l.startswith("shop"):
        p = [x for x in l.split("=", 1)[1].strip().split("\t") if x]
        nm = re.sub(r"@\w\w\w@", "", p[1]).replace("_", " ").strip()
        its = [names.get(int(a), a) for a in p[4::2]]
        S.append("| %s | %s |" % (nm, ", ".join(its[:12]) + (" ..." if len(its) > 12 else "")))
open(os.path.join(proj, "SHOPS.md"), "w").write("\n".join(S) + "\n")
print("docs written")
