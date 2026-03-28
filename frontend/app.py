import pandas as pd
import streamlit as st
from sqlalchemy import create_engine, inspect

from frontend.config import get_database_uri


@st.cache_data(show_spinner=False)
def load_data(table_name, db_uri):
    """Carga una muestra de la tabla seleccionada para el dashboard."""
    engine = create_engine(db_uri)
    query = f'SELECT * FROM "{table_name}" LIMIT 5000'
    return pd.read_sql_query(query, engine)


@st.cache_data(show_spinner=False)
def list_tables(db_uri):
    """Obtiene las tablas disponibles del esquema público."""
    engine = create_engine(db_uri)
    return inspect(engine).get_table_names(schema="public")


def main():
    """Renderiza el dashboard de exploración de tablas en PostgreSQL."""
    st.title("CRM Ferreinox | Dashboard Operativo")
    st.caption("Exploración rápida de tablas sincronizadas para validación y análisis inicial.")

    try:
        db_uri = get_database_uri()
    except RuntimeError as exc:
        st.error(str(exc))
        st.info("Configura la conexión en Streamlit Secrets o en la variable de entorno DATABASE_URL.")
        return

    st.sidebar.header("Explorador de Datos")

    try:
        tablas = list_tables(db_uri)
    except Exception as exc:
        st.sidebar.error("No fue posible consultar la base de datos.")
        st.error(f"Detalle técnico: {exc}")
        return

    if not tablas:
        st.sidebar.warning("No se encontraron tablas en el esquema público.")
        st.info("Primero ejecuta la sincronización desde el módulo de Dropbox.")
        return

    tabla_seleccionada = st.sidebar.radio("Selecciona una tabla", tablas)
    st.sidebar.markdown("---")
    st.sidebar.info(f"Tabla activa: {tabla_seleccionada}")

    try:
        df = load_data(tabla_seleccionada, db_uri)
    except Exception as exc:
        st.error(f"No se pudo leer la tabla seleccionada: {exc}")
        return

    c1, c2, c3 = st.columns(3)
    c1.metric("Filas cargadas", len(df))
    c2.metric("Columnas", len(df.columns))
    c3.metric("Estado", "Online")

    tab1, tab2 = st.tabs(["Datos", "Análisis rápido"])

    with tab1:
        st.dataframe(df, use_container_width=True)

    with tab2:
        st.subheader("Análisis automático")
        numeric_columns = df.select_dtypes(include=["number"]).columns.tolist()
        if numeric_columns:
            selected_metric = st.selectbox("Columna numérica", numeric_columns)
            st.bar_chart(df[selected_metric])
        else:
            st.info("La tabla no contiene columnas numéricas listas para graficar.")


if __name__ == "__main__":
    main()