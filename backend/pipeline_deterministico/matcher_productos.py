"""
Módulo 2: Matcher Híbrido de Productos — FUENTE DE VERDAD del inventario

Estrategia de búsqueda en 3 niveles:
  1. Búsqueda Semántica (pgvector) — similitud vectorial con embeddings
  2. Full-Text Search (PostgreSQL ts_vector) — match por tokens lingüísticos
  3. Fuzzy local (fallback) — difflib SequenceMatcher si los 2 anteriores fallan

El catálogo ERP usa abreviaciones (PQ VINILTEX BYC SA = Viniltex Baños y Cocinas).
El matcher normaliza ambos lados y resuelve sinónimos industriales.

Regla fundamental:
  - Si no hay match → ERROR, no cotizar.
  - El LLM NUNCA define SKU, precio ni referencia.
  - Solo este módulo genera los datos reales de la cotización.
"""
import json
import logging
import re
import unicodedata
from difflib import SequenceMatcher
from typing import Optional, Callable

logger = logging.getLogger("pipeline.matcher_productos")

# ══════════════════════════════════════════════════════════════════════════════
# CONFIGURACIÓN
# ══════════════════════════════════════════════════════════════════════════════

# Umbral mínimo de similitud para fuzzy matching controlado
UMBRAL_MATCH_EXACTO = 0.85
UMBRAL_MATCH_FUZZY = 0.65
# Máximo de resultados por producto a evaluar
MAX_CANDIDATOS = 10

# Mapeo de presentaciones normalizadas → patrones ERP
PRESENTACION_MAP = {
    "galon": ["galon", "gl", "gal", "3.79l", "3.79 l", "1 gl"],
    "cunete": ["cunete", "cuñete", "cun", "5 gl", "5gl", "18.93l", "20l"],
    "cuarto": ["cuarto", "1/4", "qt", "0.946l", "946ml"],
    "litro": ["litro", "lt", "1l", "1 l"],
    "unidad": ["unidad", "und", "un", "pza"],
    "kit": ["kit", "juego", "set"],
}

# ══════════════════════════════════════════════════════════════════════════════
# SINÓNIMOS ERP — El catálogo usa abreviaciones industriales
# ══════════════════════════════════════════════════════════════════════════════

# Mapeo: nombre comercial genérico → abreviaciones del ERP Ferreinox
SINONIMOS_ERP = {
    "baños y cocinas": ["byc", "b&c", "banos y cocinas", "banos cocinas"],
    "viniltex": ["viniltex", "pq viniltex"],
    "koraza": ["koraza", "pq koraza"],
    "intervinil": ["intervinil", "pq intervinil"],
    "aquablock": ["aquablock", "pq aquablock"],
    "estuco acrilico": ["estuco prof", "estuco acrilico", "estuco acrili"],
    "pintulux": ["pintulux", "pq pintulux"],
    "galon": ["3.79l", "3.79 l", "1gl", "gl", "galon"],
    "cunete": ["18.93l", "18.93 l", "5gl", "cunete", "cuñete"],
    "cuarto": ["0.946l", "946ml", "1/4 gl", "cuarto"],
    "blanco": ["blanco", "bco", "sa blanco"],
    "gris": ["gris"],
    "profesional": ["prof"],
    "exterior": ["ext"],
    "interior": ["int"],
    "advanced": ["advanced", "adv"],
    "ultra": ["ultra"],
    "anticorrosivo": ["anticor", "antic"],
    "epoxico": ["epox", "epoxico"],
    "poliuretano": ["pu", "poliuretano"],
}


def expandir_sinonimos_erp(texto: str) -> str:
    """Expande un nombre genérico con sinónimos del ERP para mejor búsqueda."""
    texto_lower = texto.lower()
    expansiones = [texto_lower]
    for nombre_generico, alias_erp in SINONIMOS_ERP.items():
        if nombre_generico in texto_lower:
            for alias in alias_erp:
                if alias not in texto_lower:
                    expansiones.append(alias)
    return " ".join(expansiones)


