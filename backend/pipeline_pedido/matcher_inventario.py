"""
matcher_inventario.py — Motor de match de productos contra inventario PostgreSQL
================================================================================

Responsabilidades:
  1. Recibir líneas de pedido parseadas (producto, cantidad, unidad, código)
  2. Resolver cada línea contra el inventario real vía lookup_fn inyectada
  3. Cruzar con catálogo International (data/international_products.json) para RAL
  4. Cruzar con color_formulas.json para colores de sistema Pintuco
  5. Detectar productos bicomponentes → inyectar catalizador/ajustador
  6. Detectar complementarios Abracol
  7. Retornar ResultadoMatch con productos resueltos, pendientes y fallidos
"""
from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Callable, Optional

logger = logging.getLogger("pipeline_pedido.matcher")

# ============================================================================
# RUTAS DE DATOS
# ============================================================================
# En Docker: __file__ = /app/pipeline_pedido/matcher_inventario.py
#   parent = /app/pipeline_pedido/, parent.parent = /app/
# En local: __file__ = .../backend/pipeline_pedido/matcher_inventario.py
#   parent.parent = .../backend/
_MODULE_DIR = Path(__file__).resolve().parent
_BACKEND_DIR = _MODULE_DIR.parent          # /app/ en Docker, .../backend/ en local
_DATA_DIR_CANDIDATES = [
    _BACKEND_DIR / "data",                  # /app/data/ o .../backend/data/
    _BACKEND_DIR.parent / "data",           # .../CRM_Ferreinox/data/ (local)
    Path("/app/data"),                      # fallback absoluto Docker
]

def _find_data_file(name: str) -> Path:
    for d in _DATA_DIR_CANDIDATES:
        p = d / name
        if p.exists():
            return p
    return _DATA_DIR_CANDIDATES[0] / name   # default (will fail gracefully)

_INTERNATIONAL_JSON = _find_data_file("international_products.json")
_COLOR_FORMULAS_JSON = _find_data_file("color_formulas.json")

# ============================================================================
# CATÁLOGOS EN MEMORIA (lazy-load)
# ============================================================================
_international_catalog: list[dict] | None = None
_color_formulas: list[dict] | None = None


def _load_international() -> list[dict]:
    global _international_catalog
    if _international_catalog is None:
        try:
            with open(_INTERNATIONAL_JSON, "r", encoding="utf-8") as f:
                _international_catalog = json.load(f)
        except Exception as exc:
            logger.warning("No se pudo cargar international_products.json: %s", exc)
            _international_catalog = []
    return _international_catalog


def _load_color_formulas() -> list[dict]:
    global _color_formulas
    if _color_formulas is None:
        try:
            with open(_COLOR_FORMULAS_JSON, "r", encoding="utf-8") as f:
                _color_formulas = json.load(f)
        except Exception as exc:
            logger.warning("No se pudo cargar color_formulas.json: %s", exc)
            _color_formulas = []
    return _color_formulas


# ============================================================================
# BICOMPONENTES — Reglas de catalizador/ajustador
# ============================================================================
BICOMPONENTES = {
    "interthane": {
        "nombre": "Interthane 990",
        "senales": ["interthane", "inthane", "inter thane"],
        "catalizador": "PHA046",
        "senales_catalizador": ["pha046", "pha 046", "catalizador interthane"],
        "ajustador": "21050",
        "senales_ajustador": ["21050", "ajustador 21050", "ajustador interthane"],
    },
    "epoxico": {
        "nombre": "Epoxico (Pintucoat/Intergard/Interseal)",
        "senales": [
            "pintucoat", "epoxi", "epoxy", "epoxico",
            "intergard", "interseal", "670", "740",
        ],
        "catalizador": "Parte B",
        "senales_catalizador": [
            "parte b", "catalizador epoxi", "componente b",
            "catalizador epox", "hardener",
        ],
        "ajustador": "209",
        "senales_ajustador": ["ajustador 209", "209"],
    },
    "trafico": {
        "nombre": "Trafico / Acrilica Mantenimiento",
        "senales": [
            "trafico", "tráfico", "acrilica mantenimiento",
            "pintura canchas", "demarcacion",
        ],
        "catalizador": "",  # sin catalizador
        "senales_catalizador": [],
        "ajustador": "204",
        "senales_ajustador": ["ajustador 204", "204"],
    },
}

# Líneas International que requieren RAL
LINEAS_RAL_OBLIGATORIO = {
    "interseal 670 hs", "intergard 740",
    "interthane 990", "acrilica mantenimiento",
}


# ============================================================================
# PRESENTACIONES — Fracciones tipo "2/1", "3/5", "4/4"
# ============================================================================
# El vendedor dice "2/1 viniltex" → 2 galones de viniltex
# "3/5 koraza" → 3 cuñetes de koraza
# "4/4 2650" → 4 cuartos del código 2650
PRESENTATION_FRACTIONS = {
    "1": "galon",     # 1/1 = galón
    "4": "cuarto",    # 1/4 = cuarto
    "5": "cunete",    # 1/5 = cuñete
    "2": "balde",     # 1/2 = medio cuñete / balde
}

PRESENTATION_ALIASES = {
    "cunete": ["cunete", "cunetes", "cuenete", "cuñete", "cuñetes",
              "caneca", "canecas", "cubeta", "cubetas", "18.93l", "5gl", "1/5"],
    "galon": ["galon", "galón", "galones", "gal", "3.79l", "1gl", "1/1"],
    "cuarto": ["cuarto", "cuartos", "0.95l", "1/4", "1/4gl"],
    "octavo": ["octavo", "octavos"],
    "balde": ["medio cuñete", "medio cunete", "medio cuñete", "9.46l", "1/2", "balde"],
}


