import streamlit as st
import dropbox

# --- Script para explorar carpetas y archivos en Dropbox ---
dropbox_sources = {}
if "dropbox_rotacion" in st.secrets:
    dropbox_sources["Rotación Inventarios"] = st.secrets["dropbox_rotacion"]
if "dropbox_cartera" in st.secrets:
    dropbox_sources["Cartera Ferreinox"] = st.secrets["dropbox_cartera"]
if "dropbox_ventas" in st.secrets:
    dropbox_sources["Ventas Ferreinox"] = st.secrets["dropbox_ventas"]

def get_dropbox_client(app_key, app_secret, refresh_token):
    return dropbox.Dropbox(
        oauth2_refresh_token=refresh_token,
        app_key=app_key,
        app_secret=app_secret
    )

st.title("Explorador de Dropbox: Carpetas y Archivos")
if not dropbox_sources:
    st.error("No hay configuraciones de Dropbox disponibles en secrets.toml")
else:
    fuente = st.selectbox("Selecciona la carpeta de Dropbox a explorar:", list(dropbox_sources.keys()))
    dropbox_conf = dropbox_sources[fuente]
    dbx = get_dropbox_client(
        dropbox_conf["app_key"],
        dropbox_conf["app_secret"],
        dropbox_conf["refresh_token"]
    )
    ruta = st.text_input("Ruta a explorar (ejemplo: /, /RotacionInventarios, /RotacionInventarios/data):", value="/")
    if st.button("Listar contenido"):
        try:
            archivos = dbx.files_list_folder(ruta).entries
            st.success(f"Archivos/carpetas encontrados en {ruta}:")
            for f in archivos:
                st.write(f"{f.name} ({'Carpeta' if hasattr(f, 'path_display') and f.path_display.endswith('/') else 'Archivo'})")
        except Exception as e:
            st.error(f"Error: {e}")
