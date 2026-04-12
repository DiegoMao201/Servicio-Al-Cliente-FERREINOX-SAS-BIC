import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

from sqlalchemy import text

from backend.ingest_technical_sheets import get_db_engine


STATUS_PATH = Path("artifacts/rag/reingest_watch_status_2026-04-12.json")
CURATED_REPORT_PATH = Path("artifacts/rag/rag_corpus_rebuild_report.json")
POLL_SECONDS = 120
STABLE_POLLS_REQUIRED = 4
MIN_READY_FOR_STABLE_EXIT = 300


def read_curated_target() -> int:
    if not CURATED_REPORT_PATH.exists():
        return 0
    payload = json.loads(CURATED_REPORT_PATH.read_text(encoding="utf-8"))
    return int(payload.get("curated_documents") or 0)


def read_counts() -> dict:
    engine = get_db_engine()
    with engine.connect() as conn:
        profile_row = conn.execute(text("""
            SELECT
                COUNT(*) AS total_profiles,
                COUNT(*) FILTER (WHERE extraction_status = 'ready') AS ready_profiles,
                COUNT(*) FILTER (WHERE COALESCE(profile_json ->> 'schema_version', '') = '2026-04-12.profile.v3') AS v3_profiles
            FROM public.agent_technical_profile
        """)).mappings().one()
        chunk_row = conn.execute(text("SELECT COUNT(*) AS total_chunks FROM public.agent_technical_doc_chunk")).mappings().one()
    return {
        "total_profiles": int(profile_row["total_profiles"] or 0),
        "ready_profiles": int(profile_row["ready_profiles"] or 0),
        "v3_profiles": int(profile_row["v3_profiles"] or 0),
        "total_chunks": int(chunk_row["total_chunks"] or 0),
    }


def write_status(payload: dict) -> None:
    STATUS_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATUS_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def run_command(script_name: str) -> None:
    subprocess.run([sys.executable, script_name], check=True)


def main() -> None:
    curated_target = read_curated_target()
    previous_counts = None
    stable_polls = 0

    while True:
        counts = read_counts()
        now = datetime.now().isoformat()

        if previous_counts == counts:
            stable_polls += 1
        else:
            stable_polls = 0

        status_payload = {
            "timestamp": now,
            "curated_target": curated_target,
            "counts": counts,
            "stable_polls": stable_polls,
            "poll_seconds": POLL_SECONDS,
        }
        write_status(status_payload)
        print(json.dumps(status_payload, ensure_ascii=False), flush=True)

        reached_target = curated_target > 0 and counts["ready_profiles"] >= curated_target
        stabilized_enough = stable_polls >= STABLE_POLLS_REQUIRED and counts["ready_profiles"] >= MIN_READY_FOR_STABLE_EXIT

        if reached_target or stabilized_enough:
            break

        previous_counts = counts
        time.sleep(POLL_SECONDS)

    run_command("export_rag_100_products_and_new_cases.py")
    run_command("compare_rag_audits.py")

    final_payload = {
        "timestamp": datetime.now().isoformat(),
        "status": "completed",
        "counts": read_counts(),
        "comparison_json": "artifacts/rag/rag_100_product_audit_comparison_2026-04-12.json",
        "comparison_md": "artifacts/rag/rag_100_product_audit_comparison_2026-04-12.md",
    }
    write_status(final_payload)
    print(json.dumps(final_payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()