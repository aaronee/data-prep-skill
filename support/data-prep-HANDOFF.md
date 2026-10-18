# data-prep — handoff document

Date: **2026-10-18**. Read this first, then `data-prep-skill-report-v5.md` (same
folder) for the full audit — every shipped file (18) is embedded in it,
byte-verified.

## One-liner

`~/.agents/skills/data-prep/` is a Python-stdlib Agent Skill that cleans LiteParse
(`lit`) PDF/DOCX JSON output into RAG-ready text + section-aware chunks, with an
audit trail (`removed.jsonl`), a built-in retention report, real BM25 eval with a
**fail-closed** gate, and an LLM filler-chunk classifier with real failure
handling. It is in **v5** state (v4 + the 8-defect fix round F1–F8, applied via a
verified patch), fully tested (**42/42**, portable, 0 ResourceWarnings), the three
real books re-checked **byte-identical** to v4, the live LLM run executed and
logged, and the STRICT eval gate **measured and passing** on all three books.
**One item is open**: the gold questions were agent-written (self-check-verified),
not human-written — the report's §7 asks for direction (candidate: hand to a
Designer Agent to design the gold-verification workflow).

## What changed in v5 (2026-10-18)

- **F1** eval gate fails closed: `--min-hit` now exits 1 on <`--min-questions`
  (default 20) STRICT-graded questions, invalid gold rows, remaining `TODO` rows,
  or an empty file; `#` lines are comments.
- **F2** `filter_llm.py`: HTTP 401/403 aborts at the first call (exit 2, writes
  nothing); 3 consecutive failures abort; partial failures → `WARNING … INCOMPLETE`
  + exit 3. Pre-v5 it wrote a normal-looking filtered file with exit 0.
- **F3** LLM cache key = hash(chunk + model + prompt); a `keep=false, type=content`
  verdict can no longer drop a chunk; new dry-run suspects `index-like` /
  `bibliography-like` (trading: 6/271 now, was 4 — c0030, c0162 newly caught).
- **F4** `make_eval_candidates.py`: emits `# excerpt` + `TODO write a question …`
  stubs; a human writes the questions; the gate fails until TODOs are answered.
- **F5** text mode: removing a bare page number no longer splits the paragraph
  (hyphenation joins across it).
- **F6** R8 mono detection case-insensitive + wider (menlo, monaco, inconsolata,
  cmtt, …); `mono` no longer matches `monotype`; new `--code-fonts "A,B"` flag.
- **F7** tests close files (0 ResourceWarnings); two vacuous assertions made real;
  suite grew 28 → 42 (new `tests/test_f06_gate_textpn.py`, 10 tests; `test_llm_api`
  6 → 10).
- **F8** UTF-8 on all file I/O.
- Docs: SKILL.md flags/eval/LLM sections, rules.md changelog v3.13–v3.18,
  llm-run-log.md v5 paragraphs.

## Current state (all verified 2026-10-18)

- **Tests**: 42/42, from a copied folder with no install present
  (`HOME=/tmp/fakehome`), 0 ResourceWarnings under `-W always`.
- **Real books** — v5 re-run at `/tmp/v5/f3/` is **byte-identical** to the v4 run
  at `/tmp/v3/f3/` (chunks.json SHA-256 equal; clean/removed `cmp`-identical;
  removed.jsonl rule+text counter diff: 0 newly removed, 0 rescued on all 3):

  | book | chunks | removed lines | over 150% cap | retention WARNINGs |
  |---|---|---|---|---|
  | trading (214 pp) | 271 | 1,008 | 0 | 0 |
  | gatheral | 159 | 1,471 | 0 | 10 (running-header/title artifacts, pre-existing kind) |
  | prado | 356 | 2,868 | 0 | 13 (same; `figure` 97.0%) |

- **LLM pass**: live run **executed 2026-10-17** (endpoint `http://localhost:8000`,
  model `Qwen3.8-27B-oQ4e-mtp`): 4/271 suspects → 2 legal drops (c0268/c0270,
  content-verified, 0 wrong drops), 2 content keeps; identical rerun = 4/4 cache
  hits, 0 API calls, byte-identical output. Full record: `docs/llm-run-log.md`.
