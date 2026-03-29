import argparse
import os

from sqlalchemy import create_engine, inspect, text


def build_database_url(cli_database_url=None):
    """Obtiene la conexión desde CLI, DATABASE_URL o POSTGRES_DB_URI."""
    database_url = cli_database_url or os.getenv("DATABASE_URL") or os.getenv("POSTGRES_DB_URI")
    if database_url:
        return database_url

    raise RuntimeError(
        "No se encontró una URI de conexión. Usa --db-uri o define DATABASE_URL/POSTGRES_DB_URI."
    )


def main():
    parser = argparse.ArgumentParser(description="Resetea el esquema public de PostgreSQL de forma controlada.")
    parser.add_argument("--db-uri", type=str, default=None, help="URI completa de PostgreSQL.")
    parser.add_argument(
        "--yes-i-understand",
        action="store_true",
        help="Confirma explícitamente que deseas borrar todo el esquema public.",
    )
    args = parser.parse_args()

    if not args.yes_i_understand:
        raise SystemExit(
            "Operación cancelada. Repite el comando con --yes-i-understand para confirmar el borrado total."
        )

    database_url = build_database_url(args.db_uri)
    engine = create_engine(database_url, isolation_level="AUTOCOMMIT")

    with engine.connect() as connection:
        inspector = inspect(connection)
        tables = inspector.get_table_names(schema="public")

        print("Tablas detectadas antes del reset:")
        if tables:
            for table_name in tables:
                print(f"- {table_name}")
        else:
            print("- Ninguna")

        connection.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
        connection.execute(text("CREATE SCHEMA public"))
        connection.execute(text("GRANT ALL ON SCHEMA public TO postgres"))
        connection.execute(text("GRANT ALL ON SCHEMA public TO public"))

    print("\nEsquema public reiniciado correctamente.")


if __name__ == "__main__":
    main()