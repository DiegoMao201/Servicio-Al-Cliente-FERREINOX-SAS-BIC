import csv
import json
import re
from io import StringIO

import dropbox
import pandas as pd
from sqlalchemy import create_engine, text


ENCODINGS = ["utf-8", "latin1", "cp1252"]
DELIMITERS = [",", "|", ";", "\t", "{"]


def slugify_identifier(value):
    """Convierte nombres arbitrarios en identificadores SQL estables."""
    normalized = re.sub(r"[^a-zA-Z0-9]+", "_", value.strip().lower())
    normalized = re.sub(r"_+", "_", normalized).strip("_")
    return normalized or "archivo"


def build_target_table_name(source_label, file_name):
    """Genera el nombre de la tabla raw a partir de la fuente y archivo."""
    source_slug = slugify_identifier(source_label)
    file_slug = slugify_identifier(file_name.rsplit(".", 1)[0])
    return f"raw_{source_slug}_{file_slug}"


def get_dropbox_client(config):
    """Devuelve un cliente autenticado de Dropbox."""
    return dropbox.Dropbox(
        oauth2_refresh_token=config["refresh_token"],
        app_key=config["app_key"],
        app_secret=config["app_secret"],
    )


def list_csv_files(dbx, folder):
    """Lista archivos CSV dentro de una carpeta de Dropbox."""
    entries = dbx.files_list_folder(folder).entries
    return [entry for entry in entries if isinstance(entry, dropbox.files.FileMetadata) and entry.name.lower().endswith(".csv")]


def detect_delimiter(text_content):
    """Intenta detectar automáticamente el delimitador del archivo."""
    sample = text_content[:2048]
    try:
        return csv.Sniffer().sniff(sample, delimiters=DELIMITERS).delimiter
    except Exception:
        return ","


def parse_dropbox_csv(dbx, file_path, has_header):
    """Descarga y parsea un CSV de Dropbox con detección de encoding y delimitador."""
    _, response = dbx.files_download(file_path)
    content = response.content

    for encoding in ENCODINGS:
        try:
            text_content = content.decode(encoding)
            delimiter = detect_delimiter(text_content)
            header = 0 if has_header else None
            dataframe = pd.read_csv(StringIO(text_content), sep=delimiter, encoding=encoding, header=header)

            expected_cols = len(dataframe.columns)
            bad_rows = []
            reader = csv.reader(StringIO(text_content), delimiter=delimiter)
            for idx, row in enumerate(reader):
                if has_header and idx == 0:
                    continue
                if len(row) != expected_cols:
                    bad_rows.append((idx + 1, row))

            return {
                "ok": True,
                "dataframe": dataframe,
                "encoding": encoding,
                "delimiter": delimiter,
                "bad_rows": bad_rows,
            }
        except UnicodeDecodeError:
            continue
        except Exception as exc:
            return {"ok": False, "error": f"Error leyendo el archivo con encoding {encoding}: {exc}"}

    return {"ok": False, "error": "No se pudo leer el archivo con los encodings comunes (utf-8, latin1, cp1252)."}


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


def upload_dataframe(db_uri, dataframe, target_table):
    """Reemplaza la tabla raw de destino con el dataframe actual."""
    engine = create_engine(db_uri)
    dataframe = dataframe.astype(str)
    with engine.begin() as connection:
        dataframe.to_sql(target_table, connection, if_exists="replace", index=False)


def validate_columns(columns):
    """Valida que los nombres de columnas sean únicos y no vacíos."""
    cleaned = [str(column).strip() for column in columns]
    if any(not column for column in cleaned):
        return False, "Todos los nombres de columna deben ser obligatorios."
    if len(set(cleaned)) != len(cleaned):
        return False, "Todos los nombres de columna deben ser únicos."
    return True, None