- **Eval gate** — verified gold files exist and the gate has been **run**:

  | book | LENIENT hit@3 | STRICT hit@3 | STRICT MRR | `--min-hit 0.8` |
  |---|---|---|---|---|
  | trading | 20/20 | 18/20 (90%) | 0.817 | PASS (exit 0) |
  | gatheral | 20/20 | 17/20 (85%) | 0.742 | PASS |
  | prado | 19/20 | 19/20 (95%) | 0.850 | PASS |

  Gold: `~/Downloads/gold-candidates/verified_{trading,gatheral,prado}.txt`
  (3×20 rows, 4-column) + per-row `verified_*.notes.md` (verbatim chunk quote +
  occurrence count per row, for cheap human spot-check). Self-check: 0 errors
  (phrase in cited chunk, ≤5 chunks book-wide, no phrase-in-question, 20 rows,
  4 columns, valid ids). Logs: `/tmp/v5/eval3_*.log` (volatile).
  The 5 STRICT misses (chunk-boundary artifacts — phrase in a top-3 chunk, gold
  page off by the boundary): trading Q2 *zero theta* (p6), Q13 *1/K2* (p57);
  gatheral Q4 *10% plus the worst monthly return* (p22), Q5 *Nassim Nicholas
  Taleb* (p25), Q20 *eliminate dS terms* (p84); prado Q14 *d < 0.6* (p113).

## OPEN — gold provenance, request for direction (report v5 §7)

DoD says ≥20 **human-written** verified questions per book. The user cannot verify
gold manually and delegated. History: round 1 (instructed external model) wrote
nothing to disk; round 2 → 88 self-check errors; round 3 → 53 errors, self-check
never re-run. The coding agent then authored the 3×20 gold files itself (user
directed), mechanically verified (0 errors), and ran the gate (results above).
The numbers are honestly labeled in the report as **agent-written,
self-check-verified, human spot-check pending**. Options on the table:
1. **Accept** the agent-verified gold as canonical (gate passes 90/85/95 ≥ 80%;
   notes.md provided for optional spot-check). ← coding agent's recommendation
2. **Iterate the 5 misses** (rewrite or re-pin those questions, re-run gate).
3. **Designer Agent designs the delegation workflow** (the model failed at
   process — not writing files, not running the self-check — not at content).
The user will pass the report to a Designer Agent; a decision on 1/2/3 is the
main open item.

## Secondary open item (optional)

The v5 dry-run heuristics newly flag 2 trading suspects (c0030 bibliography-like,
c0162 index-like). Whether to send them through the live LLM pass is the user's
call (`content` can never be dropped; the LLM verdict is the decider). Requires
the key, which the user sets in `LLM_API_KEY` — **never write the key into any
file, log, or command line; use the env var.**

## Key paths

| what | where |
|---|---|
| skill (18 shipped files; SHA-256 in report v5 §5) | `~/.agents/skills/data-prep/` |
| operational guide / rules + changelog (now v3.13–v3.18) | `SKILL.md`, `references/rules.md` |
| main script (geometry + text modes, chunking, fail-closed eval) | `scripts/prep.py` (~43.6 KB) |
| LLM classifier (abort semantics, model-keyed cache) | `scripts/filter_llm.py` |
| candidate gold generator (excerpt + TODO stubs) | `scripts/make_eval_candidates.py` |
| tests (42) | `tests/` — new: `test_f06_gate_textpn.py` (10); `test_llm_api.py` (10) |
| backups (persistent) | `~/.agents/skills/data-prep.bak-v5pre.tar.gz` (pre-v5 patch), `data-prep.bak-step5`, all v4 step backups (`data-prep.bak-step*`, `prep.py.bak-*`, `filter_llm.py.bak-f2`) |
| reports (all preserved) | `~/Downloads/data-prep-skill-report.md` (v1), `-v2.md`, `-v3.md`, `-v4.md`, **`-v5.md` (current)** |
| per-step run record for the v5 round | `/tmp/v5/REPORT-v5.md` (volatile; includes the 5 listed deviations) |
| input caches (PDFs gone) | `~/Downloads/*.lit.json` (trading, gatheral, prado) |
| canonical v4/v5 books (volatile, byte-identical) | `/tmp/v3/f3/…` and `/tmp/v5/f3/{trading,gatheral,prado}/` (+ `eval3_*.log` gated-eval logs) |
| v5 regression before/after `removed.jsonl` | `/tmp/v5/before/`, `/tmp/v5/after/` |
| gold files (persistent) | `~/Downloads/gold-candidates/` — `candidates_*.txt` (original generator output), **`verified_*.txt` + `verified_*.notes.md` (current)**, `instruction.md` (the self-contained instructions given to the external model, with the embedded self-check script) |
| self-check script (volatile) | `/tmp/goldcheck.py` — also embedded in `instruction.md` |
| report generators (volatile) | `/tmp/v5/mkreport5.py` (v5), `/tmp/v3/mkreport4.py` (v4) |
| v5 task + patch (the audited fix round) | `~/Downloads/files/TASK-v5.md`, `~/Downloads/files/v5.patch` |