def _canonizar_presentacion(text: str) -> str:
    """Normaliza texto de presentación a clave canónica."""
    t = text.lower().strip()
    for canon, aliases in PRESENTATION_ALIASES.items():
        if t in aliases or t == canon:
            return canon
    return t


# ============================================================================
# ALIAS DE PRODUCTO — Sinónimos comunes en el comercio
# ============================================================================
PRODUCT_ALIASES = {
    # Colorante y concentrado son lo mismo
    "concentrado": "colorante",
    "concentrados": "colorante",
    # NOTA: vinílico NO es intervinil — es línea IQ VINILICO (producto diferente)
    # "vinilico": "intervinil",  ← INCORRECTO, son productos distintos
    # Acriltex variantes
    "acriltex": "acriltex",
    "acril tex": "acriltex",
    # Abreviaturas comunes
    "vltx": "viniltex",
    "krz": "koraza",
    "itv": "intervinil",
    "pcoat": "pintucoat",
    # Normalización de palabras unidas
    "multisuperficie": "multi superficie",
    "multiusos": "multi usos",
}

# ============================================================================
# P-CODES → Línea DOMESTICO — Todos los P## son Doméstico
# ============================================================================
DOMESTICO_P_CODES = {
    "p11": "domestico blanco",
    "p 11": "domestico blanco",
    "p12": "domestico marfil",
    "p 12": "domestico marfil",
    "p45": "domestico",
    "p 45": "domestico",
    "p90": "domestico vino tinto",
    "p 90": "domestico vino tinto",
    "p153": "domestico aluminio",
    "p 153": "domestico aluminio",
}

# Referencia por defecto para pulidora sola (sin calificador)
PULIDORA_DEFAULT_REF = "120025"

# ============================================================================
# AEROSOLES — Dos líneas distintas, requiere clarificación
# ============================================================================
AEROSOL_LINES = {
    "aerocolor": "aerocolor",
    "tekbond": "aerosol tekbond",
}
AEROSOL_KEYWORDS = ["aerosol", "aerocolor", "tekbond"]

# ============================================================================
# COLORES COMPUESTOS — Detectar antes de separar tokens
# ============================================================================
# Orden: compuestos PRIMERO (más específicos), luego simples
COMPOUND_COLORS = [
    "blanco puro", "blanco mate", "blanco hueso", "blanco antiguo",
    "blanco roto", "blanco brillante", "blanco perla",
    "negro mate", "negro brillante",
    "verde bronce", "verde pino", "verde esmeralda", "verde manzana",
    "verde perico", "verde selva", "verde agua",
    "azul profundo", "azul cielo", "azul rey", "azul oceano",
    "azul petroleo", "azul cobalto",
    "rojo fiesta", "rojo colonial", "rojo indio", "rojo oxido",
    "mar profundo", "arena dorada", "gris plata", "gris perla",
    "gris basalto", "gris grafito", "gris humo",
    "amarillo oro", "amarillo cromo", "amarillo trafico",
    "terracota oscuro", "terracota claro",
    "ocre colonial", "marron habano", "marron tabaco",
    "naranja fiesta", "bronce antiguo",
    "vino tinto", "blanco almendra", "azul milano",
    "alta temperatura",
    # Bases (para cuando piden "base pastel", "base deep" etc.)
    "base pastel", "base tint", "base deep", "base accent",
    "base medio", "base transparente",
]

SIMPLE_COLORS = [
    "blanco", "negro", "gris", "rojo", "verde", "azul",
    "amarillo", "naranja", "marfil", "crema", "bronce",
    "transparente", "terracota", "ocre", "marron", "habano",
    "tabaco", "plata", "dorado", "cafe", "chocolate",
    "salmon", "beige", "hueso", "arena", "coral",
    "lila", "violeta", "morado", "magenta", "rosado",
    "aluminio", "vino", "milano",
]

# ============================================================================
# ABREVIATURAS DE ACABADO — "M" = mate, "B" = brillante, "S" = satinado
# ============================================================================
FINISH_ABBREVIATIONS = {
    r'\bM\b': 'mate',
    r'\bB\b': 'brillante',
    r'\bS\b': 'satinado',
    r'\bSG\b': 'semigloss',
    r'\bSM\b': 'semimate',
}

FINISH_WORDS = [
    "mate", "brillante", "satinado", "semibrillante",
    "semimate", "semigloss",
]


# ============================================================================
# NORMALIZACIÓN
# ============================================================================
_ACCENT_MAP = str.maketrans(
    "áéíóúàèìòùâêîôûäëïöüñ",
    "aeiouaeiouaeiouaeioun",
)


def _norm(text: str | None) -> str:
    if not text:
        return ""
    return text.lower().translate(_ACCENT_MAP).strip()


# ============================================================================
# PRESENTACIÓN — inferir de descripción ERP y filtrar resultados
# ============================================================================
# Tamaños ERP → presentación canónica
_ERP_SIZE_TO_PRES = {
    "18.93l": "cunete", "18.93": "cunete", "20l": "cunete",
    "5gl": "cunete", "5g": "cunete",
    "9.46l": "balde", "9.46": "balde", "2.5gl": "balde",
    "3.79l": "galon", "3.79": "galon", "3.78l": "galon",
    "3.7l": "galon", "1gl": "galon", "1g": "galon",
    "0.95l": "cuarto", "0.95": "cuarto", "0.9": "cuarto",
    "1/4gl": "cuarto", "1/4": "cuarto",
    "0.70l": "octavo", "0.5l": "octavo",
    "1.2g": "galon",  # Presentación especial aerosol/pintulux
}


