import argparse
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

STATIC_TARGETS = [
    ROOT / "artifacts/agent/e2e_battery_20",
    ROOT / "artifacts/agent/new_quote_battery",
    ROOT / "artifacts/agent/new_quote_battery_report.json",
    ROOT / "artifacts/agent/new_quote_battery_report.md",
    ROOT / "artifacts/agent/real_world_combo_battery",
    ROOT / "artifacts/rag/gemini_threshold_audit.json",
    ROOT / "reports/audits/_audit_results.json",
    ROOT / "reports/audits/full_rag_real_world_combo_audit.json",
    ROOT / "reports/audits/full_rag_real_world_combo_audit.md",
]

DEFAULT_GLOB_TARGETS = [
    "artifacts/agent/*combo*battery*",
    "reports/audits/full_rag_*_audit.json",
    "reports/audits/full_rag_*_audit.md",
]

OPTIONAL_GLOB_TARGETS = [
    "artifacts/agent/conv_*_turn_*.json",
]


def iter_targets(include_conversation_turns: bool):
    seen = set()
    for path in STATIC_TARGETS:
        if path.exists() and path not in seen:
            seen.add(path)
            yield path

    for pattern in DEFAULT_GLOB_TARGETS:
        for path in ROOT.glob(pattern):
            if path.exists() and path not in seen:
                seen.add(path)
                yield path

    if include_conversation_turns:
        for pattern in OPTIONAL_GLOB_TARGETS:
            for path in ROOT.glob(pattern):
                if path.exists() and path not in seen:
                    seen.add(path)
                    yield path


def remove_path(path: Path, dry_run: bool) -> str:
    rel_path = path.relative_to(ROOT)
    if dry_run:
        return f"DRY-RUN {rel_path}"
    if path.is_dir():
        shutil.rmtree(path)
    else:
        path.unlink()
    return f"REMOVED {rel_path}"


def main() -> int:
    parser = argparse.ArgumentParser(description="Limpia artefactos generados de baterías y auditorías ruidosas.")
    parser.add_argument("--dry-run", action="store_true", help="Muestra qué se eliminaría sin tocar archivos.")
    parser.add_argument(
        "--include-conversation-turns",
        action="store_true",
        help="Incluye los conv_*_turn_*.json generados bajo artifacts/agent.",
    )
    args = parser.parse_args()

    targets = list(iter_targets(include_conversation_turns=args.include_conversation_turns))
    if not targets:
        print("No se encontraron artefactos generados para limpiar.")
        return 0

    for path in targets:
        print(remove_path(path, dry_run=args.dry_run))

    print(f"Total: {len(targets)} artefacto(s) {'detectados' if args.dry_run else 'eliminados'}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())