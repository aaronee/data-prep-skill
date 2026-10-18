# REPORT-v7 — data-prep skill, v7 EVIDENCE ROUND (read-only)

Date: 2026-10-18. Executed `~/.agents/skills/data-prep` (v6 state) on the local agent.
No skill file was created, edited or deleted. Raw output only; interpretation is
reserved for the reviewer.

## 1. Step 1 — v6 state hash check + snapshot

```
$ cd ~/.agents/skills/data-prep
$ sha256sum scripts/prep.py scripts/filter_llm.py tests/test_f07_hardening.py SKILL.md references/rules.md tools/removed_summary.py | cut -c1-16,65-
05d51ea007105c78  scripts/prep.py
8ff8b3d422fb8c4f  scripts/filter_llm.py
0c17e728cfe08c5d  tests/test_f07_hardening.py
51538d52b6b8580f  SKILL.md
b37800b9bdde26f9  references/rules.md
95c9e2e6468a779e  tools/removed_summary.py
```
All six first-16-hex match expected.

```
$ find . -type f | sort | xargs sha256sum > /tmp/v7/support/00_hash_before.txt
$ wc -l /tmp/v7/support/00_hash_before.txt
      27 /tmp/v7/support/00_hash_before.txt
```
27 lines as expected.

## 2. Step 2 — helper scripts

The five files were in `~/Downloads/v7/` and copied to `/tmp/v7/scripts/`
(copies, bit-identical; no edits, no PATH FIX needed). Inputs listed:
each of `/tmp/v6/f3/{trading,gatheral,prado}` contains 4 files (chunks.json,
clean.txt, removed.jsonl, report.txt); `/tmp/v6/gold` contains 6 files;
exactly 3 `*.lit.json` in `~/Downloads`.

```
$ python3 -m py_compile v7common.py r6_diag.py gold_page_check.py bib_leak.py gatheral_probes.py && echo COMPILED
COMPILED
$ sha256sum /tmp/v7/scripts/*.py | cut -c1-16,65-
c31e0fc32cafddaf  /tmp/v7/scripts/bib_leak.py
f6c631d9e7968cf1  /tmp/v7/scripts/gatheral_probes.py
3942e1569947ad2c  /tmp/v7/scripts/gold_page_check.py
36fa7af0eec41ae9  /tmp/v7/scripts/r6_diag.py
f4da4c29727aa55c  /tmp/v7/scripts/v7common.py
```

## 3. Step 3 — replication check

```
$ python3 - <<'PY' | tee /tmp/v7/support/10_xcheck_r6_counts.txt
trading removed.jsonl R6-body lines = 24
gatheral removed.jsonl R6-body lines = 494
prado removed.jsonl R6-body lines = 1064
```
Expected 24/494/1064 — match.

```
$ cd /tmp/v7/scripts
$ python3 r6_diag.py trading /tmp/v7/support/diag_trading 2-3,67-68
input: /Users/KHOA/Downloads/Trading Volatility, Correlation, Term Structure and Skew | Colin Bennett, Miguel A. Gil.lit.json
EPISODES = 3
TOTAL R6-body lines = 24
TOTAL R6-body chars = 1158
log rows written = 180
exit=0
```

## 4. Step 4 — E1 + E2 on the three books

gatheral:
```
$ python3 r6_diag.py gatheral /tmp/v7/support/diag_gatheral 24-26,30-35
input: /Users/KHOA/Downloads/The Volatility Surface: A Practitioner's Guide | Jim Gatheral.lit.json
EPISODES = 3
TOTAL R6-body lines = 494
TOTAL R6-body chars = 22531
log rows written = 242
exit=0
```
prado A:
```
$ python3 r6_diag.py prado /tmp/v7/support/diag_prado_A 68-70,83-89,138-141,154-156,195-198,220-224,247-253,272-274,288-290,325-328,344-348,355-356
input: /Users/KHOA/Downloads/Advances in Financial Machine Learning | Marcos López de Prado.lit.json
EPISODES = 23
TOTAL R6-body lines = 1064
TOTAL R6-body chars = 75156
log rows written = 1420
exit=0
```
prado B:
```
$ python3 r6_diag.py prado /tmp/v7/support/diag_prado_B 47,100,116,129,163-164,176,185-186,236,305-306
input: /Users/KHOA/Downloads/Advances in Financial Machine Learning | Marcos López de Prado.lit.json
EPISODES = 23
TOTAL R6-body lines = 1064
TOTAL R6-body chars = 75156
log rows written = 468
exit=0
```

