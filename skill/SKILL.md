---
name: data-prep
description: Clean LiteParse (`lit`) PDF/DOCX output into RAG-ready text and chunks — removes headers/footers, chart ticks, TOC, boilerplate; rewraps prose; emits section-aware chunks with a removed-line audit. Use after the liteparse skill has parsed a document (or a .lit.json cache exists) when RAG-ready artifacts are needed.
---

# data-prep

Deterministic cleanup + chunking for RAG. All rules are data-driven (geometry,
recurrence, vocabulary) — nothing is hardcoded per document.

## Run

```bash
python3 ~/.agents/skills/data-prep/scripts/prep.py <doc.pdf | doc.lit.json | doc.md | doc.txt>
```

Common options:

| flag | meaning |
|---|---|
| `--ocr` | run OCR (scanned documents only; costs ~1.6s/page) |
| `--eval QFILE` | retrieval eval with gold answers (see below) |
| `--min-hit F` | eval gate: exit 1 if STRICT hit@3 < F, if fewer than --min-questions graded, or if any invalid/TODO row exists |
| `--outdir DIR` | output location (relative, absolute, subfolder — all work) |
| `--chunk-tokens N` | chunk target, default 400 tokens (~1600 chars), hard cap 150% |
| `--disable R1,R3` | ablation: switch rules off (R1…R8; R1b has its own switch) |
| `--footnote-zone F` | R8: bottom-band fraction of page height (default 0.72) |
| `--footnote-ratio F` | R8: max cell height as fraction of body height (default 0.85) |
| `--code-fonts "A,B"` | R8: extra font-name substrings treated as code (never dropped) |
| `--min-questions N` | with --min-hit: need at least N STRICT-graded questions (default 20); also fails on invalid/TODO rows |
| `--min-chunks N` | with --min-hit: gold rows must cite at least N distinct chunks (default 10); rows whose key phrase appears in the question, or that duplicate another question, are invalid; `--min-hit` without `--eval` is an error |
| `--text-recur-min N` | text mode: lines repeated ≥N times are recurring headers (default 8) |
| `--margin-band F` | R1b: page top/bottom fraction treated as margin (default 0.08) |
| `--margin-min-pages N` | R1b: a margin line must repeat on ≥N pages (default 4) |
| `--recur-frac / --zone / --gap-cut / --drop-sections` | threshold overrides |

A `.lit.json` parse cache is written next to the PDF — reruns skip `lit`
(0.8s end-to-end on a 214-page book). `--no-cache` forces re-parse.

## Outputs (next to input or in --outdir)

| file | what |
|---|---|
| `<name>.clean.txt` | cleaned text, `--- Page N ---` sections (cross-page paragraphs appear on each spanned page) |
| `<name>.chunks.json` | chunks: `id, source, chunk_index, page [first,last], page_label (printed), path (section heading chain), text, embed_text, sha256` |
| `<name>.report.txt` | **built-in verification** — retention table, most-lost tokens, warnings, totals |
| `<name>.removed.jsonl` | one row per dropped line: `page, page_label, rule, text` — audit any removal |

## Verification (non-negotiable, before indexing)

1. Read the report. Retention WARNING (<95%) on a content word → inspect
   `removed.jsonl` for that word. Warnings for possible two-column layout →
   check a page manually.
2. `--eval` with gold answers. Question file format, one per line:
   `question | key phrase | expected page` (page = PDF page, not printed);
   optional 4th column `chunk id` — a row that cites a chunk is validated
   (the phrase must occur in that chunk; stale/leaky gold rows are excluded
   and reported, not counted).
   Plain `question` works but is ungraded. Two metrics over real BM25
   (k1=1.5, b=0.75): **LENIENT** = chunk contains the phrase OR covers the
   page; **STRICT** = BOTH (a chunk on the right page that says it). Grade
   on **STRICT** — LENIENT can pass on a right-phrase/wrong-page chunk.
   Run on **3+ different documents**; gate with `--min-hit 0.8`.
   No gold file yet? `scripts/make_eval_candidates.py <name>.chunks.json`
   writes 20 spread, deterministic candidates (one content-word key phrase +
   PDF page + chunk id, question never quotes the answer, content chunks
   only) that a human verifies/rewrites before grading.
   STRICT grading needs a numeric page. Text-mode inputs (.md/.txt) have no pages, so they can only be
   graded LENIENT; the gate needs a PDF/lit-JSON run. Candidate files contain `TODO` rows: replace the
   TODO text with a real question (never use the key word), or delete the row.
   Optional embedding retrieval: `--embed-cmd '<text→vector command>'`.

## LLM pass (filler chunks: legal, bio, acknowledgments, index)

```bash
python3 ~/.agents/skills/data-prep/scripts/filter_llm.py <name>.chunks.json \
    --endpoint http://localhost:8000/v1/chat/completions --model qwen2.5 \
    [--api-key KEY] [--max-tokens N] --dry-run
```

- API key: `--api-key` or the `LLM_API_KEY` env var, sent as
  `Authorization: Bearer …`; never printed, never cached. Transient errors
  (401/timeout) default to keep and are NOT cached, so a rerun retries.
- Heuristic pre-selection marks only *suspect* chunks; the LLM is the decider.
  Non-suspects are auto-kept (that's what makes this cheap: a few calls, not hundreds).
- Schema-constrained JSON: `keep, type, summary, keywords`. Types: content,
  toc, index, bibliography, front_matter, ad, legal, author_bio, acknowledgments, junk.
- **Original text is never modified** — summaries/keywords go to metadata fields.
- Results cached by chunk `sha256` in `<name>.llmcache.json` (reruns cost zero).
  Dropped chunks → `<name>.dropped.jsonl`. Parse failure → default keep.
- Exit codes: 0 ok; 2 auth error (401/403); 3 some calls failed (output incomplete, rerun);
  1 stopped after 3 consecutive failures (verdicts already obtained are still cached). Put the key in the environment: `export LLM_API_KEY=...`;
  do not pass it with `--api-key` on a shared machine (it shows in `ps` and shell history).
- For Qwen with thinking mode: add
  `--extra-json '{"chat_template_kwargs":{"enable_thinking":false}}'`.

## Rules, thresholds, failure patterns, changelog

See `references/rules.md`.
