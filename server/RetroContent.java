import java.io.BufferedReader;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.FileReader;
import java.io.IOException;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Properties;
import java.util.Random;

/**
 * RetroRemakeRSPS content on top of GodzHell, driven by the data files tools/build_world.py and
 * tools/progression4.py generate: zones.cfg, shopnpcs.cfg, extradrops.cfg, mysterybox.cfg, customnpcs.cfg,
 * weapons.cfg, slayer.cfg (plus npc.cfg for combat levels).
 *
 * Features: teleport menu, market shopkeepers, custom NPCs (run as a base NPC, drawn as the custom one),
 * custom drop tables with jackpots, mystery boxes, slayer tasks with points and rewards, timed event bosses,
 * one max-hit formula for melee, ranged and magic, and weapon animation templates.
 */
public class RetroContent {

	static class Zone { int id, x, y, h; String category, name; }
	static class DropTable { int chance; int[] items, amounts; }
	static class CustomNpc { int id, base, hp, maxHit, tier; String role, name; }
	static class Menu { String kind; String category; int page; List<String> entries = new ArrayList<String>(); }
	static class Slayer { int task = -1, left, points, tier = 1, done; }

	private static final Random RANDOM = new Random();
	private static final int PAGE_SIZE = 4;
	private static final int OPTION_TITLE = 2493, OPTION_FIRST = 2494, OPTION_IFACE = 2492, OPTION_BUTTON = 9190;
	private static final int EVENT_FIRST_TICKS = 1200;   // 10 minutes after start (500 ms ticks)
	private static final int EVENT_EVERY_TICKS = 4800;   // then every 40 minutes

	private static boolean loaded = false;
	private static final List<Zone> zones = new ArrayList<Zone>();
	private static final List<String> categories = new ArrayList<String>();
	private static final Map<String, Integer> shopByTile = new HashMap<String, Integer>();
	private static final Map<Integer, List<DropTable>> drops = new HashMap<Integer, List<DropTable>>();
	private static final List<DropTable> globalDrops = new ArrayList<DropTable>();
	private static final List<Integer> globalMinCombat = new ArrayList<Integer>();
	private static final Map<Integer, Integer> npcCombat = new HashMap<Integer, Integer>();
	private static final Map<Integer, CustomNpc> customNpcs = new LinkedHashMap<Integer, CustomNpc>();
	private static final Map<Integer, Integer> weaponTemplates = new HashMap<Integer, Integer>();
	private static final Map<Integer, int[]> tierPools = new HashMap<Integer, int[]>();
	private static final Map<Integer, String> tierNames = new HashMap<Integer, String>();
	private static int boxItem = 6199;
	private static final List<Integer> boxRewards = new ArrayList<Integer>();
	private static final List<Integer> boxWeights = new ArrayList<Integer>();
	private static int boxTotalWeight = 0;
	private static int eventX = -1, eventY = -1;
	private static String eventArea = "";
	private static int maxTier = 1;
	private static final Map<Integer, int[]> tierStats = new HashMap<Integer, int[]>();   // tier -> {damage budget, defence budget, level}

	private static final Map<Integer, Menu> menus = new HashMap<Integer, Menu>();
	private static final Map<String, Slayer> slayers = new HashMap<String, Slayer>();

	private static long ticks = 0;
	private static int eventSlot = -1, eventId = -1, eventCleanup = -1, nextEvent = 0;

	// ------------------------------------------------------------------------------------ loading

