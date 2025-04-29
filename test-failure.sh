#!/bin/bash
curl -X POST "http://localhost:5000/webhook" \
-H "Content-Type: application/json" \
-d '{
  "extra": {
    "result": "FAILURE",
    "trackers": ["Aither", "Blutopia"],
    "searchee": {
      "path": "Some.Failed.Torrent.Name.1080p"
    }
  }
}'
