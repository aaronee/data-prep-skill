# data-prep — a RAG-prep skill for LiteParse (`lit`) document output

A local agent **skill** (in the `pi`/Claude-skill style: `SKILL.md` + references +
stdlib-only Python) that turns LiteParse (`lit`) PDF/DOCX extraction output
(`*.lit.json`) into **RAG-ready text and chunks**: removes running headers,
footnotes, TOC, boilerplate and front/back matter, rewraps prose, and emits
section-aware chunks with a full removal audit. Includes a built-in
retrieval-quality gate (BM25 eval against a gold question file) and an
optional LLM pass that drops suspected boilerplate/legal chunks.

This repository is the **development archive** of the skill: the current code
(v6, 2026-10-18), all per-round reports, and the raw evidence files produced
by the audit rounds (v6, v7).

```
data-prep-skill/
├── skill/                      ← the skill, exactly as installed (~/.agents/skills/data-prep)
│   ├── SKILL.md                ← entry point: when/how to use, runbook
│   ├── references/rules.md     ← removal rules R1–R8, chunking, gate semantics, changelog
│   ├── scripts/
│   │   ├── prep.py             ← pipeline: lit.json → clean.txt + chunks.json + removed.jsonl + report
│   │   ├── filter_llm.py       ← optional LLM pass: keep/drop suspect chunks, cached, resumable
│   │   └── make_eval_candidates.py  ← gold-question generator (30 questions; human must rewrite)
│   ├── tests/                  ← 49 unit tests (stdlib unittest), incl. F-series hardening
│   ├── tools/removed_summary.py
│   ├── docs/llm-run-log.md     ← live LLM-filter run records (key-free)
│   └── gold/                   ← verified gold question files for the 3 real books
└── support/
    ├── data-prep-skill-report-v6.md      ← v6 fix-round report (19-file hash table, all raw outputs)
    ├── data-prep-HANDOFF.md              ← v5→v6 handoff notes
    ├── v6_support_files/                 ← v6 audit evidence (rerun proofs, F9 episodes, gate scores, …)
    ├── v7/                               ← TASK-v7 spec + REPORT-v7.md
    └── v7_support_files/                 ← v7 evidence-round output (E1–E5, 14 files)
```

## The pipeline

```
book.lit.json (LiteParse output: pages → text items with font/position)
   │  prep.py  (stdlib only, ~2700 lines)
   ├─ R1/R1b running-header & margin-repeat removal (frequency across pages)
   ├─ R2 page numbers · R3 chart ticks · R4/R5 TOC · R6 front/back-matter sections
   ├─ R8 footnotes (position zone + monospace fonts)
   ├─ rewrap prose, detect headings, build section-aware paragraphs
   ├─ chunks.json (id, path, page range, text, embed_text, sha256) + 150% size cap
   ├─ removed.jsonl (every removed line: page, rule, text) → removed_summary.py
   └─ --eval gold.txt → BM25 (k1=1.5, b=0.75) LENIENT/STRICT hit@3 + MRR gate
        --min-hit 0.8 fails closed (needs ≥20 STRICT-graded rows, ≥10 distinct
        cited chunks, no duplicate/leaky rows)
```

Optional LLM pass (`filter_llm.py`): flags suspicious chunks (boilerplate,
index-like, bibliography-like heuristics), asks the model `keep | content|legal|boilerplate`,
writes `chunks.filtered.json` + `dropped.jsonl`, caches verdicts by
`sha256(chunk|model|prompt-hash)` so reruns cost zero API calls. Resumable after
network failure.

### Books validated (real documents, 2026-10-18)

| book | pages | chunks | gate STRICT hit@3 | gate |
|---|---|---|---|---|
| Trading Volatility… (Bennett & Gil) | 214 | 271 | 90% (18/20) | PASS |
| The Volatility Surface (Gatheral) | 210 | 159 | 85% (17/20) | PASS |
| Advances in Financial ML (de Prado) | 393 | 356 | 95% (19/20) | PASS |

v6 output is **byte-identical** to v5 on all three books (SHA-256 verified);
regression-tested that way after every round.

## Development history

| round | what happened | report |
|---|---|---|
| v1–v4 (2026-10-15→17) | built pipeline + R1–R8 + eval gate; fixed F1–F5 class defects (recurring-header false positives, TOC leaks, gate text-page handling, encoding) | `support/` history in `references/rules.md` changelog v3.0→v3.18 |
| v5 (2026-10-18) | hardening + gold-gate validation (rejects leakey/duplicate rows, `--min-questions`); live LLM run first happened on v4 code | `v6` report §5 context; HANDOFF |
| **v6** (2026-10-18) | fix round for v5 audit findings G1–G4: `--min-chunks` citation-diversity check, `--min-hit`-without-`--eval` → exit 2, LLM cache saved on abort, 7 new tests. **49/49 tests pass, 0 ResourceWarnings.** Live LLM re-run: 6 suspects → 2 legal drops, **0 wrong drops**, rerun 0 API calls, byte-identical. | `support/data-prep-skill-report-v6.md` |
| **v7** (2026-10-18) | read-only **evidence round** for the F9 reviewer: 5 scripts (E1–E5), replication checks, gold page check, bib-leak scan, gatheral probes. No code changed; skill folder proven byte-unchanged. | `support/v7/REPORT-v7.md` |

