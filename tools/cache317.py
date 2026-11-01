"""Minimal read-only reader for a 317 cache (main_file_cache.dat + idxN) and its JAG archives."""
import bz2, struct, sys


class Cache:
    def __init__(self, d):
        self.dat = open(d + "/main_file_cache.dat", "rb").read()
        self.idx = [open(d + "/main_file_cache.idx%d" % i, "rb").read() for i in range(5)]

    def file(self, index, fid):
        ix = self.idx[index]
        if fid * 6 + 6 > len(ix):
            return None
        e = ix[fid * 6: fid * 6 + 6]
        size = (e[0] << 16) | (e[1] << 8) | e[2]
        sector = (e[3] << 16) | (e[4] << 8) | e[5]
        out, part = bytearray(), 0
        while len(out) < size and sector:
            blk = self.dat[sector * 520: sector * 520 + 520]
            take = min(size - len(out), 512)
            out += blk[8:8 + take]
            sector = (blk[4] << 16) | (blk[5] << 8) | blk[6]
            part += 1
        return bytes(out)


def unbz(data, size):
    return bz2.decompress(b"BZh1" + data)[:size]


def archive(raw):
    """Return {name_hash: bytes} for a JAG archive."""
    def u24(b, o):
        return (b[o] << 16) | (b[o + 1] << 8) | b[o + 2]
    usize, csize = u24(raw, 0), u24(raw, 3)
    buf, whole = raw[6:], False
    if usize != csize:
        buf, whole = unbz(raw[6:6 + csize], usize), True
    n = struct.unpack(">H", buf[0:2])[0]
    off, out, pos = 2, {}, 2 + n * 10
    for _ in range(n):
        h = struct.unpack(">i", buf[off:off + 4])[0]
        us, cs = u24(buf, off + 4), u24(buf, off + 7)
        off += 10
        data = buf[pos:pos + cs]
        out[h] = data if whole else unbz(data, us)
        pos += cs
    return out


def name_hash(s):
    h = 0
    for c in s.upper():
        h = (h * 61 + ord(c) - 32) & 0xFFFFFFFF
    return h - (1 << 32) if h & 0x80000000 else h


def config_counts(cache_dir):
    c = Cache(cache_dir)
    cfg = archive(c.file(0, 2))
    counts = {}
    for name in ("obj.idx", "npc.idx", "loc.idx"):
        b = cfg.get(name_hash(name))
        counts[name] = struct.unpack(">H", b[0:2])[0] if b else None
    return counts


if __name__ == "__main__":
    print(config_counts(sys.argv[1]))


# ---------------------------------------------------------------- map reading
import gzip, zlib


def gunzip(raw):
    return zlib.decompressobj(31).decompress(raw)


class Buf:
    def __init__(self, b):
        self.b, self.p = b, 0

    def u8(self):
        v = self.b[self.p]; self.p += 1; return v

    def u16(self):
        v = (self.b[self.p] << 8) | self.b[self.p + 1]; self.p += 2; return v

    def smart(self):
        return self.u8() - 0 if self.b[self.p] < 128 else self.u16() - 32768


