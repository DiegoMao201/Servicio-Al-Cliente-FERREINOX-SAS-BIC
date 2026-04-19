import base64
import calendar
import io
import json
import logging
import re
from datetime import date, datetime
from html import escape
from typing import Any, Optional

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError


logger = logging.getLogger("internal_agent_ops")

_XL_DARK_FILL = PatternFill("solid", fgColor="111827")
_XL_ACCENT_FILL = PatternFill("solid", fgColor="F59E0B")
_XL_LIGHT_FILL = PatternFill("solid", fgColor="F9FAFB")
_XL_BORDER = Border(
    left=Side(style="thin", color="D1D5DB"),
    right=Side(style="thin", color="D1D5DB"),
    top=Side(style="thin", color="D1D5DB"),
    bottom=Side(style="thin", color="D1D5DB"),
)


_ROUTINE_ALIAS_MAP = {
    "/rutina_diaria_gerencia": "rutina_diaria_gerencia",
    "/rutina_cartera": "rutina_cartera",
    "/rutina_bodega": "rutina_bodega",
    "/rutina_compras": "rutina_compras",
    "/rutina_comercial": "rutina_comercial",
    "rutina gerencia": "rutina_diaria_gerencia",
    "cierre gerencia": "rutina_diaria_gerencia",
    "rutina cartera": "rutina_cartera",
    "seguimiento cartera": "rutina_cartera",
    "rutina bodega": "rutina_bodega",
    "reposicion bodega": "rutina_bodega",
    "rutina compras": "rutina_compras",
    "rutina comercial": "rutina_comercial",
}

_ROLE_FALLBACKS = {
    "administrador": ("administracion", "Administracion", "control"),
    "gerente": ("gerencia_general", "Gerencia General", "ejecutivo"),
    "operador": ("bodega", "Bodega", "operativo"),
    "vendedor": ("comercial", "Comercial", "ventas"),
    "empleado": ("empleado_operativo", "Empleado Operativo", "soporte"),
}


def _normalize_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip()).lower()


def _format_currency(value: Any) -> str:
    try:
        numeric = float(value or 0)
    except (TypeError, ValueError):
        numeric = 0.0
    return f"${numeric:,.0f}"


def _format_number(value: Any) -> str:
    try:
        numeric = float(value or 0)
    except (TypeError, ValueError):
        numeric = 0.0
    if numeric.is_integer():
        return str(int(numeric))
    return f"{numeric:,.2f}"


def _format_percent(value: Any) -> str:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return "N/D"
    return f"{numeric:,.1f}%"


def detect_requested_routine(user_message: Optional[str]) -> Optional[str]:
    normalized = _normalize_text(user_message)
    if not normalized:
        return None
    for alias, routine_key in _ROUTINE_ALIAS_MAP.items():
        if alias in normalized:
            return routine_key
    return None


def _infer_role_profile_from_auth(internal_auth: Optional[dict]) -> dict:
    internal_auth = internal_auth or {}
    employee_context = internal_auth.get("employee_context") or {}
    cargo = _normalize_text(employee_context.get("cargo"))
    base_role = _normalize_text(internal_auth.get("role")) or "empleado"

    if any(token in cargo for token in ("geren", "direccion")):
        role_key, display_name, prompt_mode = ("gerencia_general", "Gerencia General", "ejecutivo")
    elif "cartera" in cargo:
        role_key, display_name, prompt_mode = ("cartera", "Cartera", "cobranza")
    elif any(token in cargo for token in ("compra", "abastecimiento")):
        role_key, display_name, prompt_mode = ("compras", "Compras", "abastecimiento")
    elif any(token in cargo for token in ("bodega", "almacen", "despacho")):
        role_key, display_name, prompt_mode = ("bodega", "Bodega", "operativo")
    elif any(token in cargo for token in ("admin", "contab", "tesorer")):
        role_key, display_name, prompt_mode = ("administracion", "Administracion", "control")
    else:
        role_key, display_name, prompt_mode = _ROLE_FALLBACKS.get(
            base_role,
            ("empleado_operativo", "Empleado Operativo", "soporte"),
        )

    return {
        "role_key": role_key,
        "display_name": display_name,
        "prompt_mode": prompt_mode,
        "base_role": base_role or "empleado",
        "priority_focus": [],
        "allowed_kpis": [],
        "allowed_tools": [],
        "guidance_template": None,
    }


def _fetch_role_profile(engine, internal_auth: Optional[dict]) -> dict:
    fallback = _infer_role_profile_from_auth(internal_auth)
    if not engine or not (internal_auth or {}).get("user_id"):
        return fallback

    try:
        with engine.begin() as connection:
            row = connection.execute(
                text(
                    """
                    SELECT
                        rp.role_key,
                        rp.display_name,
                        rp.base_role,
                        rp.prompt_mode,
                        rp.priority_focus,
                        rp.allowed_kpis,
                        rp.allowed_tools,
                        rp.guidance_template
                    FROM public.agent_user_role_profile urp
                    JOIN public.agent_role_profile rp ON rp.role_key = urp.role_key
                    WHERE urp.user_id = :user_id
                      AND urp.is_active = true
                    ORDER BY urp.updated_at DESC
                    LIMIT 1
                    """
                ),
                {"user_id": internal_auth.get("user_id")},
            ).mappings().one_or_none()
    except SQLAlchemyError as exc:
        logger.debug("role profile lookup unavailable: %s", exc)
        row = None

    if not row:
        return fallback

    return {
        "role_key": row.get("role_key") or fallback["role_key"],
        "display_name": row.get("display_name") or fallback["display_name"],
        "prompt_mode": row.get("prompt_mode") or fallback["prompt_mode"],
        "base_role": row.get("base_role") or fallback["base_role"],
        "priority_focus": list(row.get("priority_focus") or []),
        "allowed_kpis": list(row.get("allowed_kpis") or []),
        "allowed_tools": list(row.get("allowed_tools") or []),
        "guidance_template": row.get("guidance_template"),
    }


def _fetch_routine_definition(engine, routine_key: Optional[str]) -> Optional[dict]:
    if not routine_key:
        return None
    if not engine:
        return {"routine_key": routine_key, "display_name": routine_key.replace("_", " ").title()}

    try:
        with engine.begin() as connection:
            row = connection.execute(
                text(
                    """
                    SELECT routine_key, display_name, command_token, role_key, description, prompt_hint, default_filters
                    FROM public.agent_internal_routine
                    WHERE routine_key = :routine_key
                      AND is_active = true
                    LIMIT 1
                    """
                ),
                {"routine_key": routine_key},
            ).mappings().one_or_none()
            return dict(row) if row else None
    except SQLAlchemyError as exc:
        logger.debug("routine definition unavailable: %s", exc)
        return None


