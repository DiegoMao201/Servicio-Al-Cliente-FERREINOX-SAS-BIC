import csv
import json
import re
from collections import Counter
from io import BytesIO, StringIO
from pathlib import Path

import dropbox
import pandas as pd
from sqlalchemy import create_engine, inspect, text

from frontend.data_catalog import get_canonical_spec


ENCODINGS = ["utf-8", "latin1", "cp1252"]
DELIMITERS = [",", "|", ";", "\t", "{"]
SUPPORTED_EXTENSIONS = (".csv", ".xlsx", ".xls")


def slugify_identifier(value):
    """Convierte nombres arbitrarios en identificadores SQL estables."""
    normalized = re.sub(r"[^a-zA-Z0-9]+", "_", value.strip().lower())
    normalized = re.sub(r"_+", "_", normalized).strip("_")
    return normalized or "archivo"


def build_target_table_name(source_label, file_name):
    """Genera el nombre de la tabla raw a partir de la fuente y archivo."""
    canonical_spec = get_canonical_spec(source_label, file_name)
    if canonical_spec:
        return canonical_spec["target_table"]
    source_slug = slugify_identifier(source_label)
    file_slug = slugify_identifier(file_name.rsplit(".", 1)[0])
    return f"raw_{source_slug}_{file_slug}"


def validate_table_name(table_name):
    """Restringe los identificadores SQL de tablas a nombres seguros."""
    if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", table_name):
        raise ValueError(f"Nombre de tabla no válido: {table_name}")
    return table_name


def quote_identifier(identifier):
    """Escapa identificadores SQL simples de forma segura."""
    return '"' + str(identifier).replace('"', '""') + '"'


def get_dropbox_client(config):
    """Devuelve un cliente autenticado de Dropbox."""
    return dropbox.Dropbox(
        oauth2_refresh_token=config["refresh_token"],
        app_key=config["app_key"],
        app_secret=config["app_secret"],
    )


def list_csv_files(dbx, folder):
    """Lista archivos tabulares soportados dentro de una carpeta de Dropbox."""
    entries = dbx.files_list_folder(folder).entries
    return [
        entry
        for entry in entries
        if isinstance(entry, dropbox.files.FileMetadata) and entry.name.lower().endswith(SUPPORTED_EXTENSIONS)
    ]


def detect_delimiter(text_content):
    """Intenta detectar automáticamente el delimitador del archivo."""
    sample = text_content[:2048]
    try:
        return csv.Sniffer().sniff(sample, delimiters=DELIMITERS).delimiter
    except Exception:
        return ","


def profile_delimiter_shape(text_content, delimiter):
    """Mide la forma del archivo con un delimitador dado usando csv.reader."""
    reader = csv.reader(StringIO(text_content), delimiter=delimiter)
    widths = [len(row) for row in reader]
    width_counter = Counter(widths)
    most_common_width, most_common_count = width_counter.most_common(1)[0] if width_counter else (0, 0)
    bad_rows = sum(count for width, count in width_counter.items() if width != most_common_width)
    return {
        "delimiter": delimiter,
        "row_count": len(widths),
        "most_common_width": most_common_width,
        "most_common_ratio": (most_common_count / len(widths)) if widths else 0,
        "bad_rows": bad_rows,
    }


def detect_best_delimiter(text_content, expected_columns=None):
    """Elige el delimitador más consistente, priorizando el ancho esperado cuando existe."""
    candidates = [profile_delimiter_shape(text_content, delimiter) for delimiter in DELIMITERS]
    if expected_columns:
        candidates.sort(
            key=lambda item: (
                item["most_common_width"] == expected_columns,
                item["most_common_ratio"],
                item["most_common_width"],
                -item["bad_rows"],
            ),
            reverse=True,
        )
    else:
        candidates.sort(key=lambda item: (item["most_common_width"], item["most_common_ratio"], -item["bad_rows"]), reverse=True)
    return candidates[0]


def normalize_row_length(row, expected_columns, delimiter):
    """Normaliza una fila al ancho esperado sin descartarla."""
    values = [value.strip() if isinstance(value, str) else value for value in row]
    if len(values) == expected_columns:
        return values, None
    if len(values) < expected_columns:
        return values + [None] * (expected_columns - len(values)), "padded"
    merged_tail = delimiter.join(str(value) for value in values[expected_columns - 1 :] if value is not None)
    normalized = values[: expected_columns - 1] + [merged_tail]
    return normalized, "merged_tail"


