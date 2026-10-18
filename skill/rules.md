# data-prep rules, thresholds, and failure patterns

## Pipeline overview

**Geometry mode** (`.pdf/.docx/.pptx/.xlsx` via `lit`, or a `.json` lit dump):
uses per-item `x, y, width, height, font_name, font_size` to filter *before*
text projection. Steps:

1. `prepare_page` (R2): zone-filter short numeric items (page numbers); capture
   the printed page label; group items into lines (y-tolerance = 0.55× median
   item height, anchored to the line's first item); detect table rows
   (inter-cell gap > max(`--gap-cut`, 3× median positive gap)).
   **The same prepared lines feed the R1 pre-pass and the main pass** — one
   line builder, so the two can never disagree about a line's text.
2. R1 frequency pre-pass: per-page distinct-line counts (full key + 6-token
   stem key), threshold = max(5, `--recur-frac` × n_pages), default frac 0.15.
3. Main pass: R4 → R1 → R1b → R8 → R3 → R6 (per line), R5 (per page).
   `prepare_page` also reorders two-column pages (left column, then right)
   before any rule runs, when a consistent ≥12pt vertical gutter is found.
4. R7: paragraph building (below).
5. Chunking (below) → outputs + report + `removed.jsonl`.

**Text mode** (`.md/.txt`): no geometry. MD `#` headings (or all-caps lines
in .txt) → path stack; blank lines → paragraph breaks; R1/R4/R6 applied
textually. No R2/R3/R5 (they need geometry). Simpler by design — markdown is
usually already clean.

## Rules

| rule | what it removes | how | guard / tradeoff |
|---|---|---|---|
| **R1** recurring lines | running headers/footers, "Source: … estimates", watermarks | full-line key (digits collapsed to `#`) repeated on ≥ max(5, frac×pages) *distinct* pages; or 6-token stem key for short lines | **lines ≥5 tokens use a strong key (no digit-collapse)** — protects body sentences that only differ in a number (v1 finding #9). <8 normalized chars never suppressed. Stem key needs ≥3 tokens, ≤60 chars |
| **R1b** margin repeat | running headers that sit in the top/bottom margin band and repeat per chapter (below the 15% global R1 threshold) | normalized line in top/bottom `--margin-band` (0.08) on ≥ `--margin-min-pages` (4) distinct pages | **skips lines with >2 digits** — numbered template lines (figure captions) are not margin repeats (v1 finding #9 class). `--disable R1b` turns it off — its own switch, no longer coupled to `--disable R1` |
| **R8** footnote | small-font lines in the bottom 28% of a page (footnotes, bottom-band chart ticks/labels, index entries, running footers) | `y > --footnote-zone`·H (0.72) and **every** cell `h ≤ --footnote-ratio`·body_h (0.85, max cell height), not a table row. **Exempt (kept): figure/table captions, monospace-font lines (see `--code-fonts`), code-looking lines** (≥3 of `=(){}[];_+*` with letter ratio <0.75) — v3 audit: code listings and captions were being dropped | a bullet marker does not make a body line a footnote. RAG value near zero (the referent stays); `--disable R8` turns it off. Real-doc check: zero caption rows in R8 on all three books; prado `figure` retention 85.6%→97.0% |
| **R2** page numbers | "42", "42 / 118", "– 42 –" (geometry: in-band items; **text mode: bare "12" / "Page 34" lines**, value 1–2000, year-like 1900–2100 kept as content) | short (≤3 chars) purely-numeric item in top/bottom `--zone` (0.12) band | printed label captured for chunks; only in-band + short |
| **R3** chart ticks | standalone axis numbers, "0.5", "12%", gridline labels | numeric line (≤3 cells) **unless the previous emitted line is open prose** (no terminal punctuation `. ! ? : ; %`) | a wrapped number that continues a sentence (`The premium is` / `15%.`) is kept; a standalone number after a finished sentence is dropped. Chart with labels glued to ticks will not be caught — known limit |
| **R4** TOC dot leaders | "Chapter 3 ....... 13" | any line with ≥5 consecutive dots | safe: only TOC/leader lines look like this |
| **R5** whole TOC pages | entire pages of TOC | ≥3 dot-leader lines on one page | counted on prepared lines (pre-R4), so the two rules stay consistent |
| **R6** front/back matter sections | TOC, index, references, bibliography, copyright, disclaimer, disclosures, acknowledgments, back cover | heading (single cell, Bold or ≥1.25× body height, <80 chars, no `\|`, no trailing `.`) whose normalized text is in `--drop-sections` → drop until the next heading | **state persists across pages** (v1 bug 1); **the heading that ends a dropped section is kept** (v1 bug 2); section names are a CLI list, not hardcoded |
| **R7** paragraph building | *(rebuilds)* | break on: bullet/number marker (`-`, `•`, `1.`, `2)`), y-gap > 1.5× median line height, page boundary (unless previous page ended mid-sentence); join within page + across pages otherwise | see dehyphenation below |

### Dehyphenation (vocabulary-aware)

At a `word-` + `continuation` break:
- next starts **uppercase** → concat, keep hyphen: `Black-` + `Scholes` → `Black-Scholes`
- next starts lowercase → merge **only if** the merged first word exists in the
  document's vocabulary (hyphen-preserving tokens from all raw items):
  `infor-` + `mation` + vocab has "information" → `information`
- otherwise **lossless** keep: `risk-` + `neutral` → `risk- neutral` (both tokens
  stay searchable; we don't know the compound)

## Chunking

- Units: `para | head | table`. Tables (runs of table rows) are **atomic** —
  never split mid-table.
- Target = `--chunk-tokens` × 4 chars (default 400 tokens); **hard cap 150%** —
  a chunk is flushed before a piece would push it over the cap; over-cap
  paragraphs are split on sentence boundaries.
- Heading hierarchy from item height (≥90% of tallest = h1, ≥75% = h2, else h3)
  drives the `path` stack; **path is captured at chunk start**, not end.
- Orphan heading: a chunk never ends on a bare heading — the heading is carried
  to the next chunk (or merged into the final chunk if the doc ends there).
- Fields: `id, source, chunk_index, page [first,last], page_label` (printed
  number, from R2), `path`, `text`, `embed_text` (path + text), `sha256`.

## Verification

The report prints, built in:
- **retention table**: top-15 content words, raw count → indexed count.
  Indexed = chunk text (clean.txt double-counts cross-page paragraphs).
  WARNING at <95%. A WARNING on a word that also appears in running headers is
  often *legit* (the header was removed) — confirm via `removed.jsonl`.
- **most-lost tokens**: top-20 raw→clean token losses — false positives are
  findable in one look.
- **warnings**: possible two-column layout (page >40% table-row lines), no
  headings detected (paths will be flat), chunks over cap.

### Eval

`--eval QFILE`; line format `question | key phrase | expected page`.
Real BM25 (k1=1.5, b=0.75, length-normalized). A top-3 chunk is CORRECT if its
page range contains the gold page **or** it contains the key phrase.
Metrics: **hit@3, MRR**. Reference results (v2, this machine):

| document | chunks | hit@3 | MRR |
|---|---|---|---|
| Trading Volatility (214p) | 272 | 6/6 | 0.889 |
| Volatility Surface, Gatheral (210p) | 164 | 4/5 | 0.700 |
| Advances in FML, de Prado (393p) | 362 | 2/3 | 0.667 |

de Prado misses are *content* issues the deterministic pass can't fix:
endorsement blurbs (pp. 3–9) have no section heading, so R6 can't cut them —
that's what the LLM pass is for (`author_bio`, `front_matter`).

**Embedding retrieval** (optional): `--embed-cmd CMD` where CMD reads text on
stdin and prints a space-separated float vector; cosine top-3. Example:

```bash
--embed-cmd "curl -s http://localhost:8000/v1/embeddings -d @- | python3 -c 'import json,sys; print(\" \".join(map(str, json.load(sys.stdin)[\"data\"][0][\"embedding\"])))'"
```

## LLM pass (`filter_llm.py`)

Suspect pre-selection (any of): letter ratio < 0.55; boilerplate regex
(rights/copyright/disclaimer/acknowledg/©/isbn/www/publisher); <80 chars;
>6× median chunk length; near-duplicate prefix. Over-flags a little (~1.5% of
chunks) — cheap because the LLM is the decider. Endpoint is
OpenAI-compatible; `--all` forces every chunk; `--dry-run` lists suspects
without calls. Cache keyed by chunk `sha256`.

## CLI reference

```
prep.py INPUT [--ocr] [--no-cache] [--outdir DIR] [--eval QFILE]
          [--chunk-tokens 400] [--recur-frac 0.15] [--zone 0.12]
          [--gap-cut 24] [--drop-sections a,b,c] [--disable R1,...,R7]
          [--embed-cmd CMD]
filter_llm.py CHUNKS.json --endpoint URL [--model qwen2.5]
             [--extra-json '{...}'] [--max-suspects 100] [--all] [--dry-run]
```

Ablation example: `--disable R3` shows how many "ticks" were prose;
`--recur-frac 0.30` loosens R1 (fewer removed lines).

## Failure patterns (know these before debugging)

1. **Two-column books** — items in both columns share y; they merge into one
   line with `|` separators. Report warns; verify before indexing.
2. **Running header + page number on one line** (real books) — the numeric
   cell is R2-removed, the header is R1-removed; they never reach R3.
3. **Chart ticks with labels** — R3 only catches standalone numeric lines;
   labeled ticks (e.g. "12%  Jan") survive. LLM pass may flag the chunk.
4. **No bold headings** — paths go flat; eval still works; consider
   `--drop-sections` is the only lever.
5. **Scanned PDFs** — always `--ocr`; born-digital PDFs never need it.
6. **Retention >95% but low hit@3** — cleanup is fine, chunking/retrieval is
   the problem (wrong target size, flat paths).
7. **Retention WARNING on a header word** — usually legit (header was the
   most-repeated instance); check `removed.jsonl` before panicking.

## v3 changelog

- **v3.6 (fix round, step 1) — portable tests.** `tests/fixtures.py` hardcoded `~/.agents/skills/data-prep/scripts/prep.py`, so a fresh checkout ran the *installed* copy, not the file beside it (10/12 errors without the install; reproduced under `HOME=/tmp/fakehome`). `PREP` is now resolved relative to `__file__` (`..`/scripts/prep.py); `run_eval` uses `with open(...)`. Suite is green from a copied folder with no install present.
- **v3.7 (fix round, step 2) — `filter_llm.py` API key.** Previously it could never authenticate (no way to send a key). Now `--api-key` (default `LLM_API_KEY` env) is sent as `Authorization: Bearer …`; the key is never printed or written to the chunk-hash cache. `--max-tokens` caps completion length. Mock-server tests (`tests/test_llm_api.py`) prove: key sent from flag and from env, no header without a key, a 401 is kept-but-not-cached, a drop verdict is cached, and a rerun makes zero server calls.
- **v3.8 (fix round, step 3) — R8 exemptions + flags.** R8 no longer drops code listings or figure/table captions: exempt are caption-leading lines (`figure/table/exhibit/chart/listing` + number), monospace-font lines, and code-looking lines (≥3 of `=(){}[];_+*`, letter ratio <0.75). The band and font ratio are now flags (`--footnote-zone`, `--footnote-ratio`, defaults 0.72/0.85). R1b got its own `--disable R1b` switch (it was coupled to `--disable R1`). Real docs: R8 row counts fell (trading 149→142, gatheral 231→230, prado 486→251), zero caption-like rows remain, prado `figure` retention 85.6%→97.0%, and **no newly-dropped lines** (exemptions only rescue content).
- **v3.9 (fix round, step 4) — text-mode bare page numbers.** Text mode removed the `Page N` label but left the bare number line, which got glued into the paragraph. Now a standalone `12` or `Page 34` line is dropped in text mode (explicit `Page N` always; bare values only in 1–2000, with a year-like 1900–2100 kept as content). `--disable R2` turns it off. Covered for both `.md` and `.txt`.
- **v3.10 (fix round, step 5) — non-circular eval candidates + leakage guard.** `make_eval_candidates.py` no longer lets the question quote the answer: the key phrase is now ONE content word that must occur in the cited chunk, the question never contains that word, and only content chunks are cited (legal/boilerplate/notice excluded, never taken from `removed.jsonl`). Output gains a 4th column (chunk id). `run_eval` accepts that column and rejects gold rows whose cited chunk lacks the phrase (stale/leaky gold is excluded, not counted); 3-column files still work.
- **v3.11 (fix round, step 6) — live LLM run.** Executed 2026-10-17 against `http://localhost:8000` (model `Qwen3.8-27B-oQ4e-mtp`) on the trading f3 chunks: 4/271 suspects → 2 drops (c0268/c0270, Santander legal disclaimers — content-verified, 0 wrong drops) and 2 content keeps; identical rerun served 4/4 from cache with 0 API calls and byte-identical output. Key passed via env for the single run, never printed or stored. Full record: `docs/llm-run-log.md`.
- **v3.12 (fix round, step 7) — docs cleanup.** SKILL.md flags table, rules.md R2/R1b/R8 rows and the changelog above updated to match shipped behaviour.

- **v3.13 (v5 round) — eval gate fails closed.** `--min-hit` now fails on zero gradable questions, fewer than `--min-questions` (20), invalid gold rows, TODO rows, or an empty file. `#` lines are comments; `TODO` rows are skipped.
- **v3.14 (v5 round) — filter_llm failure handling + cache key.** 401/403 aborts at the first call (exit 2, no output); 3 consecutive failures abort; partial failures exit 3. Cache key now includes model + prompt hash. Only non-content types can be dropped. Added index-like and bibliography-like suspect heuristics.
- **v3.15 (v5 round) — candidates.** `make_eval_candidates.py` emits `# excerpt` comments and `TODO` question stubs (a human writes the questions).
- **v3.16 (v5 round) — text-mode page numbers.** Removing a bare page number no longer splits the paragraph; hyphenation joins across it.
- **v3.17 (v5 round) — R8 fonts.** Case-insensitive monospace names (menlo, monaco, inconsolata, cmtt, ...), `mono` no longer matches `monotype`; new `--code-fonts` flag.
- **v3.18 (v5 round) — hygiene.** UTF-8 on all file I/O; tests close their files (0 ResourceWarnings); two vacuous assertions in `test_f03_r8.py` made real.
- **v3.19 (v6 round) — gate hardening.** Gold rows are invalid if the key phrase appears in the question (leak) or the question duplicates another; `--min-hit` also needs `--min-chunks` (default 10) distinct cited chunks; `--min-hit` without `--eval` is an error; `filter_llm.py` saves already-obtained verdicts before aborting after 3 failures.

- v3.5: strict eval — `--eval` now grades two metrics per question: **LENIENT** (top-3 chunk contains the key phrase OR covers the expected page — the v2 behaviour) and **STRICT** (BOTH: a chunk on the right page that contains the phrase). Questions with only one gold column are LENIENT-only (reported as ungraded for STRICT). `--min-hit F` exits 1 when STRICT hit@3 < F. `scripts/make_eval_candidates.py` (stdlib, deterministic, no LLM) writes 20 spread candidate gold lines (question + phrase + PDF page) from a chunks.json for human verification. Verified: the v2 trading gold (6 Q) scores LENIENT 6/6 vs **STRICT 5/6 — the miss is "call overwriting", gold page 25 falls in the gap between chunks p23-24/p24/p26 (phrase right, page off by the chunk boundary); v2's 6/6 had masked it. Synthetic tests: right-phrase/wrong-page and wrong-phrase/right-page both LENIENT-hit but STRICT-miss; gate pass/fail both covered.
- v3.4: R8 footnotes + column splitting — a small-font line in the bottom 28% of a page (every cell `h ≤ 0.85×body_h`, `y > 0.72×H`, not a table row) is dropped: footnotes, bottom-band chart ticks/labels, index entries, running footers. Column splitting — when `find_gutter` finds a ≥12pt empty vertical band in the page middle with ≥30% of cells on each side, `reorder_columns` emits the left column top-to-bottom, then the right, so two-column pages read in order instead of interleaved `a | b` rows; `build_paragraphs` treats a backward y-jump as a column break (same cross-join logic as a page break). Verified: synthetic two-column 16-line page reads left→right with zero `|`; real docs: prado's 7.4pt "Profit-Taking" running footers (12 pages) and trading/gatheral chart labels removed; R8 also closes the v2 TOC-sub-entry leak. Corrective fix in-step: line `h` is the MAX cell height (was cells[0] — a small bullet marker made body lines look like footnotes; prado lost ~100 real bullets). Known limit: narrow-gutter (<12pt) two-column pages (e.g. trading pp. 151/152) are NOT split — the v2 "possible two-column layout" warning stays as the safety net; every R8 row sampled per book is a label/footnote/code/back-matter line (the few borderline callout lines are listed in `removed.jsonl`).
- v3.3: `clean_unicode` — NFKC (ligatures ﬁ/ﬃ→fi/ffi), `(cid:N)` removal, zero-width/soft-hyphen/invisible removal, control-char removal (keeps \t\n\r), applied to every item on load in geometry mode and to the whole file on read in text mode. All three real books (born-digital) contain zero such characters — verified no-op on them; covered by synthetic tests.
- v3.2: R1b margin repeat — a normalized line sitting in the top/bottom `--margin-band` (default 8%) on `--margin-min-pages` (default 4) or more pages is a running header and is dropped (position-based, independent of the 15% global R1 threshold). Skips lines with >2 digits (numbered template lines such as figure captions — v1 finding #9 class). Controlled by `--disable R1b` (own switch; the v3.2 coupling to R1 was a bug fixed in the v3.6 round). Verified: trading 0 rows; gatheral 72, de Prado 226, all read as running headers only. Corrective fix: `split_para` now hard-splits sentence-less over-cap paragraphs at whitespace, restoring the 0-over-cap guarantee after heading reflow merged index entries (prado 2400+ char chunks).
- v3.1: text mode gains R1 recurring-line removal (`--text-recur-min`, default 8; md table rows/separators excluded; first occurrence of a repeated `#` heading kept) and shares `join_hyphenated` with geometry mode — unknown compounds now emit `risk-neutral` (no space) instead of `risk- neutral`; vocab-confirmed words merge; capitalized continuations concat.

## v2 changelog (what the audit found and what changed)

1. R6 drop state reset per page → persists across pages now.
2. Heading that ends a dropped section was deleted → kept now.
3. R1 pre-pass joined table cells with `" "` while the main pass dropped R2
   cells first and joined with `" | "` → identical keys; one shared line builder.
4. `--outdir` ignored for absolute inputs; relative+subfolder crashed →
   basename naming, `os.makedirs`.
5. Dehyphenation merged blindly (`riskneutral`) → vocabulary-aware.
6. R3 dropped *any* 1–3-cell numeric line (killed wrapped prose numbers) →
   prose-continuation guard.
7. No paragraph logic (one blob per page) → y-gap + bullet breaking,
   cross-page joins.
8. Chunks up to 3× target + duplicate trailing chunk → 150% hard cap,
   sentence splitting, no-dup check.
9. (bonus) R1 digit-collapse merged body sentences that only differed in a
   number → strong keys for ≥5-token lines.