def _fetch_alerts(engine, role_key: str, store_code: Optional[str], limit: int = 3) -> list[dict]:
    if not engine:
        return []

    store_code = re.sub(r"\D", "", str(store_code or "")) or None
    try:
        with engine.begin() as connection:
            rows = connection.execute(
                text(
                    """
                    SELECT alert_type, severity, title, detail, payload
                    FROM public.vw_internal_alert_candidates
                    WHERE assigned_role_key = :role_key
                       OR :role_key = 'gerencia_general'
                       OR (:store_code IS NOT NULL AND COALESCE(payload->>'cod_almacen', '') = :store_code)
                    ORDER BY CASE severity WHEN 'alta' THEN 1 WHEN 'media' THEN 2 ELSE 3 END,
                             title ASC
                    LIMIT :limit
                    """
                ),
                {"role_key": role_key, "store_code": store_code, "limit": limit},
            ).mappings().all()
            return [dict(row) for row in rows]
    except SQLAlchemyError as exc:
        logger.debug("alert snapshot unavailable: %s", exc)
        return []


def _fetch_pending_items(engine, user_id: Optional[int], role_key: str, limit: int = 5) -> list[dict]:
    if not engine:
        return []

    try:
        with engine.begin() as connection:
            rows = connection.execute(
                text(
                    """
                    SELECT item_type, item_id, title, summary, due_at, priority, owner_user_id, role_key
                    FROM public.vw_internal_pending_queue
                    WHERE (:user_id IS NOT NULL AND owner_user_id = :user_id)
                       OR role_key = :role_key
                    ORDER BY priority_rank ASC, due_at NULLS LAST, created_at DESC
                    LIMIT :limit
                    """
                ),
                {"user_id": user_id, "role_key": role_key, "limit": limit},
            ).mappings().all()
            return [dict(row) for row in rows]
    except SQLAlchemyError as exc:
        logger.debug("pending items unavailable: %s", exc)
        return []


def _fetch_role_kpi_lines(engine, role_key: str, store_code: Optional[str], routine_key: Optional[str]) -> list[str]:
    if not engine:
        return []

    lines: list[str] = []
    params = {"store_code": re.sub(r"\D", "", str(store_code or "")) or None}
    try:
        with engine.begin() as connection:
            if role_key == "gerencia_general" or routine_key == "rutina_diaria_gerencia":
                ventas = connection.execute(
                    text(
                        """
                        SELECT
                            COALESCE(SUM(CASE WHEN sales_date = CURRENT_DATE THEN net_sales END), 0) AS ventas_hoy,
                            COALESCE(SUM(CASE WHEN sales_date >= date_trunc('month', CURRENT_DATE)::date THEN net_sales END), 0) AS ventas_mes
                        FROM public.mv_internal_sales_daily
                        """
                    )
                ).mappings().one()
                cartera = connection.execute(
                    text(
                        """
                        SELECT
                            COALESCE(SUM(balance_total), 0) AS cartera_total,
                            COALESCE(SUM(balance_61_90 + balance_91_plus), 0) AS cartera_vencida
                        FROM public.mv_internal_cartera_cliente
                        """
                    )
                ).mappings().one()
                inventario = connection.execute(
                    text(
                        """
                        SELECT
                            COUNT(*) FILTER (WHERE health_status = 'quiebre_critico') AS quiebres,
                            COUNT(*) FILTER (WHERE health_status = 'sobrestock') AS sobrestock
                        FROM public.mv_internal_inventory_health
                        """
                    )
                ).mappings().one()
                lines.append(
                    f"KPI rapido: ventas hoy {_format_currency(ventas.get('ventas_hoy'))}, ventas mes {_format_currency(ventas.get('ventas_mes'))}."
                )
                if float(ventas.get("ventas_mes") or 0) > 0:
                    today = date.today()
                    proyeccion_mes = (float(ventas.get("ventas_mes") or 0) / max(today.day, 1)) * calendar.monthrange(today.year, today.month)[1]
                    lines.append(f"KPI rapido: proyección cierre mes {_format_currency(proyeccion_mes)}.")
                lines.append(
                    f"KPI rapido: cartera vencida {_format_currency(cartera.get('cartera_vencida'))} sobre total {_format_currency(cartera.get('cartera_total'))}."
                )
                lines.append(
                    f"KPI rapido: quiebres criticos {inventario.get('quiebres') or 0}, sobrestock {inventario.get('sobrestock') or 0}."
                )

            elif role_key in {"cartera", "administracion"} or routine_key == "rutina_cartera":
                cartera = connection.execute(
                    text(
                        """
                        SELECT
                            COUNT(*) FILTER (WHERE (balance_61_90 + balance_91_plus) > 0) AS clientes_vencidos,
                            COALESCE(SUM(balance_61_90), 0) AS bucket_61_90,
                            COALESCE(SUM(balance_91_plus), 0) AS bucket_91_plus
                        FROM public.mv_internal_cartera_cliente
                        """
                    )
                ).mappings().one()
                lines.append(
                    f"KPI rapido: clientes vencidos {cartera.get('clientes_vencidos') or 0}, 61-90 {_format_currency(cartera.get('bucket_61_90'))}, >90 {_format_currency(cartera.get('bucket_91_plus'))}."
                )

            elif role_key in {"bodega", "compras"} or routine_key in {"rutina_bodega", "rutina_compras"}:
                inventario = connection.execute(
                    text(
                        """
                        SELECT
                            COUNT(*) FILTER (WHERE health_status = 'quiebre_critico') AS quiebres,
                            COUNT(*) FILTER (WHERE health_status = 'reposicion_recomendada') AS reposicion,
                            COUNT(*) FILTER (WHERE health_status = 'sobrestock') AS sobrestock,
                            COUNT(*) FILTER (WHERE health_status = 'sin_movimiento') AS sin_movimiento
                        FROM public.mv_internal_inventory_health
                        WHERE :store_code IS NULL OR cod_almacen = :store_code
                        """
                    ),
                    params,
                ).mappings().one()
                lines.append(
                    f"KPI rapido: quiebres {inventario.get('quiebres') or 0}, reposicion {inventario.get('reposicion') or 0}, sobrestock {inventario.get('sobrestock') or 0}, sin movimiento {inventario.get('sin_movimiento') or 0}."
                )

            elif role_key == "comercial" or routine_key == "rutina_comercial":
                ventas = connection.execute(
                    text(
                        """
                        SELECT
                            COALESCE(SUM(CASE WHEN sales_date = CURRENT_DATE THEN net_sales END), 0) AS ventas_hoy,
                            COALESCE(SUM(CASE WHEN sales_date >= date_trunc('month', CURRENT_DATE)::date THEN net_sales END), 0) AS ventas_mes,
                            COUNT(DISTINCT CASE WHEN sales_date >= date_trunc('month', CURRENT_DATE)::date THEN codigo_vendedor END) AS vendedores_activos
                        FROM public.mv_internal_sales_daily
                        WHERE :store_code IS NULL OR regexp_replace(COALESCE(serie, ''), '[^0-9]', '', 'g') = :store_code
                        """
                    ),
                    params,
                ).mappings().one()
                lines.append(
                    f"KPI rapido: ventas hoy {_format_currency(ventas.get('ventas_hoy'))}, ventas mes {_format_currency(ventas.get('ventas_mes'))}, vendedores activos {ventas.get('vendedores_activos') or 0}."
                )
                if float(ventas.get("ventas_mes") or 0) > 0:
                    today = date.today()
                    proyeccion_mes = (float(ventas.get("ventas_mes") or 0) / max(today.day, 1)) * calendar.monthrange(today.year, today.month)[1]
                    lines.append(f"KPI rapido: proyección cierre mes {_format_currency(proyeccion_mes)}.")
    except SQLAlchemyError as exc:
        logger.debug("role KPI snapshot unavailable: %s", exc)

    return lines


