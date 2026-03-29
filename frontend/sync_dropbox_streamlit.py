import streamlit as st

from frontend.config import get_database_uri, get_dropbox_sources
from frontend.dropbox_sync_service import (
    build_target_table_name,
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
    if parse_result["bad_rows"]:
        message = f"Se detectaron {len(parse_result['bad_rows'])} filas con número irregular de columnas."
        record_sync_run(db_uri, None, source_label, file_name, target_table, "error", message=message)
        return False, message

    if len(dataframe.columns) != len(columns):
        message = "La estructura actual del archivo no coincide con el esquema guardado."
        record_sync_run(db_uri, None, source_label, file_name, target_table, "error", message=message)
        return False, message

    dataframe.columns = columns
    upload_dataframe(db_uri, dataframe, target_table)
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
    return True, f"Sincronización exitosa de {file_name} hacia {target_table}."


def main():
    """Renderiza el módulo principal de sincronización Dropbox -> PostgreSQL raw."""
    st.title("Sincronización Dropbox")
    st.caption("Carga archivos CSV de Dropbox a tablas raw y guarda los esquemas directamente en PostgreSQL.")

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
        st.warning("No se encontraron archivos CSV en la carpeta configurada.")
        return

    file_lookup = {file_entry.name: file_entry for file_entry in files}
    selected_file_name = st.selectbox("Archivo CSV", list(file_lookup.keys()))
    selected_file = file_lookup[selected_file_name]
    saved_schema = fetch_saved_schema(db_uri, source_label, selected_file.path_lower)

    default_has_header = saved_schema["has_header"] if saved_schema else False
    has_header = st.checkbox("La primera fila contiene encabezados", value=default_has_header)

    parse_result = parse_dropbox_csv(dbx, selected_file.path_lower, has_header=has_header)
    if not parse_result["ok"]:
        st.error(parse_result["error"])
        return

    if parse_result["bad_rows"]:
        st.error(f"Se detectaron {len(parse_result['bad_rows'])} filas con diferente número de columnas. Corrige el archivo antes de sincronizar.")
        return

    dataframe = parse_result["dataframe"]
    st.subheader("Vista previa")
    st.dataframe(dataframe.head(), use_container_width=True)

    default_target_table = saved_schema["target_table"] if saved_schema else build_target_table_name(source_label, selected_file_name)
    target_table = st.text_input("Tabla destino en PostgreSQL", value=default_target_table).strip()

    st.subheader("Esquema de columnas")
    edited_columns = render_column_editor(dataframe, saved_columns=saved_schema["columns"] if saved_schema else None)
    is_valid, validation_message = validate_columns(edited_columns)
    if not is_valid:
        st.error(validation_message)
        return

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