def parse_csv_content(content, has_header, expected_columns=None):
    """Parsea CSV tolerando filas irregulares y conservando todas las líneas."""
    for encoding in ENCODINGS:
        try:
            text_content = content.decode(encoding)
            best_profile = detect_best_delimiter(text_content, expected_columns=expected_columns)
            delimiter = best_profile["delimiter"] or detect_delimiter(text_content)
            reader = csv.reader(StringIO(text_content), delimiter=delimiter)
            rows = list(reader)
            if not rows:
                return {
                    "ok": True,
                    "dataframe": pd.DataFrame(),
                    "encoding": encoding,
                    "delimiter": delimiter,
                    "bad_rows": [],
                    "repaired_rows": [],
                }

            effective_expected = expected_columns or best_profile["most_common_width"] or len(rows[0])
            if has_header:
                header_row, data_rows = rows[0], rows[1:]
                header_row, _ = normalize_row_length(header_row, effective_expected, delimiter)
                columns = [str(value).strip() if value is not None else f"column_{index + 1}" for index, value in enumerate(header_row)]
            else:
                columns = list(range(effective_expected))
                data_rows = rows

            normalized_rows = []
            repaired_rows = []
            for index, row in enumerate(data_rows, start=2 if has_header else 1):
                normalized_row, repair_action = normalize_row_length(row, effective_expected, delimiter)
                normalized_rows.append(normalized_row)
                if repair_action:
                    repaired_rows.append({"line": index, "action": repair_action, "original_width": len(row)})

            dataframe = pd.DataFrame(normalized_rows, columns=columns)
            return {
                "ok": True,
                "dataframe": dataframe,
                "encoding": encoding,
                "delimiter": delimiter,
                "bad_rows": [],
                "repaired_rows": repaired_rows,
            }
        except UnicodeDecodeError:
            continue
        except Exception as exc:
            return {"ok": False, "error": f"Error leyendo el archivo con encoding {encoding}: {exc}"}

    return {"ok": False, "error": "No se pudo leer el archivo con los encodings comunes (utf-8, latin1, cp1252)."}


def parse_excel_content(content, has_header):
    """Parsea Excel preservando todas las filas de la primera hoja."""
    try:
        workbook = pd.ExcelFile(BytesIO(content))
        sheet_name = workbook.sheet_names[0]
        header = 0 if has_header else None
        dataframe = pd.read_excel(workbook, sheet_name=sheet_name, header=header, dtype=object)
        return {
            "ok": True,
            "dataframe": dataframe,
            "encoding": None,
            "delimiter": f"excel:{sheet_name}",
            "bad_rows": [],
            "repaired_rows": [],
        }
    except Exception as exc:
        return {"ok": False, "error": f"Error leyendo el archivo Excel: {exc}"}


def parse_dropbox_csv(dbx, file_path, has_header, source_label=None, file_name=None):
    """Descarga y parsea un archivo tabular de Dropbox con soporte CSV y Excel."""
    _, response = dbx.files_download(file_path)
    content = response.content
    lower_path = file_path.lower()
    resolved_file_name = file_name or Path(lower_path).name
    canonical_spec = get_canonical_spec(source_label, resolved_file_name) if source_label else None

    expected_columns = len(canonical_spec["columns"]) if canonical_spec else None
    if lower_path.endswith(".csv"):
        return parse_csv_content(content, has_header=has_header, expected_columns=expected_columns)
    if lower_path.endswith((".xlsx", ".xls")):
        return parse_excel_content(content, has_header=has_header)
    return {"ok": False, "error": f"Formato no soportado: {file_path}"}


