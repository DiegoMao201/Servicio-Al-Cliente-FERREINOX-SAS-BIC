import argparse
import json
import os
import socket
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url


REPORT_PATH = Path(__file__).resolve().parent / "db_diagnostics_report.json"


def build_database_url(cli_database_url=None):
    """Obtiene el URI de PostgreSQL desde CLI, DATABASE_URL o variables DB_* del entorno."""
    database_url = cli_database_url or os.getenv("DATABASE_URL") or os.getenv("POSTGRES_DB_URI")
    if database_url:
        return database_url

    db_user = os.getenv("DB_USER")
    db_password = os.getenv("DB_PASSWORD")
    db_host = os.getenv("DB_HOST", "db")
    db_port = os.getenv("DB_PORT", "5432")
    db_name = os.getenv("DB_NAME", "ferreinox_db")
    ssl_mode = os.getenv("PGSSLMODE")

    if not db_user or not db_password:
        raise RuntimeError(
            "No se encontró DATABASE_URL/POSTGRES_DB_URI ni variables DB_USER/DB_PASSWORD para construir la conexión."
        )

    database_url = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
    if ssl_mode:
        database_url = f"{database_url}?sslmode={ssl_mode}"
    return database_url


def tcp_probe(host, port, timeout=5):
    """Prueba conectividad TCP básica al host y puerto de PostgreSQL."""
    try:
        with socket.create_connection((host, int(port)), timeout=timeout):
            return {"ok": True, "message": "TCP connection succeeded"}
    except Exception as exc:
        return {"ok": False, "message": str(exc)}


def fetch_server_overview(connection):
    """Obtiene información básica de la conexión activa."""
    overview_query = text(
        """
        SELECT
            version() AS postgres_version,
            current_database() AS current_database,
            current_user AS current_user,
            inet_server_addr()::text AS server_ip,
            inet_server_port() AS server_port,
            current_setting('server_version') AS server_version
        """
    )
    overview = dict(connection.execute(overview_query).mappings().one())

    try:
        ssl_row = connection.execute(
            text(
                "SELECT ssl, version, cipher, bits FROM pg_stat_ssl WHERE pid = pg_backend_pid()"
            )
        ).mappings().one_or_none()
        overview["ssl"] = dict(ssl_row) if ssl_row else None
    except Exception as exc:
        overview["ssl"] = {"unavailable": str(exc)}

    return overview


def fetch_table_inventory(connection, sample_rows):
    """Construye inventario de tablas, columnas y volumen estimado."""
    tables_query = text(
        """
        SELECT
            t.schemaname,
            t.relname AS table_name,
            COALESCE(t.n_live_tup, 0) AS estimated_rows,
            pg_total_relation_size(format('%I.%I', t.schemaname, t.relname)) AS total_bytes
        FROM pg_stat_user_tables t
        WHERE t.schemaname = 'public'
        ORDER BY t.relname
        """
    )

    columns_query = text(
        """
        SELECT
            column_name,
            data_type,
            is_nullable,
            ordinal_position
        FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = :table_name
        ORDER BY ordinal_position
        """
    )

    inventory = []
    tables = connection.execute(tables_query).mappings().all()
    for table in tables:
        table_name = table["table_name"]
        columns = [dict(row) for row in connection.execute(columns_query, {"table_name": table_name}).mappings().all()]
        table_info = dict(table)
        table_info["columns"] = columns

        if sample_rows > 0:
            sample_query = text(f'SELECT * FROM "public"."{table_name}" LIMIT {sample_rows}')
            table_info["sample_rows"] = [dict(row) for row in connection.execute(sample_query).mappings().all()]

        inventory.append(table_info)

    return inventory


def main():
    parser = argparse.ArgumentParser(description="Diagnóstico e inventario de PostgreSQL para CRM Ferreinox.")
    parser.add_argument("--db-uri", type=str, default=None, help="URI completa de PostgreSQL para la prueba.")
    parser.add_argument("--sample-rows", type=int, default=0, help="Cantidad de filas de muestra por tabla.")
    args = parser.parse_args()

    database_url = build_database_url(args.db_uri)
    parsed_url = make_url(database_url)

    report = {
        "generated_at": datetime.now(UTC).isoformat(),
        "target": {
            "drivername": parsed_url.drivername,
            "host": parsed_url.host,
            "port": parsed_url.port,
            "database": parsed_url.database,
            "username": parsed_url.username,
            "query": dict(parsed_url.query),
        },
    }

    tcp_result = tcp_probe(parsed_url.host or "localhost", parsed_url.port or 5432)
    report["tcp_probe"] = tcp_result

    print("=" * 72)
    print("CRM Ferreinox | PostgreSQL Diagnostics")
    print("=" * 72)
    print(f"Host: {report['target']['host']}")
    print(f"Port: {report['target']['port']}")
    print(f"Database: {report['target']['database']}")
    print(f"User: {report['target']['username']}")
    print(f"TCP probe: {'OK' if tcp_result['ok'] else 'FAIL'} -> {tcp_result['message']}")

    if not tcp_result["ok"]:
        report["database_connection"] = {"ok": False, "error": "TCP probe failed before SQL login."}
        REPORT_PATH.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"\nReporte guardado en: {REPORT_PATH}")
        raise SystemExit(1)

    try:
        engine = create_engine(database_url, pool_pre_ping=True)
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
            report["database_connection"] = {"ok": True}
            report["server_overview"] = fetch_server_overview(connection)
            report["tables"] = fetch_table_inventory(connection, args.sample_rows)

        print("SQL login: OK")
        print(f"PostgreSQL version: {report['server_overview']['server_version']}")
        print(f"Current database: {report['server_overview']['current_database']}")
        print(f"Current user: {report['server_overview']['current_user']}")
        print(f"Public tables found: {len(report.get('tables', []))}")

        for table in report.get("tables", []):
            print(f"- {table['table_name']}: {table['estimated_rows']} rows est., {len(table['columns'])} columns")

    except Exception as exc:
        report["database_connection"] = {"ok": False, "error": str(exc)}
        print(f"SQL login: FAIL -> {exc}")
        REPORT_PATH.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"\nReporte guardado en: {REPORT_PATH}")
        raise SystemExit(2)

    REPORT_PATH.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nReporte guardado en: {REPORT_PATH}")


if __name__ == "__main__":
    main()