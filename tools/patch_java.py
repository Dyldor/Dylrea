"""Insert the RetroRemake hooks into the GodzHell server source. Safe to run more than once."""
import sys, os

MARK = "// RetroRemake"


def patch(path, edits):
    raw = open(path, encoding="latin-1", newline="").read()
    crlf = "\r\n" in raw
    s = raw.replace("\r\n", "\n")
    for name, anchor, after, insert, start_at in edits:
        if (MARK + " " + name) in s:
            print("  already patched:", name)
            continue
        base = s.index(start_at) if start_at else 0
        i = s.index(anchor, base)
        j = i + len(anchor) if after else i
        s = s[:j] + insert.replace("@@", MARK + " " + name) + s[j:]
        print("  patched:", name)
    open(path, "w", encoding="latin-1", newline="").write(s.replace("\n", "\r\n") if crlf else s)


def main(server_dir):
    p = lambda f: os.path.join(server_dir, f)
    print("client.java")
    patch(p("client.java"), [
        ("zones", "public void customCommand(String command) {", True,
         "\n\t\tif (RetroContent.handleCommand(this, command)) return; @@\n", None),
        ("market", "boolean PutNPCCoords = false;", True,
         "\n\t\t\t\tint retroShop = RetroContent.shopFor(server.npcHandler.npcs[NPCSlot]); @@\n"
         "\t\t\t\tif (retroShop > 0) { WanneShop = retroShop; PutNPCCoords = true; NPCID = -1; }\n",
         "case 155: //first Click npc"),
        ("mysterybox", "int ItemID = inStream.readUnsignedWordBigEndian();", True,
         "\n\t\t\t\tif (RetroContent.openBox(this, ItemID, ItemSlot)) break; @@\n",
         "case 122:\t// Call for burying bones"),
    ])
    print("NPCHandler.java")
    patch(p("NPCHandler.java"), [
        ("drops", "MonsterDropItem(i);", True, "\n\t\t\t\t\t\tRetroContent.dropExtra(this, i); @@\n", None),
    ])
    print("ObjectHandler.java")
    s = open(p("ObjectHandler.java"), encoding="latin-1", newline="").read()
    if 'loadObjects("config\\\\objects.cfg");' in s:
        s = s.replace('loadObjects("config\\\\objects.cfg");', 'loadObjects("Config/objects.cfg"); ' + MARK + " path works on every OS")
        open(p("ObjectHandler.java"), "w", encoding="latin-1", newline="").write(s)
        print("  patched: objects path")
    else:
        print("  already patched: objects path")


def replace_all(path, name, old, new):
    raw = open(path, encoding="latin-1", newline="").read()
    crlf = "\r\n" in raw
    s = raw.replace("\r\n", "\n")
    if (MARK + " " + name) in s:
        print("  already patched:", name); return
    n = s.count(old)
    if n == 0:
        raise SystemExit("anchor not found for %s in %s" % (name, path))
    s = s.replace(old, new.replace("@@", MARK + " " + name))
    open(path, "w", encoding="latin-1", newline="").write(s.replace("\n", "\r\n") if crlf else s)
    print("  patched: %s (%d place%s)" % (name, n, "s" if n > 1 else ""))


