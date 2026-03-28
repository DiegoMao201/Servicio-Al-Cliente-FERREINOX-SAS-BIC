
# =========================================
# Sincronizador Dropbox → PostgreSQL
# -----------------------------------------
# App Streamlit profesional para cargar y actualizar
# datos de Dropbox en PostgreSQL con manejo robusto
# de esquemas, encoding, delimitadores y errores.
# =========================================

# --- Librerías principales ---
import csv              # Detección de delimitadores y validación
import json             # Guardar/cargar esquemas
import os               # Operaciones de sistema
from io import StringIO
from pathlib import Path

import dropbox          # API de Dropbox
import pandas as pd     # Manipulación de datos
import streamlit as st  # Interfaz web
from sqlalchemy import create_engine  # ORM para PostgreSQL

from frontend.config import get_database_uri, get_dropbox_sources


dropbox_sources = get_dropbox_sources()
DB_URI = get_database_uri(required=False)
ESQUEMAS_PATH = Path(__file__).resolve().parent.parent / "esquemas_guardados.json"

def get_dropbox_client(app_key, app_secret, refresh_token):
    """
    Devuelve un cliente autenticado de Dropbox usando refresh_token.
    """
    return dropbox.Dropbox(
        oauth2_refresh_token=refresh_token,
        app_key=app_key,
        app_secret=app_secret
    )

def list_csv_files(dbx, folder):
    """
    Lista todos los archivos CSV en una carpeta de Dropbox.
    """
    files = dbx.files_list_folder(folder).entries
    return [f for f in files if isinstance(f, dropbox.files.FileMetadata) and f.name.endswith('.csv')]

def download_csv(dbx, file_path):
    """
    Descarga y lee un archivo CSV de Dropbox, detectando encoding y delimitador automáticamente.
    Valida que todas las filas tengan el mismo número de columnas.
    Si hay filas problemáticas, permite descargarlas para revisión.
    """
    _, res = dbx.files_download(file_path)
    encodings = ["utf-8", "latin1", "cp1252"]
    possible_delims = [',', '|', ';', '\t', '{']
    content = res.content
    for enc in encodings:
        try:
            text = content.decode(enc)
            # Detectar delimitador automáticamente
            sniffer = csv.Sniffer()
            sample = text[:2048]
            try:
                dialect = sniffer.sniff(sample, delimiters=possible_delims)
                delim = dialect.delimiter
            except Exception:
                delim = ','  # Por defecto
            # Leer con pandas
            df = pd.read_csv(StringIO(text), header=None, encoding=enc, sep=delim)
            # Validar filas problemáticas
            expected_cols = len(df.columns)
            bad_rows = []
            reader = csv.reader(StringIO(text), delimiter=delim)
            for idx, row in enumerate(reader):
                if len(row) != expected_cols:
                    bad_rows.append((idx+1, row))
            if bad_rows:
                st.error(f"El archivo tiene filas problemáticas con diferente número de columnas. Total: {len(bad_rows)}. Descarga el reporte, corrige y vuelve a intentar.")
                # Generar CSV de filas problemáticas
                output = StringIO()
                writer = csv.writer(output, delimiter=delim)
                writer.writerow(["Fila", "Contenido"])
                for idx, row in bad_rows:
                    writer.writerow([idx, str(row)])
                st.download_button("Descargar filas problemáticas", data=output.getvalue(), file_name="filas_problema.csv", mime="text/csv")
                return None
            return df
        except UnicodeDecodeError:
            continue
        except Exception as e:
            st.error(f"Error leyendo el archivo con encoding {enc}: {e}")
            return None
    st.error("No se pudo leer el archivo con los encodings comunes (utf-8, latin1, cp1252). Por favor, revisa el archivo.")
    return None

def guardar_esquema(tabla, columnas):
    """
    Guarda el esquema de columnas para una tabla específica en un archivo local JSON.
    """
    esquemas = {}
    if ESQUEMAS_PATH.exists():
        with ESQUEMAS_PATH.open("r", encoding="utf-8") as f:
            esquemas = json.load(f)
    esquemas[tabla] = columnas
    with ESQUEMAS_PATH.open("w", encoding="utf-8") as f:
        json.dump(esquemas, f, ensure_ascii=False, indent=2)

def cargar_esquema(tabla):
    """
    Carga el esquema de columnas guardado para una tabla específica.
    """
    if ESQUEMAS_PATH.exists():
        with ESQUEMAS_PATH.open("r", encoding="utf-8") as f:
            esquemas = json.load(f)
        return esquemas.get(tabla)
    return None

def clean_dataframe(df, tabla):
    """
    Permite al usuario organizar y nombrar las columnas del DataFrame.
    Valida unicidad y no vacíos antes de guardar el esquema.
    Si ya existe un esquema guardado, lo aplica automáticamente.
    """
    esquema_guardado = cargar_esquema(tabla)
    if esquema_guardado:
        df.columns = esquema_guardado
        st.info("Usando esquema de columnas guardado para esta tabla.")
        return df, False
    # Si no tiene encabezados, pedirlos al usuario
    if df.columns.to_list() == list(range(len(df.columns))):
        st.write("El archivo no tiene nombres de columnas. Por favor, asígnalos:")
        col_names = []
        for i in range(len(df.columns)):
            col_names.append(st.text_input(f"Nombre para columna {i+1}", key=f"col_{i}"))
        df.columns = col_names
    else:
        # Si tiene encabezados, permitir editarlos
        df.columns = [st.text_input(f"Nombre para columna {i+1}", v, key=f"col_{i}") for i, v in enumerate(df.columns)]
    # Validar unicidad y no vacíos
    col_set = set(df.columns)
    if len(col_set) != len(df.columns) or any([c.strip() == '' for c in df.columns]):
        st.error("Todos los nombres de columna deben ser únicos y no vacíos. Corrige antes de continuar.")
        return df, True  # editable, pero no dejar avanzar
    return df, True