Non-empty proof:
```
$ wc -l /tmp/v7/support/diag_*/lines.txt /tmp/v7/support/diag_*/episodes_split.txt
     244 /tmp/v7/support/diag_gatheral/lines.txt
    1422 /tmp/v7/support/diag_prado_A/lines.txt
     470 /tmp/v7/support/diag_prado_B/lines.txt
     182 /tmp/v7/support/diag_trading/lines.txt
      34 /tmp/v7/support/diag_gatheral/episodes_split.txt
     223 /tmp/v7/support/diag_prado_A/episodes_split.txt
     223 /tmp/v7/support/diag_prado_B/episodes_split.txt
      32 /tmp/v7/support/diag_trading/episodes_split.txt
    2830 total

$ head -3 /tmp/v7/support/diag_prado_A/lines.txt
# body_h (median item height) = 9.09; heading test = font name contains 'Bold' OR height >= 11.36
# cols: page line state outcome cand(1=looks like heading) cells font height | text[:80]
p68   L1   drop-off R1b margin                     cand=0 cells=1 font=TimesLTStd-Roman       h=  7.3 | REFERENCES

$ head -8 /tmp/v7/support/diag_prado_A/episodes_split.txt
# marker = first R6-dropped line matching CHAPTER n / PART n / 'd.d Title'. 'from marker' is an UPPER bound for lost prose (heuristic).
EP  1: trigger pg 14 'Contents' -> released pg 14 by 'ix'
       dropped: 21 lines / 570 chars; pages 14..14
       marker: pg 14 '1.1 Motivation, 3'
       before marker: 3 lines / 90 chars | from marker to release: 18 lines / 480 chars
       after-release kept: pg 15 | x | CONTENTS
       after-release kept: pg 15 | Essential Types of Financial Data,
       after-release kept: pg 15 | 2.2.1 Fundamental Data, 23
```

## 5. Step 5 — E3 bibliography that survived

```
$ python3 bib_leak.py > /tmp/v7/support/70_bib_leak.txt; echo "exit=$?"
exit=0
$ grep -E '^(####|chunks with)' /tmp/v7/support/70_bib_leak.txt
################ trading  chunks=271
chunks with >=3 author-initials-(year) matches: 0 of 271
################ gatheral  chunks=159
chunks with >=3 author-initials-(year) matches: 0 of 159
################ prado  chunks=356
chunks with >=3 author-initials-(year) matches: 13 of 356
```

## 6. Step 6 — E4 gold pages vs parsed PDF

```
$ python3 gold_page_check.py > /tmp/v7/support/60_gold_page_check.txt; echo "exit=$?"
exit=0
$ grep '^SUMMARY' /tmp/v7/support/60_gold_page_check.txt
SUMMARY trading: rows=20 MATCH=15 OFF_BY_ONE=5 | gold_page_equals_chunk_first_page=20/20
SUMMARY gatheral: rows=20 MATCH=14 OFF_BY_ONE=4 WRONG_PAGE=2 | gold_page_equals_chunk_first_page=20/20
SUMMARY prado: rows=20 MATCH=15 OFF_BY_ONE=5 | gold_page_equals_chunk_first_page=20/20
```

## 7. Step 7 — E5 gatheral probes (output of gatheral_probes.py)

```
### chunks whose page range touches pages 22-27
  c0008 pages=[20, 22] len=1621 path='Figures' | 'minimum monthly return of each coupon period. | 130 11.1 Payoff of a variance swap (dashed line) and volatility swap (solid line) as a funct'
  c0009 pages=[22, 24] len=663 path='Tables' | '6.1 Upper and lower arbitrage bounds for one-year 0.5 strike options for various credit spreads (at-the-money volatility is 20%). | 79 6.2 I'
  c0010 pages=[24, 24] len=2035 path='Foreword' | 'Jim has given round six of these lectures on volatility modeling at the Courant Institute of New York University, slowly purifying these not'
  c0011 pages=[24, 25] len=2055 path='Foreword' | 'II The difference between Jim Gatheral and other members of the quant community lies in the following: To many, models provide a representat'
  c0012 pages=[25, 25] len=85 path='Foreword' | '-Nassim Nicholas Taleb1 June, 2006 1Author, Dynamic Hedging and Fooled by Randomness.'
  c0013 pages=[26, 26] len=2394 path='Preface' | 'E ver since the advent of the Black-Scholes option pricing formula, the study of implied volatility has become a central preoccupation for b'
  c0014 pages=[26, 27] len=20 path='Preface' | 'xxiii xxiv | PREFACE'
  c0015 pages=[27, 27] len=2390 path='Preface' | 'option to the super exotic Napoleon. One of the themes of this book is the representation of implied volatility in terms of a weighted avera'
  c0016 pages=[27, 28] len=350 path='Preface' | 'To be able to follow the mathematics, basic knowledge of probability and stochastic calculus such as could be obtained by reading Neftci (20'

### probes against clean.txt (whitespace collapsed, lowercased)
  full=0 first6words=0  'in this chapter, we begin our exploration of the volatility surface by'
  full=0 first6words=0  'that it might make sense to model volatility as a random variable'
  full=0 first6words=0  'figure 1.1 spx daily log returns from december 31, 1984'
  full=0 first6words=0  'sv models bring some order into this chaos'
  full=0 first6words=0  'there is a simple economic argument that justifies the mean reversion'
  full=0 first6words=0  'consider the distribution of the volatility of ibm in 100 years'
  full=0 first6words=0  'in this section, we follow wilmott (2000) closely'
  full=0 first6words=0  'one need only recall the stock market crash of october 1987'
```

