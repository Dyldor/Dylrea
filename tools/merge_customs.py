"""Merge hardcoded custom items from other Delta-era clients into a base client + server.

Client: copies `if(i == N){...}` blocks from donor Class8.java files into the base Class8.method198.
Server: appends matching `item = ...` lines from the donor servers' item.cfg to the base item.cfg.

Rules
- An incoming item whose name already exists in the base (any ID) is a duplicate and is skipped.
- An incoming item keeps its ID when the base has no custom block and no item.cfg entry for that ID.
- Otherwise (ID clash with a different base item, or it would overwrite a stock item) it is moved
  to a fresh ID starting at NEW_ID_START, so stock items and existing customs stay intact.
Writes a TSV report of every decision.
"""
import re, sys, json, os, difflib

NEW_ID_START = 20000


def norm(s):
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def find_blocks(src):
    """Yield (id, start_of_if, end_after_brace, body) for if(i == N){...} blocks that set class8 fields."""
    for m in re.finditer(r"if\s*\(\s*i\s*==\s*(\d+)\s*\)\s*\{", src):
        k, depth = m.end(), 1
        while depth and k < len(src):
            c = src[k]
            if c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
            k += 1
        body = src[m.end():k - 1]
        if "class8." in body or re.search(r"\b(Jukky\w+|NEO|NewColor|Zoom|Models)\s*\(", body):
            yield int(m.group(1)), m.start(), k, body


def block_name(body):
    m = re.search(r'aString170\s*=\s*"([^"]*)"', body) or re.search(r'Jukkyname\s*\(\s*"([^"]*)"', body) \
        or re.search(r'NEO\s*\(\s*"([^"]*)"', body)
    return m.group(1).strip() if m else None


def load_cfg(path):
    items = {}
    for line in open(path, errors="ignore"):
        line = line.rstrip("\r\n")
        m = re.match(r"\s*item\s*=\s*(\d+)\s+(\S.*)$", line)
        if m:
            items.setdefault(int(m.group(1)), line)
    return items


def cfg_name(line):
    parts = re.split(r"\t+", re.sub(r"^\s*item\s*=\s*", "", line))
    return parts[1].replace("_", " ") if len(parts) > 1 else None


def main(cfg_path):
    cfg = json.load(open(cfg_path))
    base_client = open(cfg["base_client"], encoding="latin-1").read().replace("\r\n", "\n")
    base_cfg_lines = open(cfg["base_item_cfg"], encoding="latin-1").read().replace("\r\n", "\n")
    base_cfg = load_cfg(cfg["base_item_cfg"])

    base_blocks = {i: b for i, _, _, b in find_blocks(base_client)}
    taken_ids = set(base_blocks) | set(base_cfg)
    base_names = {norm(block_name(b)) for b in base_blocks.values() if block_name(b)}
    base_names |= {norm(cfg_name(l)) for l in base_cfg.values() if cfg_name(l)}

    donor_cfgs = [load_cfg(p) for p in cfg["donor_item_cfgs"]]
    next_id = NEW_ID_START
    added_blocks, added_cfg, report = [], [], []

    for donor in cfg["donor_clients"]:
        src = open(donor, encoding="latin-1").read().replace("\r\n", "\n")
        label = donor.split("/servers/")[-1].split("/")[0]
        for iid, _, _, body in find_blocks(src):
            name = block_name(body)
            key = norm(name)
            if not name:
                report.append((label, iid, "", "skip", "no name in block"))
                continue
            if key in base_names:
                report.append((label, iid, name, "skip", "duplicate name already present"))
                continue
            same_id = block_name(base_blocks[iid]) if iid in base_blocks and block_name(base_blocks[iid]) \
                else (cfg_name(base_cfg[iid]) if iid in base_cfg else None)
            if same_id and difflib.SequenceMatcher(None, key, norm(same_id)).ratio() >= 0.75:
                report.append((label, iid, name, "skip", "same item as base '%s' at this id" % same_id))
                continue
            # source item.cfg line for this donor ID (first donor cfg that names it the same, else any)
            src_line = None
            for dc in donor_cfgs:
                ln = dc.get(iid)
                if ln and norm(cfg_name(ln)) == key:
                    src_line = ln
                    break
            if iid in taken_ids:
                new_id = next_id
                while new_id in taken_ids:
                    new_id += 1
                next_id = new_id + 1
                why = "id clash with base item '%s'" % (block_name(base_blocks[iid]) if iid in base_blocks
                                                       else cfg_name(base_cfg.get(iid, "")) or "?")
            else:
                new_id, why = iid, "kept id"
            taken_ids.add(new_id)
            base_names.add(key)
            new_body = body
            added_blocks.append("        if(i == %d) { // %s, from %s (orig id %d)\n%s\n        }\n"
                                % (new_id, name, label, iid, new_body.strip("\n")))
            if src_line:
                line = re.sub(r"^\s*item\s*=\s*\d+", "item = %d" % new_id, src_line)
            else:
                line = "item = %d\t%s\tA_custom_item.\t10000\t10000\t10000\t0\t0\t0\t0\t0\t0\t0\t0\t0\t0\t0\t0" % (
                    new_id, name.replace(" ", "_"))
            added_cfg.append(line)
            report.append((label, iid, name, "add as %d" % new_id, why + ("" if src_line else "; server stats defaulted")))

    # insert client blocks just before method198's `return class8;`
    m198 = base_client.index("public static final Class8 method198(int i)")
    ret = base_client.index("return class8;", m198)
    marker = "        // ---- merged custom items (tools/merge_customs.py) ----\n"
    out_client = base_client[:ret] + marker + "".join(added_blocks) + "        " + base_client[ret:]
    # append server cfg lines before [ENDOFITEMLIST]
    end = base_cfg_lines.rindex("[ENDOFITEMLIST]")
    out_cfg = base_cfg_lines[:end].rstrip("\n") + "\n" + "\n".join(added_cfg) + "\n" + base_cfg_lines[end:]

    open(cfg["out_client"], "w", encoding="latin-1").write(out_client.replace("\n", "\r\n"))
    open(cfg["out_item_cfg"], "w", encoding="latin-1").write(out_cfg.replace("\n", "\r\n"))
    with open(cfg["report"], "w") as f:
        f.write("source\torig_id\tname\tdecision\treason\n")
        for r in report:
            f.write("\t".join(map(str, r)) + "\n")
    adds = sum(1 for r in report if r[3].startswith("add"))
    print("added %d items (%d moved to new IDs), skipped %d" % (
        adds, sum(1 for r in report if r[3].startswith("add") and "clash" in r[4]), len(report) - adds))


if __name__ == "__main__":
    main(sys.argv[1])
