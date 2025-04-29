#!/bin/bash
curl -X POST "http://localhost:5000/webhook" \
-H "Content-Type: application/json" \
-d '{
  "extra": {
    "result": "INJECTED",
    "trackers": ["Aither", "Blutopia", "FileList"],
    "searchee": {
      "path": "Suits.L.A.S01E10.Slugfest.1080p.AMZN.WEB-DL.DDP5.1.H.264-FLUX.mkv"
    }
  }
}'