def _inferir_presentacion_de_row(row: dict) -> str:
    """Infiere la presentación canónica de un producto desde su descripción ERP."""
    desc = _norm(
        row.get("descripcion_comercial")
        or row.get("descripcion")
        or row.get("nombre_articulo")
        or ""
    )
    # Normalizar comas decimales (ERP usa "0,9" en vez de "0.9")
    desc = desc.replace(",", ".")
    # Mirar campo explícito primero
    pres_expl = _norm(row.get("presentacion_canonica", ""))
    if pres_expl:
        canon = _canonizar_presentacion(pres_expl)
        if canon in PRESENTATION_ALIASES:
            return canon

    # Buscar patrones de tamaño en la descripción
    for size_tok, pres in _ERP_SIZE_TO_PRES.items():
        if size_tok in desc:
            return pres
    # Fallback por keywords
    for canon, aliases in PRESENTATION_ALIASES.items():
        for alias in aliases:
            if alias in desc:
                return canon
    return ""


def _filtrar_por_presentacion(rows: list[dict], unidad_solicitada: str) -> list[dict]:
    """Filtra resultados de lookup para que coincida la presentación solicitada.

    Si no hay coincidencias exactas, retorna todos (soft filter).
    Mapeo: galon también acepta 1.2G (pintulux); balde = medio cuñete.
    """
    if not unidad_solicitada or not rows:
        return rows

    target = _canonizar_presentacion(unidad_solicitada)
    # Equivalencias: balde == medio cuñete, octavo == fracción
    target_set = {target}
    if target == "balde":
        target_set.add("medio cunete")
    if target == "octavo":
        target_set.add("fraccion")

    matching = [r for r in rows if _inferir_presentacion_de_row(r) in target_set]
    return matching if matching else rows


# ============================================================================
# PRE-PROCESADOR DE LÍNEAS DE PEDIDO
# ============================================================================

def preprocesar_linea(linea: dict) -> dict:
    """
    Enriquece una línea de pedido cruda con:
      - Extracción de fracciones (2/1 → qty=2, pres=galon)
      - Extracción de códigos numéricos directos (13883, 517, 2650)
      - Expansión de aliases (colorante→concentrado, vinilico→intervinil)
      - Búsqueda en color_formulas.json por código (1504→"Viniltex Advanced VERDE AGUA Base Tint")

    Input: dict con keys: producto, cantidad, unidad, codigos, color, marca, texto
    Output: dict enriquecido con las mismas keys + campos adicionales
    """
    texto = str(linea.get("texto", linea.get("producto", "")))
    producto = str(linea.get("producto", texto))
    cantidad = linea.get("cantidad", 0) or 0
    unidad = linea.get("unidad", "")
    codigos = list(linea.get("codigos", []))
    color = linea.get("color", "")
    marca = linea.get("marca", "")

    texto_norm = _norm(texto)
    producto_norm = _norm(producto)

    # ── 1. Detectar patrón fracción: N/P (e.g., "2/1", "3/5", "4/4") ──
    frac_match = re.match(
        r'^\s*(\d{1,3})\s*/\s*([1245])\s+(.+)$', texto_norm,
    )
    if frac_match:
        qty = int(frac_match.group(1))
        denom = frac_match.group(2)
        resto = frac_match.group(3).strip()
        pres = PRESENTATION_FRACTIONS.get(denom, "")
        if pres:
            cantidad = qty
            unidad = pres
            producto = resto
            producto_norm = _norm(resto)
            logger.debug(
                "FRACCION: %s/%s → qty=%d pres=%s producto='%s'",
                qty, denom, qty, pres, resto,
            )

    # ── 2. Extraer códigos numéricos directos (4-10 dígitos) ──
    numeric_codes = re.findall(r'\b(\d{4,10})\b', producto_norm)
    for nc in numeric_codes:
        if nc not in codigos:
            codigos.append(nc)

    # ── 3. Expandir aliases de producto ──
    for alias, reemplazo in PRODUCT_ALIASES.items():
        if alias in producto_norm:
            producto_norm = producto_norm.replace(alias, reemplazo)
            producto = producto_norm

    # ── 3b. Expandir P-codes a Doméstico ──
    for pcode, domestico_name in DOMESTICO_P_CODES.items():
        if re.search(rf'\b{re.escape(pcode)}\b', producto_norm):
            # Reemplazar el P-code por el nombre completo para mejor búsqueda
            producto_norm = re.sub(rf'\b{re.escape(pcode)}\b', domestico_name, producto_norm)
            # Eliminar palabras duplicadas (ej: "domestico aluminio aluminio" → "domestico aluminio")
            words = producto_norm.split()
            seen = []
            for w in words:
                if w not in seen:
                    seen.append(w)
            producto_norm = " ".join(seen)
            producto = producto_norm
            logger.debug("P-CODE: '%s' → '%s'", pcode, domestico_name)
            break  # Solo un P-code por línea

    # ── 4. Extraer colores compuestos del texto ──
    acabado = linea.get("acabado", "")
    if not color:
        for cc in COMPOUND_COLORS:
            if cc in producto_norm:
                color = cc
                logger.debug("COLOR_COMPUESTO: '%s' en '%s'", cc, producto_norm)
                break
    if not color:
        for sc in SIMPLE_COLORS:
            if re.search(rf'\b{re.escape(sc)}\b', producto_norm):
                color = sc
                break

    # ── 5. Detectar acabado (mate, brillante, etc.) ──
    if not acabado:
        for pat, fin in FINISH_ABBREVIATIONS.items():
            if re.search(pat, texto):  # Case-sensitive: "M" vs "m"
                acabado = fin
                # Limpiar la abreviatura del producto para evitar ruido en búsqueda
                producto_norm = re.sub(pat, '', producto_norm, flags=re.IGNORECASE).strip()
                producto_norm = re.sub(r'\s+', ' ', producto_norm)
                producto = producto_norm
                logger.debug("ACABADO_ABREV: '%s' → '%s'", pat, fin)
                break
    if not acabado:
        for fw in FINISH_WORDS:
            if fw in producto_norm:
                acabado = fw
                break

    # ── 6. Buscar código de color en color_formulas.json ──
    color_formula_info = None
    for nc in codigos:
        formula = buscar_color_por_codigo(nc)
        if formula:
            color_formula_info = formula
            if not marca:
                marca = formula.get("producto", "")
            if not color:
                color = formula.get("nombre", "")
            logger.debug(
                "COLOR_FORMULA: código %s → %s %s (Base %s)",
                nc, formula.get("producto"), formula.get("nombre"),
                formula.get("base"),
            )
            break

    # ── 7. Si producto es solo código numérico, buscar en formulas ──
    if re.fullmatch(r'\d{4,10}', producto_norm.strip()) and not color_formula_info:
        formula = buscar_color_por_codigo(producto_norm.strip())
        if formula:
            color_formula_info = formula
            marca = formula.get("producto", "")
            color = formula.get("nombre", "")

    # ── 8. Canonizar presentación si viene en texto libre ──
    if unidad:
        unidad = _canonizar_presentacion(unidad)

    result = dict(linea)
    result.update({
        "producto": producto,
        "cantidad": cantidad if cantidad else (linea.get("cantidad") or 1),
        "unidad": unidad,
        "codigos": codigos,
        "color": color,
        "marca": marca,
        "acabado": acabado,
        "texto": texto,
        "_color_formula": color_formula_info,
    })
    return result


