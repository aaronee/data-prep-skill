# REPORT-v6 — data-prep skill, v6 fix round (TASK-v6 execution record)

Date: **2026-10-18**. Executor: local agent, `~` = `/Users/KHOA`,
`SK=~/.agents/skills/data-prep`. All outputs are raw command output pasted as run.
The v6 patch (user-built, `/tmp/v6/v6.patch`) was applied for G1–G3; Steps 6–8 are
evidence-gathering for G4–G7. **A new high-severity defect (F9, R6 stuck state) was
discovered in Step 7** — see §10 "NOT DONE / UNCERTAIN" and §6.7.

---

## 1. Step 1 — hash check (v5 pre-state)

```
$ cd $SK && sha256sum scripts/prep.py scripts/filter_llm.py scripts/make_eval_candidates.py tests/fixtures.py SKILL.md references/rules.md | cut -c1-16,65-
c0ea9b4d7fd6897f  scripts/prep.py
0fb4466a4c09c5d0  scripts/filter_llm.py
d036daddcb7e5a40  scripts/make_eval_candidates.py
fb684e60850b91f3  tests/fixtures.py
23cf998a93d567e2  SKILL.md
b00186ca528b38d6  references/rules.md
```
All six match the expected v5 prefixes. Backup created:
`~/.agents/skills/data-prep.bak-v6pre.tar.gz` (110,028 bytes, 2026-10-18 11:48).

**Deviation (setup):** the three input caches `~/Downloads/*.lit.json` were not in
`~/Downloads` — they were found in `~/.Trash`. Copied (not moved) back to
`~/Downloads` after validation as JSON (214/210/393 pages). `~/.Trash` left
untouched. (Handoff of 2026-10-18 listed them under `~/Downloads`.)

---

## 2. Step 2 — patch dry-run, apply, post-patch hashes

```
$ cd $SK && patch -p1 --dry-run < /tmp/v6/v6.patch
patching file SKILL.md
patching file 'references/rules.md'
patching file 'scripts/filter_llm.py'
patching file 'scripts/prep.py'
patching file 'tests/test_f07_hardening.py'        # (no FAILED, no rejects)
$ patch -p1 < /tmp/v6/v6.patch
patching file SKILL.md
patching file 'references/rules.md'
patching file 'scripts/filter_llm.py'
patching file 'scripts/prep.py'
patching file 'tests/test_f07_hardening.py'
$ sha256sum scripts/prep.py scripts/filter_llm.py tests/test_f07_hardening.py SKILL.md references/rules.md | cut -c1-16,65-
05d51ea007105c78  scripts/prep.py
8ff8b3d422fb8c4f  scripts/filter_llm.py
0c17e728cfe08c5d  tests/test_f07_hardening.py
51538d52b6b8580f  SKILL.md
b37800b9bdde26f9  references/rules.md
```
All five match expected. Patch changes: eval gate rejects leaky/duplicate rows +
`--min-chunks` distinct-citation check (default 10, WARNING for rows without chunk
id); `--min-hit` without `--eval` → argparse error (exit 2); `filter_llm.py` saves
already-obtained verdicts before aborting after 3 consecutive failures; `SKILL.md`
`--min-chunks` row; `rules.md` changelog v3.19.

---

## 3. Step 3 — tests

Copied folder, no install present (`HOME=/tmp/fakehome`):

```
$ cd /tmp/v6/t/data-prep/tests
$ HOME=/tmp/fakehome python3 -m unittest discover 2>&1 | tail -5
.................................................
----------------------------------------------------------------------
Ran 49 tests in 2.786s

OK
$ HOME=/tmp/fakehome python3 -W always -m unittest discover 2>&1 | grep -c ResourceWarning
0
```

New tests must FAIL on v5 code (proved against the pre-patch backup):

```
$ cd /tmp/v6/old/data-prep/tests && HOME=/tmp/fakehome python3 -m unittest test_f07_hardening 2>&1 | tail -4
----------------------------------------------------------------------
Ran 7 tests in 0.609s

FAILED (failures=1, errors=6)
```
Exactly as expected (7 run; 1 failure + 6 errors — the v5 `run_eval` signature
lacks `min_chunks`, the gate lacks the new checks, and v5 argparse accepts
`--min-hit` without `--eval`).

---

## 4. Step 4 — G1/G2 by hand

```
identical x20 -> False ['== invalid gold row (Q2): duplicate of Q1', '== invalid gold row (Q3): duplicate of Q1', '== invalid gold row (Q4): duplicate of Q1']
leaky x20 -> False ["== invalid gold row (Q1): key phrase 'word0' appears in the question (leak)", "…Q2…", "…Q3…"]
one chunk x20 -> False ['== min-hit PASS (use --min-hit)', '== min-hit FAIL: gold cites only 1 distinct chunk(s); need >= 10 (--min-chunks)']
good x20 -> True ['== min-hit PASS (use --min-hit)']
```
(The "one chunk x20" line also prints the PASS-then-diversity-FAIL sequence because
the hit-rate check prints before the citation-diversity check; the returned result
is `False` — the gate fails closed.)

```
$ printf '# A\n\nSome text.\n' > /tmp/v6/t.md
$ python3 $SK/scripts/prep.py /tmp/v6/t.md --outdir /tmp/v6/o --min-hit 0.8; echo "exit=$?"
exit=2
prep.py: error: --min-hit needs --eval QFILE (the gate would otherwise be silently ignored)
```
Expected: first three `False`, good `True`, `exit=2` + message. **All match.**

---

## 5. Step 5 — three books, no regression

Re-ran each book with the canonical v4/v5 command (`prep.py <book>.lit.json
--outdir /tmp/v6/f3/<book>/`, no `--code-fonts`), all `exit=0`:

