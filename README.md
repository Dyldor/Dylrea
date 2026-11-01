# RetroRemakeRSPS

A personal, offline retro custom server. It's built on **GodzHell**, with content from about 30 servers from 2007 to 2012,
and a 10-tier progression path built around custom armour sets, custom weapons and custom bosses.

## Play (one step)
1. Install **Java 8 or newer** if you don't have it ([adoptium.net](https://adoptium.net), the default installer is fine).
2. Unzip this folder anywhere, then **double-click `RetroRemakeRSPS.jar`**.
   - If double-clicking a `.jar` does nothing on your computer, use **`Play.bat`** (Windows), **`Play.command`** (Mac) or **`play.sh`** (Linux) instead.
3. The launcher starts the server and opens the game. Log in with any name and password; a new account is created on first login.
   When you close the game it waits about 20 seconds so your character saves, then stops the server.

Everything is precompiled, so nothing needs building. The server's output goes to `server/logs/server-console.log` and the
client's to `client/client-console.log`.

**Owner rights (optional):** after your first login, close the game. Set `character-rights = 3` in
`server/characters/<you>.txt` and play again. As owner, `::item <id>` drops any item ([ITEMS.md](ITEMS.md) has the IDs).

## How to play
- **You start at home** (Edgeville bank), where you'll find:
  - the **Rift Guide**: click him for the **main menu**, which covers everything without typing commands
    (Teleports, Slayer, My progress, Event boss, Help);
  - the **Slayer Sage**, for tasks and rewards;
  - the **Novice Outfitter**, who sells the tier 1 Verdant gear;
  - the **Rainbow Tablets** shop.
- **Teleport menu** (Rift Guide → Teleports, or `::teleports`), in progression order:
  - every custom monster, guardian and boss, in tier order;
  - the event arena;
  - skilling spots;
  - home.
- **Each tier** has four monster types, two guardians and a boss, all custom, with new models in the tier's colours.
  - **Monsters** drop any of the tier's gear (1 in 40), and gear two tiers up (1 in 400).
  - **First guardian:** helms, shields, gloves and boots (1 in 4). **Second guardian:** capes, jewellery, ranged and magic accessories (1 in 4). Guardians also drop gear two tiers up (1 in 60).
  - **Boss:** bodies, legs and weapons (1 in 3), gear two tiers up (1 in 40), three tiers up (1 in 250), and mystery boxes (1 in 10).
- **Jackpot drops** from two or three tiers up are big upgrades: a two-tier jump raises your max hit by about 1.5–1.7×.
- **Slayer** (Slayer Sage or `::slayer`, check progress with `::task`):
  - Tasks are custom monsters and guardians from your current tier and the one below it. Beating a tier's boss unlocks the next tier of tasks.
  - Each finished task gives points, Slayer XP, and a 1-in-4 bonus item from the next tier.
  - Points buy mystery boxes, gear crates from your tier or the one above, and rare cosmetics.
- **Event bosses** (Jett Colossus, Pumpkin King, Frostfather, Party Wyrm) spawn in the event arena: the first 10 minutes after start-up, then every 40 minutes after the last one dies.
  - Chat announces them; `::event` takes you there.
  - They drop mystery boxes, top-tier gear and the rare cosmetics.
