"""Minimal 317 test client: logs in, sends commands and button clicks, then logs out."""
import socket, struct, sys, time, random

MASK = 0xFFFFFFFF


class ISAAC:
    def __init__(self, seed):
        self.mem = [0] * 256; self.rsl = [0] * 256; self.a = self.b = self.c = 0; self.count = 0
        for i, s in enumerate(seed):
            self.rsl[i] = s & MASK
        self._init()

    def _mix(self, v):
        a, b, c, d, e, f, g, h = v
        a ^= (b << 11) & MASK; d = (d + a) & MASK; b = (b + c) & MASK
        b ^= c >> 2; e = (e + b) & MASK; c = (c + d) & MASK
        c ^= (d << 8) & MASK; f = (f + c) & MASK; d = (d + e) & MASK
        d ^= e >> 16; g = (g + d) & MASK; e = (e + f) & MASK
        e ^= (f << 10) & MASK; h = (h + e) & MASK; f = (f + g) & MASK
        f ^= g >> 4; a = (a + f) & MASK; g = (g + h) & MASK
        g ^= (h << 8) & MASK; b = (b + g) & MASK; h = (h + a) & MASK
        h ^= a >> 9; c = (c + h) & MASK; a = (a + b) & MASK
        return [a, b, c, d, e, f, g, h]

    def _init(self):
        v = [0x9e3779b9] * 8
        for _ in range(4):
            v = self._mix(v)
        for src in (self.rsl, self.mem):
            for i in range(0, 256, 8):
                v = [(v[k] + src[i + k]) & MASK for k in range(8)]
                v = self._mix(v)
                self.mem[i:i + 8] = v
        self._isaac(); self.count = 256

    def _isaac(self):
        self.c = (self.c + 1) & MASK
        self.b = (self.b + self.c) & MASK
        for i in range(256):
            x = self.mem[i]
            m = i & 3
            if m == 0: self.a ^= (self.a << 13) & MASK
            elif m == 1: self.a ^= self.a >> 6
            elif m == 2: self.a ^= (self.a << 2) & MASK
            else: self.a ^= self.a >> 16
            self.a = (self.mem[(i + 128) & 255] + self.a) & MASK
            y = (self.mem[(x >> 2) & 255] + self.a + self.b) & MASK
            self.mem[i] = y
            self.b = (self.mem[(y >> 10) & 255] + x) & MASK
            self.rsl[i] = self.b

    def next(self):
        if self.count == 0:
            self._isaac(); self.count = 256
        self.count -= 1
        return self.rsl[self.count]


def main(host, port, name, password, script):
    s = socket.create_connection((host, port), timeout=10)
    s.sendall(bytes([14, 0]))
    resp = b""
    while len(resp) < 17:
        resp += s.recv(17 - len(resp))
    server_key = struct.unpack(">q", resp[9:17])[0]
    client_key = random.getrandbits(62)
    enc = bytes([10]) + struct.pack(">qq", client_key, server_key) + struct.pack(">i", 1234) + name.encode() + b"\n" + password.encode() + b"\n"
    payload = bytes([255]) + struct.pack(">H", 317) + bytes([0]) + b"\0" * 36 + bytes([len(enc)]) + enc
    s.sendall(bytes([16, len(payload)]) + payload)
    r = s.recv(3)
    print("login response", list(r))
    if not r or r[0] != 2:
        return 1
    seed = [(client_key >> 32) & MASK, client_key & MASK, (server_key >> 32) & MASK, server_key & MASK]
    out = ISAAC(seed)
    s.settimeout(0.5)
    got = 0

    def drain(sec):
        nonlocal got
        end = time.time() + sec
        while time.time() < end:
            try:
                d = s.recv(65536)
                if not d:
                    raise SystemExit("server closed the connection")
                got += len(d)
            except socket.timeout:
                pass

    def command(text):
        body = text.encode() + b"\n"
        s.sendall(bytes([(103 + out.next()) & 0xFF, len(body)]) + body)
        print("sent ::" + text)
        drain(1.2)

    def button(bid):
        s.sendall(bytes([(185 + out.next()) & 0xFF]) + struct.pack(">H", bid))
        print("clicked button", bid)
        drain(1.2)

    drain(4)
    print("bytes received after login:", got)
    for step in script:
        if isinstance(step, int):
            button(step)
        else:
            command(step)
    drain(2)
    s.close()
    print("total bytes received:", got)
    return 0


if __name__ == "__main__":
    steps = ["menu", 2494, 2494, 2494, "tiers", "progress", "slayer", 2494, "task", "event", "help", "tp market", "teleports", 2498, 2498, "home"]
    sys.exit(main("127.0.0.1", 43594, sys.argv[1] if len(sys.argv) > 1 else "testbot", "testpass", steps))
