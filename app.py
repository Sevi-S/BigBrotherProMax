import sqlite3
from flask import Flask, jsonify, render_template_string, g

DB = "sleep.db"
app = Flask(__name__)

PAGE = """<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Sleep Tracker (Local)</title>
  <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
  <style>
    body { font-family: system-ui, sans-serif; margin: 24px; background: #0b0f16; color: #e6e6e6; }
    .row { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
    .card { background: #121a27; border: 1px solid #24324a; border-radius: 14px; padding: 16px; }
    .kpis { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; }
    .kpi { padding: 12px; border-radius: 12px; background:#0f1521; border:1px solid #24324a; }
    .kpi .v { font-size: 22px; font-weight: 700; margin-top: 6px; }
    select { background:#0f1521; color:#e6e6e6; border:1px solid #24324a; padding:8px 10px; border-radius:10px; }
    canvas { width: 100% !important; height: 280px !important; }
    .muted { color:#9bb0cc; font-size: 13px; }
  </style>
</head>
<body>
  <div style="display:flex; align-items:flex-end; justify-content:space-between; gap:16px;">
    <div>
      <h1 style="margin:0 0 8px;">Sleep Tracker (Localhost)</h1>
      <div class="muted">Sleep monitoring dashboard.</div>
    </div>
    <div>
      <label class="muted">Night:</label><br/>
      <select id="nightSelect"></select>
    </div>
  </div>

  <div class="card" style="margin-top:16px;">
    <div class="kpis" id="kpis"></div>
  </div>

  <div class="row" style="margin-top:16px;">
    <div class="card">
      <div style="display:flex;justify-content:space-between;align-items:center;">
        <strong>Sleep stages</strong><span class="muted">segments</span>
      </div>
      <canvas id="stagesChart"></canvas>
    </div>
    <div class="card">
      <div style="display:flex;justify-content:space-between;align-items:center;">
        <strong>Heart rate</strong><span class="muted">bpm</span>
      </div>
      <canvas id="hrChart"></canvas>
    </div>
  </div>

  <div class="row" style="margin-top:16px;">
    <div class="card">
      <div style="display:flex;justify-content:space-between;align-items:center;">
        <strong>SpO₂</strong><span class="muted">%</span>
      </div>
      <canvas id="spo2Chart"></canvas>
    </div>
    <div class="card">
      <div style="display:flex;justify-content:space-between;align-items:center;">
        <strong>History</strong><span class="muted">sleep score</span>
      </div>
      <canvas id="historyChart"></canvas>
    </div>
  </div>

<script>
let stagesChart, hrChart, spo2Chart, historyChart;

function fmtMinutes(m){ const h=Math.floor(m/60), mm=m%60; return `${h}h ${String(mm).padStart(2,'0')}m`; }
function stageColor(stage){
  return ({Awake:"#f87171", Light:"#60a5fa", Deep:"#34d399", REM:"#a78bfa"})[stage] || "#9ca3af";
}

function renderKpis(n){
  const k = document.getElementById("kpis");
  const items = [
    ["Sleep score", n.sleep_score],
    ["Total sleep", fmtMinutes(n.total_sleep_min)],
    ["Avg HR", `${n.avg_hr_bpm} bpm`],
    ["Avg SpO₂", `${n.avg_spo2}%`],
    ["Min SpO₂", `${n.min_spo2}%`],
  ];
  k.innerHTML = items.map(([label,val]) => `
    <div class="kpi"><div class="muted">${label}</div><div class="v">${val}</div></div>
  `).join("");
}

function makeStagesChart(segs){
  const labels = segs.map((_,i)=>`#${i+1}`);
  const data = segs.map(s=>s.duration_min);
  const colors = segs.map(s=>stageColor(s.stage));
  if (stagesChart) stagesChart.destroy();
  stagesChart = new Chart(document.getElementById("stagesChart"), {
    type:"bar",
    data:{ labels, datasets:[{ data, backgroundColor: colors }]},
    options:{
      plugins:{ legend:{display:false}, tooltip:{ callbacks:{ label:(ctx)=>`${segs[ctx.dataIndex].stage}: ${segs[ctx.dataIndex].duration_min} min` } } },
      scales:{ x:{ ticks:{display:false}, grid:{display:false} }, y:{ beginAtZero:true } }
    }
  });
}

function makeLine(canvasId, labels, values){
  return new Chart(document.getElementById(canvasId), {
    type:"line",
    data:{ labels, datasets:[{ data: values, tension:0.25, pointRadius:0 }] },
    options:{ plugins:{ legend:{display:false} }, scales:{ x:{ grid:{display:false} } } }
  });
}

async function loadNightOptions(){
  const r = await fetch("/api/nights");
  const nights = await r.json();
  const sel = document.getElementById("nightSelect");
  sel.innerHTML = "";
  nights.forEach(n=>{
    const opt = document.createElement("option");
    opt.value = n.night_date;
    opt.textContent = `${n.night_date}${n.sleep_score != null ? ' (score ' + n.sleep_score + ')' : ''}`;
    sel.appendChild(opt);
  });
  sel.onchange = ()=>loadNight(sel.value);
  if (nights.length) loadNight(nights[0].night_date);
}

async function loadHistory(){
  const r = await fetch("/api/nights");
  const nights = await r.json();
  const labels = nights.map(x=>x.night_date).reverse();
  const scores = nights.map(x=>x.sleep_score).reverse();
  if (historyChart) historyChart.destroy();
  historyChart = new Chart(document.getElementById("historyChart"), {
    type:"bar",
    data:{ labels, datasets:[{ data:scores }]},
    options:{ plugins:{ legend:{display:false} }, scales:{ y:{ beginAtZero:true, max:100 } } }
  });
}

async function loadNight(d){
  const r = await fetch(`/api/night/${d}`);
  const n = await r.json();

  renderKpis(n);
  makeStagesChart(n.sleep_stages_segments);

  if (hrChart) hrChart.destroy();
  hrChart = makeLine("hrChart", n.times, n.hr_bpm);

  if (spo2Chart) spo2Chart.destroy();
  spo2Chart = makeLine("spo2Chart", n.times, n.spo2_pct);
}

loadNightOptions();
loadHistory();
</script>
</body>
</html>
"""

