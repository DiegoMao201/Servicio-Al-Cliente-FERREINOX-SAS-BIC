import json

with open('test_super_agent_results.json','r',encoding='utf-8') as f:
    data = json.load(f)

print(f"Timestamp: {data.get('timestamp','N/A')}")
print(f"Version: {data.get('version','N/A')}")

# Summary stats
rag_sum = data.get('rag',{})
agent_sum = data.get('agent',{})
total_sum = data.get('total',{})
print(f"\nRAG Summary: {rag_sum}")
print(f"Agent Summary: {agent_sum}")  
print(f"Total Summary: {total_sum}")

# Agent conversations detail
cats = {}
fails_detail = []
warns_detail = []

for conv in data.get('agent_conversations',[]):
    cat = conv.get('category','unknown')
    cid = conv.get('id', conv.get('conversation_id','?'))
    for turn in conv.get('turns',[]):
        v = turn.get('verdict','')
        if cat not in cats:
            cats[cat] = {'pass':0,'warn':0,'fail':0}
        if v == 'PASS': cats[cat]['pass'] += 1
        elif v == 'WARN':
            cats[cat]['warn'] += 1
            warns_detail.append(f"  [{cat}] Conv {cid} Turn {turn.get('turn','?')}: {turn.get('reason','')[:120]}")
        elif v == 'FAIL':
            cats[cat]['fail'] += 1
            fails_detail.append(f"  [{cat}] Conv {cid} Turn {turn.get('turn','?')}: {turn.get('reason','')[:120]}")

if cats:
    total_p, total_w, total_f = 0,0,0
    for cat, r in sorted(cats.items()):
        p,w,f_ = r['pass'],r['warn'],r['fail']
        total_p += p; total_w += w; total_f += f_
        status = 'PASS' if f_==0 and w==0 else ('WARN' if f_==0 else 'FAIL')
        print(f"  {cat}: {p}P/{w}W/{f_}F [{status}]")
    print(f"\nTOTAL AGENT: {total_p}P/{total_w}W/{total_f}F = {total_p+total_w+total_f} turns")

print(f"\n--- AGENT FAILS ---")
for f in fails_detail: print(f)
print(f"\n--- AGENT WARNS ---")
for w in warns_detail: print(w)

# RAG details
print("\n\n=== RAG DETAILS ===")
rag_details = data.get('rag_details',[])
rcats = {}
rfails = []
rwarns = []
for t in rag_details:
    cat = t.get('category','unknown')
    if cat not in rcats:
        rcats[cat] = {'pass':0,'warn':0,'fail':0}
    v = t.get('verdict','')
    if v == 'PASS': rcats[cat]['pass'] += 1
    elif v == 'WARN':
        rcats[cat]['warn'] += 1
        rwarns.append(f"  [{cat}] {t.get('id','?')}: {t.get('query','')[:60]}")
    elif v == 'FAIL':
        rcats[cat]['fail'] += 1
        rfails.append(f"  [{cat}] {t.get('id','?')}: {t.get('query','')[:60]} -> {t.get('reason','')[:100]}")

rp,rw,rf = 0,0,0
for cat, r in sorted(rcats.items()):
    p,w,f_ = r['pass'],r['warn'],r['fail']
    rp += p; rw += w; rf += f_
    status = 'PASS' if f_==0 and w==0 else ('WARN' if f_==0 else 'FAIL')
    print(f"  {cat}: {p}P/{w}W/{f_}F [{status}]")

print(f"\nTOTAL RAG: {rp}P/{rw}W/{rf}F = {rp+rw+rf} tests")
print(f"\n--- RAG FAILS ---")
for f in rfails: print(f)
print(f"\n--- RAG WARNS ---")
for w in rwarns: print(w)
