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
                COUNT(*) FILTER (WHERE extraction_status = 'ready') AS ready_profiles,
                                COUNT(*) FILTER (
                                        WHERE extraction_status = 'ready'
                                            AND COALESCE(profile_json ->> 'schema_version', '') = '2026-04-12.profile.v3'
                                ) AS profiles_v3,
                COUNT(*) FILTER (
                    WHERE extraction_status = 'ready'
                                            AND jsonb_typeof(COALESCE(profile_json -> 'surface_targets', '[]'::jsonb)) = 'array'
                                            AND jsonb_array_length(COALESCE(profile_json -> 'surface_targets', '[]'::jsonb)) > 0
                ) AS profiles_with_surfaces,
                COUNT(*) FILTER (
                    WHERE extraction_status = 'ready'
                                            AND jsonb_typeof(COALESCE(profile_json -> 'application_methods', '[]'::jsonb)) = 'array'
                                            AND jsonb_array_length(COALESCE(profile_json -> 'application_methods', '[]'::jsonb)) > 0
                ) AS profiles_with_methods,
                COUNT(*) FILTER (
                    WHERE extraction_status = 'ready'
                                            AND jsonb_typeof(COALESCE(profile_json -> 'alerts', '[]'::jsonb)) = 'array'
                                            AND jsonb_array_length(COALESCE(profile_json -> 'alerts', '[]'::jsonb)) > 0
                ) AS profiles_with_critical_alerts,
                COUNT(*) FILTER (
                    WHERE extraction_status = 'ready'
                                            AND jsonb_typeof(COALESCE(profile_json -> 'diagnostic_questions', '[]'::jsonb)) = 'array'
                                            AND jsonb_array_length(COALESCE(profile_json -> 'diagnostic_questions', '[]'::jsonb)) > 0
                                ) AS profiles_with_diagnostic_questions,
                                COUNT(*) FILTER (
                                        WHERE extraction_status = 'ready'
                                            AND jsonb_typeof(COALESCE(profile_json -> 'restricted_surfaces', '[]'::jsonb)) = 'array'
                                            AND jsonb_array_length(COALESCE(profile_json -> 'restricted_surfaces', '[]'::jsonb)) > 0
                                ) AS profiles_with_restricted_surfaces,
                                COUNT(*) FILTER (
                                        WHERE extraction_status = 'ready'
                                            AND jsonb_typeof(COALESCE(profile_json -> 'source_excerpts', '[]'::jsonb)) = 'array'
                                            AND jsonb_array_length(COALESCE(profile_json -> 'source_excerpts', '[]'::jsonb)) > 0
                                ) AS profiles_with_source_excerpts
            FROM public.agent_technical_profile
        """)).mappings().one()
        sample_rows = conn.execute(text("""
            SELECT
                canonical_family,
                marca,
                completeness_score,
                profile_json -> 'commercial_context' ->> 'summary' AS summary,
                                jsonb_array_length(COALESCE(profile_json -> 'surface_targets', '[]'::jsonb)) AS compatible_surfaces,
                                jsonb_array_length(COALESCE(profile_json -> 'restricted_surfaces', '[]'::jsonb)) AS restricted_surfaces,
                jsonb_array_length(COALESCE(profile_json -> 'application' -> 'surface_preparation', '[]'::jsonb)) AS prep_steps,
                                jsonb_array_length(COALESCE(profile_json -> 'application_methods', '[]'::jsonb)) AS application_methods,
                jsonb_array_length(COALESCE(profile_json -> 'application' -> 'dilution' -> 'ratio_texts', '[]'::jsonb)) AS dilution_notes,
                                jsonb_array_length(COALESCE(profile_json -> 'alerts', '[]'::jsonb)) AS critical_alerts,
                                jsonb_array_length(COALESCE(profile_json -> 'diagnostic_questions', '[]'::jsonb)) AS diagnostic_questions,
                                jsonb_array_length(COALESCE(profile_json -> 'source_excerpts', '[]'::jsonb)) AS source_excerpts
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
        "profiles_v3": int(totals["profiles_v3"] or 0),
        "profiles_with_surfaces": int(totals["profiles_with_surfaces"] or 0),
        "profiles_with_methods": int(totals["profiles_with_methods"] or 0),
        "profiles_with_critical_alerts": int(totals["profiles_with_critical_alerts"] or 0),
        "profiles_with_diagnostic_questions": int(totals["profiles_with_diagnostic_questions"] or 0),
        "profiles_with_restricted_surfaces": int(totals["profiles_with_restricted_surfaces"] or 0),
        "profiles_with_source_excerpts": int(totals["profiles_with_source_excerpts"] or 0),
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
    print(f"Perfiles schema v3: {report['profiles_v3']}")
    print(f"Promedio completitud: {report['avg_score']}")
    print(f"Perfiles fuertes (>=0.75): {report['strong_profiles']}")
    print(f"Con superficies compatibles: {report['profiles_with_surfaces']}")
    print(f"Con superficies restringidas: {report['profiles_with_restricted_surfaces']}")
    print(f"Con métodos de aplicación: {report['profiles_with_methods']}")
    print(f"Con alertas críticas: {report['profiles_with_critical_alerts']}")
    print(f"Con preguntas diagnósticas: {report['profiles_with_diagnostic_questions']}")
    print(f"Con excerptos fuente: {report['profiles_with_source_excerpts']}")
    print(f"Reporte: {output_path}")


if __name__ == "__main__":
    main()