	private static synchronized void load() {
		if (loaded) return;
		loaded = true;
		for (String[] t : rows("zones.cfg", "zone")) {
			if (t.length < 6) continue;
			Zone z = new Zone();
			z.id = parse(t[0]); z.category = t[1].trim(); z.x = parse(t[2]); z.y = parse(t[3]); z.h = parse(t[4]); z.name = t[5].trim();
			zones.add(z);
			if (!categories.contains(z.category)) categories.add(z.category);
		}
		for (String[] t : rows("shopnpcs.cfg", "shopnpc"))
			if (t.length >= 4) shopByTile.put(t[0].trim() + "," + t[1].trim() + "," + t[2].trim(), parse(t[3]));
		for (String[] t : rows("extradrops.cfg", "table")) {
			if (t.length < 3) continue;
			DropTable d = table(parse(t[1]), t[2]);
			if (d == null) continue;
			int npc = parse(t[0]);
			List<DropTable> list = drops.get(npc);
			if (list == null) { list = new ArrayList<DropTable>(); drops.put(npc, list); }
			list.add(d);
		}
		for (String[] t : rows("extradrops.cfg", "global")) {
			if (t.length < 3) continue;
			DropTable d = table(parse(t[1]), t[2]);
			if (d != null) { globalDrops.add(d); globalMinCombat.add(parse(t[0])); }
		}
		for (String[] t : rows("npc.cfg", "npc")) if (t.length >= 3) npcCombat.put(parse(t[0]), parse(t[2]));
		for (String[] t : rows("mysterybox.cfg", "box")) boxItem = parse(t[0]);
		for (String[] t : rows("mysterybox.cfg", "reward")) {
			if (t.length < 2) continue;
			int w = Math.max(1, parse(t[1]));
			boxRewards.add(parse(t[0])); boxWeights.add(w); boxTotalWeight += w;
		}
		for (String[] t : rows("customnpcs.cfg", "customnpc")) {
			if (t.length < 7) continue;
			CustomNpc n = new CustomNpc();
			n.id = parse(t[0]); n.base = parse(t[1]); n.hp = parse(t[2]); n.maxHit = parse(t[3]);
			n.tier = parse(t[4]); n.role = t[5].trim(); n.name = t[6].trim();
			customNpcs.put(n.id, n);
			if (!n.role.equals("event") && n.tier > maxTier && n.tier < 99) maxTier = n.tier;
		}
		for (String[] t : rows("customnpcs.cfg", "eventarea"))
			if (t.length >= 4) { eventX = parse(t[0]); eventY = parse(t[1]); eventArea = t[3].trim(); }
		for (String[] t : rows("customnpcs.cfg", "tiername"))
			if (t.length >= 3) tierNames.put(parse(t[0]), t[1].trim() + " (" + t[2].trim() + ")");
		for (String[] t : rows("weapons.cfg", "weapon")) if (t.length >= 2) weaponTemplates.put(parse(t[0]), parse(t[1]));
		for (String[] t : rows("customnpcs.cfg", "tierstat"))
			if (t.length >= 4) tierStats.put(parse(t[0]), new int[] { parse(t[1]), parse(t[2]), parse(t[3]) });
		for (String[] t : rows("slayer.cfg", "tierpool")) {
			if (t.length < 2) continue;
			String[] p = t[1].split(",");
			int[] ids = new int[p.length];
			int n = 0;
			for (String s : p) { int v = parse(s); if (v > 0) ids[n++] = v; }
			int[] out = new int[n];
			System.arraycopy(ids, 0, out, 0, n);
			tierPools.put(parse(t[0]), out);
		}
		nextEvent = EVENT_FIRST_TICKS;
		misc.println("RetroRemake: " + zones.size() + " zones, " + customNpcs.size() + " custom NPCs, " + drops.size()
				+ " drop tables, " + boxRewards.size() + " mystery box rewards, " + weaponTemplates.size() + " weapon templates.");
	}

	private static DropTable table(int chance, String spec) {
		String[] parts = spec.split(",");
		int[] items = new int[parts.length], amounts = new int[parts.length];
		int n = 0;
		for (String p : parts) {
			String[] ia = p.trim().split(":");
			if (ia.length != 2) continue;
			items[n] = parse(ia[0]); amounts[n] = Math.max(1, parse(ia[1])); n++;
		}
		if (n == 0) return null;
		DropTable d = new DropTable();
		d.chance = Math.max(1, chance);
		d.items = new int[n]; d.amounts = new int[n];
		System.arraycopy(items, 0, d.items, 0, n);
		System.arraycopy(amounts, 0, d.amounts, 0, n);
		return d;
	}

	/** Rows of "key = a<TAB>b..." with any trailing "// comment" removed. */
	private static List<String[]> rows(String file, String key) {
		List<String[]> out = new ArrayList<String[]>();
		BufferedReader in = null;
		try {
			in = new BufferedReader(new FileReader("./" + file));
			String line;
			while ((line = in.readLine()) != null) {
				int c = line.indexOf("//");
				if (c >= 0) line = line.substring(0, c);
				line = line.trim();
				int eq = line.indexOf('=');
				if (eq < 0 || !line.substring(0, eq).trim().equals(key)) continue;
				out.add(line.substring(eq + 1).trim().replaceAll("\t+", "\t").split("\t"));
			}
		} catch (IOException e) {
			misc.println("RetroRemake: could not read " + file + " (" + e.getMessage() + ")");
		} finally {
			if (in != null) try { in.close(); } catch (IOException ignored) { }
		}
		return out;
	}

	private static int parse(String s) {
		try { return Integer.parseInt(s.trim()); } catch (NumberFormatException e) { return -1; }
	}

	// ------------------------------------------------------------------------------------ commands

