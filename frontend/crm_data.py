import pandas as pd
import streamlit as st
from sqlalchemy import create_engine, text

from frontend.data_catalog import CATALOG_SPECS


def task_area_expression(alias="agent_task"):
    return f"""
        CASE
            WHEN {alias}.tipo_tarea = 'seguimiento_cartera' THEN 'Contabilidad'
            WHEN {alias}.tipo_tarea = 'contactar_asesor' THEN 'Ventas'
            WHEN {alias}.tipo_tarea LIKE '%reclamo%' THEN 'Servicio al cliente'
            WHEN {alias}.tipo_tarea LIKE 'validaci%' OR {alias}.tipo_tarea LIKE 'verificaci%' THEN 'Backoffice'
            ELSE 'Operaciones'
        END
    """


def build_routing_rules_dataframe():
    return pd.DataFrame(
        [
            {
                "Momento del flujo": "Cliente reclama un pedido, entrega o servicio",
                "Detección IA": "intent = reclamo | priority = alta/critica",
                "Salida esperada": "Crear tarea prioritaria y enviar correo con conversación completa",
                "Área destino": "Servicio al cliente",
                "Canal": "Correo + tarea",
            },
            {
                "Momento del flujo": "Cliente solicita saldo, facturas o cartera vencida",
                "Detección IA": "intent = consulta_cartera",
                "Salida esperada": "Responder, crear seguimiento si hay mora y notificar si supera umbral",
                "Área destino": "Contabilidad",
                "Canal": "WhatsApp + tarea",
            },
            {
                "Momento del flujo": "Cliente pide cotización o disponibilidad",
                "Detección IA": "intent = consulta_productos | cotizacion",
                "Salida esperada": "Resolver en línea o escalar vendedor con resumen estructurado",
                "Área destino": "Ventas",
                "Canal": "WhatsApp + correo",
            },
            {
                "Momento del flujo": "Cliente necesita compra especial o abastecimiento",
                "Detección IA": "intent = compra_especial | abastecimiento",
                "Salida esperada": "Consolidar necesidad y elevar a compras",
                "Área destino": "Compras",
                "Canal": "Correo + tarea",
            },
            {
                "Momento del flujo": "Se entrega documento técnico o solución resuelta",
                "Detección IA": "intent = consulta_documentacion | cierre_conversacion",
                "Salida esperada": "Cerrar caso y guardar señal de aprendizaje confiable",
                "Área destino": "Agente IA",
                "Canal": "Memoria estructurada",
            },
        ]
    )


def _load_existing_objects(connection):
    rows = connection.execute(
        text(
            """
            SELECT table_name AS object_name, 'table' AS object_type
            FROM information_schema.tables
            WHERE table_schema = 'public'
            UNION ALL
            SELECT table_name AS object_name, 'view' AS object_type
            FROM information_schema.views
            WHERE table_schema = 'public'
            """
        )
    ).mappings().all()
    tables = {row["object_name"] for row in rows if row["object_type"] == "table"}
    views = {row["object_name"] for row in rows if row["object_type"] == "view"}
    return tables, views


@st.cache_data(show_spinner=False, ttl=30)
def load_data_readiness(db_uri):
    engine = create_engine(db_uri)
    raw_tables = [spec["target_table"] for spec in CATALOG_SPECS]
    postgrest_views = sorted({view_name for spec in CATALOG_SPECS for view_name in spec["postgrest_views"]})

    with engine.connect() as connection:
        tables, views = _load_existing_objects(connection)
        sync_log_exists = "sync_run_log" in tables
        raw_rows = []
        for spec in CATALOG_SPECS:
            exists = spec["target_table"] in tables
            row_count = 0
            if exists:
                row_count = connection.execute(text(f'SELECT COUNT(*) FROM public."{spec["target_table"]}"')).scalar_one()
            raw_rows.append(
                {
                    "Fuente": spec["source_label"],
                    "Archivo": spec["file_name"],
                    "Tabla raw": spec["target_table"],
                    "Existe": "Si" if exists else "No",
                    "Filas": row_count,
                    "Vistas": ", ".join(spec["postgrest_views"]) or "Sin vista directa",
                }
            )

        latest_runs = []
        if sync_log_exists:
            latest_runs = connection.execute(
                text(
                    """
                    SELECT source_label, file_name, target_table, status, row_count, message, executed_at
                    FROM public.sync_run_log
                    ORDER BY executed_at DESC
                    LIMIT 12
                    """
                )
            ).mappings().all()

    raw_df = pd.DataFrame(raw_rows)
    return {
        "raw_df": raw_df,
        "latest_runs_df": pd.DataFrame(latest_runs),
        "raw_ready": int((raw_df["Existe"] == "Si").sum()) if not raw_df.empty else 0,
        "raw_with_data": int((raw_df["Filas"] > 0).sum()) if not raw_df.empty else 0,
        "raw_total": len(CATALOG_SPECS),
        "views_ready": sum(1 for view_name in postgrest_views if view_name in views),
        "views_total": len(postgrest_views),
    }


