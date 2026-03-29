import streamlit as st

from frontend.config import get_database_uri, get_dropbox_sources
from frontend.data_catalog import CATALOG_SPECS, get_canonical_spec
from frontend.dropbox_sync_service import (
    build_target_table_name,
    execute_sql_script,
    ensure_sync_tables,
    fetch_saved_schema,
    get_dropbox_client,
    list_csv_files,
    list_saved_schemas,
    parse_dropbox_csv,
    record_sync_run,
    save_sync_schema,
    upload_dataframe,
    validate_columns,
)


def render_column_editor(dataframe, saved_columns=None):
    """Renderiza inputs para confirmar o editar nombres de columnas."""
    base_columns = saved_columns or [str(column).strip() for column in dataframe.columns]
    edited_columns = []
    for index, column_name in enumerate(base_columns):
        edited_columns.append(
            st.text_input(f"Nombre para columna {index + 1}", value=column_name, key=f"column_{index}").strip()
        )
    return edited_columns


def sync_single_file(db_uri, source_label, dropbox_folder, file_name, file_path, target_table, has_header, columns, dbx):
    """Sincroniza un archivo Dropbox hacia una tabla raw en PostgreSQL."""
    parse_result = parse_dropbox_csv(dbx, file_path, has_header=has_header)
    if not parse_result["ok"]:
        record_sync_run(db_uri, None, source_label, file_name, target_table, "error", message=parse_result["error"])
        return False, parse_result["error"]

    dataframe = parse_result["dataframe"]
    if len(dataframe.columns) != len(columns):
        message = "La estructura actual del archivo no coincide con el esquema guardado."
        record_sync_run(db_uri, None, source_label, file_name, target_table, "error", message=message)
        return False, message

    dataframe.columns = columns
    upload_dataframe(db_uri, dataframe, target_table, mode="truncate_append")
    registry_id = save_sync_schema(
        db_uri,
        source_label,
        dropbox_folder,
        file_name,
        file_path,
        target_table,
        has_header,
        columns,
        parse_result["delimiter"],
        parse_result["encoding"],
    )
    record_sync_run(db_uri, registry_id, source_label, file_name, target_table, "success", row_count=len(dataframe))
    repaired_rows = parse_result.get("repaired_rows", [])
    if repaired_rows:
        return True, f"Sincronización exitosa de {file_name} hacia {target_table}. Filas reparadas: {len(repaired_rows)}."
    return True, f"Sincronización exitosa de {file_name} hacia {target_table}."


def sync_catalog_entry(db_uri, spec, dropbox_conf, dbx, write_mode):
    file_lookup = {file_entry.name.lower(): file_entry for file_entry in list_csv_files(dbx, dropbox_conf.get("folder", "/"))}
    selected_file = file_lookup.get(spec["file_name"].lower())
    if not selected_file:
        record_sync_run(db_uri, None, spec["source_label"], spec["file_name"], spec["target_table"], "error", message="Archivo no encontrado en Dropbox.")
        return False, f"No se encontró {spec['file_name']} en {spec['source_label']}."

    parse_result = parse_dropbox_csv(dbx, selected_file.path_lower, has_header=False)
    if not parse_result["ok"]:
        record_sync_run(db_uri, None, spec["source_label"], spec["file_name"], spec["target_table"], "error", message=parse_result["error"])
        return False, parse_result["error"]

    dataframe = parse_result["dataframe"]
    if len(dataframe.columns) != len(spec["columns"]):
        message = f"La estructura de {spec['file_name']} no coincide con el catálogo canónico."
        record_sync_run(db_uri, None, spec["source_label"], spec["file_name"], spec["target_table"], "error", message=message)
        return False, message

    dataframe.columns = spec["columns"]
    upload_dataframe(db_uri, dataframe, spec["target_table"], mode=write_mode)
    registry_id = save_sync_schema(
        db_uri,
        spec["source_label"],
        dropbox_conf.get("folder", "/"),
        spec["file_name"],
        selected_file.path_lower,
        spec["target_table"],
        False,
        spec["columns"],
        parse_result["delimiter"],
        parse_result["encoding"],
    )
    record_sync_run(db_uri, registry_id, spec["source_label"], spec["file_name"], spec["target_table"], "success", row_count=len(dataframe))
    repaired_rows = parse_result.get("repaired_rows", [])
    repair_note = f", reparadas {len(repaired_rows)} filas" if repaired_rows else ""
    return True, f"{spec['file_name']} -> {spec['target_table']} ({len(dataframe)} filas{repair_note})"


def sync_canonical_base(db_uri, dropbox_sources):
    results = []
    initialized_tables = set()
    source_clients = {}

    for source_label, dropbox_conf in dropbox_sources.items():
        source_clients[source_label] = (dropbox_conf, get_dropbox_client(dropbox_conf))

    for spec in CATALOG_SPECS:
        if spec["source_label"] not in source_clients:
            results.append((False, f"No hay configuración Dropbox para {spec['source_label']}"))
            continue

        dropbox_conf, dbx = source_clients[spec["source_label"]]
        write_mode = "append" if spec["target_table"] in initialized_tables else "truncate_append"
        success, message = sync_catalog_entry(db_uri, spec, dropbox_conf, dbx, write_mode)
        if success:
            initialized_tables.add(spec["target_table"])
        results.append((success, message))

    return results


