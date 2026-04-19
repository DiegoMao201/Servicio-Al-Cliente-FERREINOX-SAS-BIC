import json
from collections import Counter

with open("test_super_agent_results.json", encoding="utf-8") as f:
    d = json.load(f)

a = d.get("agent", {})
print(f"AGENT: PASS={a.get('pass',0)} WARN={a.get('warn',0)} FAIL={a.get('fail',0)}")

convs = d.get("agent_conversations", [])
cats = Counter()
cat_fail = Counter()
cat_warn = Counter()
fails = []
for c in convs:
    cat = c.get("category", "?")
    for t in c.get("turns", []):
        cats[cat] += 1
        if t.get("status") == "FAIL":
            cat_fail[cat] += 1
            fails.append((c.get("name", "?"), cat, t.get("details", [])))
        elif t.get("status") == "WARN":
            cat_warn[cat] += 1

print()
for cat in sorted(cats):
    p = cats[cat] - cat_fail[cat] - cat_warn[cat]
    print(f"  {cat:35s}: P={p:2d} W={cat_warn[cat]:2d} F={cat_fail[cat]:2d}")

print(f"\nFAILS ({len(fails)}):")
for name, cat, details in fails:
    print(f"  [{cat}] {name}")
    for d2 in details[:3]:
        print(f"    {d2}")

# Also check turns for fail info
print("\n--- DETAILED FAIL ANALYSIS ---")
for c in convs:
    if c.get("failed", 0) > 0:
        cat = c.get("category", "?")
        name = c.get("name", "?")
        f_count = c.get("failed", 0)
        print(f"  [{cat}] {name} (fails={f_count})")