# ============================================================================
# DATACLASSES DE RESULTADO
# ============================================================================

@dataclass
class LineaResuelta:
    """Producto resuelto contra inventario."""
    producto_solicitado: str = ""
    cantidad: float = 0
    unidad: str = ""
    codigo_encontrado: str = ""
    descripcion_real: str = ""
    marca: str = ""
    presentacion_real: str = ""
    precio_unitario: float = 0
    stock_disponible: float = 0
    disponible: bool = False
    score_match: float = 0
    tipo_match: str = ""  # exact_code / fuzzy / catalog / smart
    es_bicomponente: bool = False
    requiere_ral: bool = False
    ral_detectado: str = ""
    color_detectado: str = ""
    linea_international: str = ""
    descuento_pct: float = 0
    original_text: str = ""
    cat_producto: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class LineaPendiente:
    """Producto que requiere acción del usuario (RAL, clarificación)."""
    producto_solicitado: str = ""
    cantidad: float = 0
    unidad: str = ""
    razon: str = ""  # missing_ral / ambiguous / missing_store
    mensaje_usuario: str = ""
    opciones: list[dict] = field(default_factory=list)
    original_text: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class LineaFallida:
    """Producto no encontrado en inventario."""
    producto_solicitado: str = ""
    cantidad: float = 0
    unidad: str = ""
    razon: str = ""
    original_text: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class BicomponenteInyectado:
    """Catalizador o ajustador auto-inyectado."""
    tipo: str = ""  # catalizador / ajustador
    para_producto: str = ""
    nombre: str = ""
    codigo_encontrado: str = ""
    descripcion_real: str = ""
    cantidad_sugerida: float = 0
    precio_unitario: float = 0
    stock_disponible: float = 0
    disponible: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ResultadoMatchPedido:
    """Resultado completo del matching de un pedido."""
    productos_resueltos: list[LineaResuelta] = field(default_factory=list)
    productos_pendientes: list[LineaPendiente] = field(default_factory=list)
    productos_fallidos: list[LineaFallida] = field(default_factory=list)
    bicomponentes_inyectados: list[BicomponenteInyectado] = field(default_factory=list)
    descuentos_aplicados: list[dict] = field(default_factory=list)
    tienda_codigo: str = ""
    tienda_nombre: str = ""

    def to_dict(self) -> dict:
        return {
            "productos_resueltos": [p.to_dict() for p in self.productos_resueltos],
            "productos_pendientes": [p.to_dict() for p in self.productos_pendientes],
            "productos_fallidos": [p.to_dict() for p in self.productos_fallidos],
            "bicomponentes_inyectados": [b.to_dict() for b in self.bicomponentes_inyectados],
            "descuentos_aplicados": self.descuentos_aplicados,
            "tienda_codigo": self.tienda_codigo,
            "tienda_nombre": self.tienda_nombre,
        }

    @property
    def tiene_pendientes(self) -> bool:
        return len(self.productos_pendientes) > 0

    @property
    def total_resueltos(self) -> int:
        return len(self.productos_resueltos)


# ============================================================================
# DETECCIÓN INTERNATIONAL + RAL
# ============================================================================