# ══════════════════════════════════════════════════════════════════════════════
# BÚSQUEDA HÍBRIDA PostgreSQL (Semántica + Full-Text)
# ══════════════════════════════════════════════════════════════════════════════

async def search_hybrid_pg(
    query: str,
    pg_pool,
    tabla: str = "agent_inventario",
    embedding_fn: Optional[Callable] = None,
    top_k: int = 15,
) -> list[dict]:
    """
    Búsqueda híbrida: combina pgvector (semántica) + FTS (full-text) + ILIKE (fuzzy).

    Flujo:
      1. Si hay embedding_fn → buscar por similitud vectorial (cosine)
      2. Full-text search con to_tsvector/to_tsquery (español)
      3. Fallback ILIKE por tokens
      4. Fusionar resultados con RRF (Reciprocal Rank Fusion)

    Args:
        query: Texto de búsqueda (nombre genérico del producto)
        pg_pool: asyncpg pool o connection
        tabla: Tabla de inventario
        embedding_fn: Función async que genera embedding (ej. OpenAI)
        top_k: Máximo resultados

    Returns:
        Lista de dicts con campos del inventario + score_hibrido
    """
    resultados_semantic = []
    resultados_fts = []
    resultados_ilike = []

    query_expandido = expandir_sinonimos_erp(query)
    tokens = [t for t in query_expandido.split() if len(t) > 2]

    # ── 1. Búsqueda semántica con pgvector ──
    if embedding_fn and pg_pool:
        try:
            embedding = await embedding_fn(query)
            sql_semantic = f"""
                SELECT *, 1 - (embedding <=> $1::vector) as score_semantic
                FROM {tabla}
                WHERE embedding IS NOT NULL
                ORDER BY embedding <=> $1::vector
                LIMIT $2
            """
            rows = await pg_pool.fetch(sql_semantic, str(embedding), top_k)
            resultados_semantic = [dict(r) for r in rows]
        except Exception as e:
            logger.warning("HYBRID: Búsqueda semántica falló: %s", e)

    # ── 2. Full-Text Search con ts_vector ──
    if pg_pool and tokens:
        try:
            # Construir tsquery: combinar tokens con OR para tolerancia
            tsquery_parts = " | ".join(tokens[:6])
            sql_fts = f"""
                SELECT *,
                    ts_rank_cd(
                        to_tsvector('spanish', COALESCE(descripcion,'') || ' ' || COALESCE(descripcion_comercial,'')),
                        to_tsquery('spanish', $1)
                    ) as score_fts
                FROM {tabla}
                WHERE to_tsvector('spanish', COALESCE(descripcion,'') || ' ' || COALESCE(descripcion_comercial,''))
                    @@ to_tsquery('spanish', $1)
                ORDER BY score_fts DESC
                LIMIT $2
            """
            rows = await pg_pool.fetch(sql_fts, tsquery_parts, top_k)
            resultados_fts = [dict(r) for r in rows]
        except Exception as e:
            logger.warning("HYBRID: Full-text search falló: %s", e)

    # ── 3. Fallback ILIKE por tokens ──
    if pg_pool and tokens and not resultados_semantic and not resultados_fts:
        try:
            conditions = " AND ".join(
                f"(LOWER(descripcion) LIKE '%' || ${i+1} || '%' OR LOWER(descripcion_comercial) LIKE '%' || ${i+1} || '%')"
                for i, _ in enumerate(tokens[:4])
            )
            sql_ilike = f"""
                SELECT * FROM {tabla}
                WHERE {conditions}
                LIMIT ${{len(tokens[:4]) + 1}}
            """
            # Ejecutar con parámetros dinámicos
            params = [t.lower() for t in tokens[:4]] + [top_k]
            rows = await pg_pool.fetch(sql_ilike, *params)
            resultados_ilike = [dict(r) for r in rows]
        except Exception as e:
            logger.warning("HYBRID: ILIKE search falló: %s", e)

    # ── 4. Fusión RRF (Reciprocal Rank Fusion) ──
    return _fusionar_rrf(resultados_semantic, resultados_fts, resultados_ilike, top_k)