def build_internal_operational_context(engine, internal_auth: Optional[dict], user_message: Optional[str], conversation_context: Optional[dict]) -> str:
    internal_auth = internal_auth or {}
    role_profile = _fetch_role_profile(engine, internal_auth)
    routine_key = detect_requested_routine(user_message)
    routine = _fetch_routine_definition(engine, routine_key)
    employee_context = internal_auth.get("employee_context") or {}

    lines = []
    lines.append("")
    lines.append("═══ CAPA OPERATIVA INTERNA ═══")
    lines.append(
        f"Perfil operativo activo: {role_profile.get('display_name', 'Empleado Operativo')} ({role_profile.get('role_key', 'empleado_operativo')})."
    )
    lines.append(f"Modo de respuesta esperado: {role_profile.get('prompt_mode', 'soporte')}.")
    if role_profile.get("guidance_template"):
        lines.append(f"Directriz: {role_profile['guidance_template']}")
    if routine:
        lines.append(f"Rutina detectada: {routine.get('display_name')} ({routine.get('command_token')}).")
        if routine.get("prompt_hint"):
            lines.append(f"Objetivo de la rutina: {routine.get('prompt_hint')}")

    lines.extend(
        _fetch_role_kpi_lines(
            engine,
            role_profile.get("role_key") or "empleado_operativo",
            employee_context.get("store_code"),
            routine_key,
        )
    )

    alerts = _fetch_alerts(engine, role_profile.get("role_key") or "empleado_operativo", employee_context.get("store_code"))
    if alerts:
        lines.append("Alertas activas:")
        for alert in alerts[:3]:
            lines.append(f"  • [{str(alert.get('severity') or '').upper()}] {alert.get('title')}: {alert.get('detail')}")

    lines.append("Si el pedido del colaborador es gerencial o administrativo, prioriza KPIs, alertas y accion concreta.")
    return "\n".join(lines)


def _clamp_limit(raw_value: Any, default: int, minimum: int, maximum: int) -> int:
    try:
        value = int(raw_value or default)
    except (TypeError, ValueError):
        value = default
    return max(minimum, min(value, maximum))


def _resolve_store_code(raw_value: Any) -> Optional[str]:
    normalized = re.sub(r"\D", "", str(raw_value or "")).strip()
    return normalized or None


def _is_valid_email(value: Optional[str]) -> bool:
    if not value:
        return False
    return bool(re.match(r"^[^\s@]+@[^\s@]+\.[^\s@]+$", value.strip()))


def _fetch_sales_projection(engine, store_code: Optional[str]) -> dict:
    today = date.today()
    days_in_month = calendar.monthrange(today.year, today.month)[1]
    params = {"start_month": today.replace(day=1), "today": today, "store_code": store_code}
    with engine.begin() as connection:
        row = connection.execute(
            text(
                """
                SELECT
                    COALESCE(SUM(net_sales), 0) AS ventas_mes_actual,
                    COUNT(DISTINCT sales_date) AS dias_con_venta,
                    COALESCE(AVG(NULLIF(net_sales, 0)), 0) AS promedio_dia_con_venta
                FROM public.mv_internal_sales_daily
                WHERE sales_date BETWEEN :start_month AND :today
                  AND (:store_code IS NULL OR regexp_replace(COALESCE(serie, ''), '[^0-9]', '', 'g') = :store_code)
                """
            ),
            params,
        ).mappings().one()

        prev_start = (today.replace(day=1).replace(month=today.month - 1) if today.month > 1 else date(today.year - 1, 12, 1))
        prev_end = prev_start.replace(day=min(today.day, calendar.monthrange(prev_start.year, prev_start.month)[1]))
        prev_row = connection.execute(
            text(
                """
                SELECT COALESCE(SUM(net_sales), 0) AS ventas_mes_anterior_mismo_corte
                FROM public.mv_internal_sales_daily
                WHERE sales_date BETWEEN :prev_start AND :prev_end
                  AND (:store_code IS NULL OR regexp_replace(COALESCE(serie, ''), '[^0-9]', '', 'g') = :store_code)
                """
            ),
            {"prev_start": prev_start, "prev_end": prev_end, "store_code": store_code},
        ).mappings().one()

    ventas_mes = float(row.get("ventas_mes_actual") or 0)
    elapsed_days = max(today.day, 1)
    proyeccion = (ventas_mes / elapsed_days) * days_in_month if ventas_mes > 0 else 0
    ventas_prev = float(prev_row.get("ventas_mes_anterior_mismo_corte") or 0)
    variacion = ((ventas_mes - ventas_prev) / ventas_prev * 100.0) if ventas_prev > 0 else None
    return {
        "ventas_mes_actual": ventas_mes,
        "dias_transcurridos": today.day,
        "dias_mes": days_in_month,
        "proyeccion_cierre_mes": proyeccion,
        "promedio_dia_con_venta": float(row.get("promedio_dia_con_venta") or 0),
        "ventas_mes_anterior_mismo_corte": ventas_prev,
        "variacion_pct": round(variacion, 1) if variacion is not None else None,
    }


def _fetch_inventory_rows(engine, health_statuses: list[str], store_code: Optional[str], limit: int) -> list[dict]:
    with engine.begin() as connection:
        rows = connection.execute(
            text(
                """
                SELECT
                    cod_almacen,
                    almacen_nombre,
                    referencia,
                    descripcion,
                    stock_total,
                    historial_ventas_metric,
                    reorder_point,
                    reorder_qty_recommended,
                    inventory_value,
                    health_status
                FROM public.mv_internal_inventory_health
                WHERE health_status = ANY(:statuses)
                  AND (:store_code IS NULL OR cod_almacen = :store_code)
                ORDER BY inventory_value DESC, reorder_qty_recommended DESC, historial_ventas_metric ASC
                LIMIT :limit
                """
            ),
            {"statuses": health_statuses, "store_code": store_code, "limit": limit},
        ).mappings().all()
    return [dict(row) for row in rows]