def main_v3(server_dir):
    p = lambda f: os.path.join(server_dir, f)
    print("NPC.java")
    patch(p("NPC.java"), [("visual", "public int npcType;", True, " public int retroVisual = -1; @@\n", None)])
    replace_all(p("NPC.java"), "hpbar", "str.writeByteS(HP); // Their current hp, for HP bar",
                "str.writeByteS(MaxHP > 255 ? Math.max(0, HP) * 200 / MaxHP : HP); // @@")
    replace_all(p("NPC.java"), "hpbarmax1", "str.writeByteC(MaxHP); // Their max hp, for HP bar",
                "str.writeByteC(MaxHP > 255 ? 200 : MaxHP); // @@")
    replace_all(p("NPC.java"), "hpbarmax2", "str.writeByte(MaxHP); // Their max hp, for HP bar",
                "str.writeByte(MaxHP > 255 ? 200 : MaxHP); // @@")
    print("NPCHandler.java")
    patch(p("NPCHandler.java"), [
        ("spawn", "npcs[slot] = newNPC;", False, "RetroContent.onSpawn(newNPC); @@\n\t\t", "public void newNPC(int npcType"),
        ("respawn", "int old1 = npcs[i].npcType;", True, "\n\t\t\t\t\t\tif (npcs[i].retroVisual >= 0) old1 = npcs[i].retroVisual; @@", None),
    ])
    replace_all(p("NPCHandler.java"), "npchit", "server.playerHandler.players[Player].hitDiff = hitDiff;",
                "hitDiff = RetroContent.npcHit(npcs[NPCID], hitDiff, server.playerHandler.players[Player]); // @@\n"
                "\t\t\t\t\t\tserver.playerHandler.players[Player].hitDiff = hitDiff;")
    print("Player.java")
    replace_all(p("Player.java"), "npctype", "str.writeBits(12, npc.npcType);",
                "str.writeBits(12, RetroContent.visualType(npc)); // @@")
    print("ItemHandler.java")
    replace_all(p("ItemHandler.java"), "itemlist", "public static int MaxListedItems = 10000;",
                "public static int MaxListedItems = 16000; // @@")
    replace_all(p("ItemHandler.java"), "itemlistloop", "for (int i = 0; i < 9999; i++) {",
                "for (int i = 0; i < MaxListedItems; i++) { // @@")
    print("client.java")
    replace_all(p("client.java"), "rangebonus", "int RangeBonus = playerBonus[5]; //Range Bonus",
                "int RangeBonus = playerBonus[4]; // @@: index 4 is the ranged attack bonus (5 is stab defence)")
    patch(p("client.java"), [
        ("anim-run", "public int GetRunAnim(int id) \n{", True, "\nid = RetroContent.weaponTemplate(id); @@", None),
        ("anim-walk", "public int GetWalkAnim(int id) \n{", True, "\nid = RetroContent.weaponTemplate(id); @@", None),
        ("anim-stand", "public int GetStandAnim(int id) \n{", True, "\nid = RetroContent.weaponTemplate(id); @@", None),
        ("anim-block", "public int GetBlockAnim(int id) \n{", True, "\nid = RetroContent.weaponTemplate(id); @@", None),
    ])
    replace_all(p("client.java"), "anim-attack", "public int GetWepAnim()\n{",
                "public int GetWepAnim() { // @@: new weapons borrow a template weapon's attack animation\n"
                "\tint worn = playerEquipment[playerWeapon];\n"
                "\tint tpl = RetroContent.weaponTemplate(worn);\n"
                "\tif (tpl == worn) return GetWepAnim0();\n"
                "\tplayerEquipment[playerWeapon] = tpl;\n"
                "\ttry { return GetWepAnim0(); } finally { playerEquipment[playerWeapon] = worn; }\n"
                "}\n"
                "public int GetWepAnim0()\n{")


def main_client(client_dir):
    print("client Class42_Sub1.java")
    patch(os.path.join(client_dir, "Class42_Sub1.java"), [
        ("models", 'byte abyte2[] = class44.method571("model_index", null);', False,
         "{ @@: allow the models listed in RetroModels (above the original model table)\n"
         "            int max = RetroModels.MAX + 1;\n"
         "            if (anIntArrayArray1364[0].length < max) {\n"
         "                int[] v = new int[max]; System.arraycopy(anIntArrayArray1364[0], 0, v, 0, anIntArrayArray1364[0].length); anIntArrayArray1364[0] = v;\n"
         "                byte[] b = new byte[max]; System.arraycopy(aByteArrayArray1342[0], 0, b, 0, aByteArrayArray1342[0].length); aByteArrayArray1342[0] = b;\n"
         "                int[] c = new int[max]; System.arraycopy(anIntArrayArray1365[0], 0, c, 0, anIntArrayArray1365[0].length); anIntArrayArray1365[0] = c;\n"
         "            }\n"
         "            for (int z = 0; z < RetroModels.IDS.length; z++) anIntArrayArray1364[0][RetroModels.IDS[z]] = 1;\n"
         "        }\n        ", None)])


