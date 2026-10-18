#!/usr/bin/env python3
"""Replicates the gate's BM25 ranker EXACTLY from prep.py run_eval
(k1=1.5, b=0.75, toks=re.findall(r'[a-z0-9]+', text.lower()),
 idf=log(1+(N-df+0.5)/(df+0.5)), scored over all chunks, sorted(reverse=True) —
 Python stable sort: TIES are broken by chunk index (document order)).
For the 6 STRICT misses: prints the cited chunk's rank+score and the top-6
scores, and lists all chunks tied with the cited chunk's score."""
import importlib.util, os, sys, re, math, collections, json, glob

spec = importlib.util.spec_from_file_location("prepmod", os.path.expanduser("~/.agents/skills/data-prep/scripts/prep.py"))
prep = importlib.util.module_from_spec(spec); spec.loader.exec_module(prep)

def run(book, gold, miss_rows):
    f = glob.glob(f"/tmp/v6/f3/{book}/*chunks.json")[0]
    chunks = json.load(open(f, encoding="utf-8"))
    print(f"################ {book}  ({f})  N={len(chunks)}")
    toks = [re.findall(r"[a-z0-9]+", c["text"].lower()) for c in chunks]
    dl = [len(t) for t in toks]
    N = len(toks); avgdl = sum(dl) / N
    df = collections.Counter()
    for tv in toks:
        df.update(set(tv))
    idf = {t: math.log(1 + (N - df[t] + 0.5) / (df[t] + 0.5)) for t in df}
    k1, b = 1.5, 0.75
    def bm25(qt, ct):
        tf = collections.Counter(ct); s = 0.0
        for t in qt:
            if t not in idf: continue
            f = tf[t]
            s += idf[t] * f * (k1 + 1) / (f + k1 * (1 - b + b * len(ct) / max(avgdl, 1)))
        return s
    by_id = {c["id"]: i for i, c in enumerate(chunks)}
    rows = []
    for line in open(gold, encoding="utf-8"):
        line = line.strip()
        if not line or line.startswith("#"): continue
        parts = [p.strip() for p in line.split("|")]
        rows.append((parts[0], parts[1] if len(parts) > 1 else None,
                     parts[2] if len(parts) > 2 else None,
                     parts[3] if len(parts) > 3 else None))
    for i, (q, phrase, gpage, cid) in enumerate(rows, 1):
        if i not in miss_rows: continue
        qt = re.findall(r"[a-z0-9]+", q.lower())
        scores = [bm25(qt, t) for t in toks]
        ranked = sorted(range(N), key=lambda j: scores[j], reverse=True)  # stable: ties -> lower index first
        pos = {j: r for r, j in enumerate(ranked, 1)}
        cj = by_id[cid]
        print(f"\nQ{i} (cited {cid}, gold page {gpage}, phrase {phrase!r})")
        print(f"  Q: {q}")
        print(f"  cited {cid}: score={scores[cj]:.6f} rank={pos[cj]}  pages={chunks[cj]['page']}")
        # all chunks strictly above / tied / first-below the cited score
        above = [j for j in range(N) if scores[j] > scores[cj]]
        tied  = [j for j in range(N) if scores[j] == scores[cj]]
        print(f"  chunks with score > cited : {len(above)}")
        print(f"  chunks with score == cited: {len(tied)} -> {[chunks[j]['id'] for j in tied][:10]}"
              f"{' ...' if len(tied) > 10 else ''}")
        print(f"  top-6 (rank, id, pages, score):")
        for r, j in enumerate(ranked[:6], 1):
            pg = chunks[j]["page"]; pg = f"p{pg[0]}-{pg[1]}" if pg else "text"
            mark = "  <== CITED" if j == cj else ""
            print(f"    {r}. {chunks[j]['id']} {pg:10s} {scores[j]:.6f}{mark}")
    print()

run("trading", "/tmp/v6/gold/verified_trading.txt", {2, 13})
run("gatheral", "/tmp/v6/gold/verified_gatheral.txt", {4, 5, 20})
run("prado", "/tmp/v6/gold/verified_prado.txt", {14})