def _fetch_cartera_rows(engine, limit: int) -> list[dict]:
    with engine.begin() as connection:
        rows = connection.execute(
            text(
                """
                SELECT
                    cod_cliente,
                    nombre_cliente,
                    nom_vendedor,
                    zona,
                    balance_total,
                    balance_31_60,
                    balance_61_90,
                    balance_91_plus,
                    max_dias_vencido
                FROM public.mv_internal_cartera_cliente
                WHERE (balance_31_60 + balance_61_90 + balance_91_plus) > 0
                ORDER BY balance_91_plus DESC, balance_61_90 DESC, balance_31_60 DESC
                LIMIT :limit
                """
            ),
            {"limit": limit},
        ).mappings().all()
    return [dict(row) for row in rows]


def _build_sales_projection_summary(projection: dict, store_code: Optional[str]) -> str:
    scope = f" para sede {store_code}" if store_code else ""
    variation_line = ""
    if projection.get("variacion_pct") is not None:
        variation_line = f" | variación vs corte mes anterior {projection['variacion_pct']}%"
    return (
        f"Proyección del mes{scope}: llevamos {_format_currency(projection.get('ventas_mes_actual'))} en {projection.get('dias_transcurridos')} días. "
        f"A este ritmo cerraríamos en {_format_currency(projection.get('proyeccion_cierre_mes'))}.{variation_line}"
    )


def _humanize_health_status(status: Any) -> str:
    mapping = {
        "sin_movimiento": "Sin movimiento",
        "sobrestock": "Sobrestock",
        "quiebre_critico": "Quiebre crítico",
        "reposicion_recomendada": "Reposición recomendada",
    }
    return mapping.get(str(status or "").strip(), str(status or "").replace("_", " ").strip().title())


def handle_consultar_indicadores_internos(engine, args: dict, conversation_context: Optional[dict]) -> str:
    internal_auth = dict((conversation_context or {}).get("internal_auth") or {})
    if not internal_auth.get("user_id"):
        return "No hay sesión interna válida para consultar indicadores."

    employee_context = internal_auth.get("employee_context") or {}
    store_code = _resolve_store_code(args.get("almacen") or employee_context.get("store_code"))
    query_type = _normalize_text(args.get("tipo_consulta") or "")
    limit = _clamp_limit(args.get("limite"), default=5, minimum=3, maximum=20)

    try:
        if query_type == "proyeccion_ventas_mes":
            projection = _fetch_sales_projection(engine, store_code)
            return _build_sales_projection_summary(projection, store_code)

        if query_type == "inventario_baja_rotacion":
            rows = _fetch_inventory_rows(engine, ["sin_movimiento", "sobrestock"], store_code, limit)
            if not rows:
                return "No encontré referencias quedadas o de baja rotación para ese filtro."
            lines = ["Resumen de baja rotación:"]
            for row in rows[: min(limit, 5)]:
                lines.append(
                    f"- {row.get('referencia')} | {row.get('descripcion')} | {row.get('almacen_nombre')} | stock {_format_number(row.get('stock_total'))} | valor {_format_currency(row.get('inventory_value'))}"
                )
            lines.append("Si quieres el detalle completo, te lo envío por correo con Excel.")
            return "\n".join(lines)

        if query_type == "cartera_vencida_resumen":
            rows = _fetch_cartera_rows(engine, limit)
            if not rows:
                return "No encontré clientes vencidos para ese corte."
            lines = ["Resumen de cartera vencida:"]
            for row in rows[: min(limit, 5)]:
                vencido = float(row.get("balance_31_60") or 0) + float(row.get("balance_61_90") or 0) + float(row.get("balance_91_plus") or 0)
                lines.append(
                    f"- {row.get('nombre_cliente')} | vencido {_format_currency(vencido)} | >90 {_format_currency(row.get('balance_91_plus'))} | vendedor {row.get('nom_vendedor') or 'N/A'}"
                )
            lines.append("Si quieres el detalle completo, te lo envío por correo con Excel.")
            return "\n".join(lines)

        if query_type == "quiebres_stock":
            rows = _fetch_inventory_rows(engine, ["quiebre_critico"], store_code, limit)
            if not rows:
                return "No encontré quiebres críticos para ese filtro."
            lines = ["Quiebres críticos detectados:"]
            for row in rows[: min(limit, 5)]:
                lines.append(
                    f"- {row.get('referencia')} | {row.get('descripcion')} | {row.get('almacen_nombre')} | stock {_format_number(row.get('stock_total'))} | sugerido {_format_number(row.get('reorder_qty_recommended'))}"
                )
            lines.append("Si quieres el detalle completo, te lo envío por correo con Excel.")
            return "\n".join(lines)

        if query_type == "sobrestock":
            rows = _fetch_inventory_rows(engine, ["sobrestock"], store_code, limit)
            if not rows:
                return "No encontré referencias en sobrestock para ese filtro."
            lines = ["Sobrestock detectado:"]
            for row in rows[: min(limit, 5)]:
                lines.append(
                    f"- {row.get('referencia')} | {row.get('descripcion')} | {row.get('almacen_nombre')} | stock {_format_number(row.get('stock_total'))} | valor {_format_currency(row.get('inventory_value'))}"
                )
            lines.append("Si quieres el detalle completo, te lo envío por correo con Excel.")
            return "\n".join(lines)
    except SQLAlchemyError as exc:
        logger.warning("consultar_indicadores_internos failed: %s", exc)
        return "No pude consultar los indicadores internos. Verifica que esté aplicado backend/internal_agent_ops.sql."

    return "No reconozco ese indicador interno. Usa proyección, baja rotación, cartera vencida, quiebres o sobrestock."


def _build_inventory_summary_metrics(rows: list[dict]) -> list[tuple[str, str]]:
    total_rows = len(rows)
    total_value = sum(float(row.get("inventory_value") or 0) for row in rows)
    total_stock = sum(float(row.get("stock_total") or 0) for row in rows)
    return [
        ("Referencias incluidas", _format_number(total_rows)),
        ("Unidades acumuladas", _format_number(total_stock)),
        ("Valor inventario", _format_currency(total_value)),
    ]


def _build_cartera_summary_metrics(rows: list[dict]) -> list[tuple[str, str]]:
    saldo_total = sum(float(row.get("balance_total") or 0) for row in rows)
    saldo_90 = sum(float(row.get("balance_91_plus") or 0) for row in rows)
    return [
        ("Clientes incluidos", _format_number(len(rows))),
        ("Saldo total", _format_currency(saldo_total)),
        ("Saldo >90 días", _format_currency(saldo_90)),
    ]


