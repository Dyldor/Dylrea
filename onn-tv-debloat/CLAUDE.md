# onn Google TV box debloat — context for Claude Code

This folder is a self-contained task, unrelated to the REA tool in the rest of this repo.
Ignore the repo-root AGENTS.md conventions for this folder.

## Goal (from the owner)
Debloat their Walmart **onn Google TV box** over ADB: remove bloat, **no ads**, and
**stop it listening to them or spying on them**. USB/network debugging is already on.

## How to do it
1. Make sure `adb` works (`adb version`). On Windows: `winget install Google.PlatformTools`.
2. Ask the user for the box's IP (TV: Settings → Network & Internet → their Wi-Fi).
3. Dry run first and show the user the list — **do not remove anything until they approve**:
   - Windows: `powershell -ExecutionPolicy Bypass -File .\onn-debloat.ps1 -Ip <IP>`
   - Mac/Linux: `./onn-debloat.sh <IP>`
   The first connection shows an "Allow debugging?" prompt on the TV — user must tick
   "Always allow" and accept.
4. Optionally run `adb shell pm list packages` and suggest other obvious bloat to the user.
   Ask whether they use Netflix / Prime Video / Disney+ etc. before removing those.
5. Apply with `-Apply` / `--apply`. Undo everything with `-Restore` / `--restore`.

## What the scripts do (all reversible)
- `pm uninstall -k --user 0` on preinstalled promo/streaming apps (restorable with
  `cmd package install-existing`).
- Disable Google Assistant (`com.google.android.katniss`) and the ambient screensaver
  (`com.google.android.apps.tv.dreamx`). **Voice button on the remote stops working.**
- Revoke microphone permission from Google Play Services, the launcher and Assistant.
- Turn off error reporting; set animations to 0.5x for snappier menus.

## Never remove / disable
`com.google.android.apps.tv.launcherx` (home screen, unless a replacement launcher is
installed and set first), `com.google.android.tvrecommendations`, `com.google.android.gms`,
`com.android.vending`, `com.google.android.tungsten.setupwraith`, `com.android.tv.settings`,
or anything containing `onn`, `amlogic`, `droidlogic`. These can bootloop or brick the UI.

## Manual steps on the TV (ADB can't do these) — remind the user
1. Settings → Accounts & Sign In → account → **Apps only mode: On** (biggest ad reduction;
   install wanted apps first, Play Store is hidden while on).
2. Settings → Privacy → Ads → **Delete advertising ID** / opt out of personalization.
3. Settings → Privacy → **Usage & Diagnostics: Off**.
4. Settings → Privacy → **Location: Off**.
5. Settings → Privacy → **Google Assistant: Off** (if shown).

## Optional: fully ad-free home screen
Install **Projectivy Launcher** from the Play Store, set it as default (Projectivy has a
setting for this), and only then consider `pm disable-user --user 0
com.google.android.apps.tv.launcherx`. Re-enable with `pm enable` if anything goes wrong.

## Honest limits
A Google TV box signed into a Google account still talks to Google; removing Play
Services would break the Play Store and most apps, so it's kept.