def detectar_linea_international(texto: str) -> dict | None:
    """Detecta si el texto pide un producto International y extrae RAL si presente."""
    norm = _norm(texto)
    catalogo = _load_international()
    lineas_detectadas = set()

    for entry in catalogo:
        linea_norm = _norm(entry.get("linea", ""))
        # Señales de búsqueda
        tokens_linea = linea_norm.split()
        if all(t in norm for t in tokens_linea if len(t) > 2):
            lineas_detectadas.add(entry["linea"])

    # También detectar por palabras clave directas
    keyword_map = {
        "interseal": "INTERSEAL 670 HS",
        "670": "INTERSEAL 670 HS",
        "intergard": "INTERGARD 740",
        "740": "INTERGARD 740",
        "interthane": "INTERTHANE 990",
        "990": "INTERTHANE 990",
        "acrilica mantenimiento": "ACRILICA MANTENIMIENTO",
        "acrilica mant": "ACRILICA MANTENIMIENTO",
    }
    for kw, linea in keyword_map.items():
        if kw in norm:
            lineas_detectadas.add(linea)

    if not lineas_detectadas:
        return None

    # Extraer RAL del texto
    ral_match = re.search(r"\bral\s*(\d{4})\b", norm)
    ral = ral_match.group(1) if ral_match else ""

    return {
        "lineas": list(lineas_detectadas),
        "ral": ral,
    }


def buscar_international_por_ral(linea: str, ral: str) -> dict | None:
    """Busca un producto International específico por línea + RAL."""
    catalogo = _load_international()
    for entry in catalogo:
        if _norm(entry.get("linea", "")) == _norm(linea) and entry.get("ral") == ral:
            return entry
    return None


def buscar_color_formula(producto: str, color_nombre: str) -> dict | None:
    """Busca una fórmula de color Pintuco por producto y nombre de color."""
    formulas = _load_color_formulas()
    prod_norm = _norm(producto)
    color_norm = _norm(color_nombre)
    for f in formulas:
        if _norm(f.get("producto", "")) == prod_norm and color_norm in _norm(f.get("nombre", "")):
            return f
    # Búsqueda parcial
    for f in formulas:
        if prod_norm in _norm(f.get("producto", "")) and color_norm in _norm(f.get("nombre", "")):
            return f
    return None


def buscar_color_por_codigo(codigo: str) -> dict | None:
    """Busca color en color_formulas.json por código numérico (e.g., '1504').
    También busca en international_products.json por codigo_galon/codigo_cunete.
    Retorna dict con {producto, codigo, nombre, base} o None."""
    codigo = str(codigo).strip()
    if not codigo:
        return None

    # 1. Buscar en color_formulas.json
    formulas = _load_color_formulas()
    for f in formulas:
        if str(f.get("codigo", "")).strip() == codigo:
            return f

    # 2. Buscar en international_products.json por codigo_galon o codigo_cunete
    catalogo = _load_international()
    for entry in catalogo:
        if str(entry.get("codigo_galon", "")).strip() == codigo:
            return {
                "producto": entry.get("linea", ""),
                "codigo": codigo,
                "nombre": f"RAL {entry.get('ral', '')} ({entry.get('tonalidad', '')})",
                "base": entry.get("base", ""),
                "_source": "international",
                "_entry": entry,
            }
        if str(entry.get("codigo_cunete", "")).strip() == codigo:
            return {
                "producto": entry.get("linea", ""),
                "codigo": codigo,
                "nombre": f"RAL {entry.get('ral', '')} ({entry.get('tonalidad', '')})",
                "base": entry.get("base", ""),
                "_source": "international",
                "_entry": entry,
            }
    return None


# ============================================================================
# DETECCIÓN BICOMPONENTES
# ============================================================================

def detectar_bicomponente(texto: str) -> str | None:
    """Retorna key del bicomponente detectado o None."""
    norm = _norm(texto)
    for key, bico in BICOMPONENTES.items():
        for senal in bico["senales"]:
            if senal in norm:
                return key
    return None


def _tiene_producto_en_lista(productos: list[str], senales: list[str]) -> bool:
    """Verifica si algún producto en la lista matchea las señales."""
    for prod in productos:
        prod_norm = _norm(prod)
        for senal in senales:
            if senal in prod_norm:
                return True
    return False


# ============================================================================
# MOTOR PRINCIPAL DE MATCHING
# ============================================================================