	/** ::teleports, ::zones, ::tp, ::tiers, ::task, ::slayer, ::event. Returns true when the command was ours. */
	public static boolean handleCommand(client c, String command) {
		load();
		String cmd = command.trim();
		String lower = cmd.toLowerCase();
		if (lower.equals("menu") || lower.equals("rift")) { openMain(c); return true; }
		if (lower.equals("commands") || lower.equals("help")) { help(c); return true; }
		if (lower.equals("progress")) { progress(c); return true; }
		if (lower.equals("teleports") || lower.equals("teleport") || lower.equals("tele")) { openTeleports(c); return true; }
		if (lower.equals("zones") || lower.startsWith("zones ")) { listZones(c, cmd.length() > 5 ? cmd.substring(6).trim() : ""); return true; }
		if (lower.equals("tp") || lower.startsWith("tp ")) { teleportByArg(c, cmd.length() > 2 ? cmd.substring(3).trim() : ""); return true; }
		if (lower.equals("tiers")) { listTiers(c); return true; }
		if (lower.equals("task")) { slayerStatus(c); return true; }
		if (lower.equals("slayer")) { openSlayer(c); return true; }
		if (lower.equals("event")) { eventCommand(c); return true; }
		return false;
	}

	private static void listTiers(client c) {
		c.sendMessage("Tiers - ::teleports for the menu. Bosses drop their tier's gear, sometimes gear 2-3 tiers higher.");
		for (int t = 1; t <= maxTier; t++) {
			String boss = "";
			for (CustomNpc n : customNpcs.values())
				if (n.tier == t && n.role.equals("boss")) boss = " - boss " + n.name + " (" + n.hp + " hp)";
			c.sendMessage("Tier " + t + ": " + (tierNames.containsKey(t) ? tierNames.get(t) : "") + boss);
		}
		c.sendMessage("Your slayer tier: " + slayer(c).tier + ".");
	}

	private static void listZones(client c, String arg) {
		if (arg.length() == 0) {
			StringBuilder sb = new StringBuilder();
			for (String cat : categories) { if (sb.length() > 0) sb.append(", "); sb.append(cat); }
			c.sendMessage("Zones: " + sb + ". Type ::zones <category> or open ::teleports.");
			return;
		}
		List<Zone> list = new ArrayList<Zone>();
		for (Zone z : zones) if (z.category.equalsIgnoreCase(arg)) list.add(z);
		if (list.isEmpty()) { c.sendMessage("No such zone category."); return; }
		for (Zone z : list) c.sendMessage(z.id + ". " + z.name);
	}

	private static void teleportByArg(client c, String arg) {
		if (arg.length() == 0) { openTeleports(c); return; }
		Zone target = null;
		int id = parse(arg);
		if (id > 0) {
			for (Zone z : zones) if (z.id == id) target = z;
		} else {
			String a = arg.toLowerCase();
			List<Zone> partial = new ArrayList<Zone>();
			for (Zone z : zones) {
				String n = z.name.toLowerCase();
				if (n.equals(a)) { target = z; break; }
				if (n.indexOf(a) >= 0) partial.add(z);
			}
			if (target == null && partial.size() == 1) target = partial.get(0);
			if (target == null && partial.size() > 1) {
				c.sendMessage(partial.size() + " zones match \"" + arg + "\":");
				for (int i = 0; i < Math.min(6, partial.size()); i++) c.sendMessage(partial.get(i).id + ". " + partial.get(i).name);
				return;
			}
		}
		if (target == null) { c.sendMessage("No zone \"" + arg + "\". Open ::teleports."); return; }
		teleport(c, target.x, target.y, target.h, target.name);
	}

	private static void teleport(client c, int x, int y, int h, String name) {
		if (c.teleblock) { c.sendMessage("A magical force stops you from teleporting."); return; }
		c.teleportToX = x;
		c.teleportToY = y;
		c.heightLevel = h;
		c.sendMessage("You teleport to " + name + ".");
	}

	// ------------------------------------------------------------------------------------ menus

	private static void show(client c, Menu m, String title, String[] lines) {
		menus.put(c.playerId, m);
		c.sendFrame126(title, OPTION_TITLE);
		for (int i = 0; i < 5; i++) c.sendFrame126(i < lines.length && lines[i] != null ? lines[i] : "", OPTION_FIRST + i);
		c.sendFrame164(OPTION_IFACE);
	}

	private static void close(client c) {
		menus.remove(c.playerId);
		c.RemoveAllWindows();
	}

	/** The Rift Guide's main menu: everything the server adds, without typing commands. */
	public static void openMain(client c) {
		load();
		Menu m = new Menu();
		m.kind = "main";
		show(c, m, "RetroRemakeRSPS - what would you like to do?", new String[] {
			"Teleports (all tiers, bosses, skilling, home)", "Slayer tasks and rewards", "My progress",
			eventId > 0 && eventCleanup < 0 ? "Event boss (active now!)" : "Event boss", "Help: all commands" });
	}

