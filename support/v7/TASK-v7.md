# TASK-v7 — data-prep skill: EVIDENCE ROUND (read-only, no code changes)

Audience: the local agent. Follow the steps IN ORDER. Do not skip, merge or reorder them.
This round **changes no skill file**. It only runs five read-only helper scripts and collects their raw output.
Another reviewer (not you) will interpret the output. **Do not interpret, fix, rank or explain.**
Paste raw output; the only judgements you may write are the PASS/FAIL checks that this file defines.

## 0. Rules (read twice)

1. Do NOT edit, create or delete any file under `~/.agents/skills/data-prep/` (no code, no docs, no tests, no `.bak` cleanup). Everything you write goes under `/tmp/v7/` or `~/Downloads/v7_support_files/`.
2. Do NOT edit the helper scripts. The only allowed change is a wrong path, and then you must report it as `PATH FIX: <old> -> <new>`.
3. Do NOT edit `REPORT-v6.md`, `REPORT-v6_1.md` or any gold file (`verified_*.txt`, `*.notes.md`).
4. If any expected number, hash or exit code below does not match, **STOP**, paste the full output, and wait for the user. Do not continue to the next step.
5. If a script crashes, STOP and paste the FULL traceback. Do not rewrite the script to make it run.
6. Do not claim anything you did not run. "Should be fine" is not a result.
7. Never print or write the LLM API key. This round needs no key and no network.
8. Anything you cannot do is reported as `BLOCKED: <reason>`. Never skip a step silently.
9. Do not summarize the support files in your report. The reviewer reads the raw files.

Variables: `SK=~/.agents/skills/data-prep`. Output root: `/tmp/v7/`.

## 1. Why this round exists (context only, do not act on it)

The v6 audit found a real defect, called **F9**: rule R6 ("front/back matter") drops everything after a heading such as `REFERENCES` until the next heading that R6 recognises. When the next chapter's opening lines are not recognised as a heading (for example because rules R1/R1b consume them first), the drop state stays on and chapter-opening prose is deleted. Measured so far: prado 1,064 R6-body lines in 23 episodes, gatheral 494 lines in 3 episodes, trading 24 lines in 3 episodes. The reviewer needs five kinds of evidence before writing a fix:

| # | Evidence | Script |
|---|---|---|
| E1 | For each suspicious episode: what each line on the pages around the chapter opener looks like, and which rule consumed it. | `r6_diag.py` -> `lines.txt` |
| E2 | For every episode: lines/characters dropped before and after the first chapter/section marker. | `r6_diag.py` -> `episodes_split.txt` |
| E3 | Whether bibliography text that should have been dropped is still inside the chunks. | `bib_leak.py` |
| E4 | For all 60 gold rows: the page where the key phrase really occurs in the parsed PDF, versus the gold page. | `gold_page_check.py` |
| E5 | Gatheral foreword area chunks, plus a corrected probe of the lost Chapter-1 opener. | `gatheral_probes.py` |

## 2. Step 1 — verify you are on the v6 state and snapshot hashes

```bash
mkdir -p /tmp/v7/support /tmp/v7/scripts && cd ~/.agents/skills/data-prep
sha256sum scripts/prep.py scripts/filter_llm.py tests/test_f07_hardening.py SKILL.md references/rules.md tools/removed_summary.py | cut -c1-16,65-
```
Expected first 16 hex, by file: `prep.py 05d51ea007105c78`, `filter_llm.py 8ff8b3d422fb8c4f`, `test_f07_hardening.py 0c17e728cfe08c5d`, `SKILL.md 51538d52b6b8580f`, `rules.md b37800b9bdde26f9`, `removed_summary.py 95c9e2e6468a779e`. Any mismatch: STOP.

Then save a full snapshot of every file in the skill folder (used again in step 9):
```bash
cd ~/.agents/skills/data-prep && find . -type f | sort | xargs sha256sum > /tmp/v7/support/00_hash_before.txt
wc -l /tmp/v7/support/00_hash_before.txt
```
Expected: `27` lines (19 shipped files + 8 `*.bak-*` backups). Any other number: STOP.

## 3. Step 2 — place and check the helper scripts

The user places these five files in `/tmp/v7/scripts/`: `v7common.py`, `r6_diag.py`, `gold_page_check.py`, `bib_leak.py`, `gatheral_probes.py`. If any is missing: `BLOCKED: script <name> missing`, ask the user.