def _fusionar_rrf(
    semantic: list[dict],
    fts: list[dict],
    ilike: list[dict],
    top_k: int,
    k: int = 60,
    w_semantic: float = 0.5,
    w_fts: float = 0.35,
    w_ilike: float = 0.15,
) -> list[dict]:
    """
    Reciprocal Rank Fusion: combina rankings de múltiples fuentes.
    score_rrf = sum(weight_i / (k + rank_i)) para cada fuente.
    """
    scores: dict[str, float] = {}
    items: dict[str, dict] = {}

    def _add_results(resultados: list[dict], weight: float):
        for rank, item in enumerate(resultados):
            key = item.get("codigo_articulo") or item.get("referencia") or str(rank)
            rrf_score = weight / (k + rank + 1)
            scores[key] = scores.get(key, 0.0) + rrf_score
            if key not in items:
                items[key] = item

    _add_results(semantic, w_semantic)
    _add_results(fts, w_fts)
    _add_results(ilike, w_ilike)

    # Ordenar por score compuesto y retornar
    sorted_keys = sorted(scores.keys(), key=lambda x: scores[x], reverse=True)[:top_k]
    resultado = []
    for key in sorted_keys:
        item = dict(items[key])
        item["_score_hibrido"] = round(scores[key], 6)
        resultado.append(item)

    return resultado


# ══════════════════════════════════════════════════════════════════════════════
# NORMALIZACIÓN
# ══════════════════════════════════════════════════════════════════════════════

def normalizar_texto(texto: str) -> str:
    """Normaliza texto para comparación: lowercase, sin acentos, sin caracteres especiales."""
    if not texto:
        return ""
    texto = texto.lower().strip()
    # Remover acentos
    texto = unicodedata.normalize("NFD", texto)
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    # Remover caracteres especiales excepto espacios y números
    texto = re.sub(r"[^\w\s]", " ", texto)
    # Colapsar espacios
    texto = re.sub(r"\s+", " ", texto).strip()
    return texto


def extraer_palabras_clave(nombre_producto: str) -> list[str]:
    """Extrae las palabras significativas de un nombre de producto."""
    normalizado = normalizar_texto(nombre_producto)
    # Palabras insignificantes para matching
    stopwords = {
        "de", "del", "la", "el", "los", "las", "para", "con", "en",
        "por", "una", "un", "y", "o", "a", "al",
    }
    palabras = [p for p in normalizado.split() if p not in stopwords and len(p) > 1]
    return palabras


# ══════════════════════════════════════════════════════════════════════════════
# RESULTADO DEL MATCH
# ══════════════════════════════════════════════════════════════════════════════

class ResultadoMatch:
    """Resultado de un intento de match contra inventario."""

    def __init__(
        self,
        exito: bool,
        producto_solicitado: str,
        presentacion_solicitada: str,
        cantidad: int,
        funcion: str = "",
        # Campos resueltos (solo si exito=True)
        codigo: str = "",
        descripcion_real: str = "",
        marca: str = "",
        presentacion_real: str = "",
        precio_unitario: float = 0.0,
        disponible: bool = False,
        score_match: float = 0.0,
        tipo_match: str = "",  # "exacto", "fuzzy", "no_encontrado"
        error: str = "",
        candidatos_cercanos: Optional[list] = None,
    ):
        self.exito = exito
        self.producto_solicitado = producto_solicitado
        self.presentacion_solicitada = presentacion_solicitada
        self.cantidad = cantidad
        self.funcion = funcion
        self.codigo = codigo
        self.descripcion_real = descripcion_real
        self.marca = marca
        self.presentacion_real = presentacion_real
        self.precio_unitario = precio_unitario
        self.disponible = disponible
        self.score_match = score_match
        self.tipo_match = tipo_match
        self.error = error
        self.candidatos_cercanos = candidatos_cercanos or []

    def to_dict(self) -> dict:
        d = {
            "exito": self.exito,
            "producto_solicitado": self.producto_solicitado,
            "presentacion_solicitada": self.presentacion_solicitada,
            "cantidad": self.cantidad,
            "funcion": self.funcion,
            "tipo_match": self.tipo_match,
            "score_match": round(self.score_match, 3),
        }
        if self.exito:
            d.update({
                "codigo": self.codigo,
                "descripcion_real": self.descripcion_real,
                "marca": self.marca,
                "presentacion_real": self.presentacion_real,
                "precio_unitario": self.precio_unitario,
                "disponible": self.disponible,
            })
        else:
            d["error"] = self.error
            if self.candidatos_cercanos:
                d["candidatos_cercanos"] = self.candidatos_cercanos[:3]
        return d