	private static void help(client c) {
		c.sendMessage("@blu@RetroRemakeRSPS commands (or use the Rift Guide's menu at home):");
		c.sendMessage("::menu - main menu    ::teleports - teleport menu    ::tp <number or name>");
		c.sendMessage("::tiers - the tier ladder    ::progress - your progress    ::zones <section>");
		c.sendMessage("::slayer - slayer menu    ::task - current task    ::event - join the event boss");
		c.sendMessage("::home - back home. Mystery boxes: click Open.");
	}

	private static void progress(client c) {
		Slayer s = slayer(c);
		int t = Math.min(maxTier, s.tier);
		String boss = "";
		for (CustomNpc n : customNpcs.values())
			if (n.tier == t && n.role.equals("boss")) boss = n.name;
		c.sendMessage("@blu@Your tier: " + t + (tierNames.containsKey(t) ? " - " + tierNames.get(t) : "")
				+ ". Next boss: " + (boss.length() > 0 ? boss : "none - you beat them all!") + ".");
		slayerStatus(c);
		c.sendMessage("Tip: bosses drop their tier's gear, sometimes gear two or three tiers higher.");
	}

	public static void openTeleports(client c) {
		load();
		Menu m = new Menu();
		m.kind = "tele-cats";
		m.entries.addAll(categories);
		pageOf(c, m, "Where would you like to go?");
	}

	/** Shows page m.page of m.entries: up to 4 entries and a "More / Back" line. */
	private static void pageOf(client c, Menu m, String title) {
		String[] lines = new String[5];
		int start = m.page * PAGE_SIZE;
		for (int i = 0; i < PAGE_SIZE; i++) {
			int k = start + i;
			lines[i] = k < m.entries.size() ? label(m, m.entries.get(k)) : "";
		}
		boolean more = start + PAGE_SIZE < m.entries.size();
		lines[4] = more ? "More..." : "Back";
		show(c, m, title, lines);
	}

	private static String label(Menu m, String entry) {
		if (m.kind.equals("tele-cats") && entry.startsWith("Tier ")) {
			int t = parse(entry.substring(5));
			return entry + (tierNames.containsKey(t) ? " - " + tierNames.get(t) : "");
		}
		if (m.kind.equals("tele-zones")) {
			for (Zone z : zones) if (String.valueOf(z.id).equals(entry)) return z.name;
		}
		return entry;
	}

	/** Option buttons 9190-9194 while one of our menus is open. Returns true when handled. */
	public static boolean handleButton(client c, int button) {
		Menu m = menus.get(c.playerId);
		if (m == null || button < OPTION_BUTTON || button > OPTION_BUTTON + 4) return false;
		int option = button - OPTION_BUTTON;
		if (m.kind.startsWith("tele")) {
			if (option == 4) {
				if (m.page * PAGE_SIZE + PAGE_SIZE < m.entries.size()) { m.page++; pageOf(c, m, m.kind.equals("tele-cats") ? "Where would you like to go?" : m.category); }
				else if (m.kind.equals("tele-zones")) openTeleports(c);
				else openMain(c);
				return true;
			}
			int k = m.page * PAGE_SIZE + option;
			if (k >= m.entries.size()) return true;
			if (m.kind.equals("tele-cats")) {
				String cat = m.entries.get(k);
				Menu z = new Menu();
				z.kind = "tele-zones";
				z.category = cat;
				for (Zone zz : zones) if (zz.category.equals(cat)) z.entries.add(String.valueOf(zz.id));
				pageOf(c, z, cat + (cat.startsWith("Tier ") && tierNames.containsKey(parse(cat.substring(5))) ? " - " + tierNames.get(parse(cat.substring(5))) : ""));
			} else {
				int id = parse(m.entries.get(k));
				close(c);
				for (Zone z : zones) if (z.id == id) teleport(c, z.x, z.y, z.h, z.name);
			}
			return true;
		}
		if (m.kind.equals("main")) {
			if (option == 0) openTeleports(c);
			else if (option == 1) openSlayer(c);
			else if (option == 2) { close(c); progress(c); }
			else if (option == 3) { close(c); eventCommand(c); }
			else { close(c); help(c); }
			return true;
		}
		if (m.kind.equals("slayer")) {
			if (option == 0) assignTask(c);
			else if (option == 1) openSlayerRewards(c);
			else if (option == 2) cancelTask(c);
			else if (option == 3) openMain(c);
			else close(c);
			return true;
		}
		if (m.kind.equals("slayer-rewards")) {
			buyReward(c, option);
			return true;
		}
		return false;
	}