Inputs that must already exist (from v6): `/tmp/v6/f3/{trading,gatheral,prado}/` (chunks.json, clean.txt, removed.jsonl), `/tmp/v6/gold/verified_{trading,gatheral,prado}.txt`, and the three `*.lit.json` files in `~/Downloads/`. Check:
```bash
ls /tmp/v6/f3/trading /tmp/v6/f3/gatheral /tmp/v6/f3/prado /tmp/v6/gold ~/Downloads/*.lit.json
cd /tmp/v7/scripts && python3 -m py_compile v7common.py r6_diag.py gold_page_check.py bib_leak.py gatheral_probes.py && echo COMPILED
sha256sum /tmp/v7/scripts/*.py | cut -c1-16,65- | tee /tmp/v7/support/01_script_hashes.txt
```
Expected: the listing shows each book folder and 6 gold files, exactly 3 `.lit.json` files, and `COMPILED`. A missing input: `BLOCKED: <name>`. Do not regenerate v6 outputs yourself.

## 4. Step 3 — replication check (the scripts must reproduce the earlier numbers)

Count R6-body lines directly from the v6 `removed.jsonl` files:
```bash
python3 - <<'PY' | tee /tmp/v7/support/10_xcheck_r6_counts.txt
import json, glob
for b in ("trading", "gatheral", "prado"):
    f = glob.glob(f"/tmp/v6/f3/{b}/*.removed.jsonl")
    assert len(f) == 1, (b, f)
    n = sum(1 for l in open(f[0], encoding="utf-8") if json.loads(l)["rule"] == "R6 front/back matter body")
    print(b, "removed.jsonl R6-body lines =", n)
PY
```
Expected exactly: `trading 24`, `gatheral 494`, `prado 1064`. Any other value: STOP.

Run the diagnostic on **trading** first (small, a sanity check):
```bash
cd /tmp/v7/scripts
python3 r6_diag.py trading /tmp/v7/support/diag_trading 2-3,67-68 | tee /tmp/v7/support/20_diag_trading_stdout.txt; echo "exit=${PIPESTATUS[0]}"
```
Expected stdout: `EPISODES = 3`, `TOTAL R6-body lines = 24`, `exit=0`. Anything else: STOP (the script does not replicate prep.py).

## 5. Step 4 — E1 + E2 on the three books

Run these four commands exactly (the page lists are the pages around each episode; do not change them):

```bash
cd /tmp/v7/scripts
# gatheral: episode 2 (pp.30-35, Chapter-1 opener) plus the foreword area pp.24-26
python3 r6_diag.py gatheral /tmp/v7/support/diag_gatheral 24-26,30-35 | tee /tmp/v7/support/21_diag_gatheral_stdout.txt; echo "exit=${PIPESTATUS[0]}"

# prado A: every episode whose release is 2+ pages after its trigger
python3 r6_diag.py prado /tmp/v7/support/diag_prado_A 68-70,83-89,138-141,154-156,195-198,220-224,247-253,272-274,288-290,325-328,344-348,355-356 | tee /tmp/v7/support/22_diag_prado_A_stdout.txt; echo "exit=${PIPESTATUS[0]}"

# prado B: every episode that is released on the same page by the heading BIBLIOGRAPHY
python3 r6_diag.py prado /tmp/v7/support/diag_prado_B 47,100,116,129,163-164,176,185-186,236,305-306 | tee /tmp/v7/support/23_diag_prado_B_stdout.txt; echo "exit=${PIPESTATUS[0]}"
```
Expected stdout lines:
- gatheral: `EPISODES = 3`, `TOTAL R6-body lines = 494`, `exit=0`
- prado A and prado B: `EPISODES = 23`, `TOTAL R6-body lines = 1064`, `exit=0`

Any difference: STOP. Then show the sizes and the first lines of each output, as proof they are not empty:
```bash
wc -l /tmp/v7/support/diag_*/lines.txt /tmp/v7/support/diag_*/episodes_split.txt
head -3 /tmp/v7/support/diag_prado_A/lines.txt
head -8 /tmp/v7/support/diag_prado_A/episodes_split.txt
```

## 6. Step 5 — E3 bibliography text that survived

```bash
cd /tmp/v7/scripts && python3 bib_leak.py > /tmp/v7/support/70_bib_leak.txt; echo "exit=$?"
grep -E '^(####|chunks with)' /tmp/v7/support/70_bib_leak.txt
```
Expected: `exit=0` and exactly three `####` lines (trading, gatheral, prado) each followed by a `chunks with >=3 ...` line. Paste those 6 lines in the report. The full file is a deliverable.

## 7. Step 6 — E4 gold pages versus the parsed PDF

```bash
cd /tmp/v7/scripts && python3 gold_page_check.py > /tmp/v7/support/60_gold_page_check.txt; echo "exit=$?"
grep '^SUMMARY' /tmp/v7/support/60_gold_page_check.txt
```
Expected: `exit=0` and exactly three `SUMMARY` lines. Paste them in the report. Do NOT correct any gold row, whatever the result. Possible statuses (explanation only): `MATCH` = gold page contains the phrase; `SPANS_PAGES` = phrase crosses a page break; `OFF_BY_ONE`; `WRONG_PAGE`; `PHRASE_NOT_ON_ANY_PAGE`.

