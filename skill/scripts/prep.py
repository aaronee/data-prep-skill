#!/usr/bin/env python3
"""data-prep v2: clean LiteParse (`lit`) JSON output into RAG-ready text + chunks.

Geometry mode (.pdf/.docx/.pptx/.xlsx via lit, or a .json lit dump):
  R1  recurring lines (pre-pass and main pass share ONE line builder)
  R2  page numbers (zone + short numeric); printed page label captured for chunks
  R3  chart ticks (numeric lines, with a prose-continuation guard)
  R4  TOC dot leaders          R5  whole TOC pages
  R6  front/back matter sections (state persists across pages; the heading that
      ends a dropped section is kept)
  R7  paragraphs: break on y-gaps, bullets, markers; dehyphenate only when the
      merged word exists in the document vocabulary; join across page breaks

Text mode (.md/.txt): headings (md), blank-line paragraphs, R1/R4/R6 text rules.

Outputs: <name>.clean.txt  <name>.chunks.json  <name>.report.txt
         <name>.removed.jsonl (one row per dropped line: page, rule, text)
         <name>.lit.json (parse cache, geometry mode only)

Chunk fields: id, source, chunk_index, page, page_label, path, text, embed_text,
              sha256 (content hash).

Eval (--eval QFILE): lines `question` or `question | key phrase | expected page`.
Real BM25 (k1=1.5, b=0.75), hit@3 + MRR against gold answers; optional embedding
retrieval via --embed-cmd (command reads text on stdin, prints a float vector).
"""
import argparse
import collections
import hashlib
import json
import math
import os
import re
import subprocess
import sys
import tempfile
import unicodedata

# ---------------- constants (all overridable via CLI) ----------------
TICK = re.compile(r"^-?[\d.,]+\s?%?$")
DOTS = re.compile(r"\.{5,}")
# a standalone "12" or "Page 34" line (text mode): page-number artifact.
# Explicit "Page N" is always dropped; bare values only in 1..2000, and a
# year-like 1900..2100 is content (finance books quote years on their own).
BARE_PN = re.compile(r"^([Pp]age\s+)?(\d{1,4})\s*[.:]?\s*$")
DEFAULT_FRONT_MATTER = ["contents", "table of contents", "index", "references",
                        "bibliography", "back cover", "acknowledgments",
                        "acknowledgements", "copyright", "disclaimer", "disclosures"]
DEFAULT_ZONE = 0.12
DEFAULT_RECUR_FRAC = 0.15
BULLET = re.compile(r"^\s*(?:[-•·*]|\d{1,2}[.)])\s")
TERMINAL = (".", "!", "?", ":", ";", "%")   # tuple: str.endswith needs a tuple for "any of"
STOPWORDS = {"this", "that", "with", "from", "have", "will", "would", "there",
             "their", "about", "which", "while", "between", "could", "should",
             "these", "those", "then", "than", "when", "where"}


CID = re.compile(r"\(cid:\d+\)")
INVISIBLE = re.compile(r"[\u200b\u200c\u200d\u2060\ufeff\u00ad]")
CTRL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


def read_text(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def clean_unicode(s):
    s = unicodedata.normalize("NFKC", s)   # ﬁ->fi, ﬃ->ffi
    s = CID.sub(" ", s)                      # (cid:123) -> placeholder space
    s = INVISIBLE.sub("", s)                 # zero-width chars, soft hyphens
    s = CTRL.sub("", s)                      # control chars, keep \t \n \r
    return re.sub(r"[ \t]+", " ", s)


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"\d+", "#", s.strip().lower()))


def norm_strong(s: str) -> str:
    """No digit-collapse: protects repeated body sentences whose only variation is a number."""
    return re.sub(r"\s+", " ", s.strip().lower())


def hyphen_tokens(text: str):
    return re.findall(r"[a-z0-9]+(?:-[a-z0-9]+)*", text.lower())


def join_hyphenated(prev, nxt, vocab):
    """prev ends a line with '-'. Return the correctly joined string, or None if this is not a line-break hyphen."""
    if not nxt or not prev.endswith("-") or prev.endswith("--"):
        return None
    if len(prev) < 2 or not prev[-2].isalpha():
        return None
    stem = prev.split()[-1][:-1]                       # last word, hyphen removed
    first = nxt.split()[0]
    core = re.sub(r"[^\w]+$", "", first)               # drop trailing punctuation
    if first[0].isupper() or first[0].isdigit():
        return prev + nxt                              # Black-Scholes
    if (stem + core).lower() in vocab:
        return prev[:-1] + nxt                         # informa-tion -> information
    return prev + nxt                                  # unknown: keep hyphen, NO space: risk-neutral


def recur_key(s):
    s = s.strip()
    if not s or s.startswith("|") or re.fullmatch(r"[\s|:\-=_*#]+", s):
        return None                                  # never treat md table rows/separators as headers
    k = re.sub(r"\d+", "#", re.sub(r"\s+", " ", s.lower()))
    return k if 8 <= len(k) <= 80 else None


# ---------------- loading ----------------

def load_lit(path: str, use_ocr: bool, no_cache: bool):
    if path.lower().endswith(".json"):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    if not os.path.exists(path):
        sys.exit(f"input not found: {path}")
    cache = os.path.splitext(path)[0] + ".lit.json"
    if not no_cache and os.path.exists(cache) \
            and os.path.getmtime(cache) >= os.path.getmtime(path):
        with open(cache, encoding="utf-8") as f:
            return json.load(f)
    fd, tmp = tempfile.mkstemp(suffix=".json")
    os.close(fd)
    cmd = ["lit", "parse", path, "--format", "json", "-o", tmp]
    if not use_ocr:
        cmd.insert(-2, "--no-ocr")
    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
        with open(tmp, encoding="utf-8") as f:
            data = f.read()
    finally:
        try:
            os.unlink(tmp)
        except OSError:
            pass
    with open(cache, "w", encoding="utf-8") as f:
        f.write(data)
    return json.loads(data)


