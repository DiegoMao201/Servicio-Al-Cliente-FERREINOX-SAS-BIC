import sys, json
sys.path.insert(0, "backend")
from main import get_db_engine
e = get_db_engine()
c = e.raw_connection()
cur = c.cursor()
cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name='agent_technical_profile' ORDER BY ordinal_position")
print("Columns:", [r[0] for r in cur.fetchall()])
c.close()
