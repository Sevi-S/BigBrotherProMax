PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS sessions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  night_date TEXT NOT NULL UNIQUE,          -- "YYYY-MM-DD"
  start_ts INTEGER NOT NULL,                -- unix seconds
  end_ts INTEGER,                           -- set when session ends

  sleep_score INTEGER,
  total_sleep_min INTEGER,
  sleep_efficiency INTEGER,                 -- 0..100
  awakenings INTEGER,
  resting_hr_bpm INTEGER,
  hrv_rmssd_ms INTEGER,
  avg_spo2 INTEGER,
  min_spo2 INTEGER
);

CREATE TABLE IF NOT EXISTS samples (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id INTEGER NOT NULL,
  ts REAL NOT NULL,                         -- unix seconds
  source TEXT NOT NULL CHECK(source IN ('oxi','watch')),
  hr_bpm INTEGER,
  spo2_pct INTEGER,
  ax_mg INTEGER,
  ay_mg INTEGER,
  az_mg INTEGER,
  steps INTEGER,
  FOREIGN KEY(session_id) REFERENCES sessions(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_samples_session_ts ON samples(session_id, ts);

CREATE TABLE IF NOT EXISTS stage_segments (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id INTEGER NOT NULL,
  start_ts INTEGER NOT NULL,
  end_ts INTEGER NOT NULL,
  stage TEXT NOT NULL CHECK(stage IN ('Awake','Light','Deep','REM')),
  FOREIGN KEY(session_id) REFERENCES sessions(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_stages_session_start ON stage_segments(session_id, start_ts);
