PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS sessions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  night_date TEXT NOT NULL UNIQUE,              -- "YYYY-MM-DD" (night started previous evening)
  start_ts INTEGER NOT NULL,                    -- unix seconds
  end_ts INTEGER NOT NULL,

  sleep_score INTEGER NOT NULL,
  total_sleep_min INTEGER NOT NULL,
  sleep_efficiency INTEGER NOT NULL,            -- 0..100
  awakenings INTEGER NOT NULL,

  resting_hr_bpm INTEGER NOT NULL,
  hrv_rmssd_ms INTEGER NOT NULL,

  avg_spo2 INTEGER NOT NULL,
  min_spo2 INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS samples (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id INTEGER NOT NULL,
  ts INTEGER NOT NULL,                          -- unix seconds
  hr_bpm INTEGER,
  spo2_pct INTEGER,
  FOREIGN KEY(session_id) REFERENCES sessions(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_samples_session_ts
ON samples(session_id, ts);

CREATE TABLE IF NOT EXISTS stage_segments (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id INTEGER NOT NULL,
  start_ts INTEGER NOT NULL,
  end_ts INTEGER NOT NULL,
  stage TEXT NOT NULL CHECK(stage IN ('Awake','Light','Deep','REM')),
  FOREIGN KEY(session_id) REFERENCES sessions(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_stages_session_start
ON stage_segments(session_id, start_ts);