def _extract_sales_report_payload(report_type: str, args: dict, conversation_context: Optional[dict], sales_query_fn) -> dict:
    if sales_query_fn is None:
        raise ValueError("sales query function not available")

    report_to_desglose = {
        "ventas_detalladas": "total",
        "ventas_por_tienda": "por_tienda",
        "ventas_por_vendedor": "por_vendedor",
        "ventas_por_producto": "por_producto",
        "ventas_por_cliente": "por_cliente",
        "ventas_por_dia": "por_dia",
        "ventas_por_canal": "por_canal",
    }
    desglose = report_to_desglose.get(report_type)
    if not desglose:
        raise ValueError("sales report type not supported")

    raw_payload = sales_query_fn(
        {
            "periodo": args.get("periodo") or "este mes",
            "tienda": args.get("almacen"),
            "desglose": desglose,
            "canal": args.get("canal") or "empresa",
            "tipo_venta": args.get("tipo_venta") or "todos",
            "vendedor_codigo": args.get("vendedor_codigo"),
        },
        dict(conversation_context or {}),
    )
    return json.loads(raw_payload or "{}")


def _build_sales_report_dataset(report_type: str, payload: dict) -> tuple[str, list[tuple[str, str]], list[str], list[dict], list[str], str]:
    ventas = dict(payload.get("ventas") or {})
    metrics = [
        ("Periodo", str(payload.get("periodo") or "N/D")),
        ("Tienda", str(payload.get("tienda") or "Todas")),
        ("Canal", str(payload.get("canal") or "Todos")),
        ("Ventas netas", _format_currency(ventas.get("ventas_netas"))),
        ("Facturación bruta", _format_currency(ventas.get("facturas_bruto"))),
        ("Devoluciones", _format_currency(ventas.get("devoluciones_notas_credito"))),
        ("Clientes distintos", _format_number(ventas.get("num_clientes_distintos"))),
        ("Vendedores", _format_number(ventas.get("num_vendedores"))),
    ]
    vs_prev = payload.get("vs_anio_anterior") or {}
    if vs_prev:
        metrics.append(("Variación vs año anterior", _format_percent(vs_prev.get("variacion_pct"))))

    if report_type == "ventas_detalladas":
        title = "Reporte Ejecutivo de Ventas"
        headers = ["Indicador", "Valor"]
        rows = [{"indicador": label, "valor": value} for label, value in metrics]
        keys = ["indicador", "valor"]
        return title, metrics, headers, rows, keys, "Resumen ventas"

    mapping = {
        "ventas_por_tienda": (
            "Reporte de Ventas por Tienda",
            ["Tienda", "Facturado", "Devoluciones", "Neto", "Líneas", "Clientes", "Vendedores"],
            payload.get("desglose_tiendas") or [],
            ["tienda", "facturado", "devoluciones", "neto", "lineas", "clientes", "vendedores"],
            "Detalle tiendas",
        ),
        "ventas_por_vendedor": (
            "Reporte de Ventas por Vendedor",
            ["Vendedor", "Código", "Canal", "Facturado", "Devoluciones", "Neto", "Líneas", "Clientes"],
            payload.get("desglose_vendedores") or [],
            ["vendedor", "codigo", "canal", "facturado", "devoluciones", "neto", "lineas", "clientes"],
            "Detalle vendedores",
        ),
        "ventas_por_producto": (
            "Reporte de Ventas por Producto",
            ["Producto", "Línea", "Marca", "Total", "Unidades"],
            payload.get("top_productos") or [],
            ["producto", "linea", "marca", "total", "unidades"],
            "Detalle productos",
        ),
        "ventas_por_cliente": (
            "Reporte de Ventas por Cliente",
            ["Cliente", "Total"],
            payload.get("top_clientes") or [],
            ["cliente", "total"],
            "Detalle clientes",
        ),
        "ventas_por_dia": (
            "Reporte de Ventas por Día",
            ["Fecha", "Facturado", "Líneas"],
            payload.get("desglose_dias") or [],
            ["fecha", "facturado", "lineas"],
            "Detalle diario",
        ),
        "ventas_por_canal": (
            "Reporte de Ventas por Canal",
            ["Canal", "Facturado", "Devoluciones", "Neto", "Líneas", "Clientes", "Vendedores"],
            payload.get("desglose_canales") or [],
            ["canal", "facturado", "devoluciones", "neto", "lineas", "clientes", "vendedores"],
            "Detalle canales",
        ),
    }
    title, headers, rows, keys, detail_sheet = mapping[report_type]
    return title, metrics, headers, list(rows), keys, detail_sheet


def _report_rows_and_headers(report_type: str, engine, store_code: Optional[str], limit: int, conversation_context: Optional[dict], sales_query_fn=None) -> tuple[str, list[tuple[str, str]], list[str], list[dict], list[str], str]:
    if report_type == "inventario_baja_rotacion":
        rows = _fetch_inventory_rows(engine, ["sin_movimiento", "sobrestock"], store_code, limit)
        headers = ["Almacen", "Referencia", "Descripcion", "Estado", "Stock", "Historial ventas", "Valor inventario"]
        keys = ["almacen_nombre", "referencia", "descripcion", "health_status", "stock_total", "historial_ventas_metric", "inventory_value"]
        title = "Reporte de Baja Rotación y Sobrestock"
        for row in rows:
            row["health_status"] = _humanize_health_status(row.get("health_status"))
        metrics = _build_inventory_summary_metrics(rows)
        detail_sheet = "Detalle inventario"
    elif report_type == "cartera_vencida":
        rows = _fetch_cartera_rows(engine, limit)
        headers = ["Cliente", "Codigo", "Vendedor", "Zona", "31-60", "61-90", ">90", "Saldo total", "Max días vencido"]
        keys = ["nombre_cliente", "cod_cliente", "nom_vendedor", "zona", "balance_31_60", "balance_61_90", "balance_91_plus", "balance_total", "max_dias_vencido"]
        title = "Reporte de Cartera Vencida"
        metrics = _build_cartera_summary_metrics(rows)
        detail_sheet = "Detalle cartera"
    elif report_type == "quiebres_stock":
        rows = _fetch_inventory_rows(engine, ["quiebre_critico"], store_code, limit)
        headers = ["Almacen", "Referencia", "Descripcion", "Stock", "Punto de reposición", "Sugerido", "Valor inventario"]
        keys = ["almacen_nombre", "referencia", "descripcion", "stock_total", "reorder_point", "reorder_qty_recommended", "inventory_value"]
        title = "Reporte de Quiebres Críticos"
        metrics = _build_inventory_summary_metrics(rows)
        detail_sheet = "Detalle quiebres"
    elif report_type == "sobrestock":
        rows = _fetch_inventory_rows(engine, ["sobrestock"], store_code, limit)
        headers = ["Almacen", "Referencia", "Descripcion", "Stock", "Historial ventas", "Valor inventario"]
        keys = ["almacen_nombre", "referencia", "descripcion", "stock_total", "historial_ventas_metric", "inventory_value"]
        title = "Reporte de Sobrestock"
        metrics = _build_inventory_summary_metrics(rows)
        detail_sheet = "Detalle sobrestock"
    elif report_type in {
        "ventas_detalladas",
        "ventas_por_tienda",
        "ventas_por_vendedor",
        "ventas_por_producto",
        "ventas_por_cliente",
        "ventas_por_dia",
        "ventas_por_canal",
    }:
        sales_payload = _extract_sales_report_payload(report_type, conversation_context.get("pending_tool_args") or {}, conversation_context, sales_query_fn)
        title, metrics, headers, rows, keys, detail_sheet = _build_sales_report_dataset(report_type, sales_payload)
    else:
        raise ValueError("tipo de reporte no soportado")
    return title, metrics, headers, rows, keys, detail_sheet