def ensure_sync_tables(db_uri):
    """Crea tablas de control de sincronización si aún no existen."""
    engine = create_engine(db_uri)
    statements = [
        """
        CREATE TABLE IF NOT EXISTS public.sync_schema_registry (
            id bigserial PRIMARY KEY,
            source_label varchar(120) NOT NULL,
            dropbox_folder varchar(255) NOT NULL,
            file_name varchar(255) NOT NULL,
            file_path varchar(255) NOT NULL,
            target_table varchar(150) NOT NULL,
            has_header boolean NOT NULL DEFAULT false,
            columns_json jsonb NOT NULL,
            delimiter varchar(10),
            encoding varchar(30),
            is_active boolean NOT NULL DEFAULT true,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT uq_sync_schema_registry UNIQUE (source_label, file_path)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS public.sync_run_log (
            id bigserial PRIMARY KEY,
            registry_id bigint REFERENCES public.sync_schema_registry(id) ON DELETE SET NULL,
            source_label varchar(120) NOT NULL,
            file_name varchar(255) NOT NULL,
            target_table varchar(150) NOT NULL,
            status varchar(20) NOT NULL,
            row_count integer,
            message text,
            executed_at timestamptz NOT NULL DEFAULT now()
        )
        """,
        "CREATE INDEX IF NOT EXISTS idx_sync_schema_registry_source ON public.sync_schema_registry(source_label)",
        "CREATE INDEX IF NOT EXISTS idx_sync_run_log_executed_at ON public.sync_run_log(executed_at)",
    ]

    with engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))


def fetch_saved_schema(db_uri, source_label, file_path):
    """Recupera la configuración persistida para un archivo ya sincronizado."""
    engine = create_engine(db_uri)
    query = text(
        """
        SELECT id, file_name, file_path, target_table, has_header, columns_json, delimiter, encoding
        FROM public.sync_schema_registry
        WHERE source_label = :source_label AND file_path = :file_path AND is_active = true
        """
    )
    with engine.connect() as connection:
        row = connection.execute(query, {"source_label": source_label, "file_path": file_path}).mappings().one_or_none()
    if not row:
        return None
    payload = dict(row)
    payload["columns"] = payload.pop("columns_json")
    return payload


def list_saved_schemas(db_uri, source_label):
    """Lista archivos registrados para actualización automática de una fuente."""
    engine = create_engine(db_uri)
    query = text(
        """
        SELECT id, source_label, dropbox_folder, file_name, file_path, target_table, has_header, columns_json, delimiter, encoding
        FROM public.sync_schema_registry
        WHERE source_label = :source_label AND is_active = true
        ORDER BY file_name
        """
    )
    with engine.connect() as connection:
        rows = connection.execute(query, {"source_label": source_label}).mappings().all()

    schemas = []
    for row in rows:
        payload = dict(row)
        payload["columns"] = payload.pop("columns_json")
        schemas.append(payload)
    return schemas


def save_sync_schema(db_uri, source_label, dropbox_folder, file_name, file_path, target_table, has_header, columns, delimiter, encoding):
    """Inserta o actualiza la configuración de sincronización de un archivo."""
    engine = create_engine(db_uri)
    query = text(
        """
        INSERT INTO public.sync_schema_registry (
            source_label, dropbox_folder, file_name, file_path, target_table, has_header, columns_json, delimiter, encoding, is_active, created_at, updated_at
        ) VALUES (
            :source_label, :dropbox_folder, :file_name, :file_path, :target_table, :has_header, CAST(:columns_json AS jsonb), :delimiter, :encoding, true, now(), now()
        )
        ON CONFLICT (source_label, file_path)
        DO UPDATE SET
            dropbox_folder = EXCLUDED.dropbox_folder,
            file_name = EXCLUDED.file_name,
            target_table = EXCLUDED.target_table,
            has_header = EXCLUDED.has_header,
            columns_json = EXCLUDED.columns_json,
            delimiter = EXCLUDED.delimiter,
            encoding = EXCLUDED.encoding,
            is_active = true,
            updated_at = now()
        RETURNING id
        """
    )
    params = {
        "source_label": source_label,
        "dropbox_folder": dropbox_folder,
        "file_name": file_name,
        "file_path": file_path,
        "target_table": target_table,
        "has_header": has_header,
        "columns_json": json.dumps(columns),
        "delimiter": delimiter,
        "encoding": encoding,
    }
    with engine.begin() as connection:
        return connection.execute(query, params).scalar_one()


def record_sync_run(db_uri, registry_id, source_label, file_name, target_table, status, row_count=None, message=None):
    """Registra cada ejecución de sincronización para auditoría."""
    engine = create_engine(db_uri)
    query = text(
        """
        INSERT INTO public.sync_run_log (registry_id, source_label, file_name, target_table, status, row_count, message)
        VALUES (:registry_id, :source_label, :file_name, :target_table, :status, :row_count, :message)
        """
    )
    with engine.begin() as connection:
        connection.execute(
            query,
            {
                "registry_id": registry_id,
                "source_label": source_label,
                "file_name": file_name,
                "target_table": target_table,
                "status": status,
                "row_count": row_count,
                "message": message,
            },
        )