# ══════════════════════════════════════════════════════════════════════════════
# MATCHER PRINCIPAL
# ══════════════════════════════════════════════════════════════════════════════

def match_producto_contra_inventario(
    producto_nombre: str,
    presentacion: str,
    cantidad: int,
    funcion: str,
    lookup_fn,
    price_fn=None,
    color: str = "",
) -> ResultadoMatch:
    """
    Resuelve un nombre genérico de producto contra el inventario real.

    Args:
        producto_nombre: Nombre del producto del JSON del LLM
        presentacion: Presentación solicitada (galon, cunete, etc.)
        cantidad: Cantidad solicitada
        funcion: Función en el sistema (preparacion, acabado, etc.)
        lookup_fn: Función que recibe un string de búsqueda y retorna
                   lista de dicts con campos del inventario
        price_fn: Función que recibe codigo_articulo y retorna precio
        color: Color solicitado (opcional)

    Returns:
        ResultadoMatch con el resultado del matching
    """
    logger.info(
        "MATCH: Buscando '%s' | presentacion=%s | cantidad=%d | color=%s",
        producto_nombre, presentacion, cantidad, color,
    )

    # ── Paso 1: Buscar en inventario ──
    texto_busqueda = _construir_texto_busqueda(producto_nombre, presentacion, color)
    candidatos = _buscar_candidatos(texto_busqueda, lookup_fn)

    if not candidatos:
        # Reintentar con nombre base sin color ni presentación
        candidatos = _buscar_candidatos(producto_nombre, lookup_fn)

    if not candidatos:
        logger.warning("MATCH: SIN RESULTADOS para '%s'", producto_nombre)
        return ResultadoMatch(
            exito=False,
            producto_solicitado=producto_nombre,
            presentacion_solicitada=presentacion,
            cantidad=cantidad,
            funcion=funcion,
            tipo_match="no_encontrado",
            error=f"Producto '{producto_nombre}' no encontrado en inventario",
        )

    # ── Paso 2: Scoring de candidatos ──
    scored = []
    for candidato in candidatos[:MAX_CANDIDATOS]:
        score = _calcular_score(
            producto_nombre, presentacion, color, candidato
        )
        scored.append((score, candidato))

    scored.sort(key=lambda x: x[0], reverse=True)
    best_score, best_match = scored[0]

    logger.info(
        "MATCH: Mejor candidato score=%.3f | '%s' → '%s'",
        best_score,
        producto_nombre,
        best_match.get("descripcion", "?")[:80],
    )

    # ── Paso 3: Evaluar calidad del match ──
    if best_score >= UMBRAL_MATCH_EXACTO:
        tipo = "exacto"
    elif best_score >= UMBRAL_MATCH_FUZZY:
        tipo = "fuzzy"
    else:
        # Score demasiado bajo → no es match confiable
        cercanos = [
            {
                "descripcion": c.get("descripcion", "")[:80],
                "codigo": c.get("codigo_articulo", ""),
                "score": round(s, 3),
            }
            for s, c in scored[:3]
        ]
        logger.warning(
            "MATCH: Score %.3f bajo umbral %.2f para '%s'",
            best_score, UMBRAL_MATCH_FUZZY, producto_nombre,
        )
        return ResultadoMatch(
            exito=False,
            producto_solicitado=producto_nombre,
            presentacion_solicitada=presentacion,
            cantidad=cantidad,
            funcion=funcion,
            tipo_match="bajo_umbral",
            score_match=best_score,
            error=(
                f"No se encontró match confiable para '{producto_nombre}'. "
                f"Mejor score: {best_score:.3f} (umbral: {UMBRAL_MATCH_FUZZY})"
            ),
            candidatos_cercanos=cercanos,
        )

    # ── Paso 4: Validar presentación ──
    presentacion_real = _extraer_presentacion_real(best_match)
    if presentacion and not _presentacion_compatible(presentacion, presentacion_real):
        # Buscar mismo producto con presentación correcta
        alternativa = _buscar_con_presentacion(
            producto_nombre, presentacion, scored, candidatos
        )
        if alternativa:
            best_match = alternativa[1]
            best_score = alternativa[0]
            presentacion_real = _extraer_presentacion_real(best_match)
            tipo = "exacto" if best_score >= UMBRAL_MATCH_EXACTO else "fuzzy"
        else:
            logger.warning(
                "MATCH: Presentación '%s' no encontrada para '%s'. Real: '%s'",
                presentacion, producto_nombre, presentacion_real,
            )

    # ── Paso 5: Obtener precio ──
    precio = 0.0
    codigo = best_match.get("codigo_articulo") or best_match.get("referencia") or ""
    if price_fn and codigo:
        try:
            price_info = price_fn(str(codigo))
            if price_info and isinstance(price_info, dict):
                precio = float(price_info.get("precio_mejor", 0) or 0)
        except Exception as e:
            logger.warning("MATCH: Error obteniendo precio para %s: %s", codigo, e)

    if not precio:
        precio = float(best_match.get("precio_venta", 0) or 0)

    # ── Paso 6: Construir resultado ──
    stock = float(best_match.get("stock_total", 0) or 0)

    return ResultadoMatch(
        exito=True,
        producto_solicitado=producto_nombre,
        presentacion_solicitada=presentacion,
        cantidad=cantidad,
        funcion=funcion,
        codigo=codigo,
        descripcion_real=_get_descripcion(best_match),
        marca=best_match.get("marca", "") or best_match.get("marca_producto", ""),
        presentacion_real=presentacion_real,
        precio_unitario=precio,
        disponible=stock > 0,
        score_match=best_score,
        tipo_match=tipo,
    )