def _autosize_sheet_columns(sheet):
    widths: dict[int, int] = {}
    for row in sheet.iter_rows():
        for cell in row:
            if cell.value is None:
                continue
            widths[cell.column] = max(widths.get(cell.column, 0), len(str(cell.value)))
    for col_idx, width in widths.items():
        sheet.column_dimensions[get_column_letter(col_idx)].width = min(max(width + 2, 12), 38)


def _style_summary_sheet(sheet, title: str, metrics: list[tuple[str, str]], subtitle_lines: list[str]):
    sheet.sheet_view.showGridLines = False
    sheet.merge_cells("A1:D1")
    hero = sheet["A1"]
    hero.value = title
    hero.fill = _XL_DARK_FILL
    hero.font = Font(color="FFFFFF", size=18, bold=True)
    hero.alignment = Alignment(horizontal="left", vertical="center")
    sheet.row_dimensions[1].height = 28

    row_idx = 3
    for line in subtitle_lines:
        sheet.merge_cells(start_row=row_idx, start_column=1, end_row=row_idx, end_column=4)
        cell = sheet.cell(row=row_idx, column=1, value=line)
        cell.font = Font(color="374151", size=11)
        cell.alignment = Alignment(wrap_text=True)
        row_idx += 1

    row_idx += 1
    for label, value in metrics:
        label_cell = sheet.cell(row=row_idx, column=1, value=label)
        value_cell = sheet.cell(row=row_idx, column=2, value=value)
        label_cell.fill = _XL_LIGHT_FILL
        value_cell.fill = _XL_LIGHT_FILL
        label_cell.font = Font(bold=True, color="111827")
        value_cell.font = Font(color="111827")
        label_cell.border = _XL_BORDER
        value_cell.border = _XL_BORDER
        row_idx += 1
    sheet.freeze_panes = "A3"
    _autosize_sheet_columns(sheet)


def _infer_number_format(key: str) -> Optional[str]:
    lowered = str(key or "").lower()
    if any(token in lowered for token in ["valor", "saldo", "neto", "facturado", "devoluciones", "total", "precio", "ventas"]):
        return '$#,##0'
    if "variacion" in lowered:
        return '0.0%'
    if any(token in lowered for token in ["stock", "unidades", "lineas", "clientes", "vendedores", "dias", "sugerido", "punto"]):
        return '#,##0'
    return None


def _style_detail_sheet(sheet, headers: list[str], keys: list[str], rows: list[dict]):
    sheet.sheet_view.showGridLines = False
    sheet.freeze_panes = "A2"
    for cell in sheet[1]:
        cell.fill = _XL_DARK_FILL
        cell.font = Font(color="FFFFFF", bold=True)
        cell.alignment = Alignment(horizontal="center", vertical="center")
        cell.border = _XL_BORDER

    for row_index, row in enumerate(rows, start=2):
        fill = _XL_LIGHT_FILL if row_index % 2 == 0 else None
        for col_index, key in enumerate(keys, start=1):
            cell = sheet.cell(row=row_index, column=col_index)
            cell.alignment = Alignment(vertical="top", wrap_text=True)
            cell.border = _XL_BORDER
            if fill:
                cell.fill = fill
            number_format = _infer_number_format(key)
            if number_format and isinstance(cell.value, (int, float)):
                if number_format == '0.0%' and abs(float(cell.value or 0)) > 1:
                    cell.value = float(cell.value) / 100.0
                cell.number_format = number_format

    sheet.auto_filter.ref = f"A1:{get_column_letter(len(headers))}{max(len(rows) + 1, 2)}"
    _autosize_sheet_columns(sheet)


def _build_excel_attachment(title: str, metrics: list[tuple[str, str]], headers: list[str], rows: list[dict], keys: list[str], detail_sheet_name: str, subtitle_lines: list[str]) -> tuple[str, bytes]:
    workbook = Workbook()
    summary_sheet = workbook.active
    summary_sheet.title = "Resumen"
    _style_summary_sheet(summary_sheet, title, metrics, subtitle_lines)

    sheet = workbook.create_sheet(detail_sheet_name[:31])
    sheet.append(headers)
    for row in rows:
        values = [row.get(key) for key in keys]
        sheet.append(values)
    _style_detail_sheet(sheet, headers, keys, rows)
    buffer = io.BytesIO()
    workbook.save(buffer)
    buffer.seek(0)
    filename = f"{re.sub(r'[^a-z0-9]+', '_', title.lower()).strip('_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    return filename, buffer.getvalue()


def _build_html_preview_rows(headers: list[str], rows: list[dict], keys: list[str]) -> str:
    preview_rows = rows[:5]
    if not preview_rows:
        return ""
    header_html = "".join(f"<th style='padding:10px 12px;text-align:left;border-bottom:1px solid #e5e7eb;'>{escape(str(header))}</th>" for header in headers)
    body_html = []
    for row in preview_rows:
        cols = []
        for key in keys:
            value = row.get(key)
            if isinstance(value, float):
                value = round(value, 2)
            cols.append(f"<td style='padding:10px 12px;border-bottom:1px solid #f3f4f6;'>{escape(str(value if value is not None else ''))}</td>")
        body_html.append(f"<tr>{''.join(cols)}</tr>")
    return (
        "<table style='width:100%;border-collapse:collapse;background:#ffffff;border:1px solid #e5e7eb;border-radius:12px;overflow:hidden;'>"
        f"<thead><tr style='background:#111827;color:#ffffff;'>{header_html}</tr></thead>"
        f"<tbody>{''.join(body_html)}</tbody></table>"
    )


