import json, glob
def rows_of(gold):
    out = []
    for n, line in enumerate(open(gold, encoding="utf-8"), 1):
        line = line.strip()
        if not line or line.startswith("#"): continue
        p = [x.strip() for x in line.split("|")]
        out.append((n, p[0], p[1] if len(p)>1 else "", p[2] if len(p)>2 else "", p[3] if len(p)>3 else ""))
    return out
for book, gold in [("trading","/tmp/v6/gold/verified_trading.txt"),
                   ("gatheral","/tmp/v6/gold/verified_gatheral.txt"),
                   ("prado","/tmp/v6/gold/verified_prado.txt")]:
    f = glob.glob(f"/tmp/v6/f3/{book}/*chunks.json")[0]
    chunks = {c["id"]: c for c in json.load(open(f, encoding="utf-8"))}
    print(f"################ {book}")
    for n, q, phrase, page, cid in rows_of(gold):
        if n not in (3, 8, 12, 15, 19): continue
        print(f"\n--- row {n} | Q: {q} | phrase: {phrase!r} | page: {page} | cited: {cid}")
        c = chunks.get(cid)
        print(f"    [cited chunk {cid}: pages={c['page']} path={c['path']} len={len(c['text'])}]")
        print("    " + c["text"].replace("\n", "\n    "))