def match_pedido_completo(
    lineas_parseadas: list[dict],
    lookup_fn: Callable,
    price_fn: Callable[[str], dict],
    tienda_codigo: str = "",
    tienda_nombre: str = "",
    descuentos: list[dict] | None = None,
) -> ResultadoMatchPedido:
    """
    Resuelve un pedido completo contra inventario.

    Parámetros:
        lineas_parseadas: Lista de dicts con keys:
            - texto: str (línea original)
            - producto: str (nombre/código del producto)
            - cantidad: float
            - unidad: str (galon, cuarto, cunete, unidad)
            - codigos: list[str] (códigos extraídos)
            - marca: str (marca detectada)
            - color: str (color detectado)
            - talla: str (tamaño para brochas/rodillos)
        lookup_fn: Función que busca productos en inventario.
            Firma: lookup_fn(text, product_request=None) -> list[dict]
            product_request puede incluir:
              - requested_unit: str (galon, cuarto, cunete...)
              - store_filters: list[str] (códigos de tienda)
        price_fn: Función que obtiene precio por código
        tienda_codigo: Código de la tienda de despacho
        tienda_nombre: Nombre de la tienda
        descuentos: Notas de descuento [{marca, porcentaje}]

    Retorna: ResultadoMatchPedido
    """
    resultado = ResultadoMatchPedido(
        tienda_codigo=tienda_codigo,
        tienda_nombre=tienda_nombre,
        descuentos_aplicados=descuentos or [],
    )

    nombres_resueltos: list[str] = []  # Para detección bicomponente posterior

    for linea_raw in lineas_parseadas:
        # ── PRE-PROCESAR: fracciones, códigos, aliases, color formulas ──
        linea = preprocesar_linea(linea_raw)

        texto_original = linea.get("texto", "")
        producto = linea.get("producto", texto_original)
        cantidad = linea.get("cantidad", 1) or 1
        unidad = linea.get("unidad", "")
        codigos = linea.get("codigos", [])
        color = linea.get("color", "")
        marca = linea.get("marca", "")
        color_formula = linea.get("_color_formula")

        # ── Paso 0.5: Detectar aerosol genérico → pedir clarificación ──
        producto_norm_check = _norm(producto)
        if ("aerosol" in producto_norm_check
                and "aerocolor" not in producto_norm_check
                and "tekbond" not in producto_norm_check
                and "alta temperatura" not in producto_norm_check):
            # Aerosol genérico sin especificar línea → preguntar
            resultado.productos_pendientes.append(LineaPendiente(
                producto_solicitado=producto,
                cantidad=cantidad,
                unidad=unidad,
                razon="missing_aerosol_type",
                mensaje_usuario=(
                    f"Para *{texto_original}* necesito saber si es "
                    f"*Aerocolor* o *Aerosol Tekbond*, son lineas diferentes. "
                    f"¿Cuál necesitas?"
                ),
                opciones=[
                    {"label": "Aerocolor", "value": "aerocolor"},
                    {"label": "Aerosol Tekbond", "value": "aerosol tekbond"},
                ],
                original_text=texto_original,
            ))
            continue

        # ── Paso 0.7: Pulidora sola → referencia 120025 ──
        if (re.fullmatch(r'pulidora', producto_norm_check)
                or producto_norm_check == "pulidora"):
            # "pulidora" sin más = referencia 120025
            rows = lookup_fn(PULIDORA_DEFAULT_REF)
            if not rows:
                rows = lookup_fn("pulidora 120025")
            if rows:
                best = rows[0]
                codigo = best.get("referencia", PULIDORA_DEFAULT_REF)
                descripcion = (
                    best.get("descripcion_comercial")
                    or best.get("descripcion")
                    or "Pulidora 120025"
                )
                precio = 0
                if codigo:
                    precio_data = price_fn(codigo) or {}
                    precio = float(precio_data.get("precio_mejor", 0) or 0)
                stock = float(best.get("stock_total", 0) or 0)

                resuelto = LineaResuelta(
                    producto_solicitado=producto,
                    cantidad=cantidad,
                    unidad=unidad or "galon",
                    codigo_encontrado=codigo,
                    descripcion_real=descripcion,
                    marca=best.get("marca", ""),
                    presentacion_real=best.get("presentacion_canonica", "") or unidad or "galon",
                    precio_unitario=precio,
                    stock_disponible=stock,
                    disponible=stock > 0,
                    score_match=1.0,
                    tipo_match="pulidora_default",
                    original_text=texto_original,
                )
                resultado.productos_resueltos.append(resuelto)
                nombres_resueltos.append(descripcion)
                continue

        # ── Paso 1: Detectar si es producto International ──
        intl = detectar_linea_international(producto)
        if intl:
            ral = intl["ral"]
            linea_intl = intl["lineas"][0] if intl["lineas"] else ""

            # Si requiere RAL y no lo tiene → pendiente
            if _norm(linea_intl) in LINEAS_RAL_OBLIGATORIO and not ral:
                resultado.productos_pendientes.append(LineaPendiente(
                    producto_solicitado=producto,
                    cantidad=cantidad,
                    unidad=unidad,
                    razon="missing_ral",
                    mensaje_usuario=(
                        f"El producto *{linea_intl}* requiere un codigo RAL para "
                        f"identificar el color exacto. Por favor indicame el RAL "
                        f"(ejemplo: RAL 7035, RAL 1015, etc.)"
                    ),
                    original_text=texto_original,
                ))
                continue

            # Si tiene RAL, buscar en catálogo International
            if ral:
                entry = buscar_international_por_ral(linea_intl, ral)
                if entry:
                    # Determinar presentación y precio
                    if unidad in ("cunete", "cuñete"):
                        codigo = entry.get("codigo_cunete", "")
                        precio = float(entry.get("precio_cunete", 0))
                    else:
                        codigo = entry.get("codigo_galon", "")
                        precio = float(entry.get("precio_galon", 0))

                    resuelto = LineaResuelta(
                        producto_solicitado=producto,
                        cantidad=cantidad,
                        unidad=unidad or "galon",
                        codigo_encontrado=codigo,
                        descripcion_real=f"{entry['producto']} RAL {ral} ({entry.get('tonalidad', '')})",
                        marca="International",
                        presentacion_real=unidad or "galon",
                        precio_unitario=precio,
                        stock_disponible=0,  # Se valida después vs DB
                        disponible=True,
                        score_match=1.0,
                        tipo_match="international_catalog",
                        es_bicomponente=_norm(linea_intl) in {"interthane 990", "interseal 670 hs", "intergard 740"},
                        requiere_ral=True,
                        ral_detectado=ral,
                        linea_international=linea_intl,
                        original_text=texto_original,
                    )

                    # Enriquecer con stock real si lookup_fn disponible
                    if codigo:
                        rows = lookup_fn(codigo)
                        if rows:
                            best = rows[0]
                            resuelto.stock_disponible = float(best.get("stock_total", 0) or 0)
                            resuelto.disponible = resuelto.stock_disponible > 0

                    resultado.productos_resueltos.append(resuelto)
                    nombres_resueltos.append(producto)
                    continue
                else:
                    resultado.productos_pendientes.append(LineaPendiente(
                        producto_solicitado=producto,
                        cantidad=cantidad,
                        unidad=unidad,
                        razon="ral_not_found",
                        mensaje_usuario=(
                            f"No encontre el RAL {ral} en la linea *{linea_intl}*. "
                            f"Verifica el codigo RAL o consulta las opciones disponibles."
                        ),
                        original_text=texto_original,
                    ))
                    continue

        # ── Paso 2: Color formula directo — si el código ya está en el JSON ──
        if color_formula and color_formula.get("_source") == "international":
            # Código directo de producto International (e.g., "13883")
            intl_entry = color_formula.get("_entry", {})
            if intl_entry:
                # Determinar presentación y precio
                if unidad in ("cunete", "cuñete"):
                    codigo_intl = intl_entry.get("codigo_cunete", "")
                    precio_intl = float(intl_entry.get("precio_cunete", 0))
                else:
                    codigo_intl = intl_entry.get("codigo_galon", "")
                    precio_intl = float(intl_entry.get("precio_galon", 0))

                ral_intl = intl_entry.get("ral", "")
                linea_intl = intl_entry.get("linea", "")
                resuelto = LineaResuelta(
                    producto_solicitado=producto,
                    cantidad=cantidad,
                    unidad=unidad or "galon",
                    codigo_encontrado=codigo_intl,
                    descripcion_real=(
                        f"{intl_entry.get('producto', linea_intl)} "
                        f"RAL {ral_intl} ({intl_entry.get('tonalidad', '')})"
                    ),
                    marca="International",
                    presentacion_real=unidad or "galon",
                    precio_unitario=precio_intl,
                    stock_disponible=0,
                    disponible=True,
                    score_match=1.0,
                    tipo_match="international_code_direct",
                    es_bicomponente=_norm(linea_intl) in {
                        "interthane 990", "interseal 670 hs", "intergard 740",
                    },
                    requiere_ral=True,
                    ral_detectado=ral_intl,
                    linea_international=linea_intl,
                    original_text=texto_original,
                )
                # Enriquecer con stock real
                if codigo_intl:
                    r = lookup_fn(codigo_intl)
                    if r:
                        resuelto.stock_disponible = float(r[0].get("stock_total", 0) or 0)
                        resuelto.disponible = resuelto.stock_disponible > 0
                resultado.productos_resueltos.append(resuelto)
                nombres_resueltos.append(linea_intl)
                continue

        # ── Paso 3: Lookup normal contra inventario ──
        # Construir query de búsqueda con toda la info disponible
        acabado = linea.get("acabado", "")

        # IMPORTANTE: Construir busqueda incluyendo producto+color+acabado+marca
        # pero SIN reemplazar producto por código solo (pierde contexto)
        busqueda = producto
        if codigos:
            # Incluir código JUNTO con producto, no reemplazar
            code_str = codigos[0]
            if code_str not in busqueda:
                busqueda = f"{busqueda} {code_str}"
        if color and color.lower() not in busqueda.lower():
            busqueda = f"{busqueda} {color}"
        if acabado and acabado.lower() not in busqueda.lower():
            busqueda = f"{busqueda} {acabado}"
        if marca and marca.lower() not in busqueda.lower():
            busqueda = f"{busqueda} {marca}"
        # Si hay color formula, enriquecer con producto + base para mejor match
        if color_formula and not color_formula.get("_source"):
            base_info = color_formula.get("base", "")
            prod_formula = color_formula.get("producto", "")
            if prod_formula and prod_formula.lower() not in busqueda.lower():
                busqueda = f"{prod_formula} {busqueda}"
            if base_info and base_info.lower() not in busqueda.lower():
                busqueda = f"{busqueda} {base_info}"

        # Construir product_request para que lookup_fn filtre por
        # presentación y tienda del lado de la DB
        pres_canonica = _canonizar_presentacion(unidad) if unidad else ""
        prod_request = {
            "requested_unit": pres_canonica,
            "store_filters": [tienda_codigo] if tienda_codigo else [],
            "allow_stale_with_stock": True,
            "nlu_processed": True,  # Evitar NLU redundante en lookup_fn
        }

        def _lookup(q: str) -> list[dict]:
            """Wrapper que pasa product_request a lookup_fn y filtra presentación."""
            try:
                r = lookup_fn(q, prod_request)
            except TypeError:
                # fallback si lookup_fn no acepta product_request
                r = lookup_fn(q)
            except Exception as exc:
                logger.error("_lookup EXCEPCION para q=%r: %s", q, exc)
                return []
            logger.info(
                "_lookup q=%r → %d rows (pre-filtro), prod_request=%s",
                q[:60], len(r) if r else 0, prod_request,
            )
            if not r:
                return []
            filtered = _filtrar_por_presentacion(r, pres_canonica)
            logger.info(
                "_lookup q=%r → %d rows (post-filtro pres=%s)",
                q[:60], len(filtered), pres_canonica,
            )
            return filtered

        rows = _lookup(busqueda)
        if not rows:
            # Retry sin color/acabado/marca (solo producto base)
            rows = _lookup(producto)
        if not rows and color:
            # Retry: producto + color compuesto
            rows = _lookup(f"{producto} {color}")
        if not rows and codigos:
            for c in codigos:
                rows = _lookup(c)
                if rows:
                    break
        # Retry: si hay color_formula, buscar por producto+nombre_color del JSON
        if not rows and color_formula:
            retry_q = f"{color_formula.get('producto', '')} {color_formula.get('nombre', '')}"
            rows = _lookup(retry_q.strip())
        # Último recurso: buscar solo con código + presentación
        if not rows and codigos and unidad:
            for c in codigos:
                rows = _lookup(f"{c} {unidad}")
                if rows:
                    break

        if not rows:
            resultado.productos_fallidos.append(LineaFallida(
                producto_solicitado=producto,
                cantidad=cantidad,
                unidad=unidad,
                razon="not_found",
                original_text=texto_original,
            ))
            continue

        # Seleccionar mejor match
        best = rows[0]
        codigo = (
            best.get("referencia")
            or best.get("codigo_articulo")
            or best.get("producto_codigo")
            or ""
        )
        descripcion = (
            best.get("descripcion_comercial")
            or best.get("descripcion")
            or best.get("nombre_articulo")
            or ""
        )

        # Obtener precio
        precio = 0
        if codigo:
            precio_data = price_fn(codigo) or {}
            precio = float(precio_data.get("precio_mejor", 0) or 0)
        if not precio:
            precio = float(best.get("precio_venta", 0) or best.get("pvp_sap", 0) or 0)

        stock = float(best.get("stock_total", 0) or 0)
        score = float(best.get("match_score", 0) or best.get("specific_score", 0) or 0.5)
        marca_real = best.get("marca", "") or best.get("marca_producto", "") or ""
        pres_real = best.get("presentacion_canonica", "") or unidad or ""
        cat_prod = best.get("cat_producto", "") or ""

        # Detectar bicomponente
        bico_key = detectar_bicomponente(descripcion)

        # Aplicar descuento si corresponde
        descuento = 0.0
        if descuentos:
            for d in descuentos:
                marca_desc = _norm(d.get("marca", ""))
                if marca_desc and marca_desc in _norm(marca_real):
                    descuento = float(d.get("porcentaje", 0))
                elif not marca_desc:
                    descuento = float(d.get("porcentaje", 0))

        resuelto = LineaResuelta(
            producto_solicitado=producto,
            cantidad=cantidad,
            unidad=unidad,
            codigo_encontrado=codigo,
            descripcion_real=descripcion,
            marca=marca_real,
            presentacion_real=pres_real,
            precio_unitario=precio,
            stock_disponible=stock,
            disponible=stock > 0,
            score_match=score,
            tipo_match="db_lookup",
            es_bicomponente=bico_key is not None,
            color_detectado=color,
            descuento_pct=descuento,
            original_text=texto_original,
            cat_producto=cat_prod,
        )
        resultado.productos_resueltos.append(resuelto)
        nombres_resueltos.append(descripcion)

    # ── Paso 3: Detectar bicomponentes faltantes ──
    _inyectar_bicomponentes(resultado, nombres_resueltos, lookup_fn, price_fn)

    return resultado


