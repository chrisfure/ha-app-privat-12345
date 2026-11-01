#!/bin/sh
set -e

DEST=/homeassistant/www/smarthus
mkdir -p "$DEST"
cp /www/smarthus-card.js /www/loader.js /www/version.txt "$DEST/"

echo "Smarthus er installert (versjon $(cat /www/version.txt))."
echo "Ressursadresse: /local/smarthus/loader.js (JavaScript-modul)"
