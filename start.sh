#!/bin/bash
cd "$(dirname "$0")"
source ../.venv/bin/activate

python3 app.py &
python3 ble_combined.py

kill %1 2>/dev/null