def upload_to_postgres(df, table_name):
    """
    Sube el DataFrame a PostgreSQL, reemplazando la tabla si ya existe.
    Fuerza todos los datos a string para evitar problemas de encoding.
    """
    if not DB_URI:
        st.error("No se encontró la configuración de PostgreSQL. Define postgres.db_uri o DATABASE_URL.")
        return
    df = df.astype(str)
    engine = create_engine(DB_URI)
    with engine.connect() as conn:
        df.to_sql(table_name, conn, if_exists='replace', index=False)
    st.success(f"Datos subidos a la tabla {table_name}")

def actualizar_todo(dropbox_conf, dbx, dropbox_folder):
    """
    Actualiza todas las tablas en PostgreSQL para las que ya existe un esquema guardado.
    Descarga cada archivo de Dropbox, aplica el esquema y sube los datos.
    """
    if not ESQUEMAS_PATH.exists():
        st.info("No hay archivos guardados para actualizar.")
        return
    with ESQUEMAS_PATH.open("r", encoding="utf-8") as f:
        esquemas = json.load(f)
    actualizados = []
    for tabla, columnas in esquemas.items():
        archivo_csv = tabla + ".csv"
        try:
            files = dbx.files_list_folder(dropbox_folder).entries
            file_match = next((f for f in files if f.name.lower() == archivo_csv), None)
            if not file_match:
                st.warning(f"No se encontró el archivo {archivo_csv} en Dropbox para la tabla {tabla}.")
                continue
            # Descargar y procesar el archivo
            _, res = dbx.files_download(file_match.path_lower)
            encodings = ["utf-8", "latin1", "cp1252"]
            content = res.content
            for enc in encodings:
                try:
                    text = content.decode(enc)
                    # Detectar delimitador automáticamente
                    sniffer = csv.Sniffer()
                    sample = text[:2048]
                    try:
                        dialect = sniffer.sniff(sample, delimiters=[',', '|', ';', '\t', '{'])
                        delim = dialect.delimiter
                    except Exception:
                        delim = ','
                    df = pd.read_csv(StringIO(text), header=None, encoding=enc, sep=delim)
                    df.columns = columnas
                    upload_to_postgres(df, tabla)
                    actualizados.append(tabla)
                    break
                except Exception:
                    continue
        except Exception as e:
            st.error(f"Error actualizando {tabla}: {e}")
    if actualizados:
        st.success(f"Tablas actualizadas: {', '.join(actualizados)}")
    else:
        st.info("No se actualizó ninguna tabla.")

def main():
    """
    Interfaz principal de la app Streamlit para sincronizar archivos de Dropbox a PostgreSQL.
    Permite organizar columnas, guardar esquemas y actualizar tablas automáticamente.
    """
    st.header("Sincronizar archivos de Dropbox a PostgreSQL")
    if not dropbox_sources:
        st.error("No hay configuraciones de Dropbox disponibles en Streamlit Secrets.")
        return
    if not DB_URI:
        st.error("No hay conexión PostgreSQL configurada. Define postgres.db_uri o DATABASE_URL.")
        return
    fuente = st.selectbox("Selecciona la carpeta de Dropbox:", list(dropbox_sources.keys()))
    dropbox_conf = dropbox_sources[fuente]
    dbx = get_dropbox_client(
        dropbox_conf["app_key"],
        dropbox_conf["app_secret"],
        dropbox_conf["refresh_token"]
    )
    dropbox_folder = dropbox_conf["folder"] if "folder" in dropbox_conf else "/"
    files = list_csv_files(dbx, dropbox_folder)
    if not files:
        st.warning("No se encontraron archivos CSV en la carpeta seleccionada de Dropbox.")
        return
    file_names = [f.name for f in files]
    selected_file = st.selectbox("Selecciona un archivo para procesar:", file_names)
    if selected_file:
        file_path = next(f.path_lower for f in files if f.name == selected_file)
        df = download_csv(dbx, file_path)
        if df is None:
            st.error("No se pudo cargar el archivo. Revisa el formato o el encoding.")
            return
        st.write("Vista previa del archivo:")
        st.dataframe(df.head())
        table_name = st.text_input("Nombre de la tabla en PostgreSQL:", value=selected_file.replace('.csv','').lower())
        df, editable = clean_dataframe(df, table_name)
        st.write("Vista previa con columnas organizadas:")
        # Solo mostrar la vista previa si los nombres de columna son válidos
        col_set = set(df.columns)
        if len(col_set) == len(df.columns) and all([c.strip() != '' for c in df.columns]):
            st.dataframe(df.head())
        if editable:
            if st.button("Guardar esquema y subir a PostgreSQL"):
                # Validar unicidad y no vacíos antes de guardar
                if len(set(df.columns)) != len(df.columns) or any([c.strip() == '' for c in df.columns]):
                    st.error("No puedes guardar el esquema: todos los nombres de columna deben ser únicos y no vacíos.")
                else:
                    guardar_esquema(table_name, list(df.columns))
                    upload_to_postgres(df, table_name)
        else:
            if st.button("Actualizar tabla en PostgreSQL"):
                upload_to_postgres(df, table_name)

    # Botón para actualizar todo lo guardado
    st.markdown("---")
    if st.button("Actualizar todo (archivos ya guardados)"):
        actualizar_todo(dropbox_conf, dbx, dropbox_folder)

if __name__ == "__main__":
    main()