def main():
    """Renderiza el módulo principal de sincronización Dropbox -> PostgreSQL raw."""
    st.title("Sincronización Dropbox")
    st.caption("Carga archivos CSV o Excel de Dropbox a tablas raw y guarda los esquemas directamente en PostgreSQL.")

    try:
        db_uri = get_database_uri()
        ensure_sync_tables(db_uri)
    except RuntimeError as exc:
        st.error(str(exc))
        return
    except Exception as exc:
        st.error(f"No fue posible preparar las tablas de control de sincronización: {exc}")
        return

    dropbox_sources = get_dropbox_sources()
    if not dropbox_sources:
        st.error("No hay configuraciones de Dropbox disponibles en Streamlit Secrets.")
        return

    source_label = st.selectbox("Fuente Dropbox", list(dropbox_sources.keys()))
    dropbox_conf = dropbox_sources[source_label]
    dbx = get_dropbox_client(dropbox_conf)
    dropbox_folder = dropbox_conf.get("folder", "/")

    try:
        files = list_csv_files(dbx, dropbox_folder)
    except Exception as exc:
        st.error(f"No fue posible listar la carpeta de Dropbox: {exc}")
        return

    if not files:
        st.warning("No se encontraron archivos tabulares compatibles en la carpeta configurada.")
        return

    file_lookup = {file_entry.name: file_entry for file_entry in files}
    selected_file_name = st.selectbox("Archivo tabular", list(file_lookup.keys()))
    selected_file = file_lookup[selected_file_name]
    saved_schema = fetch_saved_schema(db_uri, source_label, selected_file.path_lower)
    canonical_spec = get_canonical_spec(source_label, selected_file_name)

    default_has_header = saved_schema["has_header"] if saved_schema else False
    has_header = st.checkbox("La primera fila contiene encabezados", value=default_has_header)

    parse_result = parse_dropbox_csv(dbx, selected_file.path_lower, has_header=has_header)
    if not parse_result["ok"]:
        st.error(parse_result["error"])
        return

    dataframe = parse_result["dataframe"]
    repaired_rows = parse_result.get("repaired_rows", [])
    if repaired_rows:
        st.warning(f"Se conservaron todas las líneas y se repararon {len(repaired_rows)} filas irregulares durante la lectura.")
    st.subheader("Vista previa")
    st.dataframe(dataframe.head(), use_container_width=True)

    default_target_table = saved_schema["target_table"] if saved_schema else build_target_table_name(source_label, selected_file_name)
    target_table = st.text_input("Tabla destino en PostgreSQL", value=default_target_table).strip()

    st.subheader("Esquema de columnas")
    default_columns = saved_schema["columns"] if saved_schema else (canonical_spec["columns"] if canonical_spec else None)
    edited_columns = render_column_editor(dataframe, saved_columns=default_columns)
    is_valid, validation_message = validate_columns(edited_columns)
    if not is_valid:
        st.error(validation_message)
        return

    if canonical_spec and sum(1 for spec in CATALOG_SPECS if spec["target_table"] == canonical_spec["target_table"]) > 1:
        st.info(
            "Esta tabla raw consolida más de un archivo Dropbox. Para refrescarla completa sin perder fuentes complementarias usa el botón 'Actualizar base canónica completa'."
        )

    dataframe_preview = dataframe.copy()
    dataframe_preview.columns = edited_columns
    st.dataframe(dataframe_preview.head(), use_container_width=True)

    if st.button("Sincronizar archivo"):
        success, message = sync_single_file(
            db_uri,
            source_label,
            dropbox_folder,
            selected_file_name,
            selected_file.path_lower,
            target_table,
            has_header,
            edited_columns,
            dbx,
        )
        if success:
            st.success(message)
        else:
            st.error(message)

    st.markdown("---")
    st.subheader("Base operativa")
    st.caption("Usa estos botones para refrescar toda la base raw canónica y reaplicar la capa SQL de PostgREST.")

    action_col_1, action_col_2 = st.columns(2)
    if action_col_1.button("Actualizar base canónica completa"):
        with st.spinner("Sincronizando archivos canónicos desde Dropbox..."):
            results = sync_canonical_base(db_uri, dropbox_sources)
        success_count = sum(1 for success, _ in results if success)
        error_count = len(results) - success_count
        st.write(f"Resultado: {success_count} cargas exitosas, {error_count} con error.")
        for success, message in results:
            if success:
                st.success(message)
            else:
                st.error(message)

    if action_col_2.button("Aplicar o refrescar vistas PostgREST"):
        try:
            hardening_path = execute_sql_script(db_uri, "backend/raw_schema_hardening.sql")
            views_path = execute_sql_script(db_uri, "backend/postgrest_views.sql")
            st.success(f"Estructura raw endurecida desde {hardening_path} y vistas PostgREST aplicadas desde {views_path}.")
        except Exception as exc:
            st.error(f"No fue posible aplicar la capa SQL de PostgREST: {exc}")

    st.markdown("---")
    st.subheader("Actualización automática")
    saved_schemas = list_saved_schemas(db_uri, source_label)
    if saved_schemas:
        st.write(f"Archivos registrados para {source_label}: {len(saved_schemas)}")
        for schema in saved_schemas:
            st.caption(f"{schema['file_name']} -> {schema['target_table']}")
        if st.button("Actualizar todos los archivos registrados"):
            for schema in saved_schemas:
                success, message = sync_single_file(
                    db_uri,
                    schema["source_label"],
                    schema["dropbox_folder"],
                    schema["file_name"],
                    schema["file_path"],
                    schema["target_table"],
                    schema["has_header"],
                    schema["columns"],
                    dbx,
                )
                if success:
                    st.success(message)
                else:
                    st.error(message)
    else:
        st.info("Aún no hay archivos registrados para actualización automática.")


if __name__ == "__main__":
    main()
