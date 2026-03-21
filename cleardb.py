import sqlite3, os, sys
from datetime import date

DB = "sleep.db"

if "--full" in sys.argv:
    if os.path.exists(DB):
        os.remove(DB)
    con = sqlite3.connect(DB)
    con.executescript(open("schema.sql").read())
    con.close()
    print("DB fully reset.")
else:
    today = str(date.today())
    con = sqlite3.connect(DB)
    cur = con.execute("SELECT id FROM sessions WHERE night_date = ?", (today,))
    row = cur.fetchone()
    if row:
        sid = row[0]
        con.execute("DELETE FROM stage_segments WHERE session_id = ?", (sid,))
        con.execute("DELETE FROM samples WHERE session_id = ?", (sid,))
        con.execute("DELETE FROM sessions WHERE id = ?", (sid,))
        con.commit()
        print(f"Deleted session for {today}.")
    else:
        print(f"No session found for {today}.")
    con.close()