def replace_after(path, name, start, old, new):
    """Replace the first `old` after `start` (once; marked so it is not repeated)."""
    raw = open(path, encoding="latin-1", newline="").read()
    crlf = "\r\n" in raw
    s = raw.replace("\r\n", "\n")
    if (MARK + " " + name) in s:
        print("  already patched:", name); return
    i = s.index(start)
    j = s.index(old, i)
    s = s[:j] + new.replace("@@", MARK + " " + name) + s[j + len(old):]
    open(path, "w", encoding="latin-1", newline="").write(s.replace("\n", "\r\n") if crlf else s)
    print("  patched:", name)


def main_v4(server_dir, client_dir):
    sv, cl = (lambda f: os.path.join(server_dir, f)), (lambda f: os.path.join(client_dir, f))
    print("v4 hooks")
    patch(sv("server.java"), [("events", "npcHandler.process();", True, " RetroContent.tick(); @@", None)])
    patch(sv("client.java"), [
        ("menu", "switch(actionButtonId) {", False, "if (RetroContent.handleButton(this, actionButtonId)) break; @@\n\t\t\t\t",
         "case 185:               //clicking most buttons"),
        ("homenpcs", "if (retroShop > 0) { WanneShop = retroShop; PutNPCCoords = true; NPCID = -1; }", True,
         "\n\t\t\t\tif (retroShop == 0 && RetroContent.npcClick(this, server.npcHandler.npcs[NPCSlot])) { NPCID = -1; } @@", None),
        ("magic", "if ((EnemyHP2 - hitDiff) < 0) {", False, "hitDiff = RetroContent.magicHit(this, hitDiff); @@\n\t\t\t\t\t", None),
        ("ranged", "playerMaxHit = (int)Math.floor(MaxHit);", True,
         "\n\t\tplayerMaxHit = RetroContent.rangedMax(this); @@: same formula as melee and magic", "public void CalculateRange() {"),
    ])
    patch(sv("NPCHandler.java"), [("basedrops", "public void MonsterDropItem(int NPCID)\n{", True,
                                     "\nif (RetroContent.skipBaseDrops(npcs[NPCID])) return; @@", None)])
    replace_after(sv("client.java"), "level150", "public int getLevelForXP(int exp) {", "for (int lvl = 1; lvl <= 99; lvl++) {",
                  "for (int lvl = 1; lvl <= 150; lvl++) { // @@")
    replace_after(sv("client.java"), "level150-cap", "public int getLevelForXP(int exp) {", "return 99;", "return 150; // @@")
    replace_after(sv("client.java"), "xpcap", "public boolean addSkillXP(int amount, int skill){", "playerXP[skill] > 2000000000",
                  "playerXP[skill] > 2100000000 /* @@: room for level 150 (2,033,749,558 xp) */")
    replace_after(cl("client.java"), "c-xptable", "anIntArray1019 = new int[99];", "anIntArray1019 = new int[99];",
                  "anIntArray1019 = new int[150]; // @@")
    replace_after(cl("client.java"), "c-xploop", "anIntArray1019 = new int[150];", "for(int j = 0; j < 99; j++)",
                  "for(int j = 0; j < 150; j++) // @@")
    replace_after(cl("client.java"), "c-levelloop", "anIntArray1044[k1] = 1;", "for(int k20 = 0; k20 < 98; k20++)",
                  "for(int k20 = 0; k20 < 149; k20++) // @@")


