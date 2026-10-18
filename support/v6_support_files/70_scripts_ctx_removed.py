#!/usr/bin/env python3
"""For each flagged removed.jsonl entry (R6-body, body-prose), print the surrounding
prepared lines from the parsed input. Matches by prefix (removed.jsonl may 80-col
truncate; the prepared line keeps the full width)."""
import importlib.util, json, sys, os

PREP = os.path.expanduser("~/.agents/skills/data-prep/scripts/prep.py")
spec = importlib.util.spec_from_file_location("prepmod", PREP)
prep = importlib.util.module_from_spec(spec); spec.loader.exec_module(prep)

book = sys.argv[1]
needles = json.loads(sys.argv[2])          # [text-prefix, ...]
ctx = 8

doc = prep.load_lit(book, False, False)
for p in doc["pages"]:
    for it in p["text_items"]:
        if isinstance(it, dict):
            it["text"] = prep.clean_unicode(it.get("text", ""))

prepared = {}
for p in doc["pages"]:
    lines, _, _ = prep.prepare_page(p, prep.DEFAULT_ZONE, 24)
    prepared[p["page"]] = lines

for needle in needles:
    found = False
    for pg, lines in prepared.items():
        for i, l in enumerate(lines):
            t = l["text"]
            if t.startswith(needle) or t.strip().startswith(needle.strip()):
                found = True
                out = [f"=== page {pg}, line {i+1}/{len(lines)}  (match: {needle[:60]!r}) ==="]
                for j in range(max(0, i - ctx), min(len(lines), i + ctx + 1)):
                    mark = ">>" if j == i else "  "
                    out.append(f"{mark} L{j+1:3d}: {lines[j]['text']}")
                print("\n".join(out)); print()
    if not found:
        print(f"!! NOT FOUND: {needle[:60]!r}\n")