If `/tmp` was cleared: re-derive books with `prep.py <book>.lit.json --outdir <dir>`
and re-run the three gated evals (command line in "Eval" below) — outputs are
deterministic and were byte-verified, so they will reproduce exactly.

## How to run things

```bash
# one book
python3 ~/.agents/skills/data-prep/scripts/prep.py ~/Downloads/<book>.lit.json \
    --outdir <dir> [--eval <gold.txt> --min-hit 0.8] [--code-fonts "A,B"]

# LLM dry run (no API calls) / live run (key via env, NOT on the command line)
python3 ~/.agents/skills/data-prep/scripts/filter_llm.py <dir>/<book>.lit.chunks.json \
    --endpoint http://localhost:8000/v1/chat/completions --model <ID> --dry-run
export LLM_API_KEY=<user sets it>   # then the same command without --dry-run

# tests (from a copied folder; the installed copy must not be used)
cd ~/.agents/skills/data-prep/tests && HOME=/tmp/fakehome python3 -m unittest discover
```

## Ground rules (how this project operates — keep them)

1. **Failing test first**, then the fix. One step at a time, in written order.
2. **Backup per step** before editing; prefer a verified patch over hand edits
   (the v5 round was patch-only for code/tests; docs were hand-edited under
   backup).
3. **No per-document hardcoding** — all rules data-driven; thresholds are CLI
   flags. Never change a threshold/default to make something pass.
4. **Real-doc removed-diff after every code step** (compare `removed.jsonl`;
   every newly removed line must be junk; v5: 0 on all three books).
5. One changelog line per step in `references/rules.md`.
6. **Stdlib only** (no pip). `prep.py` has no network calls; the LLM is a
   *classifier* (keep/drop + type/summary/keywords), never a rewriter; `content`
   can never be dropped.
7. **Honest reporting**: separate observed from inferred; every number in a
   report is copied from a command output actually run; list deviations instead
   of hiding them; keep all prior reports; reports are self-contained with
   byte-verified file embeddings (re-extraction verified, not presumed).
8. **Secrets**: never store or print. The LLM key lives only in `LLM_API_KEY`
   set by the user; never on a command line (`ps`/history), never in a file.
9. **Fail closed**: gates must not pass silently (F1) — zero gradable, too few,
   invalid, or TODO rows all fail.
10. Ask before destructive/out-of-scope actions; state assumptions and proceed
    otherwise. Once the user has decided, execute — don't re-ask.

## Known limits (current, documented in report v5 §8)

- Narrow-gutter (<12pt) two-column pages not auto-split (trading pp. 151/152);
  the "possible two-column layout" warning is the safety net.
- Labeled chart ticks can survive R3 (28 surviving numeric lines in trading, all ticks).
- txt all-caps heading detection can false-positive.
- R6 can't remove unheaded filler — the LLM pass is the intended remedy.
- Retention warnings on book-title/running-header tokens (gatheral `surface`
  51.5%, prado `financial` 64.2%) are pre-existing baseline artifacts.
- Gold pages go stale when chunk boundaries move — that is what STRICT + the
  4-column gold exist for; STRICT needs a numeric page, so text-mode inputs
  (.md/.txt) grade LENIENT only.
- The 5 STRICT misses are chunk-boundary artifacts in the current gold (see
  OPEN section); they do not reflect retrieval failures.

## Suggested first moves in the new session

1. Ask the user for the §7 direction decision (accept gold / iterate misses /
   Designer Agent workflow design) — the report is already phrased for the
   Designer Agent.
2. On "accept": nothing to do — the DoD is met as measured and labeled.
3. On "iterate the 5 misses": edit the 5 questions/phrases in
   `verified_*.txt`, re-run `/tmp/goldcheck.py` (or the embedded script in
   `instruction.md`) until 0 errors, then re-run the three gated evals.
4. On "Designer Agent": pass `data-prep-skill-report-v5.md` §7 + `instruction.md`
   + this handoff; the three failure rounds are documented in report §7.
5. Optional: user decision on sending the 2 newly-flagged trading suspects
   (c0030/c0162) through the live LLM pass.
