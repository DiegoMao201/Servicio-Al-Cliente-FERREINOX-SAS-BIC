import argparse
from pathlib import Path
import tomllib

from sqlalchemy import create_engine, text

from frontend.data_catalog import CATALOG_SPECS
from frontend.dropbox_sync_service import (
    ensure_postgrest_access,
    execute_sql_script,
    get_dropbox_client,
    list_csv_files,
    parse_dropbox_csv,
    record_sync_run,
    save_sync_schema,
    upload_dataframe,
)


SOURCE_SECRET_MAP = {
    "Rotación Inventarios": "dropbox_rotacion",
    "Cartera Ferreinox": "dropbox_cartera",
    "Ventas Ferreinox": "dropbox_ventas",
}


def resolve_secrets_path(cli_path=None):
    if cli_path:
        path = Path(cli_path).resolve()
        if path.exists():
            return path
        raise FileNotFoundError(f"No se encontró el archivo de secrets: {path}")

    candidates = [
        Path("frontend/.streamlit/secrets.toml").resolve(),
        Path(".streamlit/secrets.toml").resolve(),
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise FileNotFoundError("No se encontró frontend/.streamlit/secrets.toml ni .streamlit/secrets.toml")


def load_secrets(secrets_path):
    return tomllib.loads(Path(secrets_path).read_text(encoding="utf-8"))


def get_db_uri(secrets):
    return secrets["postgres"]["db_uri"]


def sync_official_sources(db_uri, secrets):
    initialized_tables = set()
    results = []

    for spec in CATALOG_SPECS:
        source_key = SOURCE_SECRET_MAP[spec["source_label"]]
        config = secrets[source_key]
        dbx = get_dropbox_client(config)
        folder = config.get("folder", "/")
        files = {entry.name: entry for entry in list_csv_files(dbx, folder)}

        if spec["file_name"] not in files:
            raise FileNotFoundError(f"No se encontró {spec['file_name']} en {spec['source_label']}")

        entry = files[spec["file_name"]]
        parse_result = parse_dropbox_csv(
            dbx,
            entry.path_lower,
            has_header=False,
            source_label=spec["source_label"],
            file_name=spec["file_name"],
        )
        if not parse_result["ok"]:
            raise RuntimeError(f"No se pudo leer {spec['source_label']} | {spec['file_name']}: {parse_result['error']}")

        dataframe = parse_result["dataframe"]
        if len(dataframe.columns) != len(spec["columns"]):
            raise RuntimeError(
                f"{spec['source_label']} | {spec['file_name']}: columnas detectadas {len(dataframe.columns)} y esperadas {len(spec['columns'])}"
            )

        dataframe.columns = spec["columns"]
        mode = "append" if spec["target_table"] in initialized_tables else "truncate_append"
        upload_dataframe(db_uri, dataframe, spec["target_table"], mode=mode, expected_columns=spec["columns"])
        initialized_tables.add(spec["target_table"])

        registry_id = save_sync_schema(
            db_uri,
            spec["source_label"],
            folder,
            spec["file_name"],
            entry.path_lower,
            spec["target_table"],
            False,
            spec["columns"],
            parse_result["delimiter"],
            parse_result["encoding"],
        )
        record_sync_run(
            db_uri,
            registry_id,
            spec["source_label"],
            spec["file_name"],
            spec["target_table"],
            "success",
            row_count=len(dataframe),
            message=f"Sincronización oficial completada. Filas reparadas: {len(parse_result.get('repaired_rows', []))}",
        )

        results.append(
            {
                "source_label": spec["source_label"],
                "file_name": spec["file_name"],
                "target_table": spec["target_table"],
                "rows": len(dataframe),
                "repaired_rows": len(parse_result.get("repaired_rows", [])),
            }
        )

    return results


def apply_postgrest_layer(db_uri):
    execute_sql_script(db_uri, "backend/agent_schema.sql")
    ensure_postgrest_access(db_uri)
    execute_sql_script(db_uri, "backend/postgrest_views.sql")


def print_row_counts(db_uri):
    engine = create_engine(db_uri)
    targets = sorted({spec["target_table"] for spec in CATALOG_SPECS})
    with engine.connect() as connection:
        for table_name in targets:
            row_count = connection.execute(text(f'SELECT COUNT(*) FROM public."{table_name}"')).scalar_one()
            print(f"{table_name}: {row_count} filas")


def main():
    parser = argparse.ArgumentParser(description="Sincroniza los CSV oficiales del ERP y refresca PostgREST.")
    parser.add_argument("--secrets", type=str, default=None, help="Ruta al archivo secrets.toml")
    parser.add_argument("--skip-views", action="store_true", help="No reaplica la capa PostgREST")
    args = parser.parse_args()

    secrets_path = resolve_secrets_path(args.secrets)
    secrets = load_secrets(secrets_path)
    db_uri = get_db_uri(secrets)

    print(f"Usando secrets: {secrets_path}")
    print("Sincronizando base oficial CSV...")
    results = sync_official_sources(db_uri, secrets)
    for item in results:
        print(
            f"OK | {item['source_label']} | {item['file_name']} | {item['target_table']} | "
            f"{item['rows']} filas | reparadas {item['repaired_rows']}"
        )

    if not args.skip_views:
        print("Aplicando capa PostgREST...")
        apply_postgrest_layer(db_uri)
        print("OK | PostgREST actualizado")

    print("Conteo final de tablas raw:")
    print_row_counts(db_uri)


if __name__ == "__main__":
    main()