- **Cosmetics** (party hats, santa hats, h'ween masks, jester gear, the Car and the rest) are **rare and overpowered**. Their stats are above tier 10, and armour pieces boost every combat style.
- **Mystery boxes** can give anything; high tiers and cosmetics are the rarest. They come from bosses, any monster of combat level 50 or higher (1 in 300), Slayer, and the Market (1M).
- **Skills go to 150.** HP goes to 150 too.
- **Commands** (everything is also in the Rift Guide's menu; `::help` lists them in game):
  - `::menu` — the main menu;
  - `::teleports`, `::tp <number or name>`, `::zones`, `::home` — teleporting;
  - `::tiers`, `::progress`, `::task`, `::slayer`, `::event` — progression;
  - the old GodzHell commands still work.

## The tiers
| Tier | Set (colours) | Boss | Max hit in the full set |
|---|---|---|---:|
| 1 Novice | Verdant (green/brown) | Verdant Troll King | 16 |
| 2 Apprentice | Jett (blue/white) | Jett Wyrm | 23 |
| 3 Adept | Tidal (cyan/navy) | Leviathan Demon | 32 |
| 4 Toxic | Toxic (acid green/black) | Toxic Behemoth | 42 |
| 5 Veteran | Infernal (red/black) | Infernal King | 55 |
| 6 Elite | Gilded (gold/white) | Sunforged Dragon | 69 |
| 7 Royal | Royal (purple/gold) | Regal Dragon | 85 |
| 8 Champion | Molten (orange/black) | Inferno Jad | 105 |
| 9 Mythic | Void (purple/black) | Eclipse Dragon | 127 |
| 10 Divine | Rainbow | The Rainbow Dragon | 155 |

[PROGRESSION.md](PROGRESSION.md) has every NPC's HP and max hit. [ITEMS.md](ITEMS.md) has every item's tier, source and stats.
Previews of the gear and NPCs are in [previews/](previews/).

**What drops in each tier:**
- **Tier armour sets, Gandorx-style:** the same meshes in every tier, each with its own name and colour scheme. Each tier has three sets, one per style:
  - melee **Bandos**: bandos helm, chestplate, tassets, shield, boots, gloves (for example Jett bandos chestplate, Infernal bandos tassets);
  - ranged: range coif, range top, range legs, vambraces (3rd age meshes);
  - magic: mage hat, robe top, robe bottom (3rd age meshes).
  Tier 10 is the Rainbow set, with the Rainbow full helm.
- **Shared gear and weapons:** a cape, amulet and ring, and weapons for every style: godsword, bow, crossbow, staff and wand.
- **Tier whips:** the old servers' coloured whips (green, blue, white, unknown-colour, red, gold, orange, lava, purple), plus a generated Rainbow whip.
- **The old servers' custom sets and items**, placed by theme. Examples:
  - trimmed Black sets in tier 1;
  - Lava, Ladies, Ivandis and Draconic in tier 8;
  - Demon, Ultimanum, Legionary and Balmung in tier 9;
  - Admin, Mod and Owner gear in tier 10;
  - skillcapes spread through the middle tiers.
- **Specials:** Rainbow claws, Halogen blade, Plasma bow and Plasma crossbow.
- **Imported 2007–08 pieces** (Zamorakian spear, Zamorak d'hide, Berserker necklace, extra skillcapes): bosses don't drop them, only monsters and mystery boxes.

**Counts:** 45 armour sets (30 generated, 15 from the old servers), 427 tiered items and cosmetics, all obtainable.
Vanilla weapons and armour are no longer sold in shops.

## Balance
- **Same max hit formula for all three styles:** (damage bonus + level) / 6.76, using your current Strength, Ranged or
  Magic level, so damage keeps growing all the way to 150. Each tier's melee, ranged and magic gear gets the same damage
  budget, so each style's full-set max hit is within 1–3 of the others.
- **Accuracy scales to 150 as well.** Every hit on an NPC rolls your Attack, Ranged or Magic level plus the style's bonus
  against the NPC's tier defence; GodzHell had no accuracy before. Custom NPCs roll against your Defence level and
  armour, so Defence also matters to 150.
- **Fixes:**
  - Magic damage now scales with gear instead of being fixed per spell.
  - Ranged hits now use the real ranged max hit (they were always random(15)) and the ranged bonus (the stab defence bonus was read by mistake).
  - Every custom bow and crossbow now fires as a ranged weapon; before, only a few hard-coded bow IDs did. Bows and crossbows both use arrows.
  - Food now heals up to your real max HP; it stopped at 99 before.
- **Monsters have about one full-set hit of HP**, so you one-hit lower tiers as you progress. Guardians and bosses take
  longer. Custom NPC damage is reduced by your armour, so armour upgrades count.
- **Custom gear is well above vanilla:** tier 1 already beats rune, and the stat scale comes from the old custom servers' own items.

## How it was made (for tinkering)
- **Content is regenerated by scripts:**
  - `tools/build_world.py` merges the old servers.
  - `tools/progression4.py` builds the cache, NPCs, items, models, tiers, drops and menus.
  - `tools/patch_java.py` adds the code hooks.
  - `tools/verify_cache.py` checks the result.
  - Settings live in `tools/world.example.json` (edit the paths first).
  - After changing sources, run `build.sh` / `build.bat` (needs a JDK) to rebuild the jars.
- **Custom models are new model files.** Each starts from a base mesh with its face colours rewritten, keeping the original shading:
  - gear uses a two-colour scheme (lighter faces take the main colour, darker faces the trim);
  - NPCs use two-tone bands by height;
  - Rainbow items use a rainbow gradient. They're written into the cache, and a small client patch lets the client load
  models past its original table. 871 were generated, and 591 extra models came from the Project Insanity cache.
- **Custom NPCs** (IDs 3852–3927) are new definitions in the cache. The server runs each one as its base NPC, so attacks and
  animations work, and sends the custom ID to the client.
- **Code changes** are all marked `// RetroRemake`:
  - `RetroContent.java`: menus, Slayer, events, drops, mystery boxes, custom NPCs, damage formulas, weapon animation templates;
  - NPC spawn, death and drop hooks;
  - health bars above 255 HP;
  - item and model limits raised;
  - the level cap raised to 150 on the server and the client;
  - branding.
- **Security fixes:**
  - owner commands no longer depend on usernames;
  - the password lookups are disabled;
  - the auto-restart that killed every Java process is disabled;
  - the old owners' data is removed;
  - the fake ×3 online count is fixed.
- **Removed:** about 7,500 vanilla monster spawns, vanilla teleports other than skilling and home, and 964 vanilla weapons and armour pieces from shops.

## Tested so far, and not yet
**Checked here:**
- **The server was started and played through with a test client** that speaks the game protocol:
  - login (you start at home);
  - the main menu → Teleports → Tier 1 → teleport, using real button clicks;
  - Slayer task assignment, saved to the character's `.retro` file;
  - `::tiers`, `::progress`, `::task`, `::event`, `::help`, `::tp market`, `::home`;
  - logout saving and logging back in.
  None of it produced any server errors.
- Everything compiles (Java 8 bytecode).
- The jars have the right entry points.
- Every item and NPC definition decodes the way the client reads it.
- Every model they use exists and is in the old format.
- Every NPC ID, animation and model ID is within the client's limits.
- The style balance numbers above come from the generated stats.

**Not checked here (needs the real game window):**
- how the custom models and NPCs look in game;
- combat against custom NPCs;
- gear animations;
- an event boss spawning (10 minutes after start-up).

The test client can't draw anything, so those need a real playthrough.

A few base meshes have parts the recolour can't reach (bones, textured faces), so those keep their original colour.

## Origin and licence
GodzHell and the other source servers come from community archives and GitHub uploads with no licence, and the game cache is
Jagex's property. RetroRemakeRSPS is for private, personal use.
