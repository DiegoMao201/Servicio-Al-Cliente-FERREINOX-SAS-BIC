from __future__ import annotations

import argparse
import csv
import math
import os
import re
import sys
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

import pandas as pd

try:
    from rapidfuzz import fuzz, process
except Exception:  # pragma: no cover - fallback if dependency is missing
    fuzz = None
    process = None


ROOT = Path(__file__).resolve().parent
BACKEND_PATH = ROOT / "backend"
if str(BACKEND_PATH) not in sys.path:
    sys.path.insert(0, str(BACKEND_PATH))

try:
    import main as backend_main
except Exception:
    backend_main = None


DEFAULT_INPUT = ROOT / "artifacts" / "rag_product_universe" / "plantilla_mapeo_fichas_rag_inventario.csv"
DEFAULT_OUTPUT = ROOT / "artifacts" / "rag_product_universe" / "mapeo_fichas_erp_cruzado.csv"

DESCRIPTION_COLUMN_CANDIDATES = [
    "Descripcion",
    "Descripción",
    "descripcion",
    "descripcion_exacta",
    "nombre_articulo",
    "descripcion_articulo",
]

REFERENCE_COLUMN_CANDIDATES = [
    "referencia",
    "Referencia",
    "codigo_articulo",
    "Código",
    "codigo",
    "producto_codigo",
]

STOP_PREFIXES = {
    "PQ",
    "P7",
    "IQ",
    "FT",
    "FICHA TEC",
    "FICHA TECNICA",
    "FDS",
    "HDS",
    "HOJA DE SEGURIDAD",
}

MEASURE_PATTERNS = [
    r"\b\d+(?:[.,]\d+)?\s*L\b",
    r"\b\d+(?:[.,]\d+)?\s*ML\b",
    r"\b\d+(?:[.,]\d+)?\s*KG\b",
    r"\b\d+(?:[.,]\d+)?\s*GL\b",
    r"\b\d+/\d+G\b",
    r"/\d+(?:[.,]\d+)?L/[A-Z0-9]+",
    r"/\d+(?:[.,]\d+)?KG/[A-Z0-9]+",
]

ERP_CODE_PATTERNS = [
    r"\b(?:UEA|GTA|TLA|PHA|EGA|UFA|UDA|OCA|ECP|TNT)[A-Z0-9-]*\b",
    r"\bAA7\b",
    r"\bPT\s+[AB]\b",
    r"\bCOMP\s+[AB]\b",
    r"\bPARTE\s+[AB]\b",
]

SUSPICIOUS_NAME_TOKENS = {
    "GASTOS",
    "DEDUCIBLES",
    "KIT",
    "CAT",
    "CATALIZADOR",
    "PARTE",
    "COMP",
}

COLOR_WORDS = {
    "BLANCO",
    "NEGRO",
    "ROJO",
    "VERDE",
    "AZUL",
    "AMARILLO",
    "GRIS",
    "ALUMINIO",
    "INCOLORO",
    "TRANSPARENTE",
    "CAOBA",
    "NARANJA",
    "ESMERALDA",
    "CREMA",
    "LADRILLO",
    "BASALTO",
    "PASTEL",
    "TURQUESA",
    "HUMO",
    "VIOLETA",
    "BERMELLON",
}

FINISH_EXPANSIONS = {
    "3EN1": "3 EN 1",
    "BR": "BRILLANTE",
    "MAT": "MATE",
    "SAT": "SATINADO",
    "SEMIMAT": "SEMIMATE",
}


@dataclass
class InventoryCandidate:
    description: str
    reference: str = ""
    source: str = ""
    score: float = 0.0
    query: str = ""
    match_note: str = ""


