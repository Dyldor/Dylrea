#!/bin/sh
# RetroRemakeRSPS - run to play (Linux).
cd "$(dirname "$0")"
if ! command -v java >/dev/null 2>&1; then
  echo "Java is not installed. Install Java 8 or newer (e.g. https://adoptium.net) and try again."
  exit 1
fi
exec java -jar RetroRemakeRSPS.jar
