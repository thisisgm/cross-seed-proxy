#!/bin/bash
curl -X POST "http://localhost:5000/webhook" \
-H "Content-Type: application/json" \
-d '{
  "extra": {
    "result": "INJECTED",
    "name": "Suits.L.A.S01E10.Slugfest.1080p",
    "trackers": ["Blutopia", "FileList", "Aither"],
    "searchee": {
      "path": "Suits.L.A.S01E10.Slugfest.1080p.mkv"
    }
  }
}'