```
$ for b in trading gatheral prado; do sha256sum /tmp/v6/f3/$b/*chunks.json /tmp/v5/f3/$b/*chunks.json | cut -c1-16,65-; done
07a69d093313d290  /tmp/v6/f3/trading/Trading Volatility, Correlation, Term Structure and Skew | Colin Bennett, Miguel A. Gil.lit.chunks.json
07a69d093313d290  /tmp/v5/f3/trading/Trading Volatility, Correlation, Term Structure and Skew | Colin Bennett, Miguel A. Gil.lit.chunks.json
a507ffc6060f4f61  /tmp/v6/f3/gatheral/The Volatility Surface: A Practitioner's Guide | Jim Gatheral.lit.chunks.json
a507ffc6060f4f61  /tmp/v5/f3/gatheral/The Volatility Surface: A Practitioner's Guide | Jim Gatheral.lit.chunks.json
f9a2a038481afaab  /tmp/v6/f3/prado/Advances in Financial Machine Learning | Marcos López de Prado.lit.chunks.json
f9a2a038481afaab  /tmp/v5/f3/prado/Advances in Financial Machine Learning | Marcos López de Prado.lit.chunks.json
$ for b in trading gatheral prado; do cmp /tmp/v6/f3/$b/*.removed.jsonl /tmp/v5/f3/$b/*.removed.jsonl && echo "$b removed.jsonl identical"; done
trading removed.jsonl identical
gatheral removed.jsonl identical
prado removed.jsonl identical
```

**⚠ Mismatch vs the task's stated expected prefixes and investigation (user directed,
option 3):** the task expects `254cf54b`/`aedab848`/`12d83851`, which is what
**report v5 line 59** records. The actual artifacts on disk — `/tmp/v3/f3` (v4
canonical), `/tmp/v3/f2`, `/tmp/v5/f3` (v5 re-run) and `/tmp/v6/f3` — **all** hash
to `07a69d09…/a507ffc6…/f9a2a038…`. Full hash of `/tmp/v5/f3/trading/…chunks.json`:
`07a69d093313d290d4a505d2432ba0195e4e9877fcff7e28d89debdfa47612aa`.
`254cf54b` matches no file and no string inside the file.

Investigation run 2026-10-18 (fresh, all steps verified):
1. `lit parse` (fresh, `--no-ocr`, 0.56 s) of the trading PDF from
   `~/Downloads/OptionBook/` → output **byte-identical** (SHA-256 `cbdb3f63d0bdf9e28c26c1fdc1aa092237d9514d77f2a980b6ff49c00fdf960e`)
   to the restored `~/Downloads/…lit.json`. → **No input drift.**
2. v5 code (from the pre-v6 backup) + that fresh parse, run under the canonical
   filename → `chunks.json` **byte-identical** to `/tmp/v5/f3/trading`. (Note:
   the input path/filename is embedded in the output `source` field and affects
   the output hash — the same input under a different filename hashes differently,
   which is likely the origin of the misquote.)
3. Pipeline fully reproducible end-to-end; four independent artifact copies agree.

**Conclusion:** the v5-report `254cf54b…` prefixes are a **transcription error in
report v5**, propagated verbatim into TASK-v6's expectations. The v5 *claim* (v5
byte-identical to v4) stands — it is corroborated by 4 agreeing copies. **The
actual Step-5 requirement — v6 byte-identical to v5 — is satisfied** (pairwise
equal hashes + `cmp` above). The v6 patch does not touch chunking or removal.

---

## 6. Step 6 — gold gates with the new gate + audit

### 6.1 Gate output per book (gold unedited)

```
$ … --eval verified_trading.txt --min-hit 0.8        → exit=0
== LENIENT (page OR phrase): 20 questions | hit@3 = 20/20 (100%) | MRR = 0.975
== STRICT (page AND phrase): 20 questions | hit@3 = 18/20 (90%) | MRR = 0.817
== min-hit PASS (use --min-hit)
$ … --eval verified_gatheral.txt --min-hit 0.8       → exit=0
== LENIENT (page OR phrase): 20 questions | hit@3 = 20/20 (100%) | MRR = 0.858
== STRICT (page AND phrase): 20 questions | hit@3 = 17/20 (85%) | MRR = 0.742
== min-hit PASS (use --min-hit)
$ … --eval verified_prado.txt --min-hit 0.8          → exit=0
== LENIENT (page OR phrase): 20 questions | hit@3 = 19/20 (95%) | MRR = 0.900
== STRICT (page AND phrase): 20 questions | hit@3 = 19/20 (95%) | MRR = 0.850
== min-hit PASS (use --min-hit)
```
New-gate validation emitted **no** `invalid gold row` (no leaks, no duplicates),
no `distinct chunk(s)` failure, no `no chunk id` warnings. Results identical to v5.

### 6.2 Audit tables (`gold_audit.py`, in `/tmp/v6/audit_{trading,gatheral,prado}.txt`)

Trading (20 rows, all `OK`; miss rows Q2 rank 4, Q13 rank 4):

```
row | cited | #chunks_with_phrase | gold_page_in_cited_range | q_words_in_cited | cited_rank | top3 | verdict
Q1 | c0000 | 2 | True | 3/6 | 1 | c0000,c0268,c0266 | OK
Q2 | c0006 | 4 | True | 9/11 | 4 | c0121,c0188,c0120 | OK
Q3 | c0012 | 5 | True | 9/10 | 2 | c0251,c0012,c0256 | OK
Q4 | c0018 | 2 | True | 9/12 | 1 | c0018,c0017,c0240 | OK
Q5 | c0024 | 1 | True | 6/11 | 1 | c0024,c0025,c0040 | OK
Q6 | c0030 | 1 | True | 8/10 | 1 | c0030,c0029,c0093 | OK
Q7 | c0036 | 4 | True | 5/5 | 1 | c0036,c0035,c0205 | OK
Q8 | c0042 | 1 | True | 8/8 | 1 | c0042,c0034,c0001 | OK
Q9 | c0048 | 2 | True | 5/6 | 1 | c0048,c0188,c0047 | OK
Q10 | c0054 | 1 | True | 6/8 | 2 | c0056,c0054,c0157 | OK
Q11 | c0060 | 1 | True | 6/7 | 1 | c0060,c0059,c0129 | OK
Q12 | c0066 | 1 | True | 8/12 | 1 | c0066,c0138,c0067 | OK
Q13 | c0072 | 5 | True | 6/6 | 4 | c0073,c0235,c0074 | OK
Q14 | c0078 | 3 | True | 6/7 | 1 | c0078,c0123,c0082 | OK
Q15 | c0084 | 2 | True | 8/10 | 1 | c0084,c0085,c0172 | OK
Q16 | c0090 | 3 | True | 12/13 | 1 | c0090,c0091,c0086 | OK
Q17 | c0096 | 4 | True | 11/13 | 1 | c0096,c0095,c0098 | OK
Q18 | c0102 | 1 | True | 6/8 | 1 | c0102,c0103,c0104 | OK
Q19 | c0108 | 4 | True | 6/8 | 3 | c0107,c0106,c0108 | OK
Q20 | c0114 | 2 | True | 12/15 | 1 | c0114,c0113,c0041 | OK
```