class World:
    """Tile occupancy from 317 map files: blocked terrain and tiles holding objects."""

    def __init__(self, cache_dir):
        self.c = Cache(cache_dir)
        ver = archive(self.c.file(0, 5))
        mi = ver[name_hash("map_index")]
        self.regions = {}
        for o in range(0, len(mi) - 6, 7):
            rid, mf, lf = struct.unpack(">HHH", mi[o:o + 6])
            self.regions[rid] = (mf, lf)
        self.cache = {}

    def _load(self, rid):
        if rid in self.cache:
            return self.cache[rid]
        blocked, objects = set(), set()
        entry = self.regions.get(rid)
        if entry:
            mf, lf = entry
            raw = self.c.file(4, mf)
            if raw:
                try:
                    b = Buf(gunzip(raw))
                    for z in range(4):
                        for x in range(64):
                            for y in range(64):
                                while True:
                                    op = b.u8()
                                    if op == 0:
                                        break
                                    if op == 1:
                                        b.u8(); break
                                    if op <= 49:
                                        b.u8()
                                    elif op <= 81:
                                        if (op - 49) & 1:
                                            blocked.add((x, y, z))
                except Exception:
                    pass
            raw = self.c.file(4, lf)
            if raw:
                try:
                    b = Buf(gunzip(raw))
                    oid = -1
                    while True:
                        d = b.smart()
                        if d == 0:
                            break
                        oid += d
                        pos = 0
                        while True:
                            dp = b.smart()
                            if dp == 0:
                                break
                            pos += dp - 1
                            otype = b.u8() >> 2  # type/rotation
                            if otype <= 3 or otype in (9, 10, 11):  # walls and solid objects; 22 = ground decor
                                objects.add(((pos >> 6) & 63, pos & 63, pos >> 12))
                except Exception:
                    pass
        self.cache[rid] = (blocked, objects, entry is not None)
        return self.cache[rid]

    def known(self, x, y):
        return self._load(((x >> 6) << 8) | (y >> 6))[2]

    def free(self, x, y, z=0):
        blocked, objects, ok = self._load(((x >> 6) << 8) | (y >> 6))
        t = (x & 63, y & 63, z)
        return ok and t not in blocked and t not in objects

    def nearest_free(self, x, y, z=0, radius=4):
        best = None
        for r in range(radius + 1):
            for dx in range(-r, r + 1):
                for dy in range(-r, r + 1):
                    if max(abs(dx), abs(dy)) == r and self.free(x + dx, y + dy, z):
                        return (x + dx, y + dy)
        return best


# ---------------------------------------------------------------- item definitions (obj.dat)
def _str(b, p):
    e = b.index(10, p)
    return b[p:e].decode("latin-1"), e + 1


def decode_obj(b):
    """Decode one obj.dat entry into an ordered list of (opcode, value). Handles 317 opcodes plus 114/115."""
    ops, p = [], 0
    u8 = lambda: b[p]
    while True:
        op = b[p]; p += 1
        if op == 0:
            return ops
        if op in (1, 4, 5, 6, 7, 8, 23, 24, 25, 26, 78, 79, 90, 91, 92, 93, 95, 97, 98, 110, 111, 112):
            v = (b[p] << 8) | b[p + 1]; p += 2
            if op == 23 or op == 25:
                v = (v, b[p]); p += 1
        elif op in (2, 3):
            v, p = _str(b, p)
        elif op in (11, 16):
            v = None
        elif op == 12:
            v = struct.unpack(">i", b[p:p + 4])[0]; p += 4
        elif op == 10:
            v = (b[p] << 8) | b[p + 1]; p += 2
        elif 30 <= op < 40:
            v, p = _str(b, p)
        elif op == 40:
            n = b[p]; p += 1
            v = [((b[p + 4 * k] << 8) | b[p + 4 * k + 1], (b[p + 4 * k + 2] << 8) | b[p + 4 * k + 3]) for k in range(n)]
            p += 4 * n
        elif 100 <= op < 110:
            v = ((b[p] << 8) | b[p + 1], (b[p + 2] << 8) | b[p + 3]); p += 4
        elif op in (113, 114, 115):
            v = b[p]; p += 1
        else:
            raise ValueError("unknown obj opcode %d at %d" % (op, p - 1))
        ops.append((op, v))


SUPPORTED_OBJ = set(range(0, 13)) | {16, 23, 24, 25, 26} | set(range(30, 41)) | {78, 79, 90, 91, 92, 93, 95, 97, 98} | \
    set(range(100, 114))


def encode_obj(ops, remap=None):
    out = bytearray()
    for op, v in ops:
        if op not in SUPPORTED_OBJ:
            continue
        if remap and op in remap and v is not None:
            v = remap[op](v)
        out.append(op)
        if op in (1, 4, 5, 6, 7, 8, 24, 26, 78, 79, 90, 91, 92, 93, 95, 97, 98, 110, 111, 112, 10):
            out += struct.pack(">H", v & 0xFFFF)
        elif op in (23, 25):
            out += struct.pack(">HB", v[0] & 0xFFFF, v[1] & 0xFF)
        elif op in (2, 3) or 30 <= op < 40:
            out += v.encode("latin-1") + b"\n"
        elif op in (11, 16):
            pass
        elif op == 12:
            out += struct.pack(">i", v)
        elif op == 40:
            out.append(len(v))
            for a, c in v:
                out += struct.pack(">HH", a, c)
        elif 100 <= op < 110:
            out += struct.pack(">HH", v[0] & 0xFFFF, v[1] & 0xFFFF)
        elif op in (113, 114, 115):
            out.append(v & 0xFF)
    out.append(0)
    return bytes(out)