## 8. Errata to REPORT-v6 / v6_1

1. `§9: tests/test_step3.py hash is truncated in the report. Full value: b9611755bbeba6054cf125d546a4642ef3f449a0e5a281b780e8f1a780082c0d`
2. `File count: the skill folder holds 27 files = 19 shipped + 8 *.bak-* backups (README line "26 files" was wrong).`
3. `§5: the sentence "filename ... likely the origin of the misquote" is refuted by 62_prefix_search_and_repro.txt (the same filename reproduces 07a69d09). The origin of the prefixes 254cf54b / aedab848 / 12d83851 in the v5 report is UNEXPLAINED; no file on disk has these hashes.`
4. `§6.2 note: gold_audit.py and the gate both use BM25 k1=1.5, b=0.75 (the note saying b=0.25 is wrong).`

(Verification for item 1: `grep test_step3 /tmp/v7/support/00_hash_before.txt` printed
`b9611755bbeba6054cf125d546a4642ef3f449a0e5a281b780e8f1a780082c0d  ./tests/test_step3.py`.)

## 9. Step 9 — skill folder unchanged + package

```
$ cd ~/.agents/skills/data-prep && find . -type f | sort | xargs sha256sum > /tmp/v7/support/01_hash_after.txt
$ diff /tmp/v7/support/00_hash_before.txt /tmp/v7/support/01_hash_after.txt && echo "SKILL FOLDER UNCHANGED"
SKILL FOLDER UNCHANGED
```

Package (flat copies, plain text only, no zip) — 14 files (13 copied in step 9 + REPORT-v7.md):
```
$ ls -l ~/Downloads/v7_support_files
total 840
-rw-r--r--  1 KHOA  staff    2451 Oct 18 13:36 00_hash_before.txt
-rw-r--r--  1 KHOA  staff    2451 Oct 18 13:36 01_hash_after.txt
-rw-r--r--  1 KHOA  staff     243 Oct 18 13:36 01_script_hashes.txt
-rw-r--r--  1 KHOA  staff     125 Oct 18 13:36 10_xcheck_r6_counts.txt
-rw-r--r--  1 KHOA  staff    2337 Oct 18 13:36 20_trading_episodes_split.txt
-rw-r--r--  1 KHOA  staff    2222 Oct 18 13:36 21_gatheral_episodes_split.txt
-rw-r--r--  1 KHOA  staff   40173 Oct 18 13:36 21_gatheral_lines.txt
-rw-r--r--  1 KHOA  staff  232279 Oct 18 13:36 22_prado_A_lines.txt
-rw-r--r--  1 KHOA  staff   17766 Oct 18 13:36 22_prado_episodes_split.txt
-rw-r--r--  1 KHOA  staff   76667 Oct 18 13:36 23_prado_B_lines.txt
-rw-r--r--  1 KHOA  staff   11572 Oct 18 13:36 60_gold_page_check.txt
-rw-r--r--  1 KHOA  staff    2920 Oct 18 13:36 70_bib_leak.txt
-rw-r--r--  1 KHOA  staff    2350 Oct 18 13:36 80_gatheral_probes.txt
-rw-r--r--  1 KHOA  staff    9690 Oct 18 13:36 REPORT-v7.md

$ sha256sum ~/Downloads/v7_support_files/* | cut -c1-16,65-
44b7bd26f485d2de  /Users/KHOA/Downloads/v7_support_files/00_hash_before.txt
44b7bd26f485d2de  /Users/KHOA/Downloads/v7_support_files/01_hash_after.txt
8531cc018fe41c45  /Users/KHOA/Downloads/v7_support_files/01_script_hashes.txt
ab6f6b63769aec87  /Users/KHOA/Downloads/v7_support_files/10_xcheck_r6_counts.txt
5e07433a177673fa  /Users/KHOA/Downloads/v7_support_files/20_trading_episodes_split.txt
bdd1b84ecf7387b4  /Users/KHOA/Downloads/v7_support_files/21_gatheral_episodes_split.txt
5251f3e323ea63b5  /Users/KHOA/Downloads/v7_support_files/21_gatheral_lines.txt
3455f20bf12c8b50  /Users/KHOA/Downloads/v7_support_files/22_prado_A_lines.txt
d78b7ec4f463a2dd  /Users/KHOA/Downloads/v7_support_files/22_prado_episodes_split.txt
d2e524c5a9a508a7  /Users/KHOA/Downloads/v7_support_files/23_prado_B_lines.txt
ac5050dc6c4d9b9c  /Users/KHOA/Downloads/v7_support_files/60_gold_page_check.txt
47294a331ad35aa5  /Users/KHOA/Downloads/v7_support_files/70_bib_leak.txt
c4e06c65b6f74224  /Users/KHOA/Downloads/v7_support_files/80_gatheral_probes.txt
21014078836bb69a  /Users/KHOA/Downloads/v7_support_files/REPORT-v7.md
```
(00_hash_before and 01_hash_after are byte-identical: 44b7bd26.)

## 10. NOT DONE / UNCERTAIN

none. No STOP and no BLOCKED occurred in any step.