def match_sistema_completo(
    recomendacion: dict,
    lookup_fn,
    price_fn=None,
) -> dict:
    """
    Resuelve TODOS los productos de una recomendación estructurada.

    Args:
        recomendacion: Output de llm_estructurado.extraer_recomendacion_estructurada()
        lookup_fn: Función de búsqueda en inventario
        price_fn: Función de obtención de precios

    Returns:
        {
            "exito": bool,  # True si TODOS los productos críticos matchearon
            "productos_resueltos": [...],  # Lista de ResultadoMatch.to_dict()
            "herramientas_resueltas": [...],
            "productos_fallidos": [...],
            "herramientas_fallidas": [...],
            "resumen": {"total": N, "exitosos": M, "fallidos": K},
        }
    """
    productos_resueltos = []
    productos_fallidos = []
    herramientas_resueltas = []
    herramientas_fallidas = []

    # ── Match productos del sistema ──
    for item in recomendacion.get("sistema", []):
        resultado = match_producto_contra_inventario(
            producto_nombre=item.get("producto", ""),
            presentacion=item.get("presentacion", ""),
            cantidad=int(item.get("cantidad", 1)),
            funcion=item.get("funcion", ""),
            lookup_fn=lookup_fn,
            price_fn=price_fn,
            color=item.get("color", ""),
        )
        if resultado.exito:
            productos_resueltos.append(resultado.to_dict())
        else:
            productos_fallidos.append(resultado.to_dict())

    # ── Match herramientas ──
    for item in recomendacion.get("herramientas", []):
        resultado = match_producto_contra_inventario(
            producto_nombre=item.get("producto", ""),
            presentacion="unidad",
            cantidad=int(item.get("cantidad", 1)),
            funcion="herramienta",
            lookup_fn=lookup_fn,
            price_fn=price_fn,
        )
        if resultado.exito:
            herramientas_resueltas.append(resultado.to_dict())
        else:
            herramientas_fallidas.append(resultado.to_dict())

    total = len(productos_resueltos) + len(productos_fallidos)
    exitosos = len(productos_resueltos)

    # ── Evaluar éxito global ──
    # Productos con función crítica DEBEN existir
    funciones_criticas = {"sellador", "imprimante", "base", "acabado"}
    productos_criticos_fallidos = [
        p for p in productos_fallidos
        if p.get("funcion") in funciones_criticas
    ]
    exito_global = len(productos_criticos_fallidos) == 0 and exitosos > 0

    resultado_global = {
        "exito": exito_global,
        "productos_resueltos": productos_resueltos,
        "herramientas_resueltas": herramientas_resueltas,
        "productos_fallidos": productos_fallidos,
        "herramientas_fallidas": herramientas_fallidas,
        "resumen": {
            "total_productos": total,
            "exitosos": exitosos,
            "fallidos": len(productos_fallidos),
            "herramientas_ok": len(herramientas_resueltas),
            "herramientas_fallidas": len(herramientas_fallidas),
        },
    }

    if not exito_global:
        resultado_global["razon_fallo"] = (
            f"Productos críticos sin match: "
            f"{[p['producto_solicitado'] for p in productos_criticos_fallidos]}"
        )

    logger.info(
        "MATCH_SISTEMA: %s | %d/%d productos OK, %d/%d herramientas OK",
        "ÉXITO" if exito_global else "FALLO",
        exitosos, total,
        len(herramientas_resueltas),
        len(herramientas_resueltas) + len(herramientas_fallidas),
    )

    return resultado_global