# ---------------- geometry mode: ONE line builder used by pre-pass AND main pass ----------------

def prepare_page(p, zone, gap_cut_min):
    """R2 filter + line grouping. Returns (lines, page_label, removed).
    The same prepared line objects feed R1 counting and the main pass
    (fixes the v1 pre-pass/main-pass mismatch)."""
    H = p["height"]
    page_label = None
    items, removed = [], []
    for it in p["text_items"]:
        t = it["text"].strip()
        if not t:
            continue
        in_zone = it["y"] < H * zone or it["y"] > H * (1 - zone)
        if in_zone and TICK.match(t) and len(t) <= 3:
            removed.append(("R2 page number", t))
            if it["y"] > H * (1 - zone):
                if page_label is None:
                    page_label = t
            continue
        items.append(it)
    if items:
        hs = sorted(it["height"] for it in items)
        tol = max(4.0, 0.55 * hs[len(hs) // 2])
    else:
        tol = 7.0
    items.sort(key=lambda it: (it["y"], it["x"]))
    raw_lines = []
    for it in items:
        if raw_lines and abs(it["y"] - raw_lines[-1]["anchor_y"]) < tol:
            raw_lines[-1]["cells"].append(it)
        else:
            raw_lines.append({"anchor_y": it["y"], "cells": [it]})
    raw_lines = reorder_columns(raw_lines, p["width"])   # 4b: two-column reading order
    gaps = [c2["x"] - (c1["x"] + c1["width"]) for l in raw_lines
            for c1, c2 in zip(l["cells"], l["cells"][1:]) if c2["x"] > c1["x"]]
    pos = [g for g in gaps if g > 0]
    gap_cut = max(gap_cut_min, 3 * (pos[len(pos) // 2] if pos else 0))
    lines = []
    for l in raw_lines:
        cells = sorted(l["cells"], key=lambda c: c["x"])
        texts = [c["text"].strip() for c in cells]
        is_table = any(c2["x"] - (c1["x"] + c1["width"]) > gap_cut
                       for c1, c2 in zip(cells, cells[1:]))
        text = re.sub(r"\s+", " ", (" | " if is_table else " ").join(texts)).strip()
        if not text:
            continue
        lines.append({"cells": cells, "text": text, "y": l["anchor_y"],
                      "in_zone": cells[0]["y"] < H * zone or cells[0]["y"] > H * (1 - zone),
                      "is_table": is_table, "h": max(c["height"] for c in cells),
                      "numeric": all(TICK.match(t) for t in texts) and len(texts) <= 3})
    return lines, page_label, removed


def line_keys(line):
    """(full_key, stem_key) for R1. Lines with >=8 tokens use strong (no digit-
    collapse) keys so repeated body sentences that only differ in a number are
    NOT merged (v1 finding #9)."""
    toks_raw = line["text"].split()
    n = norm_strong(line["text"]) if len(toks_raw) >= 5 else norm(line["text"])
    toks = n.split()
    full_ok = line["in_zone"] or len(n) <= 60 or len(toks) <= 12
    full = n if (full_ok and len(n) >= 8) else None
    st = " ".join(toks[:6]) if (len(toks) >= 3 and len(n) <= 60) else None
    return full, st


def margin_key(line, H, band):
    k = norm(line["text"])
    if len(k) < 4:
        return None
    if len(re.findall(r"\d", line["text"])) > 2:
        return None  # template lines with several values (numbered figure captions etc.) are not margin repeats
    return k if (line["y"] < H * band or line["y"] > H * (1 - band)) else None


MONO_RE = re.compile(r"mono(?!type)|courier|consol|code|menlo|monaco|inconsolata|"
                     r"typewriter|cmtt|lettergothic|fixed", re.I)
CAPTION_RE = re.compile(r"^(figure|fig\.|table|exhibit|chart|listing)\s*\d", re.I)
CODE_CHARS = "=(){}[];_+*"


def is_footnote(line, H, body_h, zone=0.72, ratio=0.85, extra_fonts=()):
    """Small-font line in the bottom band, not a table row: a footnote (or a
    bottom-band chart tick, which is equally unindexable). Exempt: figure/
    table captions, monospace (code) fonts, and code-looking lines — those
    carry content and stay."""
    if line["is_table"] or line["y"] <= H * zone or line["h"] > body_h * ratio:
        return False
    t = line["text"]
    if CAPTION_RE.match(t.strip()):
        return False
    extra = tuple(f.lower() for f in extra_fonts if f)
    for c in line["cells"]:
        fn = c["font_name"] or ""
        if MONO_RE.search(fn) or any(e in fn.lower() for e in extra):
            return False
    if sum(t.count(ch) for ch in CODE_CHARS) >= 3 and t \
            and sum(ch.isalpha() for ch in t) / len(t) < 0.75:
        return False
    return True


def find_gutter(cells, n_lines, W, min_gutter=12.0):
    """cells: [(x, x+w)] of every cell. Return (g0, g1) of the widest run of
    empty vertical bins in the middle half of the page with cells on both
    sides, or None. Detects two-column layouts."""
    if n_lines < 15:
        return None
    bs = 4
    nb = max(1, int(W / bs))
    cov = [0] * nb
    for (x0, x1) in cells:
        for i in range(max(0, int(x0 // bs)), min(nb, int(x1 // bs) + 1)):
            cov[i] += 1
    tol = max(1, int(0.05 * n_lines))
    lo_b, hi_b = int(0.25 * W // bs), int(0.75 * W // bs)
    best = None
    i = lo_b
    while i <= hi_b:
        if cov[i] <= tol:
            j = i
            while j <= hi_b and cov[j] <= tol:
                j += 1
            if best is None or (j - i) > (best[1] - best[0]):
                best = (i * bs, min(W, j * bs))
            i = j
        else:
            i += 1
    if best and (best[1] - best[0]) >= min_gutter:
        g0, g1 = best
        left = sum(1 for (x0, x1) in cells if x1 <= g0 + 1)
        right = sum(1 for (x0, x1) in cells if x0 >= g1 - 1)
        if min(left, right) >= 0.3 * len(cells):
            return g0, g1
    return None


def reorder_columns(raw_lines, W):
    """Split each merged line into its left/right column part; emit a full block
    of left lines (y order) before the right block so reading order is column
    1 top-to-bottom, then column 2. A line whose cells span the gutter (a full-
    width title) is emitted as-is and breaks the block."""
    if not raw_lines:
        return raw_lines
    cells = [(c["x"], c["x"] + c["width"]) for l in raw_lines for c in l["cells"]]
    g = find_gutter(cells, len(raw_lines), W)
    if not g:
        return raw_lines
    g0, g1 = g
    mid = (g0 + g1) / 2
    span = lambda l: any(c["x"] < g0 and c["x"] + c["width"] > g1 for c in l["cells"])
    ctr = lambda c: c["x"] + c["width"] / 2
    both = sum(1 for l in raw_lines if
               any(ctr(c) < mid for c in l["cells"])
               and any(ctr(c) >= mid for c in l["cells"]))
    if both < 0.7 * len(raw_lines):          # wide-gap table, not a two-column layout
        return raw_lines
    out, left_buf, right_buf = [], [], []

    def flush():
        nonlocal left_buf, right_buf
        if left_buf or right_buf:
            out.extend(left_buf)
            out.extend(right_buf)
            left_buf, right_buf = [], []

    for l in raw_lines:
        if span(l):
            flush()
            out.append(l)
            continue
        left = [c for c in l["cells"] if ctr(c) < mid]
        right = [c for c in l["cells"] if ctr(c) >= mid]
        if left:
            left_buf.append({"anchor_y": l["anchor_y"], "cells": left})
        if right:
            right_buf.append({"anchor_y": l["anchor_y"], "cells": right})
    flush()
    return out


# ---------------- paragraphs ----------------

def build_paragraphs(clean_lines, med_item_h, vocab):
    """clean_lines: [(page, line)] -> units [{text, kind, pages, h}].
    kind: para | head | table. Paragraphs break on bullets, on y-gaps > 1.5x
    median line height, and across page breaks unless the previous page ended
    mid-sentence. Dehyphenation is vocabulary-aware."""
    units = []
    buf, buf_pages, last_y, last_page = [], [], None, None
    gap_thr = 1.5 * med_item_h

    def join_next(t):
        if buf and t:
            j = join_hyphenated(buf[-1], t, vocab)
            if j is not None:
                buf[-1] = j
                return
        buf.append(t)

    def flush():
        nonlocal buf, buf_pages, last_y, last_page
        if buf:
            units.append({"text": " ".join(buf), "kind": "para",
                          "pages": [min(buf_pages), max(buf_pages)]})
        buf, buf_pages, last_y, last_page = [], [], None, None

    for pg, line in clean_lines:
        t = line["text"]
        if line["head"]:
            flush()
            units.append({"text": t, "kind": "head", "pages": [pg, pg], "h": line.get("h", 0)})
            continue
        if line["is_table"]:
            flush()
            units.append({"text": t, "kind": "table", "pages": [pg, pg]})
            last_y, last_page = line["y"], pg
            continue
        new_page = last_page is not None and pg != last_page
        gap = (line["y"] - last_y) if (last_y is not None and not new_page) else None
        col_break = gap is not None and gap < -gap_thr   # 4b: backward y-jump after a column switch
        cross_join = ((new_page or col_break) and buf
                      and not buf[-1].rstrip().endswith(TERMINAL)
                      and not BULLET.match(t))
        break_gap = gap is not None and gap > gap_thr
        if BULLET.match(t) or break_gap or ((new_page or col_break) and not cross_join and buf):
            flush()
            buf.append(t)
            buf_pages.append(pg)
        elif buf:
            join_next(t)
            buf_pages.append(pg)
        else:
            buf.append(t)
            buf_pages.append(pg)
        last_y = line["y"]
        last_page = pg
    flush()
    return units


# ---------------- chunking ----------------

def split_para(text, cap):
    sents = re.split(r"(?<=[.!?])\s+", text)
    pieces, cur = [], ""
    for s in sents:
        while len(s) > cap:                      # no sentence boundary available: hard split at whitespace
            cut = s.rfind(" ", 0, cap)
            cut = cut if cut > cap // 2 else cap
            pieces.append(s[:cut])
            s = s[cut:].lstrip()
        if cur and len(cur) + 1 + len(s) > cap:
            pieces.append(cur)
            cur = s
        else:
            cur = (cur + " " + s) if cur else s
    if cur:
        pieces.append(cur)
    return pieces or [text[:cap]]


def make_chunks(units, target, cap, source, page_labels):
    hs = [u["h"] for u in units if u["kind"] == "head" and u.get("h")]
    h1_cut = max(hs) * 0.9 if hs else float("inf")
    h2_cut = max(hs) * 0.75 if hs else float("inf")

    stack = {"h1": "", "h2": "", "h3": ""}
    chunks = []
    cur_units, cur_start_path, cur_text, carry = [], None, "", []

    def path_now():
        return " > ".join(v for v in stack.values() if v)

    def flush():
        nonlocal cur_units, cur_start_path, cur_text, carry
        if not cur_units:
            return
        # orphan-heading rule: don't end a chunk on a bare heading
        while cur_units and cur_units[-1]["kind"] == "head" and len(cur_units) > 1:
            cur_units.pop()
        if len(cur_units) == 1 and cur_units[0]["kind"] == "head":
            carry = [cur_units[0]]
            cur_units, cur_start_path, cur_text = [], None, ""
            return
        text = " ".join(u["text"] for u in cur_units)
        if chunks and text == chunks[-1]["text"]:   # no duplicate trailing chunk
            cur_units, cur_start_path, cur_text = [], None, ""
            return
        pgs = [pg for u in cur_units for pg in u["pages"] if pg is not None]
        chunk_page = [min(pgs), max(pgs)] if pgs else None
        chunks.append({
            "id": f"c{len(chunks):04d}",
            "source": source,
            "chunk_index": len(chunks),
            "page": chunk_page,
            "page_label": page_labels.get(min(pgs)) if pgs else None,
            "path": cur_start_path,
            "text": text,
            "embed_text": (cur_start_path + " " if cur_start_path else "") + text,
            "sha256": hashlib.sha256((cur_start_path + "|" + text).encode()).hexdigest()[:16],
        })
        cur_units, cur_start_path, cur_text = [], None, ""

    for u in units:
        if u["kind"] == "head":
            h = u.get("h", 0)
            if hs and h >= h1_cut:
                stack["h1"] = u["text"][:80]
                stack["h2"] = stack["h3"] = ""
            elif hs and h >= h2_cut:
                stack["h2"] = u["text"][:80]
                stack["h3"] = ""
            else:
                stack["h3"] = u["text"][:80]
        pieces = ([u] if not (u["kind"] == "para" and len(u["text"]) > cap)
                  else [{"text": p, "kind": "para", "pages": u["pages"]}
                        for p in split_para(u["text"], cap)])
        for piece in pieces:
            if cur_units and len(cur_text) + 1 + len(piece["text"]) > cap:
                flush()                       # hard cap: never mix over the limit
            if not cur_units and carry:
                cur_units = carry
                carry = []
            if cur_start_path is None:
                cur_start_path = path_now()   # path captured at CHUNK START
            cur_units.append(piece)
            cur_text += (" " if cur_text else "") + piece["text"]
            if len(cur_text) >= target:
                flush()
    flush()
    if carry and chunks:
        # lone trailing heading with nothing after it: merge into the last chunk
        htxt = carry[0]["text"]
        c = chunks[-1]
        c["text"] = htxt + " " + c["text"]
        c["embed_text"] = (c["path"] + " " if c["path"] else "") + c["text"]
        c["sha256"] = hashlib.sha256((c["path"] + "|" + c["text"]).encode()).hexdigest()[:16]
    return chunks


# ---------------- text mode ----------------

def run_text_mode(path, front_matter, disabled, removed_log, text_recur_min=8):
    text = clean_unicode(read_text(path))               # 3c: text mode, right after reading
    vocab = set(hyphen_tokens(text))
    is_md = path.lower().endswith(".md")
    units, warnings = [], []
    in_drop = False
    para_buf = []
    recurring, seen_rec = set(), set()
    if "R1" not in disabled:
        cnt = collections.Counter(k for k in map(recur_key, text.splitlines()) if k)
        recurring = {k for k, c in cnt.items() if c >= text_recur_min}

    def flush_para():
        nonlocal para_buf
        if para_buf:
            units.append({"text": " ".join(para_buf), "kind": "para", "pages": [None, None]})
        para_buf = []

    for ln in text.splitlines():
        s = ln.strip()
        k = recur_key(s)
        if k and k in recurring:
            if s.startswith("#") and k not in seen_rec:
                seen_rec.add(k)                      # keep the first occurrence of a repeated heading
            else:
                removed_log.append({"page": None, "page_label": None,
                                    "rule": "R1 recurring line (text)", "text": s})
                continue
        head = None
        if is_md and s.startswith("#"):
            head = (min(len(s) - len(s.lstrip("#")), 3), s.lstrip("#").strip())
        elif s and all(c.isupper() or c in " .-" for c in s) and 3 < len(s) < 80:
            head = (1, s)
        if head is not None:
            flush_para()
            lvl, t = head
            if "R6" not in disabled:
                if in_drop:
                    in_drop = False       # the heading that ends a dropped section is kept
                elif s.lower() in front_matter:
                    in_drop = True
                    removed_log.append({"page": None, "page_label": None,
                                        "rule": "R6 front/back matter heading", "text": t})
                    continue
            if in_drop:
                removed_log.append({"page": None, "page_label": None,
                                    "rule": "R6 front/back matter body", "text": t})
                continue
            units.append({"text": t, "kind": "head", "pages": [None, None],
                          "h": {1: 3.0, 2: 2.0}.get(lvl, 1.0)})
            continue
        if in_drop:
            removed_log.append({"page": None, "page_label": None,
                                "rule": "R6 front/back matter body", "text": s})
            continue
        if "R4" not in disabled and DOTS.search(s):
            removed_log.append({"page": None, "page_label": None,
                                "rule": "R4 TOC dot leader", "text": s})
            continue
        m = BARE_PN.match(s)
        if m and "R2" not in disabled:
            v = int(m.group(2))
            if m.group(1) is not None or (1 <= v <= 2000 and not 1900 <= v <= 2100):
                removed_log.append({"page": None, "page_label": None,
                                    "rule": "R2 page number (text)", "text": s})
                continue
        if not s:
            flush_para()
            continue
        if para_buf:
            j = join_hyphenated(para_buf[-1], s, vocab)
            if j is not None:
                para_buf[-1] = j
            else:
                para_buf.append(s)
        else:
            para_buf.append(s)
    flush_para()
    if not units:
        warnings.append("text mode: no content units found")
    return units, warnings


# ---------------- main ----------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input")
    ap.add_argument("--ocr", action="store_true", help="run OCR (scanned docs)")
    ap.add_argument("--no-cache", action="store_true", help="force re-parse even if .lit.json cache exists")
    ap.add_argument("--outdir")
    ap.add_argument("--eval", metavar="QFILE", help="questions; 'q | key phrase | page' for gold answers")
    ap.add_argument("--min-hit", type=float, metavar="F",
                    help="gate: exit 1 if STRICT hit@3 < F (e.g. 0.8)")
    ap.add_argument("--chunk-tokens", type=int, default=400, help="chunk target in tokens (~4 chars each)")
    ap.add_argument("--recur-frac", type=float, default=DEFAULT_RECUR_FRAC)
    ap.add_argument("--zone", type=float, default=DEFAULT_ZONE)
    ap.add_argument("--margin-band", type=float, default=0.08,
                    help="R1b: fraction of page top/bottom treated as margin band")
    ap.add_argument("--margin-min-pages", type=int, default=4,
                    help="R1b: a normalized margin line must repeat on at least this many pages")
    ap.add_argument("--footnote-zone", type=float, default=0.72,
                    help="R8: bottom-band fraction of page height (default 0.72)")
    ap.add_argument("--footnote-ratio", type=float, default=0.85,
                    help="R8: max cell height as a fraction of body height (default 0.85)")
    ap.add_argument("--code-fonts", default="",
                    help="comma list of extra font-name substrings R8 treats as code (never dropped)")
    ap.add_argument("--min-questions", type=int, default=20,
                    help="--min-hit gate needs at least this many STRICT-graded questions")
    ap.add_argument("--min-chunks", type=int, default=10,
                    help="--min-hit gate needs gold rows to cite at least this many distinct chunks")
    ap.add_argument("--gap-cut", type=float, default=24, help="min inter-cell gap (pt) for table detection")
    ap.add_argument("--drop-sections", default=",".join(DEFAULT_FRONT_MATTER),
                    help="comma list of normalized section names R6 cuts")
    ap.add_argument("--disable", default="",
                    help="comma list of rules to switch off (R1..R8; R1b is its own switch)")
    ap.add_argument("--text-recur-min", type=int, default=8,
                    help="text mode: a line repeated on >= this many lines is a recurring header")
    ap.add_argument("--embed-cmd", default=None,
                    help="command that reads text on stdin and prints a float vector (embedding retrieval)")
    args = ap.parse_args()
    if args.min_hit is not None and not args.eval:
        ap.error("--min-hit needs --eval QFILE (the gate would otherwise be silently ignored)")

    code_fonts = tuple(f.strip() for f in args.code_fonts.split(",") if f.strip())
    disabled = {d.strip().upper() for d in args.disable.split(",") if d.strip()}
    front_matter = {s.strip().lower() for s in args.drop_sections.split(",") if s.strip()}
    target = args.chunk_tokens * 4
    cap = int(target * 1.5)

    in_base = os.path.basename(os.path.splitext(args.input)[0])
    outdir = args.outdir or os.path.dirname(os.path.abspath(args.input))
    os.makedirs(outdir, exist_ok=True)
    removed_log = []
    page_labels = {}

    def drop(pg, label, rule, text):
        removed_log.append({"page": pg, "page_label": label, "rule": rule, "text": text})

    if args.input.lower().endswith((".md", ".txt")):
        units, warnings = run_text_mode(args.input, front_matter, disabled, removed_log,
                                        args.text_recur_min)
        n_pages = None
        raw_full_text = read_text(args.input)
        raw_chars = len(raw_full_text)
    else:
        doc = load_lit(args.input, args.ocr, args.no_cache)
        pages = doc["pages"]
        for p in pages:                                   # 3b: unicode cleaning, early, on load
            for it in p["text_items"]:
                if isinstance(it, dict):
                    it["text"] = clean_unicode(it.get("text", ""))
        n_pages = len(pages)
        thr = max(5, int(args.recur_frac * n_pages))
        heights = [it["height"] for p in pages for it in p["text_items"]]
        body_h = sorted(heights)[len(heights) // 2] if heights else 14.5
        is_heading_item = lambda it: "Bold" in (it.get("font_name") or "") or it["height"] >= body_h * 1.25
        raw_full_text = "\n".join(p.get("text", "") for p in pages)
        raw_chars = sum(len(p.get("text", "")) for p in pages)
        # token baseline = item text (spaces reconstructed, like the clean side),
        # because lit's projected text glues words together and undercounts tokens
        raw_items_text = "\n".join(" ".join(it["text"] for it in p["text_items"])
                                   for p in pages)

        prepared = []
        for p in pages:
            lines, plabel, rem = prepare_page(p, args.zone, args.gap_cut)
            page_labels[p["page"]] = plabel
            for rule, t in rem:
                drop(p["page"], plabel, rule, t)
            prepared.append((p["page"], lines))

        full_freq, stem_freq = collections.Counter(), collections.Counter()
        for pg, lines in prepared:
            fseen, sseen = set(), set()
            for line in lines:
                full, st = line_keys(line)
                if full:
                    fseen.add(full)
                if st:
                    sseen.add(st)
            full_freq.update(fseen)
            stem_freq.update(sseen)

        page_h = {pp["page"]: pp["height"] for pp in pages}
        margin_freq = collections.Counter()
        for pg, lines in prepared:
            margin_freq.update(
                {margin_key(l, page_h[pg], args.margin_band) for l in lines} - {None})
        margin_keys = {k for k, c in margin_freq.items() if c >= args.margin_min_pages}

        def is_rec(line):
            full, st = line_keys(line)
            return (full is not None and full_freq[full] >= thr) or \
                   (st is not None and stem_freq[st] >= thr)

        vocab = set()
        for p in pages:
            for it in p["text_items"]:
                vocab.update(hyphen_tokens(it["text"]))

        clean_lines, warnings = [], []
        drop_until_heading = False          # persists ACROSS pages (v1 bug 1 fix)
        table_counts = collections.Counter()
        for pg, lines in prepared:
            out_lines, prev_emitted = [], None
            dl = sum(1 for l in lines if DOTS.search(l["text"]))
            for line in lines:
                t = line["text"]
                if "R4" not in disabled and DOTS.search(t):
                    drop(pg, page_labels[pg], "R4 TOC dot leader", t)
                    continue
                if "R1" not in disabled and is_rec(line):
                    drop(pg, page_labels[pg], "R1 recurring line", t)
                    continue
                if "R1B" not in disabled and margin_key(line, page_h[pg], args.margin_band) in margin_keys:
                    drop(pg, page_labels[pg], "R1b margin repeat", t)
                    continue
                if "R8" not in disabled and is_footnote(line, page_h[pg], body_h,
                                                        args.footnote_zone, args.footnote_ratio,
                                                        code_fonts):
                    drop(pg, page_labels[pg], "R8 footnote", t)
                    continue
                if line["numeric"]:
                    is_tick = True
                    if "R3" not in disabled and prev_emitted is not None:
                        prev_is_prose = not prev_emitted["numeric"] and not prev_emitted["is_table"]
                        prev_open = not prev_emitted["text"].rstrip().endswith(TERMINAL)
                        if prev_is_prose and prev_open:
                            is_tick = False   # wrapped number belonging to the sentence
                    if is_tick:
                        drop(pg, page_labels[pg], "R3 chart tick line", t)
                        continue
                is_head = ("R6" not in disabled and len(line["cells"]) == 1
                           and is_heading_item(line["cells"][0]) and len(t) < 80
                           and "|" not in t and not t.endswith("."))
                if is_head:
                    if drop_until_heading:
                        drop_until_heading = False
                        # v1 bug 2 fix: the heading that ends a dropped section is KEPT
                    elif norm_strong(t) in front_matter:
                        drop_until_heading = True
                        drop(pg, page_labels[pg], "R6 front/back matter heading", t)
                        continue
                if drop_until_heading:
                    drop(pg, page_labels[pg], "R6 front/back matter body", t)
                    continue
                if line["is_table"]:
                    table_counts[pg] += 1
                out_lines.append({**line, "head": is_head})
                prev_emitted = out_lines[-1]
            if "R5" not in disabled and dl >= 3:
                for l in out_lines:
                    drop(pg, page_labels[pg], "R5 TOC page", l["text"])
                out_lines = []
            clean_lines.extend((pg, l) for l in out_lines)

        for pg, c in table_counts.items():
            tot = sum(1 for pg2, l in clean_lines if pg2 == pg)
            if tot and c / tot > 0.4:
                warnings.append(f"page {pg}: {c}/{tot} lines look like table rows — "
                                f"possible two-column layout (check before indexing)")

        if "R7" in disabled:
            units = [{"text": l["text"], "kind": "head" if l["head"]
                      else ("table" if l["is_table"] else "para"),
                      "pages": [pg, pg], "h": l.get("h", 0)} for pg, l in clean_lines]
        else:
            units = build_paragraphs(clean_lines, body_h, vocab)
        if not any(u["kind"] == "head" for u in units):
            warnings.append("no headings detected — chunk paths will be flat "
                            "(document may use non-bold headings)")

    # ---------------- outputs ----------------
    clean_parts = []
    if n_pages:
        by_page = collections.defaultdict(list)
        for u in units:
            if u["pages"][0] is None:
                continue
            for pg in range(u["pages"][0], u["pages"][1] + 1):
                by_page[pg].append(u)
        for pg in range(1, n_pages + 1):
            body = "\n".join(u["text"] for u in by_page.get(pg, []))
            clean_parts.append(f"--- Page {pg} ---\n" + body)
    else:
        clean_parts = [u["text"] for u in units]
    clean_text = "\n\n".join(clean_parts)
    clean_path = os.path.join(outdir, in_base + ".clean.txt")
    with open(clean_path, "w", encoding="utf-8") as f:
        f.write(clean_text)

    removed_path = os.path.join(outdir, in_base + ".removed.jsonl")
    with open(removed_path, "w", encoding="utf-8") as f:
        for row in removed_log:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    chunks = make_chunks(units, target, cap, os.path.basename(args.input), page_labels)
    chunks_path = os.path.join(outdir, in_base + ".chunks.json")
    with open(chunks_path, "w", encoding="utf-8") as f:
        json.dump(chunks, f, ensure_ascii=False, indent=1)

    # ---- built-in verification: retention table + most-lost tokens + warnings ----
    # token baseline = item text (spaces reconstructed), compared against the
    # CHUNK text — what the RAG index actually sees (clean.txt displays
    # cross-page paragraphs on every page they span, so it would double-count)
    token_source = raw_items_text if n_pages else raw_full_text
    raw_tokens = collections.Counter(hyphen_tokens(token_source))
    index_text = "\n".join(c["text"] for c in chunks)
    clean_tokens = collections.Counter(hyphen_tokens(index_text))
    total_raw, total_clean = sum(raw_tokens.values()), sum(clean_tokens.values())
    top = [t for t, _ in raw_tokens.most_common(300)
           if len(t) >= 4 and t not in STOPWORDS][:15]
    retention = [(t, raw_tokens[t], clean_tokens.get(t, 0),
                  100 * clean_tokens.get(t, 0) / raw_tokens[t] if raw_tokens[t] else 100.0)
                 for t in top]
    lost = sorted(((raw_tokens[t] - clean_tokens.get(t, 0), t) for t in raw_tokens),
                  reverse=True)[:20]
    over_cap = sum(1 for c in chunks if len(c["text"]) > cap)

    report = [f"document: {args.input}",
              f"pages: {n_pages} | raw chars: {raw_chars} | clean chars: {len(clean_text)} "
              f"(-{100 * (1 - len(clean_text) / max(1, raw_chars)):.1f}%)",
              f"tokens: raw={total_raw} clean={total_clean} "
              f"({100 * total_clean / max(1, total_raw):.1f}% kept)",
              f"chunks: {len(chunks)} (target {args.chunk_tokens} tokens; "
              f"{over_cap} over the {int(100 * cap / target)}% cap)",
              f"removed lines: {len(removed_log)} -> {removed_path}",
              "", "retention (top content words):"]
    for t, r, c, pct in retention:
        flag = "  WARNING: <95%" if pct < 95 else ""
        report.append(f"  {t:24s} {r:6d} -> {c:6d}  ({pct:5.1f}%){flag}")
    report += ["", "most-lost tokens (raw -> clean):"]
    report += [f"  {t:28s} -{n}" for n, t in lost if n > 0]
    if warnings:
        report += ["", "warnings:"] + [f"  - {w}" for w in warnings]
    report += ["", f"outputs: {clean_path}", f"           {chunks_path}", f"           {removed_path}"]
    report_text = "\n".join(report)
    with open(os.path.join(outdir, in_base + ".report.txt"), "w", encoding="utf-8") as f:
        f.write(report_text + "\n")
    print(report_text)

    if args.eval:
        ok = run_eval(args.eval, chunks, args.embed_cmd, args.min_hit, args.min_questions,
                      args.min_chunks)
        if ok is False:
            sys.exit(1)


# ---------------- eval ----------------

def run_eval(qfile, chunks, embed_cmd, min_hit=None, min_questions=20, min_chunks=10):
    """Returns True/None: True = min-hit gate passed (or no gate), False = failed."""
    qs, n_todo = [], 0
    with open(qfile, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue                       # blank lines and # comments
            if line.upper().startswith("TODO"):
                n_todo += 1                    # unedited generator stub: not a real question
                continue
            parts = [p.strip() for p in line.split("|")]
            if len(parts) >= 4:
                qs.append((parts[0], parts[1], parts[2], parts[3]))
            elif len(parts) == 3:
                qs.append((parts[0], parts[1], parts[2], None))
            elif len(parts) == 2:
                qs.append((parts[0], parts[1], None, None))
            else:
                qs.append((parts[0], None, None, None))
    if n_todo:
        print(f"== {n_todo} TODO row(s) skipped: write a real question for each, or delete the row")
    if not qs:
        print("no questions")
        return False if min_hit is not None else None

    # gold validation: a row that cites a chunk must contain the phrase in
    # that chunk — stale/leaky gold (e.g. mined from removed junk) is
    # excluded, not silently counted
    by_id = {c["id"]: c for c in chunks if c.get("id")}
    invalid = set()
    seen_q = {}
    for i, (q, phrase, gold_page, cid) in enumerate(qs):
        nq = re.sub(r"\s+", " ", q.lower()).strip()
        if nq in seen_q:
            print(f"== invalid gold row (Q{i + 1}): duplicate of Q{seen_q[nq] + 1}")
            invalid.add(i)
            continue
        seen_q[nq] = i
        if phrase and phrase.lower() in q.lower():
            print(f"== invalid gold row (Q{i + 1}): key phrase {phrase!r} appears in the question (leak)")
            invalid.add(i)
            continue
        if cid and phrase:
            if cid not in by_id:
                print(f"== invalid gold row (Q{i + 1}): unknown chunk id {cid}")
                invalid.add(i)
            elif phrase.lower() not in by_id[cid]["text"].lower():
                print(f"== invalid gold row (Q{i + 1}): phrase {phrase!r} not "
                      f"in cited chunk {cid}")
                invalid.add(i)
    if invalid:
        print(f"== {len(invalid)} invalid gold row(s) excluded from grading")

    toks = [re.findall(r"[a-z0-9]+", c["text"].lower()) for c in chunks]
    N = len(toks)
    dl = [len(t) for t in toks]
    avgdl = sum(dl) / max(1, N)
    df = collections.Counter()
    for tv in toks:
        df.update(set(tv))
    idf = {t: math.log(1 + (N - df[t] + 0.5) / (df[t] + 0.5)) for t in df}
    k1, b = 1.5, 0.75

    def bm25(qt, ct):
        tf = collections.Counter(ct)
        s = 0.0
        for t in qt:
            if t not in idf:
                continue
            f = tf[t]
            s += idf[t] * f * (k1 + 1) / (f + k1 * (1 - b + b * len(ct) / max(avgdl, 1)))
        return s

    def embed_vec(text):
        r = subprocess.run(embed_cmd, shell=True, input=text,
                           capture_output=True, text=True)
        return [float(x) for x in r.stdout.replace(",", " ").split()]

    def cos(a, bq):
        d = sum(x * y for x, y in zip(a, bq))
        na = math.sqrt(sum(x * x for x in a)) or 1.0
        nb = math.sqrt(sum(x * x for x in bq)) or 1.0
        return d / (na * nb)

    emb_q = [embed_vec(q) for q, _, _, _ in qs] if embed_cmd else None
    emb_c = [embed_vec(c["text"][:4000]) for c in chunks] if embed_cmd else None

    hits3, rr_sum, n_gold = 0, 0.0, 0
    s_hits3, s_rr_sum, s_n_gold = 0, 0.0, 0
    n_strict_ungraded = 0
    for i, (q, phrase, gold_page, cid) in enumerate(qs):
        if i in invalid:
            print(f"\nQ: {q}\n  (skipped — invalid gold)")
            continue
        qt = re.findall(r"[a-z0-9]+", q.lower())
        if embed_cmd:
            ranked = sorted(range(N), key=lambda j: cos(emb_c[j], emb_q[i]), reverse=True)
        else:
            ranked = sorted(range(N), key=lambda j: bm25(qt, toks[j]), reverse=True)
        top3 = ranked[:3]

        def page_ok(j):
            return bool(gold_page and gold_page.isdigit() and chunks[j]["page"]
                        and chunks[j]["page"][0] <= int(gold_page) <= chunks[j]["page"][1])

        def phrase_ok(j):
            return bool(phrase and phrase.lower() in chunks[j]["text"].lower())

        def is_correct(j):                 # LENIENT: page OR phrase
            return page_ok(j) or phrase_ok(j)

        def is_strict(j):                  # STRICT: page AND phrase
            return page_ok(j) and phrase_ok(j)

        first = next((r for r, j in enumerate(top3, 1) if is_correct(j)), None)
        first_s = next((r for r, j in enumerate(top3, 1) if is_strict(j)), None)
        has_gold = bool(phrase or (gold_page and gold_page.isdigit()))
        if has_gold:
            n_gold += 1
            if first:
                hits3 += 1
                rr_sum += 1.0 / first
        strict_gradable = bool(phrase) and bool(gold_page and gold_page.isdigit())
        if strict_gradable:
            s_n_gold += 1
            if first_s:
                s_hits3 += 1
                s_rr_sum += 1.0 / first_s
        elif has_gold:
            n_strict_ungraded += 1
        print(f"\nQ: {q}")
        for rank, j in enumerate(top3, 1):
            mark = "  <-- CORRECT" if (has_gold and is_correct(j)) else ""
            pg = chunks[j]["page"]
            pg_s = f"p{pg[0]}-{pg[1]}" if pg else "text"
            print(f"  {rank}. {pg_s} [{(chunks[j]['path'] or '')[:60]}] "
                  f"{chunks[j]['text'][:100]}...{mark}")
    ok = None
    if n_gold:
        print(f"\n== LENIENT (page OR phrase): {n_gold} questions | "
              f"hit@3 = {hits3}/{n_gold} ({100 * hits3 / n_gold:.0f}%) | "
              f"MRR = {rr_sum / n_gold:.3f}")
    if s_n_gold:
        ratio = s_hits3 / s_n_gold
        print(f"== STRICT (page AND phrase): {s_n_gold} questions | "
              f"hit@3 = {s_hits3}/{s_n_gold} ({100 * ratio:.0f}%) | "
              f"MRR = {s_rr_sum / s_n_gold:.3f}"
              + (f" | {n_strict_ungraded} questions ungraded (need both phrase and page)"
                 if n_strict_ungraded else ""))
        if min_hit is not None:
            ok = ratio >= min_hit
            print(("== min-hit PASS" if ok else
                   f"== min-hit FAIL: STRICT hit@3 {100 * ratio:.0f}% < "
                   f"{100 * min_hit:.0f}%") + " (use --min-hit)")
    else:
        print("\n(no gold answers in question file — add ' | key phrase | page' columns)")
    if min_hit is not None:
        if s_n_gold < min_questions:
            print(f"== min-hit FAIL: only {s_n_gold} STRICT-graded question(s); "
                  f"need >= {min_questions} (--min-questions)")
            ok = False
        if invalid:
            print(f"== min-hit FAIL: {len(invalid)} invalid gold row(s); fix or delete them")
            ok = False
        cited = {cid for i, (_, _, _, cid) in enumerate(qs) if cid and i not in invalid}
        if cited and len(cited) < min_chunks:
            print(f"== min-hit FAIL: gold cites only {len(cited)} distinct chunk(s); "
                  f"need >= {min_chunks} (--min-chunks)")
            ok = False
        n_nocid = sum(1 for i, (_, _, _, cid) in enumerate(qs) if not cid and i not in invalid)
        if n_nocid:
            print(f"== WARNING: {n_nocid} gold row(s) have no chunk id and could not be validated")
        if n_todo:
            print(f"== min-hit FAIL: {n_todo} TODO row(s) left in the question file")
            ok = False
    return ok


if __name__ == "__main__":
    main()
