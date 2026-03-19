#!/bin/bash
cd "$(dirname "$0")"
source .venv/bin/activate

python3 app.py &
sleep 2
firefox http://127.0.0.1:8000 &
python3 ble_combined.py

kill %1 2>/dev/null
