import json

with open("test_super_agent_results.json", encoding="utf-8") as f:
    d = json.load(f)

agr = d.get("agent_results", {})
for cv in agr.get("conversations", []):
    if cv.get("warns", 0) > 0 or cv.get("fails", 0) > 0:
        print(f"CONV: {cv['name']} -> {cv['pass']}/{cv['total']} PASS, {cv['warns']} WARN, {cv['fails']} FAIL")
        for t in cv.get("turns", []):
            if t.get("status") != "pass":
                print(f"  Turn: {t['user_msg'][:70]!r} => {t['status']}")
                for w in t.get("warnings", []):
                    print(f"    W: {w}")
                for e in t.get("errors", []):
                    print(f"    E: {e}")