## 8. Step 7 — E5 gatheral foreword area and corrected probes

```bash
cd /tmp/v7/scripts && python3 gatheral_probes.py > /tmp/v7/support/80_gatheral_probes.txt; echo "exit=$?"
cat /tmp/v7/support/80_gatheral_probes.txt | cut -c1-220
```
Expected: `exit=0`. Paste the output in the report. (The v6 probe for "SPX daily log returns" contained a typo; this one is corrected.)

## 9. Step 8 — errata for REPORT-v6 (write them, do not edit the old report)

In `REPORT-v7.md` add a section `Errata to REPORT-v6 / v6_1` with exactly these four items (replace nothing):

1. `§9: tests/test_step3.py hash is truncated in the report. Full value: b9611755bbeba6054cf125d546a4642ef3f449a0e5a281b780e8f1a780082c0d`
2. `File count: the skill folder holds 27 files = 19 shipped + 8 *.bak-* backups (README line "26 files" was wrong).`
3. `§5: the sentence "filename ... likely the origin of the misquote" is refuted by 62_prefix_search_and_repro.txt (the same filename reproduces 07a69d09). The origin of the prefixes 254cf54b / aedab848 / 12d83851 in the v5 report is UNEXPLAINED; no file on disk has these hashes.`
4. `§6.2 note: gold_audit.py and the gate both use BM25 k1=1.5, b=0.75 (the note saying b=0.25 is wrong).`

Before writing item 1, verify it: `grep test_step3 /tmp/v7/support/00_hash_before.txt` must print a hash that starts `b9611755bbeba6054cf125d546a4642ef3f449a0e5a281b780e8f1a780082c0d`. If it differs, STOP.

## 10. Step 9 — prove nothing changed, then package

```bash
cd ~/.agents/skills/data-prep && find . -type f | sort | xargs sha256sum > /tmp/v7/support/01_hash_after.txt
diff /tmp/v7/support/00_hash_before.txt /tmp/v7/support/01_hash_after.txt && echo "SKILL FOLDER UNCHANGED"
```
Expected: `SKILL FOLDER UNCHANGED`. Any diff: STOP and paste it.

Package flat, plain-text copies for upload:
```bash
D=~/Downloads/v7_support_files && mkdir -p $D
S=/tmp/v7/support
cp $S/diag_gatheral/lines.txt        $D/21_gatheral_lines.txt
cp $S/diag_gatheral/episodes_split.txt $D/21_gatheral_episodes_split.txt
cp $S/diag_prado_A/lines.txt         $D/22_prado_A_lines.txt
cp $S/diag_prado_A/episodes_split.txt $D/22_prado_episodes_split.txt
cp $S/diag_prado_B/lines.txt         $D/23_prado_B_lines.txt
cp $S/diag_trading/episodes_split.txt $D/20_trading_episodes_split.txt
cp $S/10_xcheck_r6_counts.txt $S/60_gold_page_check.txt $S/70_bib_leak.txt $S/80_gatheral_probes.txt $S/00_hash_before.txt $S/01_hash_after.txt $S/01_script_hashes.txt $D/
cp /tmp/v7/REPORT-v7.md $D/ 2>/dev/null || true
ls -l $D && sha256sum $D/* | cut -c1-16,65-
```
Do not zip. Plain files only.

## 11. Step 10 — write `/tmp/v7/REPORT-v7.md`

Short. Sections in this order, raw output only:
1. Step 1: hash check output and the `27` line count.
2. Step 2: script hashes, `COMPILED`, any `PATH FIX`.
3. Step 3: the three removed.jsonl counts and the trading stdout.
4. Step 4: the three stdout blocks (`EPISODES`, `TOTAL`, `exit`) and the `wc -l` / `head` proof.
5. Step 5: the 6 grep lines from `70_bib_leak.txt`.
6. Step 6: the 3 `SUMMARY` lines.
7. Step 7: the output of `gatheral_probes.py`.
8. Errata (the four items).
9. Step 9: `SKILL FOLDER UNCHANGED` and the final `sha256sum $D/*` listing.
10. `NOT DONE / UNCERTAIN`: list anything BLOCKED or any STOP you hit. If none, write `none`.

Then copy it: `cp /tmp/v7/REPORT-v7.md ~/Downloads/v7_support_files/`.

## 12. Definition of done

- All expected counts matched (27 files; 24 / 494 / 1064; 3 / 3 / 23 episodes).
- Skill folder byte-unchanged.
- Files in `~/Downloads/v7_support_files/`: the 13 support files copied in step 9 plus `REPORT-v7.md` (14 files).
- No step silently skipped; every STOP or BLOCKED is reported verbatim.
- No interpretation, no fixes, no new gold, no rule changes.