	/** Clicks on the home NPCs (Rift Guide, Slayer Sage). Returns true when handled. */
	public static boolean npcClick(client c, NPC npc) {
		load();
		if (npc == null || npc.retroVisual < 0) return false;
		CustomNpc n = customNpcs.get(npc.retroVisual);
		if (n == null) return false;
		if (n.role.equals("teleport")) { openMain(c); return true; }
		if (n.role.equals("slayer")) { openSlayer(c); return true; }
		return false;
	}

	// ------------------------------------------------------------------------------------ slayer

	private static Slayer slayer(client c) {
		String key = c.playerName == null ? "" : c.playerName.toLowerCase();
		Slayer s = slayers.get(key);
		if (s != null) return s;
		s = new Slayer();
		Properties p = new Properties();
		File f = new File("./characters/" + key + ".retro");
		if (f.exists()) {
			FileInputStream in = null;
			try {
				in = new FileInputStream(f);
				p.load(in);
				s.task = parse(p.getProperty("task", "-1"));
				s.left = parse(p.getProperty("left", "0"));
				s.points = Math.max(0, parse(p.getProperty("points", "0")));
				s.tier = Math.max(1, parse(p.getProperty("tier", "1")));
				s.done = Math.max(0, parse(p.getProperty("done", "0")));
			} catch (IOException e) {
				misc.println("RetroRemake: could not read " + f + ": " + e.getMessage());
			} finally {
				if (in != null) try { in.close(); } catch (IOException ignored) { }
			}
		}
		slayers.put(key, s);
		return s;
	}

	private static void save(client c, Slayer s) {
		String key = c.playerName == null ? "" : c.playerName.toLowerCase();
		Properties p = new Properties();
		p.setProperty("task", String.valueOf(s.task));
		p.setProperty("left", String.valueOf(s.left));
		p.setProperty("points", String.valueOf(s.points));
		p.setProperty("tier", String.valueOf(s.tier));
		p.setProperty("done", String.valueOf(s.done));
		FileOutputStream out = null;
		try {
			out = new FileOutputStream("./characters/" + key + ".retro");
			p.store(out, "RetroRemakeRSPS slayer and progression");
		} catch (IOException e) {
			misc.println("RetroRemake: could not save slayer for " + key + ": " + e.getMessage());
		} finally {
			if (out != null) try { out.close(); } catch (IOException ignored) { }
		}
	}

	public static void openSlayer(client c) {
		load();
		Slayer s = slayer(c);
		Menu m = new Menu();
		m.kind = "slayer";
		String task = s.task > 0 && customNpcs.containsKey(s.task) ? s.left + " x " + customNpcs.get(s.task).name : "none";
		show(c, m, "Slayer Sage - " + s.points + " points, task: " + task, new String[] {
			s.task > 0 ? "Remind me of my task" : "Give me a task", "Rewards (" + s.points + " points)", "Cancel my task (5 points)", "Back", "Close" });
	}

	private static void slayerStatus(client c) {
		Slayer s = slayer(c);
		if (s.task > 0 && customNpcs.containsKey(s.task))
			c.sendMessage("Task: " + s.left + " more " + customNpcs.get(s.task).name + ". Points: " + s.points + ". Tasks done: " + s.done + ".");
		else
			c.sendMessage("No task. Talk to the Slayer Sage at home or type ::slayer. Points: " + s.points + ".");
	}

	private static void assignTask(client c) {
		Slayer s = slayer(c);
		if (s.task > 0 && customNpcs.containsKey(s.task)) { close(c); slayerStatus(c); return; }
		int top = Math.min(maxTier, s.tier);
		int low = Math.max(1, top - 1);
		List<CustomNpc> pool = new ArrayList<CustomNpc>();
		for (CustomNpc n : customNpcs.values())
			if (n.tier >= low && n.tier <= top && (n.role.equals("mob") || n.role.equals("guardian"))) pool.add(n);
		if (pool.isEmpty()) { close(c); c.sendMessage("There is nothing to hunt right now."); return; }
		CustomNpc n = pool.get(RANDOM.nextInt(pool.size()));
		s.task = n.id;
		s.left = n.role.equals("guardian") ? 5 + RANDOM.nextInt(6) : 20 + RANDOM.nextInt(21);
		save(c, s);
		close(c);
		c.sendMessage("Your task: kill " + s.left + " " + n.name + " (tier " + n.tier + "). ::teleports has a teleport to them.");
	}

	private static void cancelTask(client c) {
		Slayer s = slayer(c);
		close(c);
		if (s.task <= 0) { c.sendMessage("You have no task."); return; }
		if (s.points < 5) { c.sendMessage("You need 5 points to cancel a task."); return; }
		s.points -= 5; s.task = -1; s.left = 0;
		save(c, s);
		c.sendMessage("Task cancelled.");
	}