## Current issues

### F9 — HIGH: R6 drop state eats chapter openers (pre-existing since ≤ v1, unpatched)

R6 (`drop_until_heading`) drops everything after a front/back-matter heading
(`REFERENCES`, `BIBLIOGRAPHY`, `Acknowledgments`, …) until the next heading it
recognises. Running headers of the *next* chapter are consumed earlier by R1/R1b,
so they never release the state → **the next chapter's opening pages are deleted**.

Measured (v6/v7, exact against `removed.jsonl`):

| book | R6-body lines lost | episodes | damage |
|---|---|---|---|
| prado | **1,064 lines / 75,156 chars** | 23 | ch4, ch13, ch14, ch21 … openers lost |
| gatheral | 494 lines | 3 | **entire Chapter-1 opener (pp.32–35) lost**; all 8 probe sentences 0 hits in clean.txt |
| trading | 24 lines | 3 | back matter only — harmless |

Code: `skill/scripts/prep.py` main loop, state `drop_until_heading`; trigger
`norm_strong(t) in front_matter`, release only when `is_head` is True. v5↔v6
identical in this region (proven in `support/v6_support_files/40_f9_code.txt`).
Per-episode trigger/release/marker analysis: `support/v7_support_files/2*_*.txt`.
Fix must be regression-tested with a failing test first, then re-verify all three
books (chunk diff + gates).

### Open, lower severity

1. **Bibliography in chunks (prado):** v7 `bib_leak.py` found **13/356 prado
   chunks** with ≥3 author-initials-(year) patterns that should be dropped.
   The LLM filter was run live only on trading; gatheral+prado still need it.
2. **Gold files are LLM-authored, not human-verified.** v7 `gold_page_check.py`
   (all 60 rows): 44 MATCH, 13 OFF_BY_ONE, 2 WRONG_PAGE (both gatheral),
   1 PHRASE_NOT_ON_ANY_PAGE-class probe. Gold pages all equal the cited chunk's
   first page (60/60), so the gate is consistent, but the gold itself needs
   human pass. No gold was corrected in any round (rule).
3. **Retrieval gate misses are real:** the 6 STRICT misses (of 60) are genuine
   BM25 retrieval misses (cited chunks rank 4–157, never in top-3), not
   boundary artifacts — scores in `support/v6_support_files/50_gate_scores_6misses.txt`.
   The v5 report's "boundary artifact" explanation was wrong (corrected in the
   v6 report).
4. **Unexplained v5-report hashes:** prefixes `254cf54b`/`aedab848`/`12d83851`
   in the v5 report match **no file on disk** (exhaustive search, `support/v6_support_files/62_*`);
   the v6↔v5 regression itself is byte-verified as identical.
5. Doc inaccuracy (minor): `SKILL.md` says LLM results are cached by chunk
   `sha256`; actual key is `sha256(chunk|model|prompt-hash)[:24]`.

## Next steps (planned, not started)

- **v8 — F9 fix + fidelity:** reviewer-authored fix for F9 (failing test first:
  synthetic book with per-chapter `References` + next chapter), then re-run all
  three books (byte-diff of recovered content + gates). Add a **fidelity
  sampling script** as a regression test: ~30 random pages/book, verify sampled
  raw-PDF sentences survive into `clean.txt` (≥95% pass bar). Run the LLM filter
  live on gatheral + prado (in the user's terminal; key stays in env).
- **v9 — retrieval + end-to-end quality:** human-verify/fix the 60 gold rows,
  add ~20–30 fresh questions/book, re-run the gate; then a minimal end-to-end
  RAG run (embed top-5 → answer ~50 verified questions → LLM-judge
  faithfulness/context-precision per RAGAS-style metrics) with a documented
  pass bar (proposal: faithfulness ≥ 90%, hit@3 ≥ 85%).
- Housekeeping: `SKILL.md` cache-key sentence; consider excluding in-body
  reference sections from the R6 front-matter set by position.

## Running it

```bash
# one-off (see skill/SKILL.md for the full runbook)
python3 skill/scripts/prep.py ~/Downloads/book.lit.json --outdir out/
python3 skill/scripts/prep.py ~/Downloads/book.lit.json --outdir out/ \
    --eval skill/gold/verified_trading.txt --min-hit 0.8
# tests (stdlib only, no install)
python3 -m unittest discover -s skill/tests
```

`filter_llm.py` needs `LLM_API_KEY` **in the environment only** — it is never
written, logged or committed anywhere in this repo. Local endpoint used so far:
`http://localhost:8000/v1/chat/completions`.

## Auditability

- Every round's raw outputs are kept unsummarized in `support/`.
- Skill state is snapshot-hashed at the start and end of each round
  (`00_hash_before.txt` / `01_hash_after.txt` in the v7 support files); v6 is
  pinned by the 19-file hash table in `support/data-prep-skill-report-v6.md` §9.
- `docs/llm-run-log.md` records live LLM-filter runs (verdicts, counts, hashes)
  without any secrets.