def main_v5(server_dir):
    sv = lambda f: os.path.join(server_dir, f)
    print("v5 hooks: accuracy, custom ranged weapons, levels past 99")
    start = "public boolean AttackNPC() {"
    replace_after(sv("client.java"), "custom-bows", start, "if(UseBow){",
                  "if (RetroContent.isRangedWeapon(playerEquipment[playerWeapon])) { PkingDelay = 5; wepdelay = 5; UseBow = true; } // @@\nif(UseBow){")
    replace_after(sv("client.java"), "ranged-maxhit", start, "hitDiff = misc.random(15);",
                  "hitDiff = misc.random(playerMaxHit); // @@: the ranged max hit was calculated but ignored")
    replace_after(sv("client.java"), "custom-bow-range", start,
                  "if (GoodDistance(EnemyX, EnemyY, absX, absY, 1) == true || playerEquipment[playerWeapon] == 859",
                  "if (GoodDistance(EnemyX, EnemyY, absX, absY, 1) == true || RetroContent.isRangedWeapon(playerEquipment[playerWeapon]) /* @@ */ || playerEquipment[playerWeapon] == 859")
    replace_all(sv("client.java"), "accuracy", "server.npcHandler.npcs[attacknpc].hitDiff = hitDiff;",
                "hitDiff = RetroContent.accuracy(this, server.npcHandler.npcs[attacknpc], hitDiff, UseBow ? 1 : 0); // @@\n"
                "\t\t\t\t\tserver.npcHandler.npcs[attacknpc].hitDiff = hitDiff;")
    replace_all(sv("client.java"), "magic-accuracy", "hitDiff = RetroContent.magicHit(this, hitDiff); // RetroRemake magic",
                "hitDiff = RetroContent.magicHit(this, hitDiff, server.npcHandler.npcs[npcIndex]); // RetroRemake magic, @@")
    replace_all(sv("client.java"), "food-cap", "myHP <= 99", "myHP < getLevelForXP(playerXP[3]) /* @@ */")
    replace_all(sv("client.java"), "food-cap2", "myHP >= 99", "myHP >= getLevelForXP(playerXP[3]) /* @@ */")


def main_v6(server_dir):
    sv = lambda f: os.path.join(server_dir, f)
    print("v6 hooks: safe start-up")
    replace_after(sv("ObjectHandler.java"), "object-guard", "public boolean loadObjects(String FileName) {",
                  'if (token.equals("object")) {',
                  'if (token.equals("object") && (token3.length < 7 || !(token3[6].equals("true") || token3[6].equals("false")))) { '
                  'misc.println("Skipping malformed object line: " + line); /* @@ */ } else if (token.equals("object")) {')
    replace_after(sv("server.java"), "fatal", "public static void main(java.lang.String args[]) {",
                  "public static void main(java.lang.String args[]) {",
                  "public static void main(java.lang.String args[]) {\n"
                  "\t\t// @@: if the main thread dies (bad config, crash in the game loop), stop the whole server instead of\n"
                  "\t\t// leaving the login listener running with no game loop (players would get a black screen).\n"
                  "\t\tThread.setDefaultUncaughtExceptionHandler(new Thread.UncaughtExceptionHandler() {\n"
                  "\t\t\tpublic void uncaughtException(Thread t, Throwable e) {\n"
                  "\t\t\t\tSystem.err.println(\"Fatal error in thread \" + t.getName() + \":\");\n"
                  "\t\t\t\te.printStackTrace();\n"
                  "\t\t\t\tif (\"main\".equals(t.getName())) System.exit(1);\n"
                  "\t\t\t}\n"
                  "\t\t});")


def main_v7(server_dir):
    sv = lambda f: os.path.join(server_dir, f)
    print("v7: home spawn, banner")
    replace_after(sv("Player.java"), "spawn-home-x", "// initial x and y coordinates of the player", "teleportToX = 3255;//3093;",
                  "teleportToX = 3093; // @@: new characters start at home, next to the Rift Guide")
    replace_after(sv("Player.java"), "spawn-home-y", "// initial x and y coordinates of the player", "teleportToY = 3289;//3491;",
                  "teleportToY = 3491; // @@")
    replace_after(sv("server.java"), "banner", "public static void main", 'misc.println("traxxas-scape is now running :P ");',
                  'misc.println("RetroRemakeRSPS is now running."); // @@')