	private static void openSlayerRewards(client c) {
		Slayer s = slayer(c);
		Menu m = new Menu();
		m.kind = "slayer-rewards";
		int t = Math.min(maxTier, s.tier);
		show(c, m, "Slayer rewards - " + s.points + " points", new String[] {
			"Mystery box (25 points)", "Tier " + t + " gear crate (60 points)", "Tier " + Math.min(maxTier, t + 1) + " gear crate (150 points)",
			"Rare cosmetic (300 points)", "Back" });
	}

	private static void buyReward(client c, int option) {
		Slayer s = slayer(c);
		if (option == 4) { openSlayer(c); return; }
		int[] cost = { 25, 60, 150, 300 };
		if (s.points < cost[option]) { close(c); c.sendMessage("You need " + cost[option] + " points."); return; }
		int item;
		int t = Math.min(maxTier, s.tier);
		if (option == 0) item = boxItem;
		else if (option == 3) item = pick(0);
		else item = pick(option == 1 ? t : Math.min(maxTier, t + 1));
		if (item <= 0) { close(c); c.sendMessage("That reward is not available."); return; }
		s.points -= cost[option];
		save(c, s);
		give(c, item, 1);
		close(c);
		c.sendMessage("You receive: " + c.GetItemName(item) + ". Points left: " + s.points + ".");
	}

	private static int pick(int tier) {
		int[] pool = tierPools.get(tier);
		if (pool == null || pool.length == 0) return -1;
		return pool[RANDOM.nextInt(pool.length)];
	}

	private static void give(client c, int item, int amount) {
		if (c.freeSlots() > 0) c.addItem(item, amount);
		else ItemHandler.addItem(item, c.absX, c.absY, amount, c.playerId, false);
	}

	private static void onKill(client c, CustomNpc n) {
		Slayer s = slayer(c);
		boolean dirty = false;
		if (n.role.equals("boss") && n.tier >= s.tier) {
			s.tier = Math.min(maxTier, n.tier + 1);
			dirty = true;
			c.sendMessage("@gre@You defeated " + n.name + "! Tier " + s.tier + " slayer tasks and rewards are unlocked.");
		}
		if (s.task == n.id && s.left > 0) {
			s.left--;
			c.addSkillXP(n.hp * 300, 18);
			if (s.left == 0) {
				int pts = 10 * n.tier + (n.role.equals("guardian") ? 10 : 0);
				s.points += pts; s.done++; s.task = -1;
				c.sendMessage("@gre@Task complete! +" + pts + " slayer points (" + s.points + " total).");
				if (RANDOM.nextInt(4) == 0) {
					int item = pick(Math.min(maxTier, n.tier + 1));
					if (item > 0) { give(c, item, 1); c.sendMessage("@gre@Task bonus: " + c.GetItemName(item) + "!"); }
				}
			} else if (s.left % 10 == 0) {
				c.sendMessage("Task: " + s.left + " " + n.name + " left.");
			}
			dirty = true;
		}
		if (dirty) save(c, s);
	}

	// ------------------------------------------------------------------------------------ events

	/** Called once per server cycle (500 ms). Spawns and cleans up event bosses. */
	public static void tick() {
		load();
		ticks++;
		if (eventCleanup > 0 && --eventCleanup == 0) {
			if (eventSlot > 0 && server.npcHandler.npcs[eventSlot] != null && server.npcHandler.npcs[eventSlot].retroVisual == eventId)
				server.npcHandler.npcs[eventSlot] = null;
			rebuildAll();
			eventSlot = -1; eventId = -1; nextEvent = (int) ticks + EVENT_EVERY_TICKS;
		}
		if (eventId < 0 && ticks >= nextEvent && eventX > 0) spawnEvent();
	}

	private static void spawnEvent() {
		List<CustomNpc> events = new ArrayList<CustomNpc>();
		for (CustomNpc n : customNpcs.values()) if (n.role.equals("event")) events.add(n);
		if (events.isEmpty()) { nextEvent = (int) ticks + EVENT_EVERY_TICKS; return; }
		CustomNpc n = events.get(RANDOM.nextInt(events.size()));
		server.npcHandler.newNPC(n.id, eventX, eventY, 0, eventX + 4, eventY + 4, eventX - 4, eventY - 4, 2, n.hp, false);
		eventSlot = -1;
		for (int i = 1; i < server.npcHandler.maxNPCs; i++) {
			NPC npc = server.npcHandler.npcs[i];
			if (npc != null && npc.retroVisual == n.id && npc.makeX == eventX && npc.makeY == eventY) { eventSlot = i; break; }
		}
		if (eventSlot < 0) { nextEvent = (int) ticks + EVENT_EVERY_TICKS; return; }
		eventId = n.id;
		announce("@red@[Event] " + n.name + " has appeared at the " + eventArea + "! Type ::event to join.");
	}