def split_defs(dat, idx):
    n = struct.unpack(">H", idx[0:2])[0]
    sizes = [struct.unpack(">H", idx[2 + 2 * k: 4 + 2 * k])[0] for k in range(n)]
    out, p = [], 2
    for s in sizes:
        out.append(dat[p:p + s]); p += s
    return out


def join_defs(entries):
    dat = bytearray(struct.pack(">H", len(entries)))
    idx = bytearray(struct.pack(">H", len(entries)))
    for e in entries:
        dat += e; idx += struct.pack(">H", len(e))
    return bytes(dat), bytes(idx)


# ---------------------------------------------------------------- writing
def pack_archive(files):
    """files: list of (name, bytes). Each file bzip2'd individually (BZh1, header stripped)."""
    hdr = bytearray(struct.pack(">H", len(files)))
    body = bytearray()
    for name, data in files:
        comp = bz2.compress(data, 1)[4:]
        hdr += struct.pack(">i", name_hash(name) if isinstance(name, str) else name)
        hdr += len(data).to_bytes(3, "big") + len(comp).to_bytes(3, "big")
        body += comp
    raw = bytes(hdr + body)
    return len(raw).to_bytes(3, "big") + len(raw).to_bytes(3, "big") + raw


def archive_names(raw):
    """Name hashes of an archive in their original order."""
    def u24(b, o):
        return (b[o] << 16) | (b[o + 1] << 8) | b[o + 2]
    usize, csize = u24(raw, 0), u24(raw, 3)
    buf = raw[6:] if usize == csize else unbz(raw[6:6 + csize], usize)
    n = struct.unpack(">H", buf[0:2])[0]
    return [struct.unpack(">i", buf[2 + 10 * k: 6 + 10 * k])[0] for k in range(n)]


