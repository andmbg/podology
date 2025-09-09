#!/bin/bash
EID="$1"
DB_PATH="data/Knowledge Fight/Knowledge Fight.db"
T_PATH="data/Knowledge Fight/transcripts/$EID.json"
WC_PATH="data/Knowledge Fight/wordclouds/$EID.png"

if [ -z "$EID" ]; then
    echo "Usage: $0 <episode_id>"
    exit 1
fi

echo "Cleaning up episode: $EID"

sqlite3 "$DB_PATH" "
DELETE FROM named_entity_tokens WHERE eid = '$EID';
SELECT changes() as 'Total rows deleted';
DELETE FROM named_entity_types WHERE eid = '$EID';
SELECT changes() as 'Total rows deleted';
DELETE FROM type_proximity_episode WHERE eid = '$EID';
SELECT changes() as 'Total rows deleted';
DELETE FROM word_count WHERE eid = '$EID';
SELECT changes() as 'Total rows deleted';
"

rm -f "$T_PATH"
rm -f "$WC_PATH"

echo "Cleanup complete for episode $EID"