def normalize_text(value: object) -> str:
    text = "" if value is None else str(value)
    text = text.strip()
    if not text:
        return ""
    text = unicodedata.normalize("NFKD", text)
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = text.upper()
    text = re.sub(r"\.PDF$", "", text)
    text = re.sub(r"[_\-]+", " ", text)
    text = re.sub(r"\([^)]*\)", " ", text)
    text = re.sub(r"\bCOPIA\b|\bACTUALIZADA\b|\bACTUALIZADO\b|\bFINAL\b", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def clean_filename_family(value: object) -> str:
    text = normalize_text(value)
    text = re.sub(r"^FDS\s*", "", text)
    text = re.sub(r"^HDS\s*", "", text)
    text = re.sub(r"^HOJA DE SEGURIDAD\s*", "", text)
    text = re.sub(r"^FICHA TEC(?:NICA)?\s*", "", text)
    text = re.sub(r"^GUIA\s*", "", text)
    return re.sub(r"\s+", " ", text).strip()


def pick_first_nonempty(*values: object) -> str:
    for value in values:
        text = str(value).strip() if value is not None and not (isinstance(value, float) and math.isnan(value)) else ""
        if text:
            return text
    return ""


def load_mapping_csv(path: Path) -> pd.DataFrame:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.reader(handle)
        rows = list(reader)
    if not rows:
        return pd.DataFrame()

    header = rows[0]
    parsed_rows: list[list[str]] = []
    expected_columns = len(header)
    trailing_fixed_columns = 6

    for raw_row in rows[1:]:
        if not raw_row or not any(cell.strip() for cell in raw_row):
            continue
        if len(raw_row) == expected_columns:
            parsed_rows.append(raw_row)
            continue
        if len(raw_row) > expected_columns:
            prefix = raw_row[:4]
            suffix = raw_row[-trailing_fixed_columns:]
            note = ",".join(raw_row[4:-trailing_fixed_columns]).strip()
            parsed_rows.append(prefix + [note] + suffix)
            continue
        padded_row = raw_row + [""] * (expected_columns - len(raw_row))
        parsed_rows.append(padded_row)

    df = pd.DataFrame(parsed_rows, columns=header)
    for column in [
        "tipo_documento",
        "archivo_actual",
        "nombre_recomendado",
        "accion",
        "nota",
        "lookup_inventario_sugerido",
        "ejemplo_erp_encontrado",
        "ref_erp_ejemplo",
        "familia_canonica",
        "marca",
        "estado_validacion",
    ]:
        if column not in df.columns:
            df[column] = ""
    return df


def detect_column(columns: Iterable[str], candidates: list[str]) -> Optional[str]:
    normalized_map = {normalize_text(column): column for column in columns}
    for candidate in candidates:
        match = normalized_map.get(normalize_text(candidate))
        if match:
            return match
    return None


def load_external_inventory(path: Path) -> list[dict]:
    if path.suffix.lower() in {".xlsx", ".xls"}:
        inventory_df = pd.read_excel(path)
    else:
        try:
            inventory_df = pd.read_csv(path)
        except Exception:
            inventory_df = pd.read_csv(path, sep=";")

    description_col = detect_column(inventory_df.columns, DESCRIPTION_COLUMN_CANDIDATES)
    reference_col = detect_column(inventory_df.columns, REFERENCE_COLUMN_CANDIDATES)
    if not description_col:
        raise ValueError(f"No pude detectar la columna de descripción en {path}")

    rows: list[dict] = []
    for _, row in inventory_df.iterrows():
        description = str(row.get(description_col) or "").strip()
        if not description:
            continue
        reference = str(row.get(reference_col) or "").strip() if reference_col else ""
        rows.append({"descripcion": description, "referencia": reference, "source": f"archivo:{path.name}"})
    return rows


def load_db_inventory() -> list[dict]:
    if backend_main is None:
        return []
    try:
        engine = backend_main.get_db_engine()
        with engine.connect() as connection:
            rows = connection.execute(
                backend_main.text(
                    """
                    SELECT DISTINCT
                        COALESCE(referencia, '') AS referencia,
                        COALESCE(descripcion, '') AS descripcion
                    FROM public.vw_inventario_agente
                    WHERE COALESCE(descripcion, '') <> ''
                    """
                )
            ).mappings().all()
        return [
            {
                "descripcion": str(row.get("descripcion") or "").strip(),
                "referencia": str(row.get("referencia") or "").strip(),
                "source": "db:vw_inventario_agente",
            }
            for row in rows
            if str(row.get("descripcion") or "").strip()
        ]
    except Exception:
        return []


def score_strings(query: str, choice: str) -> float:
    query_norm = normalize_text(query)
    choice_norm = normalize_text(choice)
    if not query_norm or not choice_norm:
        return 0.0
    if process and fuzz:
        score = max(
            fuzz.WRatio(query_norm, choice_norm),
            fuzz.token_set_ratio(query_norm, choice_norm),
            fuzz.partial_ratio(query_norm, choice_norm),
        )
        return float(score)
    from difflib import SequenceMatcher

    return SequenceMatcher(None, query_norm, choice_norm).ratio() * 100.0


def build_queries(row: pd.Series) -> list[str]:
    candidates = [
        clean_filename_family(row.get("lookup_inventario_sugerido")),
        clean_filename_family(row.get("nombre_recomendado")),
        clean_filename_family(row.get("familia_canonica")),
        clean_filename_family(row.get("archivo_actual")),
    ]
    queries: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        if candidate and candidate not in seen:
            seen.add(candidate)
            queries.append(candidate)
    return queries


def build_backend_request(query: str) -> dict:
    normalized_query = (query or "").strip()
    if not normalized_query:
        return {"nlu_processed": True, "core_terms": [], "search_terms": []}

    if backend_main is not None:
        try:
            base_request = backend_main.extract_product_request(normalized_query) or {}
        except Exception:
            base_request = {}
        try:
            base_request = backend_main.apply_deterministic_product_alias_rules(normalized_query, base_request)
            base_request = backend_main._apply_technical_product_request_hints(normalized_query, base_request)
        except Exception:
            pass

        core_terms = list(base_request.get("core_terms") or [])
        if not core_terms:
            core_terms = [normalized_query]

        search_terms = list(base_request.get("search_terms") or [])
        if not search_terms:
            try:
                expanded = backend_main.expand_product_terms(core_terms)
                search_terms = list(expanded or core_terms)
            except Exception:
                search_terms = core_terms[:]

        base_request["core_terms"] = core_terms[:10]
        base_request["search_terms"] = search_terms[:14]
        base_request["nlu_processed"] = True
        base_request.setdefault("color_filters", [])
        base_request.setdefault("finish_filters", [])
        base_request.setdefault("brand_filters", [])
        return base_request

    return {
        "nlu_processed": True,
        "core_terms": [normalized_query],
        "search_terms": [normalized_query],
        "color_filters": [],
        "finish_filters": [],
        "brand_filters": [],
    }


def search_with_backend(query: str) -> list[InventoryCandidate]:
    if backend_main is None or not query:
        return []
    try:
        request = build_backend_request(query)
        rows = backend_main.lookup_product_context(query, request) or []
    except Exception:
        return []

    matches: list[InventoryCandidate] = []
    for row in rows[:5]:
        description = pick_first_nonempty(row.get("descripcion"), row.get("descripcion_exacta"), row.get("nombre_articulo"))
        reference = pick_first_nonempty(row.get("referencia"), row.get("codigo_articulo"), row.get("producto_codigo"))
        score = score_strings(query, description)
        matches.append(
            InventoryCandidate(
                description=description,
                reference=reference,
                source="backend_lookup",
                score=score,
                query=query,
                match_note="lookup_product_context",
            )
        )
    return matches


def search_with_corpus(query: str, inventory_rows: list[dict]) -> Optional[InventoryCandidate]:
    if not query or not inventory_rows:
        return None
    choices = [row["descripcion"] for row in inventory_rows if row.get("descripcion")]
    if not choices:
        return None

    if process and fuzz:
        result = process.extractOne(query, choices, scorer=fuzz.WRatio)
        if not result:
            return None
        choice, score, _ = result
    else:
        ranked = sorted(((score_strings(query, choice), choice) for choice in choices), reverse=True)
        if not ranked:
            return None
        score, choice = ranked[0]

    if score < 72:
        return None

    matched_row = next((row for row in inventory_rows if row.get("descripcion") == choice), None)
    if not matched_row:
        return None
    return InventoryCandidate(
        description=matched_row.get("descripcion", ""),
        reference=matched_row.get("referencia", ""),
        source=matched_row.get("source", "corpus_fuzzy"),
        score=float(score),
        query=query,
        match_note="rapidfuzz_corpus",
    )


def cleanup_erp_family(description: str) -> str:
    text = normalize_text(description)
    if not text:
        return ""

    for prefix in sorted(STOP_PREFIXES, key=len, reverse=True):
        text = re.sub(rf"^{re.escape(prefix)}\s+", "", text)

    for key, value in FINISH_EXPANSIONS.items():
        text = re.sub(rf"\b{re.escape(key)}\b", value, text)

    for pattern in ERP_CODE_PATTERNS + MEASURE_PATTERNS:
        text = re.sub(pattern, " ", text)

    text = re.sub(r"\b(?:PT|COMP|PARTE)\s+[AB]\b", " ", text)
    text = re.sub(r"\bBASE\s+(?:ACCENT|DEEP|TINT)\b", " ", text)
    text = re.sub(r"[/\\]+", " ", text)
    text = re.sub(r"\b\d+G\b", " ", text)
    text = re.sub(r"\b\d+(?:[.,]\d+)?\b", lambda match: " " if len(match.group(0)) <= 2 else match.group(0), text)
    text = re.sub(r"\s+", " ", text).strip()

    tokens = text.split()
    while tokens and (tokens[-1] in COLOR_WORDS or re.fullmatch(r"\d{2,6}", tokens[-1] or "")):
        tokens.pop()
    text = " ".join(tokens).strip()

    text = re.sub(r"\b3 EN 1\b", "3 EN 1", text)
    text = re.sub(r"\bMATE BLAN\b", "MATE", text)
    text = re.sub(r"\bTRANSPAREN\b", "TRANSPARENTE", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def is_suspicious_auto_name(auto_name: str, match: Optional[InventoryCandidate]) -> bool:
    normalized = normalize_text(auto_name)
    if not normalized:
        return True
    if any(token in normalized.split() for token in SUSPICIOUS_NAME_TOKENS):
        return True
    if "/" in auto_name or "\\" in auto_name:
        return True
    if match and any(token in normalize_text(match.description).split() for token in {"GASTOS", "DEDUCIBLES"}):
        return True
    return False


def choose_best_match(row: pd.Series, inventory_rows: list[dict]) -> Optional[InventoryCandidate]:
    queries = build_queries(row)
    best: Optional[InventoryCandidate] = None

    for query in queries:
        corpus_match = search_with_corpus(query, inventory_rows)
        if corpus_match and (best is None or corpus_match.score > best.score):
            best = corpus_match

        if corpus_match and corpus_match.score >= 88:
            continue

        for candidate in search_with_backend(query):
            if best is None or candidate.score > best.score:
                best = candidate

    return best


def classify_validation(row: pd.Series, match: Optional[InventoryCandidate]) -> str:
    tipo = normalize_text(row.get("tipo_documento"))
    accion = normalize_text(row.get("accion"))
    if tipo in {"FDS", "HDS", "CERTIFICADO", "GUIA"} or accion == "SEPARAR TIPO DOCUMENTAL":
        return "no_reingestar_como_ficha"
    if not match:
        return "sin_match"
    auto_name = cleanup_erp_family(match.description)
    if is_suspicious_auto_name(auto_name, match):
        return "revisar_manual"
    if match.score >= 90:
        return "validado_automatico"
    if match.score >= 80:
        return "validado_con_revision"
    return "revisar_manual"


def propose_action(row: pd.Series, match: Optional[InventoryCandidate], auto_name: str) -> str:
    tipo = normalize_text(row.get("tipo_documento"))
    if tipo in {"FDS", "HDS", "CERTIFICADO", "GUIA"}:
        return "separar_tipo_documental"
    if is_suspicious_auto_name(auto_name, match):
        return "revisar"
    current_name = clean_filename_family(row.get("archivo_actual"))
    recommended = clean_filename_family(row.get("nombre_recomendado"))
    target = clean_filename_family(auto_name or recommended)
    if not target:
        return str(row.get("accion") or "revisar")
    if current_name == target:
        return "mantener"
    if recommended and recommended == target:
        return str(row.get("accion") or "renombrar")
    if match and match.score >= 80:
        return "renombrar"
    return "revisar"


def build_note(row: pd.Series, match: Optional[InventoryCandidate], auto_name: str) -> str:
    original_note = pick_first_nonempty(row.get("nota"))
    if not match:
        return original_note or "No encontré un match suficientemente confiable en inventario"
    if is_suspicious_auto_name(auto_name, match):
        return (
            f"Match encontrado en inventario ({match.source}, score {match.score:.1f}), "
            "pero la propuesta automática parece demasiado SKU-específica o dudosa; revisar manualmente"
        )
    if auto_name:
        return f"Cruce automático desde inventario ({match.source}, score {match.score:.1f}) -> {auto_name}"
    return f"Cruce automático desde inventario ({match.source}, score {match.score:.1f})"


def enrich_dataframe(df: pd.DataFrame, inventory_rows: list[dict]) -> pd.DataFrame:
    output = df.copy()
    for column in [
        "match_source",
        "match_score",
        "match_query_usada",
        "nombre_recomendado_auto",
        "accion_auto",
        "estado_validacion_auto",
        "nota_auto",
    ]:
        if column not in output.columns:
            output[column] = ""

    for index, row in output.iterrows():
        match = choose_best_match(row, inventory_rows)
        auto_name = cleanup_erp_family(match.description) if match else ""
        validation = classify_validation(row, match)
        action = propose_action(row, match, auto_name)
        note = build_note(row, match, auto_name)

        if match:
            output.at[index, "ejemplo_erp_encontrado"] = match.description
            output.at[index, "ref_erp_ejemplo"] = match.reference
            if auto_name:
                output.at[index, "nombre_recomendado_auto"] = f"{auto_name}.pdf"
                if not is_suspicious_auto_name(auto_name, match) and (not pick_first_nonempty(row.get("nombre_recomendado")) or action == "renombrar"):
                    output.at[index, "nombre_recomendado"] = f"{auto_name}.pdf"
            if not pick_first_nonempty(row.get("lookup_inventario_sugerido")):
                output.at[index, "lookup_inventario_sugerido"] = match.query

        output.at[index, "match_source"] = match.source if match else ""
        output.at[index, "match_score"] = round(match.score, 2) if match else ""
        output.at[index, "match_query_usada"] = match.query if match else ""
        output.at[index, "accion_auto"] = action
        output.at[index, "estado_validacion_auto"] = validation
        output.at[index, "nota_auto"] = note

        tipo = normalize_text(row.get("tipo_documento"))
        if tipo not in {"FDS", "HDS", "CERTIFICADO", "GUIA"}:
            output.at[index, "accion"] = action
            output.at[index, "estado_validacion"] = validation
            output.at[index, "nota"] = note

    return output


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Cruza fichas RAG contra inventario ERP y propone renombres.")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT, help="CSV de fichas a enriquecer")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="CSV de salida enriquecido")
    parser.add_argument(
        "--inventory-source",
        type=Path,
        default=None,
        help="CSV/XLSX externo del ERP. Si no se envía, usa la base conectada por backend/main.py",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    mapping_df = load_mapping_csv(args.input)

    inventory_rows = load_db_inventory()
    if args.inventory_source:
        inventory_rows.extend(load_external_inventory(args.inventory_source))

    if not inventory_rows:
        raise RuntimeError(
            "No pude cargar inventario desde la base ni desde un archivo externo. "
            "Pasa --inventory-source o revisa la conexión de backend/main.py"
        )

    enriched_df = enrich_dataframe(mapping_df, inventory_rows)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    enriched_df.to_csv(args.output, index=False, encoding="utf-8-sig")

    total = len(enriched_df)
    auto_validated = int((enriched_df["estado_validacion"] == "validado_automatico").sum())
    auto_review = int((enriched_df["estado_validacion"] == "validado_con_revision").sum())
    no_match = int((enriched_df["estado_validacion"] == "sin_match").sum())
    print(f"Cruce completado. Archivo: {args.output}")
    print(f"Total filas: {total}")
    print(f"Validado automático: {auto_validated}")
    print(f"Validado con revisión: {auto_review}")
    print(f"Sin match: {no_match}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())