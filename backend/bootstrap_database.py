import argparse
import os
from pathlib import Path

from sqlalchemy import create_engine


def build_database_url(cli_database_url=None):
    """Obtiene la conexión desde CLI, DATABASE_URL o POSTGRES_DB_URI."""
    database_url = cli_database_url or os.getenv("DATABASE_URL") or os.getenv("POSTGRES_DB_URI")
    if database_url:
        return database_url
    raise RuntimeError("No se encontró una URI de conexión. Usa --db-uri o define DATABASE_URL/POSTGRES_DB_URI.")


def main():
    parser = argparse.ArgumentParser(description="Aplica un archivo SQL contra PostgreSQL.")
    parser.add_argument("--db-uri", type=str, default=None, help="URI completa de PostgreSQL.")
    parser.add_argument("--sql-file", type=str, default="backend/schema_init.sql", help="Ruta al archivo SQL a ejecutar.")
    args = parser.parse_args()

    database_url = build_database_url(args.db_uri)
    sql_file = Path(args.sql_file).resolve()

    if not sql_file.exists():
        raise FileNotFoundError(f"No se encontró el archivo SQL: {sql_file}")

    sql_script = sql_file.read_text(encoding="utf-8")
    engine = create_engine(database_url, isolation_level="AUTOCOMMIT")

    with engine.raw_connection() as raw_connection:
        with raw_connection.cursor() as cursor:
            cursor.execute(sql_script)
        raw_connection.commit()

    print(f"Estructura aplicada correctamente desde: {sql_file}")


if __name__ == "__main__":
    main()