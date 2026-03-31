import json
import re

import pandas as pd
import streamlit as st
from sqlalchemy import create_engine, text

from frontend.data_catalog import CATALOG_SPECS


CLOSING_PATTERNS = [
    r"^(gracias|muchas gracias|mil gracias|genial gracias|super gracias|perfecto gracias)[.!?,\s]*$",
    r"^(genial|perfecto|listo|excelente|super|buenisimo|buenisima)(\s+(muchas\s+)?gracias)?[.!?,\s]*$",
    r"^(ok|okay|vale|dale|entendido|comprendido)(\s+(muchas\s+)?gracias)?[.!?,\s]*$",
    r"^(quedo atento|quedo atenta|te aviso|te escribo luego|eso era|nada mas|nada mas gracias)[.!?,\s]*$",
]


def normalize_text_value(text_value):
    return re.sub(r"\s+", " ", str(text_value or "").strip().lower())


def is_closing_message(text_value):
    lowered = normalize_text_value(text_value)
    if not lowered:
        return False
    return any(re.match(pattern, lowered) for pattern in CLOSING_PATTERNS)


def conversation_display_state(raw_state):
    return {
        "abierta": "Activa",
        "pendiente": "En seguimiento",
        "escalada": "Escalada",
        "cerrada": "Gestionada",
    }.get(raw_state or "", "Sin estado")


def task_display_state(raw_state):
    return {
        "pendiente": "Pendiente",
        "en_progreso": "En ejecución",
        "resuelta": "Gestionada",
        "cancelada": "Cancelada",
    }.get(raw_state or "", "Sin estado")


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


def annotate_conversations(conversations_df):
    if conversations_df.empty:
        return conversations_df

    annotated_df = conversations_df.copy()
    annotated_df["estado_operativo"] = annotated_df["estado"].apply(conversation_display_state)
    annotated_df["necesita_cierre"] = annotated_df.apply(
        lambda row: bool(
            row.get("estado") != "cerrada"
            and (
                row.get("intent") == "cierre_conversacion"
                or row.get("last_intent") == "cierre_conversacion"
                or is_closing_message(row.get("last_content"))
            )
        ),
        axis=1,
    )
    annotated_df["pendientes_operativos"] = annotated_df.get("pending_tasks", 0).fillna(0).astype(int)
    annotated_df["resueltas_operativas"] = annotated_df.get("resolved_tasks", 0).fillna(0).astype(int)
    return annotated_df


def build_closure_recommendation(conversation, messages_df, tasks_df):
    pending_tasks = int(tasks_df["estado"].isin(["pendiente", "en_progreso"]).sum()) if not tasks_df.empty else 0
    latest_customer_message = None
    latest_agent_intent = None

    if not messages_df.empty:
        inbound_messages = messages_df[messages_df["direction"] == "inbound"]
        outbound_messages = messages_df[messages_df["direction"] == "outbound"]
        if not inbound_messages.empty:
            latest_customer_message = inbound_messages.iloc[-1]["contenido"]
        if not outbound_messages.empty:
            latest_agent_intent = outbound_messages.iloc[-1]["intent_detectado"]

    detected_reasons = []
    if conversation.get("estado") == "cerrada":
        return {
            "already_managed": True,
            "should_close": False,
            "pending_tasks": pending_tasks,
            "reason": "La conversación ya está cerrada y visible como gestionada.",
        }

    if conversation.get("intent") == "cierre_conversacion":
        detected_reasons.append("La IA ya marcó cierre conversacional.")
    if latest_agent_intent == "cierre_conversacion":
        detected_reasons.append("El agente ya respondió con mensaje de cierre.")
    if is_closing_message(latest_customer_message):
        detected_reasons.append("El último mensaje del cliente es una despedida o agradecimiento.")

    return {
        "already_managed": False,
        "should_close": bool(detected_reasons),
        "pending_tasks": pending_tasks,
        "reason": " ".join(detected_reasons) if detected_reasons else "No hay señal fuerte de cierre todavía.",
    }


def _merge_conversation_context(existing_context, extra_context):
    merged_context = dict(existing_context or {})
    merged_context.update(extra_context or {})
    return merged_context


def mark_conversation_as_managed(db_uri, conversation_id, resolution_note=None, resolve_tasks=True):
    engine = create_engine(db_uri)
    with engine.begin() as connection:
        row = connection.execute(
            text(
                """
                SELECT contexto, resumen
                FROM public.agent_conversation
                WHERE id = :conversation_id
                """
            ),
            {"conversation_id": conversation_id},
        ).mappings().one()

        merged_context = _merge_conversation_context(
            row.get("contexto"),
            {
                "intent": "cierre_conversacion",
                "final_status": "gestionado",
                "managed_from": "frontend_operador",
                "managed_note": resolution_note or "Cierre gestionado desde el CRM.",
            },
        )

        connection.execute(
            text(
                """
                UPDATE public.agent_conversation
                SET estado = 'cerrada',
                    resumen = :summary,
                    contexto = CAST(:context_payload AS jsonb),
                    updated_at = now(),
                    last_message_at = now()
                WHERE id = :conversation_id
                """
            ),
            {
                "conversation_id": conversation_id,
                "summary": resolution_note or row.get("resumen") or "Cierre gestionado desde el CRM.",
                "context_payload": json.dumps(merged_context, ensure_ascii=True),
            },
        )

        resolved_tasks = 0
        if resolve_tasks:
            task_result = connection.execute(
                text(
                    """
                    UPDATE public.agent_task
                    SET estado = 'resuelta',
                        updated_at = now()
                    WHERE conversation_id = :conversation_id
                      AND estado IN ('pendiente', 'en_progreso')
                    """
                ),
                {"conversation_id": conversation_id},
            )
            resolved_tasks = task_result.rowcount or 0

    load_crm_hub_snapshot.clear()
    load_conversation_detail.clear()
    return {"resolved_tasks": resolved_tasks}


