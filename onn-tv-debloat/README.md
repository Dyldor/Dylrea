# onn TV box debloat

Reversible debloat + privacy hardening for a Walmart onn Google TV box over ADB.

**Easiest:** open this folder in Claude Code on your PC (Claude Desktop app → Code) and say
"debloat my onn TV box" — `CLAUDE.md` has the full context.

**Manual (Windows):**
```
winget install Google.PlatformTools
powershell -ExecutionPolicy Bypass -File .\onn-debloat.ps1 -Ip 192.168.x.x          # preview
powershell -ExecutionPolicy Bypass -File .\onn-debloat.ps1 -Ip 192.168.x.x -Apply   # do it
powershell -ExecutionPolicy Bypass -File .\onn-debloat.ps1 -Ip 192.168.x.x -Restore # undo
```
Mac/Linux: `./onn-debloat.sh <IP> [--apply|--restore]`.

Then do the manual TV settings listed in `CLAUDE.md` (Apps only mode, ads, diagnostics).