class CacheWriter:
    """Appends files to a 317 cache in place (main_file_cache.dat + idxN)."""

    def __init__(self, d):
        self.d = d

    def put(self, index, fid, data):
        datp = self.d + "/main_file_cache.dat"
        idxp = self.d + "/main_file_cache.idx%d" % index
        with open(datp, "r+b") as dat:
            dat.seek(0, 2)
            end = dat.tell()
            sector = max(1, (end + 519) // 520)
            first = sector
            chunk, pos = 0, 0
            while True:
                part = data[pos:pos + 512]
                pos += len(part)
                nxt = sector + 1 if pos < len(data) else 0
                hdr = struct.pack(">HH", fid & 0xFFFF, chunk) + nxt.to_bytes(3, "big") + bytes([index + 1])
                dat.seek(sector * 520)
                dat.write(hdr + part + b"\0" * (512 - len(part)))
                chunk += 1
                sector += 1
                if pos >= len(data):
                    break
        with open(idxp, "r+b") as ix:
            ix.seek(0, 2)
            if ix.tell() < fid * 6 + 6:
                ix.write(b"\0" * (fid * 6 + 6 - ix.tell()))
            ix.seek(fid * 6)
            ix.write(len(data).to_bytes(3, "big") + first.to_bytes(3, "big"))


# ---------------------------------------------------------------- model colours (old 317 format)
def model_colors(cache, model_id):
    """Counter of face colours (16-bit HSL) in an old-format model, or None."""
    import collections
    raw = cache.file(1, model_id)
    if not raw:
        return None
    try:
        d = gunzip(raw)
    except Exception:
        return None
    if len(d) < 18 or d[-2:] == b"\xff\xff":
        return None
    f = d[-18:]
    nv, nt = (f[0] << 8) | f[1], (f[2] << 8) | f[3]
    use_tex, prio, alpha, triskin, vskin = f[5], f[6], f[7], f[8], f[9]
    tri_len = (f[16] << 8) | f[17]
    off = nv + nt
    if prio == 255:
        off += nt
    if triskin == 1:
        off += nt
    if use_tex == 1:
        off += nt
    if vskin == 1:
        off += nv
    if alpha == 1:
        off += nt
    off += tri_len
    cols = collections.Counter()
    for k in range(nt):
        p = off + 2 * k
        if p + 2 > len(d) - 18:
            return None
        cols[(d[p] << 8) | d[p + 1]] += 1
    return cols


def hsl(c):
    return (c >> 10) & 63, (c >> 7) & 7, c & 127


def mkhsl(h, s, l):
    return ((h & 63) << 10) | ((s & 7) << 7) | (l & 127)


def decode_npc(b):
    """Decode one npc.dat entry (317 opcodes) into a dict."""
    d, p = {}, 0
    def u16():
        nonlocal p
        v = (b[p] << 8) | b[p + 1]; p += 2; return v
    def s():
        nonlocal p
        e = b.index(10, p); v = b[p:e].decode("latin-1"); p = e + 1; return v
    while p < len(b):
        op = b[p]; p += 1
        if op == 0:
            break
        if op == 1:
            n = b[p]; p += 1; d["models"] = [u16() for _ in range(n)]
        elif op == 2:
            d["name"] = s()
        elif op == 3:
            d["examine"] = s()
        elif op == 12:
            d["size"] = b[p]; p += 1
        elif op == 13:
            d["stand"] = u16()
        elif op == 14:
            d["walk"] = u16()
        elif op == 17:
            d["walk"], d["turn180"], d["turn90cw"], d["turn90ccw"] = u16(), u16(), u16(), u16()
        elif 30 <= op < 40:
            d.setdefault("actions", {})[op - 30] = s()
        elif op == 40:
            n = b[p]; p += 1; d["recolor"] = [(u16(), u16()) for _ in range(n)]
        elif op == 60:
            n = b[p]; p += 1; d["heads"] = [u16() for _ in range(n)]
        elif op in (90, 91, 92, 102, 103):
            u16()
        elif op == 93:
            d["minimap"] = False
        elif op == 95:
            d["combat"] = u16()
        elif op == 97:
            d["scaleXZ"] = u16()
        elif op == 98:
            d["scaleY"] = u16()
        elif op == 99:
            d["priority"] = True
        elif op in (100, 101):
            p += 1
        elif op == 106:
            u16(); u16(); n = b[p]; p += 1
            for _ in range(n + 1):
                u16()
        elif op == 107:
            d["clickable"] = False
        else:
            raise ValueError("npc opcode %d" % op)
    return d


# ---------------------------------------------------------------- model geometry (read-only) + colour rewrite
class Model:
    """Old-format 317 model: decodes vertices, triangles and colours; can rewrite face colours in place."""

    def __init__(self, data):
        d = self.data = bytearray(data)
        if len(d) < 18 or d[-2:] == b"\xff\xff":
            raise ValueError("not an old-format model")
        f = d[-18:]
        self.nv, self.nt = (f[0] << 8) | f[1], (f[2] << 8) | f[3]
        self.ntex, tex, prio, alpha, tskin, vskin = f[4], f[5], f[6], f[7], f[8], f[9]
        xl, yl, zl, tl = [(f[10 + 2 * k] << 8) | f[11 + 2 * k] for k in range(4)]
        k = 0
        o_flags = k; k += self.nv
        o_ctype = k; k += self.nt
        if prio == 255:
            k += self.nt
        if tskin == 1:
            k += self.nt
        o_ftype = k
        if tex == 1:
            k += self.nt
        if vskin == 1:
            k += self.nv
        if alpha == 1:
            k += self.nt
        o_tri = k; k += tl
        self.o_col = k; k += self.nt * 2
        k += self.ntex * 6
        o_x = k; k += xl
        o_y = k; k += yl
        o_z = k; k += zl
        if k != len(d) - 18:
            raise ValueError("model layout mismatch")
        self.textured = tex == 1
        self.ftype = [d[o_ftype + i] for i in range(self.nt)] if tex == 1 else [0] * self.nt

        def smart(p):
            v = d[p]
            if v < 128:
                return v - 64, p + 1
            return ((v << 8) | d[p + 1]) - 49152, p + 2
        xs, ys, zs = [], [], []
        x = y = z = 0
        px, py, pz = o_x, o_y, o_z
        for i in range(self.nv):
            fl = d[o_flags + i]
            dx = dy = dz = 0
            if fl & 1:
                dx, px = smart(px)
            if fl & 2:
                dy, py = smart(py)
            if fl & 4:
                dz, pz = smart(pz)
            x += dx; y += dy; z += dz
            xs.append(x); ys.append(y); zs.append(z)
        self.xs, self.ys, self.zs = xs, ys, zs
        tris = []
        a = b = c = last = 0
        p = o_tri
        for i in range(self.nt):
            t = d[o_ctype + i]
            if t == 1:
                v, p = smart(p); a = v + last; last = a
                v, p = smart(p); b = v + last; last = b
                v, p = smart(p); c = v + last; last = c
            elif t == 2:
                b = c
                v, p = smart(p); c = v + last; last = c
            elif t == 3:
                a = c
                v, p = smart(p); c = v + last; last = c
            elif t == 4:
                a, b = b, a
                v, p = smart(p); c = v + last; last = c
            else:
                raise ValueError("bad triangle type %d" % t)
            if not (0 <= a < self.nv and 0 <= b < self.nv and 0 <= c < self.nv):
                raise ValueError("triangle index out of range")
            tris.append((a, b, c))
        self.tris = tris

    def color(self, i):
        p = self.o_col + 2 * i
        return (self.data[p] << 8) | self.data[p + 1]

    def set_color(self, i, c):
        p = self.o_col + 2 * i
        self.data[p] = (c >> 8) & 0xFF
        self.data[p + 1] = c & 0xFF

    def face_height(self):
        """0 at the top of the model, 1 at the bottom (317 models: negative y is up)."""
        cy = [(self.ys[a] + self.ys[b] + self.ys[c]) / 3.0 for a, b, c in self.tris]
        if not cy:
            return []
        lo, hi = min(cy), max(cy)
        span = (hi - lo) or 1.0
        return [(v - lo) / span for v in cy]


def recolor_model(data, scheme):
    """Return new model bytes with face colours rewritten.

    scheme: {"type": "bands", "colors": [(h,s), (h,s)], "bands": n, "light": shift}
            {"type": "gradient", "hues": [...], "sat": s, "light": shift}
            {"type": "solid", "hue": h, "sat": s, "light": shift}
    Lightness of each face is kept (plus the shift), so shading and detail survive.
    Textured faces (colour is a texture id) are left alone.
    """
    m = Model(data)
    hgt = m.face_height()
    shift = scheme.get("light", 0)
    if scheme["type"] == "duo":
        # main colour on the lighter half of the faces, trim colour on the darker half (keeps the mesh's detail)
        ls = sorted(hsl(m.color(i))[2] for i in range(m.nt) if not (m.textured and (m.ftype[i] & 2)))
        med = ls[len(ls) // 2] if ls else 64
        (h1, s1), (h2, s2) = scheme["colors"]
        l1, l2 = scheme.get("band_light", [0, 0])
        for i in range(m.nt):
            if m.textured and (m.ftype[i] & 2):
                continue
            h, s, l = hsl(m.color(i))
            if l >= med:
                m.set_color(i, mkhsl(h1, s1, max(4, min(124, l + shift + l1))))
            else:
                m.set_color(i, mkhsl(h2, s2, max(4, min(124, l + shift + l2))))
        return bytes(m.data)
    for i in range(m.nt):
        if m.textured and (m.ftype[i] & 2):
            continue
        h, s, l = hsl(m.color(i))
        nl = max(4, min(124, l + shift))
        t = hgt[i]
        if scheme["type"] == "bands":
            cols = scheme["colors"]
            k = int(t * scheme.get("bands", 6)) % len(cols)
            nh, ns = cols[k]
            nl = max(4, min(124, l + shift + scheme.get("band_light", [0] * len(cols))[k]))
        elif scheme["type"] == "gradient":
            hues = scheme["hues"]
            nh, ns = hues[min(len(hues) - 1, int(t * len(hues)))], scheme.get("sat", 7)
        else:
            nh, ns = scheme["hue"], scheme.get("sat", 6)
        m.set_color(i, mkhsl(nh, ns, nl))
    return bytes(m.data)
