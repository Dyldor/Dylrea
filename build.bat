@echo off
rem Rebuild everything from source (needs a JDK 8+). Players do not need this: the jars are already included.
cd /d "%~dp0"
if exist out rmdir /s /q out
mkdir out\server out\client out\launcher lib 2>nul
javac -nowarn -encoding ISO-8859-1 --release 8 -d out\server server\*.java || goto :fail
dir /s /b client\*.java > out\client-sources.txt
javac -nowarn -encoding ISO-8859-1 --release 8 -d out\client @out\client-sources.txt || goto :fail
javac -nowarn --release 8 -d out\launcher launcher\Launcher.java || goto :fail
jar cf lib\server.jar -C out\server . || goto :fail
jar cf lib\client.jar -C out\client . || goto :fail
jar cfe RetroRemakeRSPS.jar Launcher -C out\launcher . || goto :fail
echo Built lib\server.jar, lib\client.jar and RetroRemakeRSPS.jar
pause
exit /b 0
:fail
echo Build failed.
pause
exit /b 1
