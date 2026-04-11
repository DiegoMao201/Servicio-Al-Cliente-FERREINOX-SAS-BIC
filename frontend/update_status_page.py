import pandas as pd
import streamlit as st
from sqlalchemy import create_engine, text

from frontend.config import get_database_uri
from frontend.data_catalog import CATALOG_SPECS


@st.cache_data(show_spinner=False, ttl=30)
def load_status_snapshot(db_uri):
    engine = create_engine(db_uri)
    snapshot = []

    with engine.connect() as connection:
        existing_tables = {
            row[0]
            for row in connection.execute(
                text(
                    """
                    SELECT table_name
                    FROM information_schema.tables
                    WHERE table_schema = 'public'
                    """
                )
            ).fetchall()
        }

        sync_log_exists = connection.execute(
            text(
                """
                SELECT EXISTS (
                    SELECT 1
                    FROM information_schema.tables
                    WHERE table_schema = 'public' AND table_name = 'sync_run_log'
                )
                """
            )
        ).scalar_one()

        for spec in CATALOG_SPECS:
            table_exists = spec["target_table"] in existing_tables
            row_count = connection.execute(text(f'SELECT COUNT(*) FROM public."{spec["target_table"]}"')).scalar_one() if table_exists else 0
            latest_log = None
            if sync_log_exists:
                latest_log = connection.execute(
                    text(
                        """
                        SELECT status, row_count, message, executed_at
                        FROM public.sync_run_log
                        WHERE source_label = :source_label AND file_name = :file_name AND target_table = :target_table
                        ORDER BY executed_at DESC
                        LIMIT 1
                        """
                    ),
                    {
                        "source_label": spec["source_label"],
                        "file_name": spec["file_name"],
                        "target_table": spec["target_table"],
                    },
                ).mappings().one_or_none()

            snapshot.append(
                {
                    "Fuente": spec["source_label"],
                    "Archivo oficial": spec["file_name"],
                    "Tabla raw": spec["target_table"],
                    "Existe": "Si" if table_exists else "No",
                    "Filas actuales": row_count,
                    "Último estado": latest_log["status"] if latest_log else ("sin registro" if table_exists else "tabla no creada"),
                    "Última carga": latest_log["executed_at"] if latest_log else None,
                    "Filas última carga": latest_log["row_count"] if latest_log else None,
                    "Detalle": latest_log["message"] if latest_log else ("Aún no hay auditoría registrada." if table_exists else "Esta tabla raw todavía no existe en la base conectada."),
                }
            )

        recent_logs = []
        if sync_log_exists:
            recent_logs = connection.execute(
                text(
                    """
                    SELECT source_label, file_name, target_table, status, row_count, message, executed_at
                    FROM public.sync_run_log
                    ORDER BY executed_at DESC
                    LIMIT 20
                    """
                )
            ).mappings().all()

    return pd.DataFrame(snapshot), pd.DataFrame(recent_logs)


def main():
    st.title("Estado de Actualización")
    st.caption("Muestra el estado real de cada CSV oficial: cuándo cargó, cuántas filas dejó y cuál fue el último resultado.")

    try:
        db_uri = get_database_uri()
    except RuntimeError as exc:
        st.error(str(exc))
        return

    try:
        snapshot_df, recent_logs_df = load_status_snapshot(db_uri)
    except Exception as exc:
        st.error(f"No fue posible cargar el estado de actualización: {exc}")
        return

    ok_count = int((snapshot_df["Último estado"] == "success").sum()) if not snapshot_df.empty else 0
    metric_1, metric_2, metric_3 = st.columns(3)
    metric_1.metric("CSV oficiales", len(CATALOG_SPECS))
    metric_2.metric("Con carga exitosa", ok_count)
    metric_3.metric("Tablas raw activas", snapshot_df["Tabla raw"].nunique() if not snapshot_df.empty else 0)

    if not snapshot_df.empty and int((snapshot_df["Existe"] == "Si").sum()) < len(CATALOG_SPECS):
        st.warning(
            "La base conectada todavía no tiene todas las tablas raw oficiales. Usa primero la página Centro Operativo y el botón único de actualización para construir la base oficial."
        )

    st.subheader("Resumen actual")
    st.dataframe(snapshot_df, width="stretch")

    st.subheader("Últimos eventos")
    if recent_logs_df.empty:
        st.info("Aún no hay eventos registrados en sync_run_log.")
    else:
        st.dataframe(recent_logs_df, width="stretch")