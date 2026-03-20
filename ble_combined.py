import asyncio
import struct
import time
from bleak import BleakScanner, BleakClient
import pandas as pd

from sleep import process

#Device names
OXIMETER_NAME = "ESP32_Oximeter"
WATCH_NAME    = "BigBrotherWatch"
WATCH_ADDRESS = "94:B5:55:C8:E9:C6"

SERVICE_UUID = "6E400001-B5A3-F393-E0A9-E50E24DCCA9E".lower()
TX_UUID      = "6E400003-B5A3-F393-E0A9-E50E24DCCA9E"

#Accel frame format
BLE_CHUNK_MAGIC     = 0xBC
FRAME_HEADER_FORMAT = "<HH"
PAYLOAD_FORMAT      = "<BBBBIIIhhhIHBB"
CHECKSUM_FORMAT     = "<H"

WATCH_TIMEOUT = 30  # seconds

#Session state
_rows           = []
_session_active = False
_last_watch_ts  = None
_both_connected = False

watch_state = {"msg_id": None, "expected": 0, "chunks": {}}


def checksum16(data: bytes) -> int:
    return sum(data) & 0xFFFF


def decode_frame(frame: bytes) -> dict | None:
    hs = struct.calcsize(FRAME_HEADER_FORMAT)
    ps = struct.calcsize(PAYLOAD_FORMAT)
    cs = struct.calcsize(CHECKSUM_FORMAT)
    if len(frame) != hs + ps + cs:
        return None
    fields = struct.unpack_from(PAYLOAD_FORMAT, frame, hs)
    checksum_rx, = struct.unpack_from(CHECKSUM_FORMAT, frame, hs + ps)
    (_, _, _, _, send_ms, _, _, ax_mg, ay_mg, az_mg, steps, _, batt_pct, _) = fields
    return {
        "ax_mg": ax_mg, "ay_mg": ay_mg, "az_mg": az_mg,
        "steps": steps,
        "checksum_ok": checksum_rx == checksum16(frame[hs:hs + ps]),
    }


def session_start():
    global _session_active
    if _session_active or not _both_connected:
        return
    _session_active = True
    _rows.clear()
    print("[SESSION START]")


def session_end():
    global _session_active
    if not _session_active:
        return
    _session_active = False
    print("[SESSION END] Running analysis...")

    df = pd.DataFrame(_rows, columns=["ts", "source", "hr_bpm", "spo2_pct", "ax_mg", "ay_mg", "az_mg", "steps"])
    process(df)

    _rows.clear()
    print("[READY] Waiting for next session...")


#Handlers
def oximeter_handler(sender, data: bytearray):
    ts = time.time()
    print(f"[OXI_RAW| {ts:.3f}] len={len(data)} {data[:40]}")
    if not _session_active:
        return  # ignore oxi data outside of a session
    text = data.decode("utf-8", errors="ignore").strip()
    hr, spo2 = None, None
    try:
        parts = text.split(",")
        h, s = int(parts[1]), int(parts[2])
        if h != -1: hr = h
        if s != -1: spo2 = s
    except (IndexError, ValueError):
        pass
    _rows.append((ts, "oxi", hr, spo2, None, None, None, None))
    print(f"[OXI  | {ts:.3f}] {text}")


def watch_handler(sender, data: bytearray):
    global _last_watch_ts
    s = watch_state
    if len(data) < 4 or data[0] != BLE_CHUNK_MAGIC:
        return
    msg_id, chunk_idx, total_chunks = data[1], data[2], data[3]
    if s["msg_id"] != msg_id:
        s.update({"msg_id": msg_id, "expected": total_chunks, "chunks": {}})
    s["chunks"][chunk_idx] = bytes(data[4:])

    if len(s["chunks"]) == s["expected"]:
        ts = time.time()
        _last_watch_ts = ts
        session_start()
        try:
            full = b"".join(s["chunks"][i] for i in range(s["expected"]))
        except KeyError:
            s.update({"msg_id": None, "expected": 0, "chunks": {}})
            return
        d = decode_frame(full)
        if d and d["checksum_ok"]:
            _rows.append((ts, "watch", None, None, d["ax_mg"], d["ay_mg"], d["az_mg"], d["steps"]))
            print(f"[ACCEL| {ts:.3f}] ax={d['ax_mg']:6d} ay={d['ay_mg']:6d} az={d['az_mg']:6d} steps={d['steps']}")
        s.update({"msg_id": None, "expected": 0, "chunks": {}})


async def session_watchdog():
    while True:
        await asyncio.sleep(5)
        if _session_active and _last_watch_ts and time.time() - _last_watch_ts > WATCH_TIMEOUT:
            print(f"[WATCHDOG] No watch data for {WATCH_TIMEOUT}s.")
            session_end()


_connected = {OXIMETER_NAME: False, WATCH_NAME: False}

async def connect_device(name, handler, device):
    global _both_connected
    if device is None:
        print(f"{name} not found during scan")
        return
    print(f"Connecting to {name} ({device.address})")
    async with BleakClient(device) as client:
        if not client.is_connected:
            print(f"{name} failed to connect")
            return
        # Find a notify-capable characteristic
        notify_char = None
        if TX_UUID.lower() in [c.uuid.lower() for s in client.services for c in s.characteristics]:
            notify_char = TX_UUID
        else:
            for svc in client.services:
                for c in svc.characteristics:
                    if "notify" in c.properties:
                        notify_char = c.uuid
                        break
                if notify_char:
                    break
        if notify_char is None:
            print(f"{name}: no notify characteristic found!")
            return
        if notify_char.lower() != TX_UUID.lower():
            print(f"{name}: using characteristic {notify_char}")
        await client.start_notify(notify_char, handler)
        _connected[name] = True
        print(f"{name} connected ✓")
        if all(_connected.values()):
            _both_connected = True
            print("[READY] Both devices connected, waiting for watch data...")
        while True:
            await asyncio.sleep(2)
            if not client.is_connected:
                _connected[name] = False
                _both_connected = False
                print(f"{name} disconnected!")
                return


async def main():
    found = {OXIMETER_NAME: None, WATCH_NAME: None}

    while any(v is None for v in found.values()):
        missing = [n for n, d in found.items() if d is None]
        print(f"Scanning for: {', '.join(missing)}...")
        devices = await BleakScanner.discover(timeout=8.0, return_adv=True)
        for d, adv in devices.values():
            if d.name in found and found[d.name] is None:
                found[d.name] = d
                print(f"Found: {d.name}")
            elif found[WATCH_NAME] is None and d.address == WATCH_ADDRESS:
                found[WATCH_NAME] = d
                print(f"Found: {WATCH_NAME} (addr={d.address})")
        if any(v is None for v in found.values()):
            print("Retrying in 5s...")
            await asyncio.sleep(5)

    try:
        await asyncio.gather(
            connect_device(OXIMETER_NAME, oximeter_handler, found[OXIMETER_NAME]),
            connect_device(WATCH_NAME, watch_handler, found[WATCH_NAME]),
            session_watchdog(),
        )
    finally:
        session_end()


asyncio.run(main())
