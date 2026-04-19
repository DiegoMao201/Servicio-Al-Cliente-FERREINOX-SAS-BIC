from pathlib import Path
try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib

from sqlalchemy import create_engine


ROOT = Path(__file__).resolve().parents[1]
SECRETS_PATH = ROOT / ".streamlit" / "secrets.toml"
SQL_PATH = ROOT / "backend" / "postgrest_views.sql"


def load_db_uri() -> str:
    secrets = tomllib.loads(SECRETS_PATH.read_text(encoding="utf-8"))
    return secrets["postgres"]["db_uri"]


def main() -> None:
    engine = create_engine(load_db_uri())
    sql_text = SQL_PATH.read_text(encoding="utf-8")
    with engine.begin() as connection:
        raw_connection = connection.connection
        cursor = raw_connection.cursor()
        cursor.execute(sql_text)
        cursor.close()
    print("Applied postgrest_views.sql successfully")


if __name__ == "__main__":
    main()