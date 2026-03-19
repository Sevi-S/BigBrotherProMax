# BigBrotherProMax — Sleep Tracker

## First time setup

```bash
git clone <repo-url>
cd BigBrotherProMax
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
./start.sh
```

## Running (after setup)

Check that bluetooth is enabled on the raspi. From the gnome menu.

after reboot restart the pythone venv

```bash
source .venv/bin/activate
```

then run the start up script

```bash
./start.sh
```

This starts the web UI, opens Firefox, and begins scanning for BLE devices.

Press **Ctrl+C** to stop.

## How it works

1. The watch button press starts a capture session
2. Oximeter and accelerometer data are recorded together
3. When the watch stops sending, the session ends and analysis runs
4. Results are uploaded to the local database
5. View sleep data at http://127.0.0.1:8000
