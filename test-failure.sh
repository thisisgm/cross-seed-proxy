#!/bin/bash
curl -X POST "http://localhost:5000/webhook" \
-H "Content-Type: application/json" \
-d '{
  "extra": {
    "result": "FAILURE",
    "name": "House.M.D.S02E01.1080p",
    "trackers": ["Blutopia", "TorrentLeech"],
    "searchee": {
      "path": "House.M.D.S02E01.1080p.mkv"
    }
  }
}'