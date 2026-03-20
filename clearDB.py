python3 -c "import sqlite3,os; os.remove('sleep.db') if os.path.exists('sleep.db') else None; c=sqlite3.connect('sleep.db'); c.executescript(open('schema.sql').read()); c.close()"
