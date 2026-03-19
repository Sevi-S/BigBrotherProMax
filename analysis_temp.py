import pandas as pd


def analyse(df: pd.DataFrame) -> dict:
    """
    Input df columns: ts, source, hr_bpm, spo2_pct, ax_mg, ay_mg, az_mg, steps

    Must return:
    {
        "kpis": {
            "sleep_score": int,
            "total_sleep_min": int,
            "sleep_efficiency": int,   # 0-100
            "awakenings": int,
            "resting_hr_bpm": int,
            "hrv_rmssd_ms": int,
            "avg_spo2": int,
            "min_spo2": int,
        },
        "stages": pd.DataFrame  # columns: start_ts, end_ts, stage
                                # stage values: 'Awake', 'Light', 'Deep', 'REM'
    }
    """
    # --- your implementation here ---

    raise NotImplementedError("analyse() not implemented yet")
