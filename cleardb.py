import sqlite3, os

DB = "sleep.db"
if os.path.exists(DB):
    os.remove(DB)
con = sqlite3.connect(DB)
con.executescript(open("schema.sql").read())
con.close()
print("DB reset.")