def handle_enviar_reporte_interno_correo(engine, args: dict, conversation_context: Optional[dict], build_brand_email_shell_fn, send_email_fn, sales_query_fn=None) -> str:
    internal_auth = dict((conversation_context or {}).get("internal_auth") or {})
    if not internal_auth.get("user_id"):
        return "No hay sesión interna válida para enviar reportes por correo."

    report_type = _normalize_text(args.get("tipo_reporte") or "")
    employee_context = internal_auth.get("employee_context") or {}
    destination_email = str(args.get("email_destino") or internal_auth.get("email") or "").strip().lower()
    if not _is_valid_email(destination_email):
        return "No tengo un correo destino válido. Pídele al colaborador el correo y luego reintenta el envío."
    store_code = _resolve_store_code(args.get("almacen") or employee_context.get("store_code"))
    limit = _clamp_limit(args.get("limite"), default=100, minimum=10, maximum=500)
    context_with_args = dict(conversation_context or {})
    context_with_args["pending_tool_args"] = dict(args or {})

    try:
        title, metrics, headers, rows, keys, detail_sheet_name = _report_rows_and_headers(
            report_type,
            engine,
            store_code,
            limit,
            context_with_args,
            sales_query_fn=sales_query_fn,
        )
    except ValueError:
        return "No reconozco ese tipo de reporte interno para correo."
    except SQLAlchemyError as exc:
        logger.warning("email report query failed: %s", exc)
        return "No pude armar el reporte interno. Verifica que esté aplicado backend/internal_agent_ops.sql."

    if not rows:
        return "No encontré datos para ese reporte."

    subtitle_lines = [
        f"Generado: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"Sede consultada: {requested_by.get('sede') if (requested_by := internal_auth.get('employee_context') or {}).get('sede') else store_code or 'Consolidado'}",
        f"Filas incluidas en detalle: {len(rows)}",
    ]
    attachment_name, attachment_bytes = _build_excel_attachment(title, metrics, headers, rows, keys, detail_sheet_name, subtitle_lines)
    requested_by = internal_auth.get("employee_context") or {}
    preview_table = _build_html_preview_rows(headers, rows, keys)
    metrics_html = "".join(
        f"<tr><td style='padding:10px 12px;border-bottom:1px solid #f3f4f6;font-weight:600;color:#111827;'>{escape(label)}</td>"
        f"<td style='padding:10px 12px;border-bottom:1px solid #f3f4f6;color:#111827;'>{escape(value)}</td></tr>"
        for label, value in metrics[:8]
    )
    body_html = (
        "<p style='margin:0 0 14px 0;font-size:15px;'>Se generó un reporte interno solicitado desde WhatsApp.</p>"
        + "<div style='background:#ffffff;border:1px solid #e5e7eb;border-radius:14px;padding:18px 20px;margin-bottom:18px;'>"
        + f"<p style='margin:0 0 8px 0;'><strong>Solicitante:</strong> {escape(str(requested_by.get('full_name') or internal_auth.get('username') or 'Colaborador Ferreinox'))}</p>"
        + f"<p style='margin:0 0 8px 0;'><strong>Cargo:</strong> {escape(str(requested_by.get('cargo') or internal_auth.get('role') or 'Perfil interno'))}</p>"
        + f"<p style='margin:0 0 8px 0;'><strong>Sede:</strong> {escape(str(requested_by.get('sede') or store_code or 'Consolidado'))}</p>"
        + f"<p style='margin:0;'><strong>Filas incluidas:</strong> {len(rows)}</p>"
        + "</div>"
        + "<div style='background:#ffffff;border:1px solid #e5e7eb;border-radius:14px;padding:0;margin-bottom:18px;overflow:hidden;'>"
        + "<div style='background:#f59e0b;color:#111827;padding:12px 16px;font-weight:700;'>Resumen ejecutivo</div>"
        + f"<table style='width:100%;border-collapse:collapse;'>{metrics_html}</table>"
        + "</div>"
        + (preview_table if preview_table else "")
        + "<p style='margin:18px 0 14px 0;'>Adjunto encontrarás el Excel con portada ejecutiva, resumen y detalle estructurado del reporte.</p>"
    )
    html_content = build_brand_email_shell_fn(title, body_html)
    text_content = (
        f"{title}\n"
        f"Solicitante: {requested_by.get('full_name') or internal_auth.get('username') or 'Colaborador Ferreinox'}\n"
        f"Cargo: {requested_by.get('cargo') or internal_auth.get('role') or 'Perfil interno'}\n"
        f"Sede: {requested_by.get('sede') or store_code or 'Consolidado'}\n"
        f"Filas incluidas: {len(rows)}\n"
        + "\n".join(f"{label}: {value}" for label, value in metrics[:6])
        + "\nSe adjunta Excel con resumen ejecutivo y detalle completo."
    )

    try:
        send_email_fn(
            destination_email,
            title,
            html_content,
            text_content,
            attachments=[
                {
                    "content": base64.b64encode(attachment_bytes).decode("ascii"),
                    "filename": attachment_name,
                    "type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    "disposition": "attachment",
                }
            ],
        )
    except Exception as exc:
        logger.warning("send internal report email failed: %s", exc)
        return f"No pude enviar el correo a {destination_email}."

    return f"Reporte enviado a {destination_email} con adjunto {attachment_name}."


