import sqlite3
import random
from datetime import datetime, date, timedelta, timezone

DB = "sleep.db"

def to_unix(dt: datetime) -> int:
    return int(dt.replace(tzinfo=timezone.utc).timestamp())

def make_fake_session(night_date: date):
    # pretend sleep 23:00 -> 07:00-ish
    start = datetime(night_date.year, night_date.month, night_date.day, 23, 0, 0)
    end = start + timedelta(minutes=random.randint(420, 520))  # 7h..8h40m
    total_minutes = int((end - start).total_seconds() / 60)

    # stage segments
    stages = ["Awake", "Light", "Deep", "REM"]
    weights = [6, 46, 24, 24]
    segs = []
    remaining = total_minutes
    cursor = start
    while remaining > 0:
        stage = random.choices(stages, weights=weights, k=1)[0]
        dur = min(remaining, random.choice([5, 10, 15, 20, 25, 30]))
        seg_start = cursor
        seg_end = cursor + timedelta(minutes=dur)
        segs.append((to_unix(seg_start), to_unix(seg_end), stage))
        cursor = seg_end
        remaining -= dur

    awake_min = sum(int((e - s) / 60) for s, e, st in segs if st == "Awake")
    total_sleep_min = max(0, total_minutes - awake_min)
    efficiency = int(100 * total_sleep_min / total_minutes) if total_minutes else 0

    base_hr = random.randint(52, 68)
    awakenings = random.randint(0, 6)
    hrv = random.randint(20, 90)

    # fake spo2
    avg_spo2 = random.randint(94, 97)
    min_spo2 = random.randint(88, avg_spo2)

    # score (roughly depends on sleep + efficiency)
    score = int(50 + (total_sleep_min / 480) * 35 + (efficiency / 100) * 15 + random.randint(-8, 8))
    score = max(35, min(98, score))

    # samples every 10s
    step = 10
    n_samples = int((end - start).total_seconds() // step)
    samples = []
    for i in range(n_samples):
        ts = to_unix(start + timedelta(seconds=i * step))
        hr = base_hr + int(6 * (random.random() - 0.5)) + random.randint(-1, 1)
        spo2 = avg_spo2 + int(3 * (random.random() - 0.5))
        spo2 = max(85, min(100, spo2))
        samples.append((ts, hr, spo2))

    session_row = {
        "night_date": night_date.isoformat(),
        "start_ts": to_unix(start),
        "end_ts": to_unix(end),
        "sleep_score": score,
        "total_sleep_min": total_sleep_min,
        "sleep_efficiency": efficiency,
        "awakenings": awakenings,
        "resting_hr_bpm": base_hr,
        "hrv_rmssd_ms": hrv,
        "avg_spo2": avg_spo2,
        "min_spo2": min_spo2,
    }
    return session_row, samples, segs

def main():
    con = sqlite3.connect(DB)
    con.execute("PRAGMA foreign_keys = ON;")

    with open("schema.sql", "r", encoding="utf-8") as f:
        con.executescript(f.read())

    # clear old fake data
    con.execute("DELETE FROM stage_segments;")
    con.execute("DELETE FROM samples;")
    con.execute("DELETE FROM sessions;")

    for i in range(14):
        nd = date.today() - timedelta(days=i + 1)
        sess, samples, segs = make_fake_session(nd)

        cur = con.execute(
            """
            INSERT INTO sessions (
              night_date, start_ts, end_ts,
              sleep_score, total_sleep_min, sleep_efficiency, awakenings,
              resting_hr_bpm, hrv_rmssd_ms, avg_spo2, min_spo2
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                sess["night_date"], sess["start_ts"], sess["end_ts"],
                sess["sleep_score"], sess["total_sleep_min"], sess["sleep_efficiency"], sess["awakenings"],
                sess["resting_hr_bpm"], sess["hrv_rmssd_ms"], sess["avg_spo2"], sess["min_spo2"]
            ),
        )
        session_id = cur.lastrowid

        con.executemany(
            "INSERT INTO samples(session_id, ts, hr_bpm, spo2_pct) VALUES (?,?,?,?)",
            [(session_id, ts, hr, sp) for ts, hr, sp in samples],
        )

        con.executemany(
            "INSERT INTO stage_segments(session_id, start_ts, end_ts, stage) VALUES (?,?,?,?)",
            [(session_id, s, e, st) for s, e, st in segs],
        )

    con.commit()
    con.close()
    print("Seeded sleep.db with 14 fake nights.")

if __name__ == "__main__":
    main()