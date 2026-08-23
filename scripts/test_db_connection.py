from app.config import get_settings
get_settings.cache_clear()
s = get_settings()
print("DATABASE_URL prefix:", s.database_url[:55] + "...")

from app.db.session import engine, init_db
init_db()
print("DB init OK — ORM tables ensured.")

from sqlalchemy import text
with engine.connect() as conn:
    rows = conn.execute(
        text("SELECT table_name FROM information_schema.tables WHERE table_schema='public' ORDER BY table_name")
    ).fetchall()
    tables = [r[0] for r in rows]
    print("Tables in public schema:", tables)