# ============================================================================
# INYECCIÓN DE BICOMPONENTES
# ============================================================================

def _inyectar_bicomponentes(
    resultado: ResultadoMatchPedido,
    nombres_resueltos: list[str],
    lookup_fn: Callable,
    price_fn: Callable,
):
    """Detecta productos bicomponentes y añade catalizador/ajustador si faltan."""
    todos_nombres = [_norm(n) for n in nombres_resueltos]
    todos_texto = " ".join(todos_nombres)

    for key, bico in BICOMPONENTES.items():
        # ¿Hay algún producto principal en el pedido?
        tiene_principal = any(
            any(s in n for s in bico["senales"])
            for n in todos_nombres
        )
        if not tiene_principal:
            continue

        # ¿Ya tiene catalizador? (solo si bico tiene catalizador)
        if bico["catalizador"]:
            tiene_cat = _tiene_producto_en_lista(nombres_resueltos, bico["senales_catalizador"])
            if not tiene_cat:
                _buscar_e_inyectar(
                    resultado, "catalizador", bico["catalizador"],
                    bico["nombre"], lookup_fn, price_fn,
                )

        # ¿Ya tiene ajustador?
        if bico["ajustador"]:
            tiene_adj = _tiene_producto_en_lista(nombres_resueltos, bico["senales_ajustador"])
            if not tiene_adj:
                _buscar_e_inyectar(
                    resultado, "ajustador", bico["ajustador"],
                    bico["nombre"], lookup_fn, price_fn,
                )


