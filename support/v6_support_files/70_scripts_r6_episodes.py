#!/usr/bin/env python3
"""Instrumented F9 run: replicates prep.py's geometry-mode main loop EXACTLY
(same rules, same order, same defaults) and adds per-R6-episode logging:
  EPISODE: trigger (rule=heading, line, page) ... release (heading line kept, page)
           or OPEN (never released) ; lines removed in episode (R6-body).
Usage: python3 r6_episodes.py <book.lit.json>
Stdlib + local module import only. Read-only (writes nothing)."""
import importlib.util, sys, collections, os

PREP = os.path.expanduser("~/.agents/skills/data-prep/scripts/prep.py")
spec = importlib.util.spec_from_file_location("prepmod", PREP)
prep = importlib.util.module_from_spec(spec); spec.loader.exec_module(prep)

path = sys.argv[1]
doc = prep.load_lit(path, False, False)          # cache read-only (no --no-cache)
pages = doc["pages"]
for p in pages:
    for it in p["text_items"]:
        if isinstance(it, dict):
            it["text"] = prep.clean_unicode(it.get("text", ""))

n_pages = len(pages)
thr = max(5, int(0.05 * n_pages))                # prep.py default recur_frac? -> read from argparse default
# NOTE: use prep.py's actual defaults:
# same defaults as prep.py main() (read from the module itself where possible):
RECUR_FRAC, ZONE, GAP_CUT = prep.DEFAULT_RECUR_FRAC, prep.DEFAULT_ZONE, 24
MARGIN_BAND, MARGIN_MIN_PAGES, FOOTNOTE_ZONE, FOOTNOTE_RATIO = 0.08, 4, 0.72, 0.85
thr = max(5, int(RECUR_FRAC * n_pages))
front_matter = {s.strip().lower() for s in prep.DEFAULT_FRONT_MATTER if s.strip()}
disabled = set(); code_fonts = ()

page_labels = {}
prepared = []
for p in pages:
    lines, plabel, rem = prep.prepare_page(p, ZONE, GAP_CUT)
    page_labels[p["page"]] = plabel
    prepared.append((p["page"], lines))

heights = [it["height"] for p in pages for it in p["text_items"]]
body_h = sorted(heights)[len(heights) // 2] if heights else 14.5
is_heading_item = lambda it: "Bold" in (it.get("font_name") or "") or it["height"] >= body_h * 1.25

full_freq, stem_freq = collections.Counter(), collections.Counter()
for pg, lines in prepared:
    fseen, sseen = set(), set()
    for line in lines:
        full, st = prep.line_keys(line)
        if full: fseen.add(full)
        if st: sseen.add(st)
    full_freq.update(fseen); stem_freq.update(sseen)

page_h = {pp["page"]: pp["height"] for pp in pages}
margin_freq = collections.Counter()
for pg, lines in prepared:
    margin_freq.update({prep.margin_key(l, page_h[pg], MARGIN_BAND) for l in lines} - {None})
margin_keys = {k for k, c in margin_freq.items() if c >= MARGIN_MIN_PAGES}

def is_rec(line):
    full, st = prep.line_keys(line)
    return (full is not None and full_freq[full] >= thr) or \
           (st is not None and stem_freq[st] >= thr)

vocab = set()
for p in pages:
    for it in p["text_items"]:
        vocab.update(prep.hyphen_tokens(it["text"]))

# ---------------- instrumented copy of the main loop ----------------
episodes = []          # list of dicts
cur = None
def new_ep(pg, t):
    global cur
    cur = {"trigger_page": pg, "trigger_line": t, "release_page": None,
           "release_line": None, "removed": 0}
    episodes.append(cur)

for pg, lines in prepared:
    prev_emitted = None
    for line in lines:
        t = line["text"]
        if prep.DOTS.search(t):
            continue
        if is_rec(line):
            continue
        if prep.margin_key(line, page_h[pg], MARGIN_BAND) in margin_keys:
            continue
        if prep.is_footnote(line, page_h[pg], body_h, FOOTNOTE_ZONE, FOOTNOTE_RATIO, code_fonts):
            continue
        if line["numeric"]:
            is_tick = True
            if prev_emitted is not None:
                prev_is_prose = not prev_emitted["numeric"] and not prev_emitted["is_table"]
                prev_open = not prev_emitted["text"].rstrip().endswith(prep.TERMINAL)
                if prev_is_prose and prev_open:
                    is_tick = False
            if is_tick:
                continue
        is_head = (len(line["cells"]) == 1 and is_heading_item(line["cells"][0])
                   and len(t) < 80 and "|" not in t and not t.endswith("."))
        if is_head:
            if cur is not None:
                cur["release_page"] = pg
                cur["release_line"] = t
                cur = None
            elif prep.norm_strong(t) in front_matter:
                new_ep(pg, t)
                continue
        if cur is not None:
            cur["removed"] += 1
            continue
        if line["is_table"]:
            pass
        prev_emitted = line

# ---------------- report ----------------
out = []
out.append(f"R6 episodes: {len(episodes)}  (trigger = heading line that set drop_until_heading; "
           f"release = next R6-visible heading, which is KEPT; removed = R6-body lines dropped in episode)")
out.append("")
tot = 0
for i, e in enumerate(episodes, 1):
    rel = (f"released at pg {e['release_page']} by {e['release_line']!r}"
           if e["release_page"] else "OPEN (never released)")
    out.append(f"EP {i:2d}: trigger pg {e['trigger_page']:>3} {e['trigger_line']!r:24} -> {rel} ; removed {e['removed']} lines")
    tot += e["removed"]
out.append("")
out.append(f"total R6-body lines attributed to episodes: {tot}")
print("\n".join(out))