@st.cache_data(show_spinner=False, ttl=30)
def load_crm_hub_snapshot(db_uri):
    engine = create_engine(db_uri)
    required_tables = {"whatsapp_contacto", "agent_conversation", "agent_message", "agent_task"}

    with engine.connect() as connection:
        tables, _ = _load_existing_objects(connection)
        if not required_tables.issubset(tables):
            return {
                "available": False,
                "missing_tables": sorted(required_tables - tables),
            }

        metrics = {
            "contactos": connection.execute(text("SELECT COUNT(*) FROM public.whatsapp_contacto")).scalar_one(),
            "conversaciones_activas": connection.execute(
                text("SELECT COUNT(*) FROM public.agent_conversation WHERE estado IN ('abierta', 'pendiente', 'escalada')")
            ).scalar_one(),
            "mensajes": connection.execute(text("SELECT COUNT(*) FROM public.agent_message")).scalar_one(),
            "tareas_pendientes": connection.execute(
                text("SELECT COUNT(*) FROM public.agent_task WHERE estado IN ('pendiente', 'en_progreso')")
            ).scalar_one(),
            "tareas_criticas": connection.execute(
                text("SELECT COUNT(*) FROM public.agent_task WHERE estado IN ('pendiente', 'en_progreso') AND prioridad IN ('alta', 'critica')")
            ).scalar_one(),
        }

        has_quotes = "agent_quote" in tables
        has_orders = "agent_order" in tables
        metrics["cotizaciones_activas"] = (
            connection.execute(text("SELECT COUNT(*) FROM public.agent_quote WHERE estado IN ('borrador', 'confirmada', 'enviada')")).scalar_one()
            if has_quotes
            else 0
        )
        metrics["pedidos_abiertos"] = (
            connection.execute(text("SELECT COUNT(*) FROM public.agent_order WHERE estado IN ('borrador', 'pendiente_confirmacion', 'confirmado')")).scalar_one()
            if has_orders
            else 0
        )

        conversations_df = pd.read_sql_query(
            text(
                """
                SELECT
                    ac.id,
                    COALESCE(NULLIF(wc.nombre_visible, ''), wc.telefono_e164) AS cliente,
                    wc.telefono_e164 AS telefono,
                    ac.estado,
                    COALESCE(NULLIF(ac.contexto->>'intent', ''), 'sin_clasificar') AS intent,
                    COALESCE(NULLIF(ac.contexto->>'priority', ''), 'media') AS prioridad,
                    COALESCE(ac.resumen, 'Sin resumen operativo') AS resumen,
                    ac.started_at,
                    ac.last_message_at,
                    COALESCE(message_counts.total_messages, 0) AS mensajes
                FROM public.agent_conversation ac
                JOIN public.whatsapp_contacto wc ON wc.id = ac.contacto_id
                LEFT JOIN (
                    SELECT conversation_id, COUNT(*) AS total_messages
                    FROM public.agent_message
                    GROUP BY conversation_id
                ) message_counts ON message_counts.conversation_id = ac.id
                ORDER BY ac.last_message_at DESC NULLS LAST, ac.updated_at DESC
                LIMIT 100
                """
            ),
            connection,
        )

        tasks_df = pd.read_sql_query(
            text(
                f"""
                SELECT
                    agent_task.id,
                    agent_task.conversation_id,
                    agent_task.tipo_tarea,
                    agent_task.prioridad,
                    agent_task.estado,
                    agent_task.resumen,
                    agent_task.due_at,
                    agent_task.updated_at,
                    {task_area_expression()} AS area_destino
                FROM public.agent_task
                ORDER BY
                    CASE agent_task.prioridad
                        WHEN 'critica' THEN 1
                        WHEN 'alta' THEN 2
                        WHEN 'media' THEN 3
                        ELSE 4
                    END,
                    agent_task.updated_at DESC
                LIMIT 100
                """
            ),
            connection,
        )

        messages_df = pd.read_sql_query(
            text(
                """
                SELECT
                    conversation_id,
                    direction,
                    COALESCE(NULLIF(intent_detectado, ''), 'sin_clasificar') AS intent_detectado,
                    estado,
                    contenido,
                    created_at
                FROM public.agent_message
                ORDER BY created_at DESC
                LIMIT 160
                """
            ),
            connection,
        )

    intents_df = (
        conversations_df.groupby("intent", dropna=False).size().reset_index(name="conversaciones")
        if not conversations_df.empty
        else pd.DataFrame(columns=["intent", "conversaciones"])
    )
    areas_df = (
        tasks_df.groupby("area_destino", dropna=False).size().reset_index(name="tareas")
        if not tasks_df.empty
        else pd.DataFrame(columns=["area_destino", "tareas"])
    )

    return {
        "available": True,
        "metrics": metrics,
        "conversations_df": conversations_df,
        "tasks_df": tasks_df,
        "messages_df": messages_df,
        "intents_df": intents_df,
        "areas_df": areas_df,
        "routing_rules_df": build_routing_rules_dataframe(),
    }