def get_db():
  if "db" not in g:
    g.db = sqlite3.connect(DB)
    g.db.row_factory = sqlite3.Row
    g.db.execute("PRAGMA foreign_keys = ON;")
  return g.db

@app.teardown_appcontext
def close_db(_):
  db = g.pop("db", None)
  if db:
    db.close()

@app.get("/")
def index():
  return render_template_string(PAGE)

@app.get("/api/nights")
def api_nights():
  db = get_db()
  rows = db.execute(
    "SELECT night_date, sleep_score FROM sessions ORDER BY night_date DESC LIMIT 30"
  ).fetchall()
  return jsonify([dict(r) for r in rows])

@app.get("/api/night/<night_date>")
def api_night(night_date: str):
  db = get_db()
  sess = db.execute(
    "SELECT * FROM sessions WHERE night_date = ?",
    (night_date,)
  ).fetchone()
  if not sess:
    return jsonify({"error": "not found"}), 404

  session_id = sess["id"]

  # samples — oxi only for HR/SpO2 charts
  samples = db.execute(
    """
    SELECT ts, hr_bpm, spo2_pct
    FROM samples
    WHERE session_id = ? AND source = 'oxi'
    ORDER BY ts
    """,
    (session_id,)
  ).fetchall()

  # downsample: keep every Nth sample to ~500 points max
  max_points = 500
  step = max(1, len(samples) // max_points)
  samples_ds = samples[::step]

  times = []
  hr = []
  spo2 = []
  for r in samples_ds:
    # label HH:MM (UTC-ish; fine for fake. later convert with local tz)
    from datetime import datetime, timezone
    t = datetime.fromtimestamp(r["ts"], tz=timezone.utc).strftime("%H:%M")
    times.append(t)
    hr.append(r["hr_bpm"])
    spo2.append(r["spo2_pct"])

  segs = db.execute(
    """
    SELECT start_ts, end_ts, stage
    FROM stage_segments
    WHERE session_id = ?
    ORDER BY start_ts
    """,
    (session_id,)
  ).fetchall()

  sleep_stages_segments = []
  for r in segs:
    duration_min = int((r["end_ts"] - r["start_ts"]) / 60)
    sleep_stages_segments.append({"stage": r["stage"], "duration_min": duration_min})

  out = dict(sess)
  out.update({
    "times": times,
    "hr_bpm": hr,
    "spo2_pct": spo2,
    "sleep_stages_segments": sleep_stages_segments
  })
  out.pop("id", None)
  return jsonify(out)

if __name__ == "__main__":
  app.run(host="127.0.0.1", port=8000, debug=True)