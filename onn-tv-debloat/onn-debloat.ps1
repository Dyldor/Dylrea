# onn Google TV box debloat for Windows — reversible (per-user uninstall, nothing removed from /system).
# Usage (PowerShell, in this folder):
#   powershell -ExecutionPolicy Bypass -File .\onn-debloat.ps1 -Ip 192.168.1.50            # dry run
#   powershell -ExecutionPolicy Bypass -File .\onn-debloat.ps1 -Ip 192.168.1.50 -Apply     # remove
#   powershell -ExecutionPolicy Bypass -File .\onn-debloat.ps1 -Ip 192.168.1.50 -Restore   # undo
param(
  [Parameter(Mandatory = $true)][string]$Ip,
  [switch]$Apply,
  [switch]$Restore
)

$adb = (Get-Command adb -ErrorAction SilentlyContinue).Source
if (-not $adb -and (Test-Path "$PSScriptRoot\platform-tools\adb.exe")) { $adb = "$PSScriptRoot\platform-tools\adb.exe" }
if (-not $adb) { Write-Error "adb not found. Install Android SDK Platform-Tools (winget install Google.PlatformTools) or unzip it into this folder."; exit 1 }

$dev = "${Ip}:5555"
& $adb connect $dev | Out-Null
& $adb -s $dev wait-for-device
function Sh([string]$cmd) { & $adb -s $dev shell $cmd }

# Safe to remove. Edit freely — delete lines for apps you actually use.
$Pkgs = @(
  'com.google.android.youtube.tvmusic',        # YouTube Music
  'com.google.android.youtube.tvkids',         # YouTube Kids
  'com.google.android.videos',                 # Google TV / Play Movies
  'com.google.android.play.games',             # Play Games
  'com.google.android.feedback',               # Feedback reporter
  'com.android.printspooler',                  # Print spooler
  'com.google.android.apps.tv.launcherx.coldstart', # Preloaded promo content
  'com.vudu.air.DownloaderTablet',             # Vudu / Fandango at Home
  'com.walmart.android',                       # Walmart
  'com.amazon.amazonvideo.livingroom',         # Prime Video
  'com.disney.disneyplus',                     # Disney+
  'com.hulu.livingroomplus',                   # Hulu
  'com.peacocktv.peacockandroid',              # Peacock
  'com.tubitv',                                # Tubi
  'com.sling',                                 # Sling
  'com.frndlytv.android',                      # Frndly
  'tv.pluto.android',                          # Pluto TV
  'com.netflix.ninja'                          # Netflix
)
# DO NOT remove: launcherx, tvrecommendations, gms, vending (Play Store), setupwraith, tv.settings,
# or anything with "onn"/"amlogic"/"droidlogic".

$Listen = @('com.google.android.katniss', 'com.google.android.apps.tv.dreamx')  # Assistant/voice, ambient screensaver
$Mic    = @('com.google.android.gms', 'com.google.android.apps.tv.launcherx', 'com.google.android.katniss')

if ($Restore) {
  foreach ($p in $Pkgs)   { $o = Sh "cmd package install-existing $p" 2>$null; if ($o -match 'installed') { "restored $p" } }
  foreach ($p in $Listen) { Sh "pm enable $p" }
  foreach ($p in $Mic)    { Sh "pm grant $p android.permission.RECORD_AUDIO" 2>$null }
  exit 0
}

$installed = (Sh "pm list packages") -replace '^package:', ''
foreach ($p in $Pkgs) {
  if ($installed -notcontains $p) { continue }
  if ($Apply) { Write-Host -NoNewline "${p}: "; Sh "pm uninstall -k --user 0 $p" }
  else { "would remove: $p" }
}

if ($Apply) {
  foreach ($p in $Listen) { Write-Host -NoNewline "disable ${p}: "; Sh "pm disable-user --user 0 $p" }
  foreach ($p in $Mic)    { Sh "pm revoke $p android.permission.RECORD_AUDIO" 2>$null; if ($LASTEXITCODE -eq 0) { "mic revoked: $p" } }
  Sh "settings put global send_action_app_error 0"
  Sh "settings put secure send_action_app_error 0"
  Sh "settings put global window_animation_scale 0.5"
  Sh "settings put global transition_animation_scale 0.5"
  Sh "settings put global animator_duration_scale 0.5"
} else {
  foreach ($p in $Listen) { "would disable: $p" }
  "Dry run only. Re-run with -Apply."
}