def ensure_text_table_structure(connection, inspector, target_table, expected_columns):
    """Recrea la tabla raw si no coincide con el esquema textual esperado."""
    current_columns = []
    current_types = []
    if inspector.has_table(target_table, schema="public"):
        current_columns = [column["name"] for column in inspector.get_columns(target_table, schema="public")]
        current_types = [str(column["type"]).upper() for column in inspector.get_columns(target_table, schema="public")]

    same_columns = current_columns == expected_columns
    text_compatible = all("TEXT" in column_type or "CHAR" in column_type for column_type in current_types)
    if same_columns and text_compatible:
        return

    if current_columns:
        connection.execute(text(f'DROP TABLE IF EXISTS public.{quote_identifier(target_table)} CASCADE'))

    column_sql = ", ".join(f"{quote_identifier(column_name)} text" for column_name in expected_columns)
    connection.execute(text(f'CREATE TABLE public.{quote_identifier(target_table)} ({column_sql})'))


def upload_dataframe(db_uri, dataframe, target_table, mode="truncate_append", expected_columns=None):
    """Carga un dataframe preservando el esquema cuando la tabla ya existe."""
    engine = create_engine(db_uri)
    target_table = validate_table_name(target_table)
    dataframe = dataframe.where(pd.notnull(dataframe), None)
    dataframe = dataframe.replace(r"^\s*$", None, regex=True)
    inspector = inspect(engine)
    table_exists = inspector.has_table(target_table, schema="public")

    with engine.begin() as connection:
        if expected_columns:
            ensure_text_table_structure(connection, inspector, target_table, expected_columns)
            table_exists = True

        if table_exists:
            if mode == "truncate_append":
                connection.execute(text(f'TRUNCATE TABLE public."{target_table}"'))
            elif mode != "append":
                raise ValueError(f"Modo de carga no soportado para tablas existentes: {mode}")
            dataframe.to_sql(target_table, connection, schema="public", if_exists="append", index=False)
            return

        dataframe.to_sql(target_table, connection, schema="public", if_exists="replace", index=False)


def execute_sql_script(db_uri, sql_file_path):
    """Ejecuta un archivo SQL completo sobre PostgreSQL."""
    script_path = Path(sql_file_path).resolve()
    if not script_path.exists():
        raise FileNotFoundError(f"No se encontró el archivo SQL: {script_path}")

    sql_script = script_path.read_text(encoding="utf-8")
    engine = create_engine(db_uri, isolation_level="AUTOCOMMIT")
    with engine.raw_connection() as raw_connection:
        with raw_connection.cursor() as cursor:
            cursor.execute(sql_script)
        raw_connection.commit()
    return str(script_path)


def ensure_postgrest_access(db_uri):
    """Crea el rol anonimo y aplica permisos de lectura para PostgREST."""
    role_engine = create_engine(db_uri, isolation_level="AUTOCOMMIT")
    with role_engine.connect() as connection:
        connection.execute(
            text("DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'web_anon') THEN CREATE ROLE web_anon NOLOGIN; END IF; END $$;")
        )

    grant_engine = create_engine(db_uri)
    statements = [
        "GRANT USAGE ON SCHEMA public TO web_anon",
        "GRANT SELECT ON ALL TABLES IN SCHEMA public TO web_anon",
        "GRANT SELECT ON ALL SEQUENCES IN SCHEMA public TO web_anon",
        "GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO web_anon",
        "ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO web_anon",
        "ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON SEQUENCES TO web_anon",
        "ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT EXECUTE ON FUNCTIONS TO web_anon",
    ]

    with grant_engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))


def validate_columns(columns):
    """Valida que los nombres de columnas sean únicos y no vacíos."""
    cleaned = [str(column).strip() for column in columns]
    if any(not column for column in cleaned):
        return False, "Todos los nombres de columna deben ser obligatorios."
    if len(set(cleaned)) != len(cleaned):
        return False, "Todos los nombres de columna deben ser únicos."
    return True, None