def _buscar_e_inyectar(
    resultado: ResultadoMatchPedido,
    tipo: str,
    nombre: str,
    para_producto: str,
    lookup_fn: Callable,
    price_fn: Callable,
):
    """Busca un catalizador/ajustador en inventario y lo inyecta como sugerencia."""
    rows = lookup_fn(nombre)
    if not rows:
        rows = lookup_fn(f"{tipo} {nombre}")

    inyectado = BicomponenteInyectado(
        tipo=tipo,
        para_producto=para_producto,
        nombre=nombre,
    )

    if rows:
        best = rows[0]
        inyectado.codigo_encontrado = (
            best.get("referencia") or best.get("codigo_articulo") or ""
        )
        inyectado.descripcion_real = (
            best.get("descripcion_comercial") or best.get("descripcion") or nombre
        )
        inyectado.stock_disponible = float(best.get("stock_total", 0) or 0)
        inyectado.disponible = inyectado.stock_disponible > 0
        if inyectado.codigo_encontrado:
            precio_data = price_fn(inyectado.codigo_encontrado) or {}
            inyectado.precio_unitario = float(
                precio_data.get("precio_mejor", 0) or 0
            )
        inyectado.cantidad_sugerida = 1

    resultado.bicomponentes_inyectados.append(inyectado)
