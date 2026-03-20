DURATION_WEIGHT = 0.2
HR_WEIGHT = 0.2
SPO2_WEIGHT = 0.2
ACCELEROMETRY_WEIGHT = 0.4

import sqlite3
import numpy as np
import pandas as pd

# df columns =  ts, source, hr_bpm, spo2_pct, ax_mg, ay_mg, az_mg, steps, batt_pct

def process(df: pd.DataFrame):
    original = df.copy()
    df["datetime"] = pd.to_datetime(df["ts"], unit="s")
    df = df.sort_values("datetime").set_index("datetime")
    spo2 = df[["spo2_pct"]]
    acc = df[["ts", "ax_mg", "ay_mg", "az_mg"]]
    BPM = df[["hr_bpm"]]
    time = df.index.to_series()

    spo2_scores, avg_spo2, min_spo2 = spo2_score(spo2)
    acc_scores = acc_score(acc)
    BPM_scores, avg_BPM = BPM_score(BPM)

    total_by_minutes = (
        spo2_scores * SPO2_WEIGHT +
        acc_scores * ACCELEROMETRY_WEIGHT +
        BPM_scores * HR_WEIGHT
    )

    bins = [0, 25, 50, 75, 100]
    labels = ["Awake", "Light", "Deep", "REM"]
    stages = total_by_minutes.to_frame(name="score")

    stages["stage"] = pd.cut(
        stages["score"],
        bins=bins,
        labels=labels,
        include_lowest=True
    )

    total_score = (
        total_by_minutes.mean() +
        duration_score(time) * DURATION_WEIGHT
    )

    SQL_upload(original, stages, total_score, avg_BPM, avg_spo2, min_spo2)

def spo2_score(spo2_data: pd.DataFrame):
    spo2_data = spo2_data.replace(-1, pd.NA)
    avg_spo2 = spo2_data["spo2_pct"].mean()
    min_spo2 = float(spo2_data["spo2_pct"].min())
    
    spo2_by_minute = average_by_minutes(spo2_data)
    ox = spo2_by_minute["spo2_pct"]



    spo2_by_minute["spo2_score"] = np.select(
        [
            ox <= 92,               # spo02 <= 92% sumn aint right
            (ox > 92) & (ox < 98),  #
            ox >= 98                # SpO2 >= 98% good
        ],
        [
            0,
            (ox-92)/6,
            1
        ],
        default=0
    )
    spo2_by_minute["spo2_score"] = spo2_by_minute["spo2_score"].clip(0, 1)
    return spo2_by_minute["spo2_score"], avg_spo2, min_spo2

def acc_score(acc_data: pd.DataFrame):
    acc_data["dt"] = acc_data.index.to_series().diff().dt.total_seconds()
    acc_data[["dx_dt", "dy_dt", "dz_dt"]] = (
        acc_data[["ax_mg", "ay_mg", "az_mg"]].diff().div(acc_data["dt"], axis=0)
    )
    # magnitude of jerk
    acc_data["jerk_mag"] = (
        (acc_data["dx_dt"]**2 + acc_data["dy_dt"]**2 + acc_data["dz_dt"]**2) ** 0.5
    )
    acc_data_by_minutes = average_by_minutes(acc_data[["jerk_mag"]])

    q05 = acc_data_by_minutes["jerk_mag"].quantile(0.05)
    q95 = acc_data_by_minutes["jerk_mag"].quantile(0.95)

    if q95 > q05:
        acc_data_by_minutes["acc_score"] = 1 - ((acc_data_by_minutes["jerk_mag"] - q05) / (q95 - q05))
        acc_data_by_minutes["acc_score"] = acc_data_by_minutes["acc_score"].clip(0, 1)
    else:
        acc_data_by_minutes["acc_score"] = 1.0

    return acc_data_by_minutes["acc_score"]

def BPM_score(HR_data: pd.DataFrame):
    HR_data = HR_data.replace(-1, pd.NA)
    avg_bpm = float(HR_data["hr_bpm"].mean())
    hr_by_minute = average_by_minutes(HR_data)
    hr = hr_by_minute["hr_bpm"]*0.75

    hr_by_minute["hr_score"] = np.select(
        [
            hr < 40,                    # hr < 40 sumn aint right
            (hr >= 40) & (hr <= 70),    # 40 =< hr <= 70 very good calm hr
            (hr > 70) & (hr < 100),     # bit elevated
            hr >= 100                   # hr >= 100 during sleep very high
        ],
        [
            0,
            1,
            (100 - hr) / 30,
            0
        ],
        default=0
    )
    hr_by_minute["hr_score"] = hr_by_minute["hr_score"].clip(0, 1)
    return hr_by_minute["hr_score"], avg_bpm

def duration_score(time_data):
    duration = ( time_data.max() - time_data.min() ).total_seconds() / 3600   # convert time to hours
    if (7 < duration) & (duration < 9):
        return 1
    elif duration >= 9:
        return 9/duration
    else:
        return duration/7

def average_by_minutes(df: pd.DataFrame):
    df = df.copy()
    df["minute"] = df.index.to_series().dt.floor("min")
    result = df.groupby("minute").mean()
    return result

def SQL_upload(df: pd.DataFrame, stages_df: pd.Series, sleep_score: float, avg_BPM:float, avg_spo2: float, min_spo2: float):
    DB = "sleep.db"
    con = sqlite3.connect(DB)

    time = pd.to_datetime(df["ts"], unit="s")

    date = time.max().date()  # or time.min().date()
    start_ts = df["ts"].min()
    end_ts = df["ts"].max()
    total_sleep_min = ( time.max() - time.min() ).total_seconds() / 60

    # --- 1. Create session row, get its ID ---
    # cur = con.cursor()
    # cur.execute(allat)
    cur = con.execute(
        "INSERT INTO sessions (night_date, start_ts, end_ts, sleep_score, total_sleep_min, "
        "resting_hr_bpm, avg_spo2, min_spo2) "
        "VALUES (?,?,?,?,?,?,?,?)", 
        (date, start_ts, end_ts, sleep_score, total_sleep_min, avg_BPM, avg_spo2, min_spo2)
    )
    session_id = cur.lastrowid

    # upload raw samples from original dataframe 
    df["session_id"] = session_id
    df.to_sql("samples", con, if_exists="append", index=False)

    # --- 3. Upload stage segments ---
    # stages_df must have columns: start_ts, end_ts, stage
    
    stages_df["start_ts"] = start_ts
    stages_df["end_ts"] = end_ts
    stages_df["session_id"] = session_id
    stages_df[["session_id", "start_ts", "end_ts", "stage"]].to_sql("stage_segments", con, if_exists="append", index=False)

    con.commit()
    con.close()