def reopen_conversation_for_followup(db_uri, conversation_id, note=None):
    engine = create_engine(db_uri)
    with engine.begin() as connection:
        row = connection.execute(
            text(
                """
                SELECT contexto
                FROM public.agent_conversation
                WHERE id = :conversation_id
                """
            ),
            {"conversation_id": conversation_id},
        ).mappings().one()

        merged_context = _merge_conversation_context(
            row.get("contexto"),
            {
                "final_status": "seguimiento",
                "managed_from": "frontend_operador",
                "managed_note": note or "Reabierta desde el CRM para seguimiento.",
            },
        )

        connection.execute(
            text(
                """
                UPDATE public.agent_conversation
                SET estado = 'pendiente',
                    contexto = CAST(:context_payload AS jsonb),
                    updated_at = now(),
                    last_message_at = now()
                WHERE id = :conversation_id
                """
            ),
            {
                "conversation_id": conversation_id,
                "context_payload": json.dumps(merged_context, ensure_ascii=True),
            },
        )

    load_crm_hub_snapshot.clear()
    load_conversation_detail.clear()


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
            "conversaciones_gestionadas": connection.execute(
                text("SELECT COUNT(*) FROM public.agent_conversation WHERE estado = 'cerrada'")
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
                    COALESCE(message_counts.total_messages, 0) AS mensajes,
                    COALESCE(task_counts.pending_tasks, 0) AS pending_tasks,
                    COALESCE(task_counts.resolved_tasks, 0) AS resolved_tasks,
                    COALESCE(last_message.last_direction, 'sin_dato') AS last_direction,
                    COALESCE(last_message.last_intent, 'sin_clasificar') AS last_intent,
                    COALESCE(last_message.last_content, '') AS last_content
                FROM public.agent_conversation ac
                JOIN public.whatsapp_contacto wc ON wc.id = ac.contacto_id
                LEFT JOIN (
                    SELECT conversation_id, COUNT(*) AS total_messages
                    FROM public.agent_message
                    GROUP BY conversation_id
                ) message_counts ON message_counts.conversation_id = ac.id
                LEFT JOIN (
                    SELECT
                        conversation_id,
                        COUNT(*) FILTER (WHERE estado IN ('pendiente', 'en_progreso')) AS pending_tasks,
                        COUNT(*) FILTER (WHERE estado = 'resuelta') AS resolved_tasks
                    FROM public.agent_task
                    GROUP BY conversation_id
                ) task_counts ON task_counts.conversation_id = ac.id
                LEFT JOIN (
                    SELECT DISTINCT ON (conversation_id)
                        conversation_id,
                        direction AS last_direction,
                        COALESCE(NULLIF(intent_detectado, ''), 'sin_clasificar') AS last_intent,
                        COALESCE(contenido, '') AS last_content
                    FROM public.agent_message
                    ORDER BY conversation_id, created_at DESC, id DESC
                ) last_message ON last_message.conversation_id = ac.id
                ORDER BY ac.last_message_at DESC NULLS LAST, ac.updated_at DESC
                LIMIT 100
                """
            ),
            connection,
        )
        conversations_df = annotate_conversations(conversations_df)

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
        if not tasks_df.empty:
            tasks_df["estado_operativo"] = tasks_df["estado"].apply(task_display_state)

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
    metrics["conversaciones_por_cerrar"] = int(conversations_df["necesita_cierre"].sum()) if not conversations_df.empty else 0

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
                    ac.last_message_at,
                    COALESCE(task_counts.pending_tasks, 0) AS pending_tasks,
                    COALESCE(task_counts.resolved_tasks, 0) AS resolved_tasks
                FROM public.agent_conversation ac
                JOIN public.whatsapp_contacto wc ON wc.id = ac.contacto_id
                LEFT JOIN (
                    SELECT
                        conversation_id,
                        COUNT(*) FILTER (WHERE estado IN ('pendiente', 'en_progreso')) AS pending_tasks,
                        COUNT(*) FILTER (WHERE estado = 'resuelta') AS resolved_tasks
                    FROM public.agent_task
                    GROUP BY conversation_id
                ) task_counts ON task_counts.conversation_id = ac.id
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
        if not tasks_df.empty:
            tasks_df["estado_operativo"] = tasks_df["estado"].apply(task_display_state)

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

    conversation_payload = dict(conversation)
    conversation_payload["estado_operativo"] = conversation_display_state(conversation_payload.get("estado"))
    closure_recommendation = build_closure_recommendation(conversation_payload, messages_df, tasks_df)

    return {
        "conversation": conversation_payload,
        "messages_df": messages_df,
        "tasks_df": tasks_df,
        "quotes_df": quotes_df,
        "orders_df": orders_df,
        "closure_recommendation": closure_recommendation,
    }