# ══════════════════════════════════════════════════════════════════════════════
# FUNCIONES INTERNAS DE SCORING
# ══════════════════════════════════════════════════════════════════════════════

def _construir_texto_busqueda(nombre: str, presentacion: str, color: str) -> str:
    """Construye el texto de búsqueda para el inventario, expandiendo sinónimos ERP."""
    partes = [nombre]
    if color:
        partes.append(color)
    if presentacion:
        partes.append(presentacion)
    texto_base = " ".join(partes)
    return expandir_sinonimos_erp(texto_base)


def _buscar_candidatos(texto: str, lookup_fn) -> list[dict]:
    """Busca candidatos usando la función de lookup del inventario."""
    try:
        # lookup_fn debe retornar lista de dicts con campos del inventario
        resultados = lookup_fn(texto)
        if isinstance(resultados, str):
            parsed = json.loads(resultados)
            if isinstance(parsed, dict):
                return parsed.get("productos", [])
            return parsed if isinstance(parsed, list) else []
        return resultados if isinstance(resultados, list) else []
    except Exception as e:
        logger.error("MATCH: Error en lookup: %s", e)
        return []


def _calcular_score(
    nombre_solicitado: str,
    presentacion: str,
    color: str,
    candidato: dict,
) -> float:
    """
    Calcula score compuesto de match entre producto solicitado y candidato.
    Componentes:
      - Similitud de nombre (peso 0.6)
      - Match de presentación (peso 0.2)
      - Match de color (peso 0.1)
      - Disponibilidad (peso 0.1)
    """
    desc_candidato = _get_descripcion(candidato)
    nombre_norm = normalizar_texto(nombre_solicitado)
    desc_norm = normalizar_texto(desc_candidato)

    # ── Score de nombre (60%) ──
    # Combinar SequenceMatcher + overlap de palabras clave + sinónimos ERP
    seq_score = SequenceMatcher(None, nombre_norm, desc_norm).ratio()

    palabras_query = set(extraer_palabras_clave(nombre_solicitado))
    palabras_desc = set(extraer_palabras_clave(desc_candidato))
    
    # Expandir con sinónimos ERP (ej. "baños y cocinas" matchea "byc")
    palabras_query_exp = set(palabras_query)
    for p in list(palabras_query):
        for nombre_gen, alias_list in SINONIMOS_ERP.items():
            if p in nombre_gen.split() or p in alias_list:
                palabras_query_exp.update(alias_list)
                palabras_query_exp.update(nombre_gen.split())

    if palabras_query:
        # overlap con sinónimos expandidos
        overlap_base = len(palabras_query & palabras_desc) / len(palabras_query)
        overlap_exp = len(palabras_query_exp & palabras_desc) / len(palabras_query_exp) if palabras_query_exp else 0
        overlap = max(overlap_base, overlap_exp)
    else:
        overlap = 0

    nombre_score = (seq_score * 0.4 + overlap * 0.6)

    # ── Score de presentación (20%) ──
    pres_score = 0.0
    if presentacion:
        pres_real = _extraer_presentacion_real(candidato)
        if _presentacion_compatible(presentacion, pres_real):
            pres_score = 1.0
        elif pres_real:
            # Tiene presentación pero no coincide
            pres_score = 0.2
    else:
        pres_score = 0.5  # No se especificó, neutral

    # ── Score de color (10%) ──
    color_score = 0.5  # Neutral si no especificado
    if color:
        color_norm = normalizar_texto(color)
        if color_norm in desc_norm:
            color_score = 1.0
        else:
            color_score = 0.0

    # ── Disponibilidad (10%) ──
    stock = float(candidato.get("stock_total", 0) or 0)
    disp_score = 1.0 if stock > 0 else 0.0

    total = (
        nombre_score * 0.6
        + pres_score * 0.2
        + color_score * 0.1
        + disp_score * 0.1
    )

    return total