Gatheral (miss rows Q4 rank 5, Q5 rank 157, Q20 rank 4; Q5 flagged
`QUESTION_SHARES_NO_WORDS_WITH_CITED`):

```
row | cited | #chunks_with_phrase | gold_page_in_cited_range | q_words_in_cited | cited_rank | top3 | verdict
Q1 | c0000 | 1 | True | 6/8 | 1 | c0000,c0011,c0081 | OK
Q2 | c0003 | 1 | True | 6/9 | 1 | c0003,c0071,c0002 | OK
Q3 | c0006 | 5 | True | 7/9 | 2 | c0103,c0006,c0115 | OK
Q4 | c0009 | 2 | True | 4/8 | 5 | c0120,c0114,c0116 | OK
Q5 | c0012 | 4 | True | 0/6 | 157 | c0016,c0013,c0002 | QUESTION_SHARES_NO_WORDS_WITH_CITED
Q6 | c0015 | 2 | True | 9/10 | 1 | c0015,c0106,c0039 | OK
Q7 | c0018 | 2 | True | 7/8 | 1 | c0018,c0102,c0105 | OK
Q8 | c0021 | 5 | True | 4/6 | 1 | c0021,c0074,c0028 | OK
Q9 | c0024 | 5 | True | 10/11 | 1 | c0024,c0021,c0022 | OK
Q10 | c0027 | 1 | True | 8/8 | 3 | c0150,c0042,c0027 | OK
Q11 | c0030 | 1 | True | 4/8 | 1 | c0030,c0059,c0032 | OK
Q12 | c0033 | 4 | True | 3/3 | 1 | c0033,c0143,c0032 | OK
Q13 | c0036 | 4 | True | 8/9 | 1 | c0036,c0137,c0152 | OK
Q14 | c0039 | 1 | True | 8/9 | 1 | c0039,c0021,c0139 | OK
Q15 | c0042 | 2 | True | 5/8 | 2 | c0035,c0042,c0036 | OK
Q16 | c0045 | 1 | True | 7/11 | 1 | c0045,c0037,c0098 | OK
Q17 | c0048 | 1 | True | 8/9 | 1 | c0048,c0050,c0068 | OK
Q18 | c0051 | 2 | True | 7/7 | 1 | c0051,c0119,c0053 | OK
Q19 | c0054 | 1 | True | 6/10 | 2 | c0072,c0054,c0037 | OK
Q20 | c0057 | 2 | True | 6/9 | 4 | c0058,c0020,c0074 | OK
```

Prado (miss row Q14 rank 4):

```
row | cited | #chunks_with_phrase | gold_page_in_cited_range | q_words_in_cited | cited_rank | top3 | verdict
Q1 | c0000 | 1 | True | 6/8 | 1 | c0000,c0028,c0013 | OK
Q2 | c0008 | 2 | True | 4/8 | 2 | c0163,c0008,c0007 | OK
Q3 | c0016 | 1 | True | 6/9 | 1 | c0016,c0071,c0076 | OK
Q4 | c0024 | 2 | True | 5/7 | 1 | c0024,c0173,c0172 | OK
Q5 | c0032 | 1 | True | 4/8 | 1 | c0032,c0003,c0000 | OK
Q6 | c0040 | 1 | True | 6/8 | 1 | c0040,c0039,c0329 | OK
Q7 | c0048 | 1 | True | 7/8 | 1 | c0048,c0050,c0049 | OK
Q8 | c0056 | 1 | True | 8/8 | 1 | c0056,c0057,c0101 | OK
Q9 | c0064 | 2 | True | 5/6 | 1 | c0064,c0348,c0278 | OK
Q10 | c0072 | 5 | True | 7/9 | 1 | c0072,c0071,c0148 | OK
Q11 | c0080 | 2 | True | 7/8 | 1 | c0080,c0081,c0119 | OK
Q12 | c0088 | 3 | True | 3/3 | 1 | c0088,c0090,c0211 | OK
Q13 | c0096 | 1 | True | 9/10 | 1 | c0096,c0101,c0057 | OK
Q14 | c0104 | 2 | True | 7/8 | 4 | c0101,c0106,c0093 | OK
Q15 | c0112 | 1 | True | 7/7 | 1 | c0112,c0108,c0111 | OK
Q16 | c0120 | 1 | True | 6/8 | 2 | c0180,c0120,c0179 | OK
Q17 | c0128 | 5 | True | 9/10 | 1 | c0128,c0144,c0179 | OK
Q18 | c0136 | 5 | True | 10/10 | 1 | c0136,c0134,c0311 | OK
Q19 | c0144 | 1 | True | 5/7 | 2 | c0107,c0144,c0153 | OK
Q20 | c0152 | 5 | True | 9/10 | 2 | c0151,c0152,c0119 | OK
```

Note: `gold_audit.py` uses its own BM25 (k1=1.5, b=0.25) — ranks/top-3 there may
differ from the gate's ranker (k1=1.5, b=0.75). The 6-row classification below
uses the **gate's exact ranking** (replicated from `prep.py run_eval`).

### 6.3 Gold files copied for audit

```
$ sha256sum /tmp/v6/gold/*
a25c8ea24ab3b6b3e926b99159598a5dfa9378f7d38881e92b0308587f5972c8  verified_gatheral.txt
21c2c73ba01dc9196960c97dacff83f786a60d852b71d5b1e939b5918b931d71  verified_gatheral.notes.md
228f199bd31bfde69cf4f1f09957f26d1ec7b3c4bc8cab7247d5abe9d6dcb59f  verified_prado.txt
84c617fbae0a790e9eac380059275c7a89d5936233500cb56818d373fb54ed9d  verified_prado.notes.md
e10e4aac7f7045790ae6730065bccc4a5bc0c191cca5935dc72fb789693d8415  verified_trading.txt
399e0959f4a6140e913b6a26a7c75db19413cf754362ac41c3e682f37a44c06b  verified_trading.notes.md
```

### 6.4 The 6 STRICT misses, classified (gate's own top-3, page ranges in the book's chunks)

