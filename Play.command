#!/bin/sh
# RetroRemakeRSPS - double-click to play (macOS).
cd "$(dirname "$0")"
if ! command -v java >/dev/null 2>&1; then
  osascript -e 'display dialog "Java is not installed. Install Java 8 or newer from https://adoptium.net and try again." buttons {"OK"}' >/dev/null 2>&1
  open "https://adoptium.net"
  exit 1
fi
exec java -jar RetroRemakeRSPS.jar
