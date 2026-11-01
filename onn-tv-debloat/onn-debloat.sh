#!/usr/bin/env bash
# onn Google TV box debloat — reversible (per-user uninstall, nothing removed from /system).
# Usage:  ./onn-debloat.sh <TV_IP>          (dry run: shows what would be removed)
#         ./onn-debloat.sh <TV_IP> --apply  (actually remove)
#         ./onn-debloat.sh <TV_IP> --restore
set -u
IP="${1:?Usage: $0 <TV_IP> [--apply|--restore]}"; MODE="${2:-}"
adb connect "$IP:5555" >/dev/null; adb -s "$IP:5555" wait-for-device
A="adb -s $IP:5555 shell"

# Safe to remove. Edit freely — comment out anything you actually use.
PKGS=(
  com.google.android.youtube.tvmusic      # YouTube Music
  com.google.android.youtube.tvkids       # YouTube Kids
  com.google.android.videos               # Google TV / Play Movies
  com.google.android.play.games           # Play Games
  com.google.android.feedback             # Feedback reporter
  com.android.printspooler                # Print spooler
  com.google.android.apps.tv.launcherx.coldstart  # Preloaded promo content
  com.vudu.air.DownloaderTablet           # Vudu / Fandango at Home
  com.walmart.android                     # Walmart
  com.amazon.amazonvideo.livingroom       # Prime Video
  com.disney.disneyplus                   # Disney+
  com.hulu.livingroomplus                 # Hulu
  com.peacocktv.peacockandroid            # Peacock
  com.tubitv                              # Tubi
  com.sling                               # Sling
  com.frndlytv.android                    # Frndly
  tv.pluto.android                        # Pluto TV
  com.netflix.ninja                       # Netflix
)
# DO NOT remove: launcherx, tvrecommendations, gms, vending (Play Store), setupwraith, tv.settings, or anything with "onn"/"amlogic"/"droidlogic".

for p in "${PKGS[@]}"; do
  if [[ "$MODE" == "--restore" ]]; then
    $A cmd package install-existing "$p" 2>/dev/null | grep -q installed && echo "restored $p"
    continue
  fi
  $A pm list packages | grep -qx "package:$p" || continue
  if [[ "$MODE" == "--apply" ]]; then echo -n "$p: "; $A pm uninstall -k --user 0 "$p"
  else echo "would remove: $p"; fi
done

# --- Privacy: stop listening + reduce tracking ---
LISTEN=(com.google.android.katniss com.google.android.apps.tv.dreamx)  # Assistant/voice, ambient screensaver (ads)
MIC=(com.google.android.gms com.google.android.apps.tv.launcherx com.google.android.katniss)
if [[ "$MODE" == "--apply" ]]; then
  for p in "${LISTEN[@]}"; do echo -n "disable $p: "; $A pm disable-user --user 0 "$p"; done
  for p in "${MIC[@]}"; do $A pm revoke "$p" android.permission.RECORD_AUDIO 2>/dev/null && echo "mic revoked: $p"; done
  $A settings put global send_action_app_error 0
  $A settings put secure send_action_app_error 0
  $A settings put global window_animation_scale 0.5
  $A settings put global transition_animation_scale 0.5
  $A settings put global animator_duration_scale 0.5
elif [[ "$MODE" == "--restore" ]]; then
  for p in "${LISTEN[@]}"; do $A pm enable "$p"; done
  for p in "${MIC[@]}"; do $A pm grant "$p" android.permission.RECORD_AUDIO 2>/dev/null; done
fi
[[ -z "$MODE" ]] && echo "Dry run only. Re-run with --apply."
