import json

with open('reports/audits/_audit_results.json','r',encoding='utf-8') as f:
    d = json.load(f)

p=w=fl=0
for item in d:
    s = item['status']
    if s=='PASS': p+=1
    elif s=='WARN': w+=1
    elif s=='FAIL': fl+=1

print(f'Audit (50 scenarios): PASS={p} WARN={w} FAIL={fl}')
print()
for item in d:
    if item['status'] in ('FAIL','WARN'):
        sc = str(item.get('scenario',''))
        print(item['status'] + " | " + sc[:80])
        det = str(item.get('details',''))
        if det:
            print("  " + det[:150])
