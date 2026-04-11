#!/usr/bin/env python3
"""Auditoría rápida de perfiles técnicos estructurados."""

from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy import text

from ingest_technical_sheets import get_db_engine


def main():
    engine = get_db_engine()
    with engine.connect() as conn:
        totals = conn.execute(text("""
            SELECT
                COUNT(*) AS total_profiles,
                AVG(completeness_score) AS avg_score,
                COUNT(*) FILTER (WHERE completeness_score >= 0.75) AS strong_profiles,
                COUNT(*) FILTER (WHERE extraction_status = 'ready') AS ready_profiles
            FROM public.agent_technical_profile
        """)).mappings().one()
        sample_rows = conn.execute(text("""
            SELECT
                canonical_family,
                marca,
                completeness_score,
                profile_json -> 'commercial_context' ->> 'summary' AS summary,
                jsonb_array_length(COALESCE(profile_json -> 'application' -> 'surface_preparation', '[]'::jsonb)) AS prep_steps,
                jsonb_array_length(COALESCE(profile_json -> 'application' -> 'dilution' -> 'ratio_texts', '[]'::jsonb)) AS dilution_notes,
                jsonb_array_length(COALESCE(profile_json -> 'alerts' -> 'critical', '[]'::jsonb)) AS critical_alerts
            FROM public.agent_technical_profile
            WHERE extraction_status = 'ready'
            ORDER BY completeness_score DESC, canonical_family
            LIMIT 50
        """)).mappings().all()

    report = {
        "total_profiles": int(totals["total_profiles"] or 0),
        "avg_score": round(float(totals["avg_score"] or 0), 4),
        "strong_profiles": int(totals["strong_profiles"] or 0),
        "ready_profiles": int(totals["ready_profiles"] or 0),
        "top_profiles": [dict(row) for row in sample_rows],
    }

    output_dir = Path(__file__).resolve().parent.parent / "artifacts" / "rag"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "technical_profile_audit.json"
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print("=" * 80)
    print("AUDITORÍA DE PERFILES TÉCNICOS")
    print("=" * 80)
    print(f"Perfiles listos: {report['ready_profiles']}")
    print(f"Promedio completitud: {report['avg_score']}")
    print(f"Perfiles fuertes (>=0.75): {report['strong_profiles']}")
    print(f"Reporte: {output_path}")


if __name__ == "__main__":
    main()