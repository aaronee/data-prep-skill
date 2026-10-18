import json, sys, collections
c = collections.Counter()
for l in open(sys.argv[1]):
    r = json.loads(l); c[(r["rule"], r["text"][:90])] += 1
for (rule, t), n in c.most_common(40): print(f"{n:5d}  {rule:32s} {t}")