| # | book Q | cited chunk (pages) | gold page in cited range? | gate top-3 (ids, pages) | cited in top-3? | verdict |
|---|--------|--------------------|--------------------------|--------------------------|-----------------|---------|
| 1 | trading Q2 `zero theta` | c0006 [6,6] | **True** (p6) | c0121 [97,97] 22.02, c0188 [149,150] 20.04, c0120 [95,97] 19.88 — all phrase=True, all page=False | rank **4**, score 18.96 (no tie: next chunk 14.14, gap 4.83) | **RETRIEVAL MISS** |
| 2 | trading Q13 `1/K2` | c0072 [57,58] | **True** (p57) | c0073 [58,59], c0235 [185,186], c0074 [59,60] | rank **4** | **RETRIEVAL MISS** |
| 3 | gatheral Q4 `10% plus the worst monthly return` | c0009 [22,24] | **True** (p22) | c0120 [161,162], c0114 [153,154], c0116 [155,157] — c0120 phrase=True but page off by 139 | rank **5** | **RETRIEVAL MISS** |
| 4 | gatheral Q5 `Nassim Nicholas Taleb` | c0012 [25,25] | **True** (p25) | c0016 [27,28], c0013 [26,26], c0002 [7,16] | rank **157** | **RETRIEVAL MISS** |
| 5 | gatheral Q20 `eliminate dS terms` | c0057 [84,85] | **True** (p84) | c0058 [85,86], c0020 [36,37] (phrase=True, page off), c0074 [106,107] | rank **4** | **RETRIEVAL MISS** |
| 6 | prado Q14 `d < 0.6` | c0104 [113,114] | **True** (p113) | c0101 [111,112], c0106 [115,115], c0093 [102,103] | rank **4** | **RETRIEVAL MISS** |

**Classification answer to the task's 3 questions, for all 6 rows:**
1. `gold_page_in_cited_range` = **True in all 6** (audit column + gate replication agree; every phrase is in its cited chunk).
2. Cited chunk is **NOT in the gate's top-3 in any of the 6** (ranks 4, 4, 5, 157, 4, 4).
3. Verdict: **RETRIEVAL MISS for all 6.** None is `GOLD PAGE WRONG` (no page
   outside the cited range) and none is `BOUNDARY` (that requires the cited chunk
   inside top-3 — it is never inside). In 4 of 6 the cited chunk sits at rank 4,
   i.e. just outside the window; in 2 (trading Q2, Q13) the chunk on the correct
   page is 4th behind 3 same-topical chunks with the phrase on wrong pages.