def main_v8(server_dir):
    sv = lambda f: os.path.join(server_dir, f)
    print("v8: save paths")
    for f in ("PlayerHandler.java", "client.java", "SaveGameHandler.java"):
        s = open(sv(f), encoding="latin-1", newline="").read()
        if "./savedGames/" in s:
            s = s.replace('"./savedGames/', '"./savedgames/')
            open(sv(f), "w", encoding="latin-1", newline="").write(s)
            print("  patched: savedgames path in", f)
    for d in ("characters", "savedgames", "charbackup", "charbackupmyth", "flagged", "flaggedauto", "logs", "moreinfo", "connectedfrom", "data"):
        os.makedirs(sv(d), exist_ok=True)
        keep = os.path.join(sv(d), ".keep")
        if not os.listdir(sv(d)):
            open(keep, "w").close()
    for f in ("data/members.txt", "data/macrowarn.txt", "data/bannedusers.txt", "data/weather.txt"):
        if not os.path.exists(sv(f)):
            open(sv(f), "w").close()
            print("  created empty", f)


BRAND = "RetroRemakeRSPS"


def main_brand(server_dir, client_dir):
    print("branding")
    sv, cl = (lambda f: os.path.join(server_dir, f)), (lambda f: os.path.join(client_dir, f))
    edits = [
        (cl("client.java"), "brand-loading", '"GodzHell is loading - please wait..."', '"%s is loading - please wait..." /* @@ */' % BRAND),
        (cl("client.java"), "brand-welcome", '"@whi@Welcome to GodzHell"', '"@whi@Welcome to %s" /* @@ */' % BRAND),
        (cl("client.java"), "brand-site", '"@whi@@ GodzHell.com"', '"@whi@A retro remake of 2007-2012 servers" /* @@ */'),
        (cl("client.java"), "brand-title", '"GodzHell", c1 / 2 - 60', '"%s" /* @@ */, c1 / 2 - 60' % BRAND),
        (cl("client.java"), "brand-site2", '"Godzhell.com"', '"%s" /* @@ */' % BRAND),
        (cl("Frame_Sub1.java"), "brand-frame", 'setTitle("Jagex");', 'setTitle("%s"); // @@' % BRAND),
        (sv("client.java"), "brand-login", 'sendMessage("Welcome to GodzHell.com World");',
         'sendMessage("Welcome to %s! Talk to the Rift Guide at home or type ::teleports."); // @@' % BRAND),
        (sv("client.java"), "brand-count", 'PlayerHandler.getPlayerCount() * 3+" players on Godzhell"',
         'PlayerHandler.getPlayerCount()+" players online" /* @@: was shown x3 */'),
        (sv("client.java"), "brand-member", '"@blu@GodzHell Membership"', '"@blu@%s Membership" /* @@ */' % BRAND),
        (sv("client.java"), "brand-pod", '"@dre@Delivery to GodzHell in a kewl member\'s pod"', '"@dre@Delivery to %s in a kewl member\'s pod" /* @@ */' % BRAND),
        (sv("client.java"), "brand-tip", '"@red@Godzhell, @whi@use the"', '"@red@%s, @whi@use the" /* @@ */' % BRAND),
    ]
    for path, name, old, new in edits:
        s = open(path, encoding="latin-1", newline="").read()
        if (MARK + " " + name) in s or ("@@" in new and new.replace("@@", MARK + " " + name) in s):
            print("  already patched:", name); continue
        if old not in s:
            print("  (not found, skipped):", name); continue
        s = s.replace(old, new.replace("@@", MARK + " " + name), 1)
        open(path, "w", encoding="latin-1", newline="").write(s)
        print("  patched:", name)


if __name__ == "__main__":
    main(sys.argv[1])
    main_v3(sys.argv[1])
    if len(sys.argv) > 2:
        main_client(sys.argv[2])
        main_brand(sys.argv[1], sys.argv[2])
        main_v4(sys.argv[1], sys.argv[2])
        main_v5(sys.argv[1])
        main_v6(sys.argv[1])
        main_v7(sys.argv[1])
        main_v8(sys.argv[1])