@st.cache_data(show_spinner=False, ttl=30)
def load_conversation_detail(db_uri, conversation_id):
    engine = create_engine(db_uri)
    with engine.connect() as connection:
        conversation = connection.execute(
            text(
                """
                SELECT
                    ac.id,
                    COALESCE(NULLIF(wc.nombre_visible, ''), wc.telefono_e164) AS cliente,
                    wc.telefono_e164 AS telefono,
                    ac.estado,
                    COALESCE(NULLIF(ac.contexto->>'intent', ''), 'sin_clasificar') AS intent,
                    COALESCE(NULLIF(ac.contexto->>'priority', ''), 'media') AS prioridad,
                    ac.resumen,
                    ac.contexto,
                    ac.started_at,
                    ac.last_message_at
                FROM public.agent_conversation ac
                JOIN public.whatsapp_contacto wc ON wc.id = ac.contacto_id
                WHERE ac.id = :conversation_id
                """
            ),
            {"conversation_id": conversation_id},
        ).mappings().one_or_none()

        if conversation is None:
            return None

        messages_df = pd.read_sql_query(
            text(
                """
                SELECT direction, COALESCE(NULLIF(intent_detectado, ''), 'sin_clasificar') AS intent_detectado, contenido, estado, created_at
                FROM public.agent_message
                WHERE conversation_id = :conversation_id
                ORDER BY created_at ASC
                LIMIT 120
                """
            ),
            connection,
            params={"conversation_id": conversation_id},
        )

        tasks_df = pd.read_sql_query(
            text(
                f"""
                SELECT id, tipo_tarea, prioridad, estado, resumen, detalle, due_at, updated_at, {task_area_expression()} AS area_destino
                FROM public.agent_task
                WHERE conversation_id = :conversation_id
                ORDER BY updated_at DESC
                """
            ),
            connection,
            params={"conversation_id": conversation_id},
        )

        tables, _ = _load_existing_objects(connection)
        quotes_df = pd.DataFrame()
        orders_df = pd.DataFrame()
        if "agent_quote" in tables:
            quotes_df = pd.read_sql_query(
                text(
                    """
                    SELECT id, estado, total, resumen, updated_at
                    FROM public.agent_quote
                    WHERE conversation_id = :conversation_id
                    ORDER BY updated_at DESC
                    """
                ),
                connection,
                params={"conversation_id": conversation_id},
            )
        if "agent_order" in tables:
            orders_df = pd.read_sql_query(
                text(
                    """
                    SELECT id, estado, total, resumen, updated_at
                    FROM public.agent_order
                    WHERE conversation_id = :conversation_id
                    ORDER BY updated_at DESC
                    """
                ),
                connection,
                params={"conversation_id": conversation_id},
            )

    return {
        "conversation": dict(conversation),
        "messages_df": messages_df,
        "tasks_df": tasks_df,
        "quotes_df": quotes_df,
        "orders_df": orders_df,
    }