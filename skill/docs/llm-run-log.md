# LLM pass run log (filter_llm.py)

## 2026-10-17 — dry-run + failure path (trading book, step-4 chunks)

Setup: `Trading Volatility…`, 269 chunks from step 4.

### Dry run (`--dry-run`, no API calls)

4/269 suspects flagged (heuristic pre-selection):

| chunk | reason | actual content |
|---|---|---|
| c0093 | boilerplate pattern | **content** (dispersion trading) — heuristic false positive |
| c0112 | boilerplate pattern | **content** (hedging back-testing) — heuristic false positive |
| c0266 | boilerplate pattern | Santander legal disclaimer — genuine filler |
| c0268 | boilerplate pattern | SIS order-instructions legal text — genuine filler |

This is the intended division of labour: the heuristic over-selects (it
may send content to the LLM), the LLM classifier decides; non-suspects are
auto-kept, which is what keeps the pass cheap (4 calls, not 269).

Limitation: before v5 no heuristic flagged index or bibliography chunks, so
such back matter was never sent to the LLM. v5 adds `index-like` and `bibliography-like` reasons;
re-run `--dry-run` and record the new suspect count.

### Failure path (endpoint reachable, no API key → HTTP 401)

All 4 calls failed → all defaulted to keep, `dropped.jsonl` empty,
269/269 kept, exit normal. Verified the fix made in this step: **transient
errors are not written to the chunk-hash cache** (previously a 401/timeout
verdict was cached and would silently suppress retries on rerun; the cache
now holds successful calls only).

v5 audit: before v5 a persistent 401 produced one request per chunk, a normal-looking filtered file
and exit 0. Since v5 it stops at the first 401 (exit 2) and writes nothing.

## 2026-10-17 — API-key support + mock-server tests (fix round, step 2)

`filter_llm.py` could not authenticate before (a key had nowhere to go).
Now: `--api-key` / `LLM_API_KEY` env → `Authorization: Bearer …`; the key is
never printed and never written to the cache; `--max-tokens` added.
`tests/test_llm_api.py` runs a real local HTTP server and proves: key sent
from flag, from env, and absent when unset; a 401 response keeps the chunk
without caching it; a drop verdict is cached and a rerun makes zero server
calls. 6/6 pass.

## 2026-10-17 — live run (trading book, v4 canonical f3 chunks)

Endpoint `http://localhost:8000` (OpenAI-compatible), model
`Qwen3.8-27B-oQ4e-mtp` — discovered via `/v1/models` with the working key.
Key supplied via the `LLM_API_KEY` env for the single run only; never printed,
never written to any file/log/cache.

Input: `/tmp/v3/f3/trading/…Gil.lit.chunks.json` — 271 chunks (v4 canonical run;
the earlier dry run used the 269-chunk step-4 file, so suspect ids shifted — see
below). Command: `filter_llm.py <chunks.json> --endpoint
http://localhost:8000/v1/chat/completions --model Qwen3.8-27B-oQ4e-mtp`
(key via env).

### Verdicts — 4/271 suspects

| chunk | verdict | type | content check |
|---|---|---|---|
| c0093 | keep (model emitted `"keep": "keep"` — non-boolean, taken as keep by the lenient parse) | content | ✓ dispersion-trading instruments — genuine content |
| c0112 | keep | content | ✓ hedging-strategy back-testing — genuine content |
| c0268 | drop | legal | ✓ Santander "obtained or derived from sources…" disclaimer |
| c0270 | drop | legal | ✓ US recipient / broker-dealer contact + copyright notice |

Result: **269/271 kept, 2 dropped** → `…Gil.lit.dropped.jsonl`; filtered chunks
→ `…Gil.chunks.filtered.json`. Both drops verified against actual content:
genuine legal boilerplate — **0 wrong drops**. The dry-run expectation
c0266/c0268 referred to the step-4 chunking: in the f3 chunks Santander's legal
text now sits in c0268/c0270 (c0266 is a content chunk there) — same two legal
pages, shifted ids.

### Zero-cost rerun

Identical command re-run: all 4 suspects served from `…Gil.llmcache.json`
(4 entries, successful verdicts only), **0 API calls**; `chunks.filtered.json`
and `dropped.jsonl` are byte-identical before/after (SHA-256 diff clean).
Rerun cost: zero.

## 2026-10-18 — live run on v5/v6 code (trading book)

Dry run: 6 suspects (v5 heuristics add index-like and bibliography-like): c0030
bibliography-like, c0093 boilerplate, c0112 boilerplate, c0162 index-like, c0268
boilerplate, c0270 boilerplate. Live verdicts: 4 keeps (c0030, c0093, c0112, c0162 —
all `content`; c0030 and c0162 are the two newly flagged suspects and both verified
as content/chart/formula text), 2 drops (c0268, c0270 — `legal`).
Dropped: c0268 (Santander disclaimer), c0270 (US-recipient ordering/regulatory notice).
Wrong drops: 0. Rerun: 0 API calls (6/6 cache hits, cache written 12:12 by the live
run), outputs byte-identical (`filtered.json` 4738b014…, `dropped.jsonl` 0f06b2a2…).
The 2026-10-17 section above was produced by v4 code and is kept only as history.