	private static void eventCommand(client c) {
		load();
		if (eventId > 0 && eventCleanup < 0) {
			for (Zone z : zones) if (z.category.equals("Event")) { teleport(c, z.x, z.y, z.h, z.name); return; }
		}
		int left = Math.max(0, nextEvent - (int) ticks) / 120;
		c.sendMessage("No event boss right now. The next one appears in about " + Math.max(1, left) + " minutes.");
	}

	private static void announce(String msg) {
		for (int i = 1; i < server.playerHandler.maxPlayers; i++) {
			Player p = server.playerHandler.players[i];
			if (p instanceof client && p.playerName != null) ((client) p).sendMessage(msg);
		}
	}

	private static void rebuildAll() {
		for (int i = 1; i < server.playerHandler.maxPlayers; i++)
			if (server.playerHandler.players[i] != null) server.playerHandler.players[i].RebuildNPCList = true;
	}

	// ------------------------------------------------------------------------------------ custom NPCs

	/** Every NPC the server creates passes through here: custom NPCs run as their base type. */
	public static void onSpawn(NPC npc) {
		load();
		CustomNpc n = customNpcs.get(npc.npcType);
		if (n == null) return;
		npc.retroVisual = n.id;
		npc.npcType = n.base;
		npc.HP = n.hp;
		npc.MaxHP = n.hp;
		npc.MaxHit = n.maxHit;
	}

	public static int visualType(NPC npc) {
		return npc.retroVisual >= 0 ? npc.retroVisual : npc.npcType;
	}

	// ------------------------------------------------------------------------------------ accuracy

	/** Tier of any NPC: custom NPCs know theirs; vanilla NPCs are estimated from combat level. */
	private static int tierOf(NPC npc) {
		CustomNpc n = customNpcs.get(visualType(npc));
		if (n != null) return n.role.equals("event") ? maxTier : Math.max(1, Math.min(maxTier, n.tier));
		Integer cb = npcCombat.get(visualType(npc));
		return Math.max(1, Math.min(maxTier, (cb == null ? 30 : cb.intValue()) / 30));
	}

	private static String roleOf(NPC npc) {
		CustomNpc n = customNpcs.get(visualType(npc));
		return n == null ? "mob" : n.role;
	}

	/** OSRS-style hit chance from an attack roll and a defence roll. */
	private static double chance(double attack, double defence) {
		return attack > defence ? 1.0 - (defence + 2.0) / (2.0 * (attack + 1.0)) : attack / (2.0 * (defence + 1.0));
	}

	/** NPC defence roll for its tier: defence level 20 + 15 per tier, defence bonus 15 per tier (more for bosses). */
	private static double npcDefenceRoll(NPC npc) {
		int t = tierOf(npc);
		String r = roleOf(npc);
		int lvl = 20 + 15 * t + (r.equals("boss") || r.equals("event") ? 10 : r.equals("guardian") ? 5 : -10);
		int bonus = 15 * t + (r.equals("event") ? 60 : 0);
		return (lvl + 8.0) * (bonus + 64.0);
	}

	/**
	 * Player hit on an NPC. Same rule for every style: level (to 150) and the style's bonus against the NPC's tier
	 * defence. style: 0 melee (attack level; best of stab/slash/crush or strength bonus), 1 ranged, 2 magic.
	 */
	public static int accuracy(client c, NPC npc, int hit, int style) {
		load();
		if (npc == null || hit <= 0) return hit;
		int lvl, bonus;
		if (style == 1) { lvl = c.playerLevel[4]; bonus = c.playerBonus[4]; }
		else if (style == 2) { lvl = c.playerLevel[6]; bonus = c.playerBonus[3]; }
		else {
			lvl = c.playerLevel[0];
			bonus = Math.max(Math.max(c.playerBonus[0], c.playerBonus[1]), Math.max(c.playerBonus[2], c.playerBonus[10]));
		}
		double attack = (lvl + 8.0) * (Math.max(0, bonus) + 64.0);
		return RANDOM.nextDouble() < chance(attack, npcDefenceRoll(npc)) ? hit : 0;
	}