def _log_action(engine, internal_auth: Optional[dict], role_key: str, tool_name: str, status: str, summary: str, payload: dict):
    if not engine:
        return
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO public.agent_internal_action_log (
                        user_id, role_key, tool_name, action_status, action_summary, payload
                    ) VALUES (
                        :user_id, :role_key, :tool_name, :action_status, :action_summary, CAST(:payload AS jsonb)
                    )
                    """
                ),
                {
                    "user_id": (internal_auth or {}).get("user_id"),
                    "role_key": role_key,
                    "tool_name": tool_name,
                    "action_status": status,
                    "action_summary": summary,
                    "payload": json.dumps(payload or {}, ensure_ascii=False, default=str),
                },
            )
    except SQLAlchemyError as exc:
        logger.debug("action log skipped for %s: %s", tool_name, exc)


def handle_crear_recordatorio_interno(engine, args: dict, conversation_context: Optional[dict]) -> str:
    internal_auth = dict((conversation_context or {}).get("internal_auth") or {})
    if not internal_auth.get("user_id"):
        return "No hay sesion interna valida para crear recordatorios."

    title = str(args.get("titulo") or "").strip()
    if not title:
        return "Falta el titulo del recordatorio interno."

    role_profile = _fetch_role_profile(engine, internal_auth)
    role_key = str(args.get("role_profile_key") or role_profile.get("role_key") or "empleado_operativo").strip()
    priority = _normalize_text(args.get("prioridad") or "media")
    if priority not in {"alta", "media", "baja"}:
        priority = "media"
    due_at = str(args.get("fecha_hora") or "").strip() or None
    detail = str(args.get("detalle") or "").strip() or None

    try:
        with engine.begin() as connection:
            reminder_id = connection.execute(
                text(
                    """
                    INSERT INTO public.agent_internal_reminder (
                        owner_user_id, role_key, title, detail, due_at, priority, status, metadata
                    ) VALUES (
                        :owner_user_id,
                        :role_key,
                        :title,
                        :detail,
                        CASE WHEN :due_at IS NULL OR :due_at = '' THEN NULL ELSE CAST(:due_at AS timestamptz) END,
                        :priority,
                        'pendiente',
                        CAST(:metadata AS jsonb)
                    )
                    RETURNING id
                    """
                ),
                {
                    "owner_user_id": internal_auth.get("user_id"),
                    "role_key": role_key,
                    "title": title,
                    "detail": detail,
                    "due_at": due_at,
                    "priority": priority,
                    "metadata": "{}",
                },
            ).scalar_one()
        _log_action(engine, internal_auth, role_key, "crear_recordatorio_interno", "ok", f"Recordatorio #{reminder_id}: {title}", args)
        due_note = f" | vence {due_at}" if due_at else ""
        return f"Recordatorio interno creado: #{reminder_id} | {title} [{priority}]{due_note}"
    except SQLAlchemyError as exc:
        logger.warning("crear_recordatorio_interno failed: %s", exc)
        return "No pude crear el recordatorio. Verifica que este aplicado backend/internal_agent_ops.sql y que la fecha tenga formato ISO."


def handle_generar_lista_pendientes(engine, args: dict, conversation_context: Optional[dict]) -> str:
    internal_auth = dict((conversation_context or {}).get("internal_auth") or {})
    role_profile = _fetch_role_profile(engine, internal_auth)
    scope = _normalize_text(args.get("alcance") or "mixto")
    if scope not in {"personal", "equipo", "mixto"}:
        scope = "mixto"
    try:
        limit = int(args.get("limite") or 8)
    except (TypeError, ValueError):
        limit = 8
    limit = max(1, min(limit, 20))

    if not engine:
        return "No hay acceso a la base para listar pendientes."

    try:
        with engine.begin() as connection:
            rows = connection.execute(
                text(
                    """
                    SELECT item_type, item_id, title, summary, due_at, priority, owner_user_id, role_key
                    FROM public.vw_internal_pending_queue
                    WHERE (
                        :scope = 'personal' AND owner_user_id = :user_id
                    ) OR (
                        :scope = 'equipo' AND role_key = :role_key
                    ) OR (
                        :scope = 'mixto' AND (owner_user_id = :user_id OR role_key = :role_key)
                    )
                    ORDER BY priority_rank ASC, due_at NULLS LAST, created_at DESC
                    LIMIT :limit
                    """
                ),
                {
                    "scope": scope,
                    "user_id": internal_auth.get("user_id"),
                    "role_key": role_profile.get("role_key") or "empleado_operativo",
                    "limit": limit,
                },
            ).mappings().all()
    except SQLAlchemyError as exc:
        logger.warning("generar_lista_pendientes failed: %s", exc)
        return "No pude consultar la lista de pendientes. Verifica que este aplicado backend/internal_agent_ops.sql."

    if not rows:
        _log_action(engine, internal_auth, role_profile.get("role_key") or "empleado_operativo", "generar_lista_pendientes", "ok", "Sin pendientes", args)
        return "No hay pendientes abiertos para ese alcance."

    lines = [f"Pendientes ({scope}):"]
    for row in rows:
        due_at = row.get("due_at")
        due_note = f" | vence {due_at:%Y-%m-%d %H:%M}" if due_at else ""
        lines.append(
            f"- {row.get('title')} [{row.get('priority')}] ({row.get('item_type')}){due_note}"
        )
    _log_action(
        engine,
        internal_auth,
        role_profile.get("role_key") or "empleado_operativo",
        "generar_lista_pendientes",
        "ok",
        f"{len(rows)} pendientes listados",
        args,
    )
    return "\n".join(lines)


def handle_sugerir_reposicion_bodega(engine, args: dict, conversation_context: Optional[dict]) -> str:
    internal_auth = dict((conversation_context or {}).get("internal_auth") or {})
    role_profile = _fetch_role_profile(engine, internal_auth)
    employee_context = internal_auth.get("employee_context") or {}
    store_code = re.sub(r"\D", "", str(args.get("almacen") or employee_context.get("store_code") or "")).strip() or None
    health_status = _normalize_text(args.get("estado") or "reposicion_recomendada")
    if health_status not in {"quiebre_critico", "reposicion_recomendada", "sobrestock", "sin_movimiento"}:
        health_status = "reposicion_recomendada"
    try:
        limit = int(args.get("limite") or 10)
    except (TypeError, ValueError):
        limit = 10
    limit = max(1, min(limit, 20))

    if not engine:
        return "No hay acceso a la base para sugerir reposicion."

    try:
        with engine.begin() as connection:
            rows = connection.execute(
                text(
                    """
                    SELECT
                        cod_almacen,
                        almacen_nombre,
                        referencia,
                        descripcion,
                        stock_total,
                        historial_ventas_metric,
                        reorder_point,
                        reorder_qty_recommended,
                        inventory_value,
                        health_status
                    FROM public.mv_internal_inventory_health
                    WHERE health_status = :health_status
                      AND (:store_code IS NULL OR cod_almacen = :store_code)
                    ORDER BY reorder_qty_recommended DESC, historial_ventas_metric DESC, stock_total ASC
                    LIMIT :limit
                    """
                ),
                {"health_status": health_status, "store_code": store_code, "limit": limit},
            ).mappings().all()
    except SQLAlchemyError as exc:
        logger.warning("sugerir_reposicion_bodega failed: %s", exc)
        return "No pude calcular reposicion. Verifica que este aplicado backend/internal_agent_ops.sql."

    if not rows:
        return "No encontré referencias para ese criterio de reposición."

    title = f"Sugerencias de {health_status}"
    if store_code:
        title += f" para almacen {store_code}"
    lines = [title + ":"]
    for row in rows:
        qty = _format_number(row.get("reorder_qty_recommended"))
        stock = _format_number(row.get("stock_total"))
        demand = _format_number(row.get("historial_ventas_metric"))
        lines.append(
            f"- {row.get('referencia')} | {row.get('descripcion')} | stock {stock} | hist {demand} | sugerido {qty}"
        )

    _log_action(
        engine,
        internal_auth,
        role_profile.get("role_key") or "empleado_operativo",
        "sugerir_reposicion_bodega",
        "ok",
        f"{len(rows)} referencias sugeridas",
        args,
    )
    return "\n".join(lines)