import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from backend.main import get_db_engine  # noqa: E402
from sqlalchemy import text  # noqa: E402

OUTPUT_JSON = ROOT / "reports" / "audits" / "technical_profile_surface_conflicts.json"
OUTPUT_MD = ROOT / "reports" / "audits" / "technical_profile_surface_conflicts.md"


def load_profiles() -> list[dict]:
    query = text(
        """
        SELECT canonical_family,
               source_doc_filename,
               COALESCE(profile_json -> 'surface_targets', '[]'::jsonb) AS surface_targets,
               COALESCE(profile_json -> 'restricted_surfaces', '[]'::jsonb) AS restricted_surfaces,
               COALESCE(profile_json -> 'solution_guidance' -> 'restricted_surfaces', '[]'::jsonb) AS guidance_restricted
        FROM public.agent_technical_profile
        WHERE extraction_status = 'ready'
        ORDER BY canonical_family
        """
    )
    engine = get_db_engine()
    with engine.connect() as conn:
        return [dict(row) for row in conn.execute(query).mappings().all()]


def normalize_values(values) -> list[str]:
    return sorted({str(value).strip().lower() for value in (values or []) if str(value).strip()})


def build_report() -> dict:
    rows = load_profiles()
    conflicts = []
    overlap_counter = Counter()
    for row in rows:
        targets = set(normalize_values(row.get("surface_targets")))
        restricted = set(normalize_values(row.get("restricted_surfaces")))
        guidance = set(normalize_values(row.get("guidance_restricted")))
        overlap = sorted((restricted | guidance) & targets)
        if not overlap:
            continue
        for value in overlap:
            overlap_counter[value] += 1
        conflicts.append(
            {
                "canonical_family": row.get("canonical_family"),
                "source_doc_filename": row.get("source_doc_filename"),
                "overlap": overlap,
                "surface_targets": sorted(targets),
                "restricted_surfaces": sorted(restricted),
                "guidance_restricted": sorted(guidance),
            }
        )

    return {
        "ready_profiles": len(rows),
        "conflict_profiles": len(conflicts),
        "overlap_breakdown": dict(sorted(overlap_counter.items())),
        "examples": conflicts[:100],
    }


def render_markdown(report: dict) -> str:
    lines = [
        "# Auditoría de conflictos de superficies en perfiles técnicos",
        "",
        f"- Perfiles listos: {report['ready_profiles']}",
        f"- Perfiles con conflicto target/restricción: {report['conflict_profiles']}",
        "",
        "## Desglose por superficie",
        "",
    ]

    for surface, count in report["overlap_breakdown"].items():
        lines.append(f"- {surface}: {count}")

    lines.extend(["", "## Ejemplos", ""])
    for item in report["examples"][:30]:
        lines.append(f"### {item['canonical_family']}")
        lines.append("")
        lines.append(f"- Fuente: {item['source_doc_filename']}")
        lines.append(f"- Overlap: {', '.join(item['overlap'])}")
        lines.append(f"- Targets: {', '.join(item['surface_targets'])}")
        lines.append(f"- Restricted: {', '.join(item['restricted_surfaces'])}")
        lines.append(f"- Guidance restricted: {', '.join(item['guidance_restricted'])}")
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def main() -> int:
    report = build_report()
    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    OUTPUT_MD.write_text(render_markdown(report), encoding="utf-8")
    print(json.dumps({
        "ready_profiles": report["ready_profiles"],
        "conflict_profiles": report["conflict_profiles"],
        "overlap_breakdown": report["overlap_breakdown"],
        "output_json": str(OUTPUT_JSON),
        "output_md": str(OUTPUT_MD),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())