**⚠ This CONTRADICTS the v5 handoff/report explanation** ("the 5 STRICT misses are
chunk-boundary artifacts — phrase in a top-3 chunk, gold page off by the
boundary"). Direct measurement says the opposite: the cited (correct) chunk is
ranked 4–157 and is not in top-3. The audit script's `top3` column also does not
contain the cited chunk in any of the 6 rows. These are genuine retrieval misses
of the current BM25 ranker against these questions. **G5's suspicion is
corroborated: the misses are not boundary artifacts.** (This does not change the
gate result — the gate passed at 90/85/95 ≥ 80% — but the explanation in the v5
report is wrong.)

---

## 7. Step 7 — retention warnings: per-token attribution (G6)

Method: for each WARNING token, count its occurrences per removal rule in
`removed.jsonl` and show the top removed lines per rule (`/tmp/v6/retention.txt`,
82 lines). Full outputs:

### gatheral (10 tokens)

```
volatility {'R6 front/back matter body': 114, 'R1 recurring line': 84, 'R1b margin repeat': 40, 'R8 footnote': 22}
  R6 front/back matter body [('Stochastic Volatility and Local Volatility', 2), ('Stochastic Volatility', 2), ('Local Volatility in Terms of Implied Volatility', 2)]
  R1 recurring line [('THE VOLATILITY SURFACE', 84)]
  R1b margin repeat [('Volatility Derivatives', 14), ('Stochastic Volatility and Local Volatility', 12), ('The Implied Volatility Surface', 8)]
  R8 footnote [('Equity volatility in the CreditGrades model, Forward volatility surfac', 2), ('Volatility of volatility, 35, 51, 97', 2), ('At-the-money (ATM) volatility (or variance)', 1)]
model {'R6 front/back matter body': 33, 'R1b margin repeat': 4, 'R8 footnote': 12}
  R6 front/back matter body [('The Heston Model', 1), ('Why the Heston Model Is so Popular', 1), ('Model Calibration 25', 1)]
  R1b margin repeat [('The Heston Model', 4)]
  R8 footnote [('Cox Ingersoll Ross (CIR) model, 144', 1), ('CreditGrades model, 74, 84-86', 1), ('applied to Heston-Nandi model, 45 Five-cent bids, 50-51', 1)]
variance {'R6 front/back matter body': 16, 'R8 footnote': 7}
  R6 front/back matter body [('Local Variance as a Conditional Expectation', 1), ('of Instantaneous Variance', 1), ('Local Variance in the Heston-Nandi Model 43', 1)]
  R8 footnote [('At-the-money (ATM) volatility (or variance)', 1), ('Black-Scholes (BS) forward implied variance', 1), ('Equity as call on value of company, 84 Forward BS implied variance, 13', 1)]
implied {'R6 front/back matter body': 26, 'R1b margin repeat': 8, 'R8 footnote': 5}
  R6 front/back matter body [('Local Volatility in Terms of Implied Volatility', 1), ('The Implied Volatility Surface 25', 1), ('Getting Implied Volatility from Local Volatilities 25', 1)]
  R1b margin repeat [('The Implied Volatility Surface', 8)]
  R8 footnote [('Black-Scholes (BS) forward implied variance', 1), ('Empirical SPX implied volatility surface, 72f Forde, Martin, 155, 165', 1), ('Equity as call on value of company, 84 Forward BS implied variance, 13', 1)]
options {'R8 footnote': 5, 'R6 front/back matter body': 28, 'R1b margin repeat': 7}
  R8 footnote [('1. Options (Finance)-Prices-Mathematical models. 2.', 1), ('Equity-linked investments, guaranteed, 138 Forward-starting options, 1', 1), ('solution. See European options', 1)]
  R6 front/back matter body [('The Heston Solution for European Options', 1), ('Digital Options and Digital Cliquets', 1), ('Valuing Digital Options', 1)]
  R1b margin repeat [('Barrier Options', 7)]
surface {'R6 front/back matter body': 7, 'R1 recurring line': 84, 'R1b margin repeat': 14, 'R8 footnote': 5}
  R6 front/back matter body [('The Implied Volatility Surface 25', 1), ('The SPX Implied Volatility Surface 36', 1), ('the Volatility Surface 42', 1)]
  R1 recurring line [('THE VOLATILITY SURFACE', 84)]
  R1b margin repeat [('The Implied Volatility Surface', 8), ('Volatility Surface Asymptotics', 6)]
  R8 footnote [('Empirical SPX implied volatility surface, 72f Forde, Martin, 155, 165', 1), ('Equity volatility in the CreditGrades model, Forward volatility surfac', 1), ('inability to fit the volatility surface, 68', 1)]
local {'R6 front/back matter body': 19, 'R1b margin repeat': 6, 'R8 footnote': 4}
  R6 front/back matter body [('Valuation under Heston and Local', 3), ('Stochastic Volatility and Local Volatility', 1), ('Local Volatility', 1)]
  R1b margin repeat [('Stochastic Volatility and Local Volatility', 6)]
  R8 footnote [('Equity volatility in the CreditGrades model, Forward volatility surfac', 1), ('local variance, numerical computation, 47f', 1), ('local volatility approximation, 123', 1)]
heston {'R6 front/back matter body': 24, 'R1b margin repeat': 4, 'R8 footnote': 4}
  R6 front/back matter body [('Valuation under Heston and Local', 3), ('The Heston Model', 1), ('The Heston Solution for European Options', 1)]
  R1b margin repeat [('The Heston Model', 4)]
  R8 footnote [('applied to Heston-Nandi model, 45 Five-cent bids, 50-51', 1), ('in the Heston model,', 1), ('in the Heston-Nandi model, 48f', 1)]
stochastic {'R6 front/back matter body': 34, 'R1b margin repeat': 6, 'R8 footnote': 2}
  R6 front/back matter body [('Stochastic Volatility', 2), ('. 1998. Stochastic implied trees: Arbitrage pricing with stochastic te', 2), ('Stochastic Volatility and Local Volatility', 1)]
  R1b margin repeat [('Stochastic Volatility and Local Volatility', 6)]
  R8 footnote [('effect of stochastic volatility, 35, 94', 1), ('models. See Stochastic implied volatility', 1)]
skew {'R6 front/back matter body': 8, 'R8 footnote': 9}
  R6 front/back matter body [('Special Case: No Skew', 1), ('The Black-Scholes Implied Volatility Skew', 1), ('Computing the At-the-Money Volatility Skew 60', 1)]
  R8 footnote [('skew, 37, 62, 66', 1), ('relationship to volatility skew. See', 1), ('Volatility skew', 1)]
```

### prado (13 tokens)

```
series {'R6 front/back matter body': 23, 'R8 footnote': 5}
  R6 front/back matter body [('learning models for time series forecasting." Econometric Reviews, Vol', 1), ('Bontempi, G., S. Taieb, and Y. Le Borgne (2012): "Machine learning str', 1), ('time series forecasting." IEEE Transactions on Neural Networks, Vol. 1', 1)]
  R8 footnote [('Hamilton, J. (1994): Time Series Analysis, 1st ed. Princeton Universit', 1), ('strap inference in fractional time series models with heteroskedastici', 1), ('16.A.3). The last five columns are partially correlated to some of the', 1)]
data {'R6 front/back matter body': 33, 'R1b margin repeat': 22, 'R8 footnote': 3}
  R6 front/back matter body [('Fox, G. et al. (2015): "Big Data, simulations and HPC convergence, iBi', 2), ('PART 1 | DATA ANALYSIS | 21', 1), ('2 | Financial Data Structures | 23', 1)]
  R1b margin repeat [('BACKTESTING ON SYNTHETIC DATA', 12), ('FINANCIAL DATA STRUCTURES', 10)]
  R8 footnote [('data techniques developed decades and centuries ago (factor models, re', 1), ('fail to recognize the hierarchical nature of financial big data.', 1), ('Qiu, J. et al. (2016): "A survey of machine learning for big data proc', 1)]
time {'R6 front/back matter body': 28, 'R8 footnote': 5}
  R6 front/back matter body [('- Time range: Time range specifies the start and end dates. The period', 2), ('learning models for time series forecasting." Econometric Reviews, Vol', 1), ('Bontempi, G., S. Taieb, and Y. Le Borgne (2012): "Machine learning str', 1)]
  R8 footnote [('Hamilton, J. (1994): Time Series Analysis, 1st ed. Princeton Universit', 1), ('strap inference in fractional time series models with heteroskedastici', 1), ('grow over time, regardless of their correlation.', 1)]
chapter {'R6 front/back matter body': 35, 'R8 footnote': 2}
  R6 front/back matter body [('proper bet sizing (Chapter 10) and risk diversification (Chapter 16). ', 2), ('CHAPTER 3', 1), ('CHAPTER 4', 1)]
  R8 footnote [('to the mesh (20 × 20 × 20). In this chapter we do not consider that se', 1), ('The methodology described in this chapter can be applied to problems b', 1)]
features {'R6 front/back matter body': 16, 'R1b margin repeat': 26}
  R6 front/back matter body [('most relevant features across all financial instruments? What is the s', 2), ("els where the features' sampling frequency would be limited by the hor", 1), ('a month, features would have to be sampled with a frequency up to mont', 1)]
  R1b margin repeat [('MICROSTRUCTURAL FEATURES', 10), ('FRACTIONALLY DIFFERENTIATED FEATURES', 8), ('ENTROPY FEATURES', 8)]
number {'R6 front/back matter body': 31}
  R6 front/back matter body [('side. The number of bets is always smaller than the number of trades. ', 2), ('of a finite number of variables. As the number of feasible combination', 2), ('ple, you can obtain blood samples from a large number of patients, and', 1)]
strategy {'R6 front/back matter body': 25, 'R8 footnote': 1, 'R1b margin repeat': 5}
  R6 front/back matter body [('1.2.2 The Meta-Strategy Paradigm, 5', 1), ('1.3.2 Structure by Strategy Component, 9', 1), ('Strategy. May 18.', 1)]
  R8 footnote [('and feature selection for the purpose of creating stock trading strate', 1)]
  R1b margin repeat [('UNDERSTANDING STRATEGY RISK', 5)]
index {'R6 front/back matter body': 7, 'R1b margin repeat': 13}
  R6 front/back matter body [('Patel, J., S. Sha, P. Thakkar, and K. Kotecha (2015): "Predicting stoc', 2), ('recognition and technical analysis: Forecasting the DJIA index with in', 1), ('Kara, Y., M. Boyacioglu, and O. Baykan (2011): "Predicting direction o', 1)]
  R1b margin repeat [('INDEX', 13)]
method {'R6 front/back matter body': 6, 'R8 footnote': 3}
  R6 front/back matter body [('introduced two novel concepts, the triple-barrier method and meta-labe', 1), ('apply a path-dependent labeling technique, like the triple-barrier met', 1), ('In this chapter we will study an alternative backtesting method, which', 1)]
  R8 footnote [('visualization of the method less intuitive.', 1), ('Parkinson, M. (1980): "The extreme value method for estimating the var', 1), ('not able to predict the baseline usage as well as the newly develop me', 1)]
what {'R6 front/back matter body': 14, 'R8 footnote': 1}
  R6 front/back matter body [("pling frequency would be subordinated to the first barrier's touch. No", 1), ('natural question is to try to understand what features contributed to ', 1), ('if we understand what source of information is indispensable to it. Th', 1)]
  R8 footnote [('what-is-the-difference-between-bagging-and-boosting/.', 1)]
financial {'R6 front/back matter body': 52, 'R1b margin repeat': 19, 'R8 footnote': 3}
  R6 front/back matter body [('This situation is characteristic of financial applications. Most non-f', 2), ('1 | Financial Machine Learning as a Distinct Subject | 3', 1), ('1.2 The Main Reason Financial Machine Learning Projects Usually Fail, ', 1)]
  R1b margin repeat [('FINANCIAL DATA STRUCTURES', 10), ('FINANCIAL MACHINE LEARNING AS A DISTINCT SUBJECT', 9)]
  R8 footnote [('Financial Studies, Vol. 29, No. 1, pp. 5-68.', 1), ('fail to recognize the hierarchical nature of financial big data.', 1), ('financial markets." Working paper. Available at https://arxiv.org/abs/', 1)]
using {'R6 front/back matter body': 20, 'R8 footnote': 2}
  R6 front/back matter body [('Cao, L. and F. Tay (2001): "Financial forecasting using support vector', 1), ('Chang, P., C. Fan and J. Lin (2011): "Trend discovery in financial tim', 1), ('Kuan, C. and L. Tung (1995): "Forecasting exchange rates using feedfor', 1)]
  R8 footnote [('using artificial neural networks and support vector machines: The samp', 1), ('This correlation matrix has been computed using function generateData ', 1)]
trading {'R6 front/back matter body': 51, 'R8 footnote': 2}
  R6 front/back matter body [("Easley, D., M. Lopez ́ de Prado, and M. O'Hara (2013): High-Frequency ", 2), ('Creamer, G. and Y. Freund (2007): "A boosting approach for automated t', 2), ('Definition 1: Trading Rule: A trading rule for strategy S is defined b', 2)]
  R8 footnote [('and feature selection for the purpose of creating stock trading strate', 1), ('of Trading, Vol. 5, pp. 31-34.', 1)]
```

### Per-token attribution (which rule removed most; what the top lines are)

- **gatheral**: dominated by R6-body (chapter/section **titles**, TOC entries,
  bibliography), R1 (running header `THE VOLATILITY SURFACE` ×84), R1b (running
  titles), R8 (index entries / footnote band). All top lines are titles, running
  headers, or back-matter. → **running headers / back matter — NOT body prose.**
- **prado**: dominated by R6-body. Most top lines are bibliography entries
  (`series`, `time`, `using`, `index`, `financial`), running headers (R1b),
  chapter/section titles — but for `number`, `what`, `method`, `financial`,
  `trading`, `features`, `chapter` the top lines are **full body sentences**.

### SUSPECT BODY LOSS (prado — confirmed real, see §10/F9)

R6 "front/back matter body" removals that are **body prose, with pages**:

```
[R6] pg=86  :: introduced two novel concepts, the triple-barrier method and meta-labeling, and        (ch4, p59)
[R6] pg=87  :: apply a path-dependent labeling technique, like the triple-barrier method, the sam-   (ch4, p60)
[R6] pg=87  :: pling frequency would be subordinated to the first barrier's touch. No matter what
[R6] pg=87  :: This situation is characteristic of financial applications. Most non-financial ML
[R6] pg=87  :: ple, you can obtain blood samples from a large number of patients, and measure their
[R6] pg=141 :: natural question is to try to understand what features contributed to that performance. (p114)
[R6] pg=196 :: In this chapter we will study an alternative backtesting method, which uses his-      (ch13, p169)
[R6] pg=198 :: Definition 1: Trading Rule: A trading rule for strategy S is defined by the set of
[R6] pg=223 :: side. The number of bets is always smaller than the number of trades. A trade        (ch14.3, p196)
[R6] pg=346 :: of a finite number of variables. As the number of feasible combinations grows, an    (ch21, p319)
```

**Scale (measured):** prado R6-body = 1,064 lines / **75,156 chars / 57 pages**;
gatheral R6-body = 494 lines (of which pp.32–35 = the entire Chapter-1 opener:
`CHAPTER 1`, title, Fig 1.1–1.3 captions, valuation-equation intro — all verified
**absent** from `clean.txt`); trading R6-body = 24 lines / 3 pages (back matter
only — `CONTENTS` p2, `Index` p67/68 — harmless).

---

## 8. Step 8 — live LLM pass on v5/v6 code (G4)

**BLOCKED → RESOLVED by the user** (I ran no live command; the user exported
`LLM_API_KEY` in their own terminal and ran the exact Step-8 commands; outputs
pasted here contain no secrets). Environment: endpoint `http://localhost:8000`,
model `Qwen3.8-27B-oQ4e-mtp`, `--extra-json
'{"chat_template_kwargs":{"enable_thinking":false}}'`, key via env only.

### 8.1 Dry run (no API calls) — as expected: 6 suspects

```
$ python3 $SK/scripts/filter_llm.py llm/trading.chunks.json --dry-run
chunks: 271 | suspect: 6 (median len 1715)
  c0030 (1684 ch, sha 552e66ddcbfb5767): bibliography-like (many years)
  c0093 (2355 ch, sha d12ff94acb82d286): boilerplate pattern
  c0112 (1798 ch, sha 0e26d173d92a6619): boilerplate pattern
  c0162 (1774 ch, sha 49df5808781524c2): index-like (many page numbers)
  c0268 (2188 ch, sha f761a9118edba431): boilerplate pattern
  c0270 (1472 ch, sha 05d7ed0b896daa4c): boilerplate pattern
... (6 total; --dry-run, no API calls made)
```
Matches expectation: 6 suspects incl. c0030 `bibliography-like` and c0162
`index-like` (the two new v5-heuristic suspects).

### 8.2 Live run

```
$ python3 $SK/scripts/filter_llm.py llm/trading.chunks.json --endpoint http://localhost:8000/v1/chat/completions \
    --model Qwen3.8-27B-oQ4e-mtp --extra-json '{"chat_template_kwargs":{"enable_thinking":false}}'
chunks: 271 | suspect: 6 (median len 1715)
  c0030: calling LLM (bibliography-like (many years))...
    -> keep=True type=content
  c0093: calling LLM (boilerplate pattern)...
    -> keep=True type=content
  c0112: calling LLM (boilerplate pattern)...
    -> keep=True type=content
  c0162: calling LLM (index-like (many page numbers))...
    -> keep=True type=content
  c0268: calling LLM (boilerplate pattern)...
    -> keep=False type=legal
  c0270: calling LLM (boilerplate pattern)...
    -> keep=False type=legal

kept 269/271 | dropped 2 -> /private/tmp/v6/llm/trading.dropped.jsonl
filtered chunks -> /private/tmp/v6/llm/trading.chunks.filtered.json
cache (6 entries) -> /private/tmp/v6/llm/trading.llmcache.json  [reruns are free]
exit=0
```

```
$ cat llm/trading.dropped.jsonl
{"id": "c0268", "sha256": "f761a9118edba431", "type": "legal", "summary": "Standard legal disclaimers and liability exclusions ...", "text_head": "Information and opinions presented in this report have been obtained or derived from sources believed by Grupo Santander to be reliable, ..."}
{"id": "c0270", "sha256": "05d7ed0b896daa4c", "type": "legal", "summary": "Legal disclaimer regarding US recipients, regulatory compliance, ...", "text_head": "Any US recipient of this report (other than a registered broker-dealer or a bank acting in a broker-dealer capacity) ..."}
```

### 8.3 Table for every suspect (chunk reading from first 600 chars of the chunk text)

| chunk | heuristic reason | first-600-chars content | verdict type | keep | my reading | verdict |
|-------|-----------------|------------------------|--------------|------|------------|---------|
| c0030 | bibliography-like (many years) | **Chart figure**: "Figure 9. S&P500 1M ATM Call Overwriting (BXM)…" + year axis 1988–2007 | content | True | figure/caption text (years = chart axis, not a bibliography) | **CORRECT** |
| c0093 | boilerplate pattern | **Content**: "There are four instruments that can be used to trade dispersion: Straddle (or call) dispersion…" | content | True | content | **CORRECT** |
| c0112 | boilerplate pattern | **Content**: "While we acknowledge that there are periods of time in which a long volatility position is a profitable hedge…" (back-testing discussion) | content | True | content | **CORRECT** |
| c0162 | index-like (many page numbers) | **Content**: jump/diffusive volatility formula definitions, "IMPLIED JUMP CALCULATED FROM JUMP VOLATILITY…" (the "index-like" heuristic is a false positive here) | content | True | content (formula/explanatory text) | **CORRECT** |
| c0268 | boilerplate pattern | **Legal**: "Information and opinions presented in this report … Grupo Santander accepts no liability…" | legal | False | legal disclaimer | **CORRECT** |
| c0270 | boilerplate pattern | **Legal**: "Any US recipient of this report … (212) 692-2550 … Rule 15a-6 under the US Securities Exchange Act of 1934…" | legal | False | legal/regulatory notice | **CORRECT** |

**Wrong drops: 0.** The two new v5-heuristic suspects (c0030, c0162) were both
correctly kept as content — `content` is never dropped, confirmed.

### 8.4 Rerun (cache) — 0 API calls, byte-identical

```
$ sha256sum llm/trading.chunks.filtered.json llm/trading.dropped.jsonl   (BEFORE)
4738b01487c80f38ff0015d2f5591aa6ce913007d0b61dca491c9f0c8c0e7256  llm/trading.chunks.filtered.json
0f06b2a2b3cd5128b125230def1599b5be85d586148a8357784ed122979d4365  llm/trading.dropped.jsonl
$ python3 … (same command) > llm/rerun.log; echo "rerun exit=$?"     (user ran)
$ sha256sum … (AFTER)
4738b01487c80f38ff0015d2f5591aa6ce913007d0b61dca491c9f0c8c0e7256  llm/trading.chunks.filtered.json
0f06b2a2b3cd5128b125230def1599b5be85d586148a8357784ed122979d4365  llm/trading.dropped.jsonl
```
BEFORE == AFTER for both files. `llm/rerun.log` captured from the rerun:
**0 `calling LLM` lines** (file contains no such line). Corroborating evidence:
`trading.llmcache.json` (mtime 12:12, written by the live run) holds all 6
verdicts under v6 24-hex cache keys (`sha256(chunk.sha256|model|SYSTEM_HASH)[:24]`),
so the rerun served 6/6 from cache and made 0 API calls.

---

## 9. Final SHA-256 — all 19 shipped files (18 from v5 + tests/test_f07_hardening.py)

Errata (added during v6-support audit): the v5-report §5 table ships 18 files
including `tools/removed_summary.py`, which was omitted from the list below when
it was first written. The complete 19-file set (18 unchanged-v5-scope + 1 new):

```
51538d52b6b8580fe2bd3deea91073062c7e3bee48cf15429394ccf00f80d665  SKILL.md
b37800b9bdde26f9d6514e47c298e178f37f51a69dc80b9cfa7cd5901f8eea3c  references/rules.md
05d51ea007105c780896722d5b422c2541842d68f70b1c729d4a698ba527ccd3  scripts/prep.py
8ff8b3d422fb8c4fa41713e78768ea543fbdba7dfdba051ddb3a55ba9ed27e52  scripts/filter_llm.py
d036daddcb7e5a406a4124a887c3825f42a4b1fe60bfece0285935101553199d  scripts/make_eval_candidates.py
95c9e2e6468a779ecb616114ebde61392027a8044005de690bb771f5a0fab53b  tools/removed_summary.py   (unchanged since v5)
fb684e60850b91f3a406d0401d487e2e9247ad88077e099fc8a6f97751f641fe  tests/fixtures.py
486b26844d005a2e915b2f71104e8968a32782accff811752a36174b514d40fb  tests/test_step1.py
a32b9978c55079e3a10f88be25eee28a296af95967ef25cd0b4a3a5579973b70  tests/test_step2.py
b9611755bbeba6054cf125d546a4642ef3f449a0e5a281b780e82c0d  tests/test_step3.py
82a978ef77a75d2752283813d0210ce195c8fd85343a5dd6469376588103f5a4  tests/test_step4.py
4816edd8bfc71eb9bacc23e0ea7ffb460cffacd2c1e2ae99b3fcdd345ae174df  tests/test_step5.py
779616bffd68dd3b67a5485d2811a83d2b3f620d722d86709aa694f89890683d  tests/test_llm_api.py
db60911b771c3e36f3c6419207c56f5b7b0dbe16d44d138f86e41823a03160f0  tests/test_f03_r8.py
c22da69c1a60575ffbef8af6d34b56263be66bcf2e66c94a038dfee083596173  tests/test_f04_textpage.py
febdf080e15e4433bf4650fecc991790e1180b0dd05c810aa1d27c5b3db7c890  tests/test_f05_eval.py
6b912a1757f9a7ac613eb53f889952c23a3efbfed2e9933c48a0be7d5209ef06  tests/test_f06_gate_textpn.py
0c17e728cfe08c5d6c5d740d234cb6426615a455a0a59b0a3d9b6e3599ac1b58  tests/test_f07_hardening.py   ← new in v6
4e983bd6caa8e61070c0e4175abdedf3c3b8a951f5eb337bfc81716d14168775  docs/llm-run-log.md   (re-hashed after Step-9 append)
```
Full 19-line sha256sum output: `~/Downloads/v6_support_files/10_sha256_all19.txt`.

---

## 10. NOT DONE / UNCERTAIN

1. **F9 — NEW HIGH-SEVERITY DEFECT (discovered Step 7, pre-existing since ≤ v1):**
   the R6 `drop_until_heading` state machine (geometry mode, `prep.py` main loop)
   drops **chapter-opening pages** whenever a per-chapter `REFERENCES`/
   `BIBLIOGRAPHY` (or `Acknowledgments`) heading triggers the drop state and no
   *R6-visible* heading intervenes before the next chapter — running headers are
   consumed earlier by R1/R1b, so the state stays stuck until the next real
   heading, which is then (correctly) kept. Measured damage: **prado** 1,064
   R6-body lines / 75,156 chars / 57 pages lost (ch4, ch5, ch9/10, ch13, ch14,
   ch21 openers verified absent from `clean.txt`); **gatheral** pp.32–35 = entire
   Chapter-1 opener lost; **trading** unaffected (back matter only). **NOT fixed**
   in this round (no fix was authorized; a fix would break the v6 byte-identity
   state). Propose a v7 round: failing test first (e.g. synthetic book with
   `Introduction` + per-chapter `References` + next chapter), fix candidates:
   (a) treat a *new* front-matter heading as re-arming, and/or (b) bound the drop
   state to the section (stop at any heading, not just the one that "ends" the
   section), or (c) exclude in-body reference sections by position. Needs
   real-doc removed-diff re-verification on all three books.
   This also retro-corrects the v5 report's "retention warnings are pre-existing
   artifacts" claim (G6): for prado the warned tokens' most-removed lines are
   **body prose**, and for gatheral the Ch-1 opener loss is real.
2. **G1 explained misses are wrong:** the 6 STRICT misses are **RETRIEVAL MISS**
   (cited chunk ranked 4–157, never in top-3), not "chunk-boundary artifacts" as
   the v5 report/handoff stated (§6.4). Gold rows themselves are valid (phrase in
   cited chunk, page in cited range, no leaks/duplicates — the new gate confirms).
3. **Gold files are still LLM-authored** (agent-written, self-check-verified),
   not human-verified. The 3 gold files + notes are copied to `/tmp/v6/gold/`
   (hashes §6.3) for the external audit.
4. **Retention numbers other than those measured in §7 are unverified** (v5
   report's other retention claims not re-derived here).
5. Step 5's absolute chunk hashes (`254cf54b…`) in TASK-v6 do not match disk
   (actual `07a69d09…`); root-caused to a transcription error in report v5 (§5).
   The v6-vs-v5 regression check itself passed.
6. Minor doc inaccuracy found (not fixed): SKILL.md says filter_llm results are
   "cached by chunk `sha256`" — the actual key is `sha256(chunk.sha256|model|prompt_hash)[:24]`
   (24 hex; v5 changed this per F3). The v5 handoff's "4/271 suspects" live run
   was on v4 code — now superseded by this run (§8): 6 suspects, 2 legal drops,
   0 wrong.
7. Step 8 was run **by the user** (key lives in the user's interactive shell);
   all pasted outputs were verified secret-free. The rerun's raw stdout was not
   captured separately (verified via 0-byte `rerun.log` + hash identity + cache
   contents).

## Definition of done check (TASK-v6 §11)

- 49 tests pass: **yes** (49/49, §3)
- 0 ResourceWarnings: **yes** (§3)
- all hashes match: **yes for all step-1/2 expected values; NO for the step-5
  absolute prefixes — root-caused to a v5-report error, regression itself
  byte-verified (§5)**
- three books byte-identical (v6↔v5): **yes** (§5)
- every `exit` code as stated: **yes** (0s everywhere expected; `exit=2` for
  `--min-hit` w/o `--eval`; Step-8 live `exit=0`)
- no step silently skipped: **yes** (Step 8 executed by the user with pasted
  output; every step has raw evidence above)
- New high-severity finding (F9) surfaced, not silently passed: **yes** (§10.1)