def _extraer_presentacion_real(candidato: dict) -> str:
    """Extrae la presentación del candidato de inventario."""
    # Intentar campo directo
    pres = candidato.get("presentacion") or candidato.get("unidad_medida") or ""
    if pres:
        return normalizar_texto(pres)

    # Inferir de la descripción
    desc = normalizar_texto(_get_descripcion(candidato))
    for nombre_pres, patrones in PRESENTACION_MAP.items():
        for patron in patrones:
            if patron in desc:
                return nombre_pres
    return ""


def _presentacion_compatible(solicitada: str, real: str) -> bool:
    """Verifica si la presentación solicitada coincide con la real."""
    solicitada_norm = normalizar_texto(solicitada)
    real_norm = normalizar_texto(real)

    if not solicitada_norm or not real_norm:
        return True  # Si falta uno, no bloquear

    # Match directo
    if solicitada_norm == real_norm:
        return True

    # Match por sinónimos
    patrones_solicitada = PRESENTACION_MAP.get(solicitada_norm, [solicitada_norm])
    return any(p in real_norm for p in patrones_solicitada)


def _buscar_con_presentacion(
    producto: str,
    presentacion: str,
    scored: list,
    candidatos: list,
) -> Optional[tuple]:
    """Busca el mismo producto con la presentación correcta."""
    for score, candidato in scored[1:]:  # Skip the first (already evaluated)
        if score < UMBRAL_MATCH_FUZZY:
            break
        pres_real = _extraer_presentacion_real(candidato)
        if _presentacion_compatible(presentacion, pres_real):
            return (score, candidato)
    return None


def _get_descripcion(candidato: dict) -> str:
    """Obtiene la mejor descripción disponible del candidato."""
    return (
        candidato.get("descripcion_comercial")
        or candidato.get("descripcion")
        or candidato.get("descripcion_normalizada")
        or candidato.get("etiqueta_auditable")
        or ""
    )
