import json

d = json.load(open("artifacts/agent/conv_004_turn_02.json", encoding="utf-8"))
for tc in d["result"].get("tool_calls", []):
    name = tc.get("name", "?")
    args = tc.get("args", {})
    res = tc.get("result", "")
    print(f"TOOL: {name}")
    print(f"ARGS: {args}")
    if isinstance(res, str):
        print(f"RESULT: {res[:300]}")
    print()
print("RESPONSE:", d["result"]["response_text"][:600])