	/**
	 * Custom NPC hit on a player: it must beat the player's defence (Defence level to 150 and average melee defence
	 * bonus), then rolls its own max hit, which armour reduces a little more.
	 */
	public static int npcHit(NPC npc, int hit, Player p) {
		load();
		if (npc == null || p == null || npc.retroVisual < 0) return hit;
		CustomNpc n = customNpcs.get(npc.retroVisual);
		if (n == null) return hit;
		if (n.maxHit <= 0) return 0;
		int t = tierOf(npc);
		int[] st = tierStats.get(t);
		int npcAttBonus = st == null ? 60 * t : (int) (st[1] * 0.9);
		int npcAttLvl = 20 + 15 * t + (n.role.equals("boss") || n.role.equals("event") ? 10 : 0);
		int def = Math.max(0, (p.playerBonus[5] + p.playerBonus[6] + p.playerBonus[7]) / 3);
		double attack = (npcAttLvl + 8.0) * (npcAttBonus + 64.0);
		double defence = (p.playerLevel[1] + 8.0) * (def + 64.0);
		if (RANDOM.nextDouble() >= chance(attack, defence)) return 0;
		int raw = RANDOM.nextInt(n.maxHit + 1);
		int out = (int) Math.round(raw / (1.0 + def / 1500.0));
		return Math.max(0, Math.min(out, p.playerLevel[3]));
	}

	/** Same formula for every style: (damage bonus + level) / 6.76; levels go to 150. */
	public static int rangedMax(client c) {
		return (int) Math.floor((Math.max(0, c.playerBonus[4]) + c.playerLevel[4]) / 6.76);
	}

	/** Magic damage on NPCs: rolled from magic attack bonus + magic level (to 150), then the accuracy roll. */
	public static int magicHit(client c, int spellHit, NPC npc) {
		int max = (int) Math.floor((Math.max(0, c.playerBonus[3]) + c.playerLevel[6]) / 6.76);
		int hit = max <= 0 ? spellHit : RANDOM.nextInt(max + 1);
		return accuracy(c, npc, hit, 2);
	}

	/** Any custom bow or crossbow (its animation template is a bow or crossbow) fires like a bow. */
	public static boolean isRangedWeapon(int itemId) {
		load();
		Integer t = weaponTemplates.get(itemId);
		return t != null && (t.intValue() == 861 || t.intValue() == 837);
	}

	public static int weaponTemplate(int itemId) {
		load();
		Integer t = weaponTemplates.get(itemId);
		return t == null ? itemId : t.intValue();
	}

	/** Custom NPCs drop only from their own tables (their base NPC's drops are skipped). */
	public static boolean skipBaseDrops(NPC npc) {
		return npc != null && npc.retroVisual >= 0;
	}

	// ------------------------------------------------------------------------------------ market, drops, box

	public static int shopFor(NPC npc) {
		load();
		if (npc == null) return 0;
		Integer id = shopByTile.get(npc.makeX + "," + npc.makeY + "," + npc.heightLevel);
		return id == null ? 0 : id.intValue();
	}

	/** Drops, slayer progress and event bookkeeping for an NPC that just died. */
	public static void dropExtra(NPCHandler handler, int slot) {
		load();
		NPC npc = handler.npcs[slot];
		if (npc == null) return;
		int killer = handler.GetNpcKiller(slot);
		Player kp = killer > 0 ? server.playerHandler.players[killer] : null;
		if (kp == null) return;
		int type = visualType(npc);
		List<DropTable> list = drops.get(type);
		if (list != null) for (DropTable d : list) roll(d, npc, killer);
		Integer combat = npcCombat.get(type);
		for (int i = 0; i < globalDrops.size(); i++)
			if (combat != null && combat.intValue() >= globalMinCombat.get(i).intValue()) roll(globalDrops.get(i), npc, killer);
		CustomNpc n = customNpcs.get(type);
		if (n != null && kp instanceof client) onKill((client) kp, n);
		if (n != null && n.role.equals("event") && slot == eventSlot) {
			announce("@red@[Event] " + n.name + " was defeated by " + kp.playerName + "!");
			eventCleanup = 20;
		}
	}

	private static void roll(DropTable d, NPC npc, int killer) {
		if (RANDOM.nextInt(d.chance) != 0) return;
		int k = RANDOM.nextInt(d.items.length);
		ItemHandler.addItem(d.items[k], npc.absX, npc.absY, d.amounts[k], killer, false);
	}

	public static boolean openBox(client c, int itemId, int slot) {
		load();
		if (itemId != boxItem || boxTotalWeight == 0) return false;
		if (slot < 0 || slot >= c.playerItems.length || c.playerItems[slot] != itemId + 1) return true;
		int r = RANDOM.nextInt(boxTotalWeight);
		int reward = boxRewards.get(0);
		for (int i = 0; i < boxRewards.size(); i++) {
			r -= boxWeights.get(i);
			if (r < 0) { reward = boxRewards.get(i); break; }
		}
		c.deleteItem(itemId, slot, 1);
		c.addItem(reward, 1);
		c.sendMessage("You open the mystery box and find: " + c.GetItemName(reward) + "!");
		return true;
	}
}
