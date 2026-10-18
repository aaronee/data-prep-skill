# v6 support files — audit material for REPORT-v6 (2026-10-18)

Generated 2026-10-18 in response to the principal's audit list. Everything here is
raw output or the exact script that produced it.

| file | what it is |
|---|---|
| 10_sha256_all19.txt | full SHA-256 of all 19 shipped files (incl. tools/removed_summary.py, the file missing from the report's first §9 list) |
| 11_find_all_files.txt | `find ~/.agents/skills/data-prep -type f \| sort` — 26 files: the 19 shipped + 8 `*.bak-*` backups + 1 extra (none other). tools/removed_summary.py is the one shipped file that was absent from the report's list |
| 20_rerun_live_endpoint.log | Step-8 rerun, live endpoint, via `tee`; exit=0; 6/6 cache hits; 0 "calling LLM"; 0 API calls |
| 21_rerun_dead_endpoint.log | same command with `--endpoint http://127.0.0.1:1/...` (unroutable): exit=0, all 6 served from cache — any real API call would have failed loudly |
| 22_llm_run_log_tail15.txt | `tail -15 docs/llm-run-log.md` (the Step-9 append) |
| 30_fulltext_c0162.txt / c0268.txt / c0270.txt | full chunk texts (c0162 = index-like false positive; c0268/c0270 = the 2 legal drops) |
| 31_cache_entries_type_keep_summary.txt | cache entries: chunk id, type, keep, summary only (no keys, no headers) |
| 40_f9_code.txt | exact F9 code in prep.py (state decl, R1/R1b pre-consumption, is_head/trigger/release) + proof v5==v6 in that region |
| 41_r6_episodes_prado.txt / gatheral.txt / trading.txt | instrumented R6-episode runs: per-episode trigger (line+page), release (line+page), lines removed; totals cross-checked against removed.jsonl (1064/494/24 exact) |
| 42_bodyprose_context_prado.txt | ±8 surrounding prepared lines for the 8 flagged body-prose removed entries |
| 43_gatheral_ch1_raw_vs_clean.txt | raw input pp.32–35 (Chapter-1 opener) + grep of 8 distinctive sentences against clean.txt: 7×0 hits, 1 hit = the TOC entry (clean.txt line 72) |
| 50_gate_scores_6misses.txt | the 6 STRICT misses: cited-chunk rank+score, top-6 scores, tie counts. Replication verified against the real gate output (same top-3). Ties broken by chunk index (stable sort). NO ties at the cited scores (Q2: rank 4, gap 4.83 to rank 5) |
| 52_gatheral_Q5_goldrow_and_c0012.txt | gold row 5 + full c0012 text (85 chars; BM25 score 0 because the name is split across a footnote and no query token matches) |
| 53_spotcheck_5rows_per_book.txt | rows 3, 8, 12, 15, 19 per book: question + cited chunk full text |
| 60_v5_report_lines52_66.txt | v5 report around line 59 (the 254cf54b claim) |
| 61_diff_v3_v5_f3.txt | `diff -q` v3/f3 vs v5/f3 chunks.json, all 3 books: identical |
| 62_prefix_search_and_repro.txt | full search: no file on disk hashes to 254cf54b/aedab848/12d83851; repro under v5-era filename does not reproduce the prefix (three-way 07a69d09); source-field evidence |
| 70_scripts_*.py | the exact scripts that produced 41/42/50/53 |
