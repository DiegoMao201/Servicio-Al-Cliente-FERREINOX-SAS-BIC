from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parent
INPUT_CSV = ROOT / "artifacts" / "pintuco_public_site" / "pintuco_public_products.csv"
OUTPUT_DIR = ROOT / "artifacts" / "pintuco_public_site"

SUSPICIOUS_INVENTORY_TOKENS = {
    "kit",
    "brocha",
    "cinta",
    "gastos",
    "varios",
    "promo",
    "pague",
    "lleve",
    "cat",
    "catalizador",
    "parte",
}

COMPONENT_HINTS = {
    "parte a",
    "parte b",
    "kit",
    "cat",
    "catalizador",
    "endurecedor",
    "componente a",
    "componente b",
    "a+b",
}

GENERIC_PUBLIC_NAMES = {
    "barniz",
    "esmalte sintetico",
    "pintura",
    "vinilo",
    "impermeabilizante",
}

BRAND_HINTS = [
    "viniltex",
    "pintulux",
    "koraza",
    "corrotec",
    "pintucoat",
    "inter",
    "aerocolor",
    "sellomax",
    "estucomastic",
    "aquablock",
    "siliconite",
    "pinturama",
    "barnex",
    "wash primer",
    "meg",
    "domestico",
]


def norm(value: object) -> str:
    text = "" if value is None else str(value)
    text = text.strip()
    if not text:
        return ""
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.lower()
    text = re.sub(r"\.pdf$", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def token_set(value: str) -> set[str]:
    return {tok for tok in re.split(r"[^a-z0-9]+", norm(value)) if tok}


def contains_brand_hint(text: str) -> bool:
    normalized = norm(text)
    return any(hint in normalized for hint in BRAND_HINTS)


def suspicious_inventory_match(text: str) -> bool:
    tokens = token_set(text)
    return any(token in tokens for token in SUSPICIOUS_INVENTORY_TOKENS)


def component_style_match(text: str) -> bool:
    normalized = norm(text)
    return any(hint in normalized for hint in COMPONENT_HINTS)


def overlap_score(public_name: str, inventory_name: str) -> float:
    public_tokens = token_set(public_name)
    inventory_tokens = token_set(inventory_name)
    if not public_tokens or not inventory_tokens:
        return 0.0
    shared = public_tokens & inventory_tokens
    return len(shared) / max(1, len(public_tokens))


def classify_row(row: pd.Series) -> tuple[str, str]:
    public_name = str(row.get("product_name") or "")
    summary = str(row.get("summary_public") or "")
    ficha = str(row.get("technical_sheet_url") or "")
    inv_name = str(row.get("inventory_match_name") or "")
    inv_canonical = str(row.get("canonical_family_from_inventory") or "")
    try:
        score = float(row.get("inventory_match_score") or 0)
    except Exception:
        score = 0.0

    overlap = max(overlap_score(public_name, inv_name), overlap_score(public_name, inv_canonical))
    has_min_content = len(summary.strip()) >= 80
    public_generic = norm(public_name) in GENERIC_PUBLIC_NAMES
    suspicious_inv = suspicious_inventory_match(inv_name) or suspicious_inventory_match(inv_canonical)
    component_inv = component_style_match(inv_name) or component_style_match(inv_canonical)
    has_brand = contains_brand_hint(public_name) or contains_brand_hint(summary)

    if not ficha:
        return "rechazado", "Sin ficha técnica pública; no usar como fuente para RAG"
    if suspicious_inv:
        return "rechazado", "El match contra inventario parece kit/accesorio/promoción o basura comercial"
    if component_inv:
        return "cuarentena", "El match apunta a componente o kit; revisar familia maestra manualmente"
    if score < 84:
        return "rechazado", "Match de inventario demasiado débil"
    if public_generic and overlap < 0.5:
        return "rechazado", "Nombre público demasiado genérico y sin correspondencia clara"
    if not has_min_content:
        return "cuarentena", "La página pública tiene poca densidad técnica; revisar manualmente"
    if not has_brand:
        return "cuarentena", "Falta señal de familia/marca suficientemente fuerte"
    if score >= 90 and overlap >= 0.6:
        return "seguro_para_enriquecimiento", "Fuente pública útil para enriquecer perfiles, no para reemplazar fichas"
    return "cuarentena", "Tiene valor, pero requiere revisión humana antes de enriquecer el RAG"


def main() -> int:
    df = pd.read_csv(INPUT_CSV)
    decisions = df.apply(classify_row, axis=1, result_type="expand")
    decisions.columns = ["decision", "decision_note"]
    result = pd.concat([df, decisions], axis=1)

    safe_df = result[result["decision"] == "seguro_para_enriquecimiento"].copy()
    quarantine_df = result[result["decision"] == "cuarentena"].copy()
    reject_df = result[result["decision"] == "rechazado"].copy()

    safe_path = OUTPUT_DIR / "pintuco_public_products_safe.csv"
    quarantine_path = OUTPUT_DIR / "pintuco_public_products_quarantine.csv"
    reject_path = OUTPUT_DIR / "pintuco_public_products_rejected.csv"
    summary_path = OUTPUT_DIR / "pintuco_public_quarantine_summary.json"

    safe_df.to_csv(safe_path, index=False, encoding="utf-8-sig")
    quarantine_df.to_csv(quarantine_path, index=False, encoding="utf-8-sig")
    reject_df.to_csv(reject_path, index=False, encoding="utf-8-sig")

    summary = {
        "total": int(len(result)),
        "safe": int(len(safe_df)),
        "quarantine": int(len(quarantine_df)),
        "rejected": int(len(reject_df)),
        "safe_path": str(safe_path),
        "quarantine_path": str(quarantine_path),
        "reject_path": str(reject_path),
        "decision_counts": result["decision"].value_counts(dropna=False).to_dict(),
    }
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())