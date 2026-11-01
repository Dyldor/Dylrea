#!/bin/sh
# Rebuild everything from source (needs a JDK 8+). Players do not need this: the jars are already included.
set -e
cd "$(dirname "$0")"
rm -rf out && mkdir -p out/server out/client out/launcher lib
javac -nowarn -encoding ISO-8859-1 --release 8 -d out/server server/*.java
find client -name '*.java' > out/client-sources.txt
javac -nowarn -encoding ISO-8859-1 --release 8 -d out/client @out/client-sources.txt
javac -nowarn --release 8 -d out/launcher launcher/Launcher.java
jar cf lib/server.jar -C out/server .
jar cf lib/client.jar -C out/client .
jar cfe RetroRemakeRSPS.jar Launcher -C out/launcher .
echo "Built lib/server.jar, lib/client.jar and RetroRemakeRSPS.jar"
