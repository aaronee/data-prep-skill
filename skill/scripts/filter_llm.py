#!/usr/bin/env python3
"""data-prep LLM pass: agent-side, never inside prep.py.

Classifies SUSPECT chunks only (cheap heuristic pre-selection) via an
OpenAI-compatible chat endpoint (local Qwen, etc.), with schema-constrained
JSON output, chunk-hash caching, and a dropped.jsonl audit trail.

Pre-selection marks a chunk suspect when ANY of:
  - letter ratio < 0.55 (symbol/table junk)
  - boilerplate regex (rights, copyright, disclaimer, acknowledg...)
  - very short (< 80 chars) OR very long (> 6x median)
  - near-duplicate of an earlier chunk (normalized prefix hash)

Non-suspect chunks are auto-kept — that's what makes this cheap.

usage:
  filter_llm.py <chunks.json> --endpoint http://localhost:8000/v1/chat/completions \
      --model qwen2.5 [--api-key KEY | LLM_API_KEY env] [--max-tokens N] \
      [--max-suspects 100] [--dry-run] [--all]

Outputs:  <name>.chunks.filtered.json   (kept chunks; suspect ones carry
                                            llm_type/summary/keywords meta)
          <name>.dropped.jsonl          (one row per dropped chunk: id, type, reason)
Cache:    <name>.llmcache.json          (keyed by chunk sha256; reruns cost $0)
"""
import argparse
import collections
import hashlib
import json
import os
import re
import sys
import urllib.error
import urllib.request

SCHEMA = """{
  "keep": true|false,
  "type": "content"|"toc"|"index"|"bibliography"|"front_matter"|"ad"|"legal"|"author_bio"|"acknowledgments"|"junk",
  "summary": "<= 25 words",
  "keywords": ["3-8", "short", "terms"]
}"""

SYSTEM = (
    "You classify a document chunk for a RAG index. Decide if it is genuine content "
    "worth keeping (prose, tables, figures' text, lists) or filler (table of contents, "
    "index, bibliography, front matter, ads, legal boilerplate, author bio, "
    "acknowledgments, OCR junk). Reply with ONLY a JSON object matching:\n"
    + SCHEMA
    + "\nIf unsure, keep=true. Do not output any other text."
)

BOILER = re.compile(
    r"all rights reserved|copyright|disclaimer|acknowledg|no part of this "
    r"(book|publication)|©|isbn|www\.|publisher", re.I)


def suspect_reasons(ch, med_len):
    r = []
    letters = sum(c.isalpha() or c == " " for c in ch["text"])
    if len(ch["text"]) and letters / len(ch["text"]) < 0.55:
        r.append("low letter ratio")
    if BOILER.search(ch["text"]):
        r.append("boilerplate pattern")
    if len(ch["text"]) < 80:
        r.append("too short")
    toks = ch["text"].split()
    if len(toks) >= 30:
        nums = sum(1 for t in toks if re.fullmatch(r"\d+([-–]\d+)?[,;.]?", t))
        years = len(re.findall(r"\b(?:19|20)\d{2}[a-z]?\b", ch["text"]))
        if nums / len(toks) > 0.15:
            r.append("index-like (many page numbers)")
        elif years / len(toks) > 0.06:
            r.append("bibliography-like (many years)")
    if med_len and len(ch["text"]) > 6 * med_len:
        r.append("abnormally long")
    if ch.get("path") and norm_prefix(ch["text"]) == ch.get("_dup"):
        r.append("near-duplicate")
    return r


DROP_TYPES = {"toc", "index", "bibliography", "front_matter", "ad", "legal",
              "author_bio", "acknowledgments", "junk"}      # "content" is NEVER dropped
SYSTEM_HASH = hashlib.sha256(SYSTEM.encode()).hexdigest()[:12]


def cache_key(chunk, model):
    """A verdict is only valid for the same chunk + model + prompt."""
    return hashlib.sha256(f"{chunk['sha256']}|{model}|{SYSTEM_HASH}".encode()).hexdigest()[:24]


def should_drop(verdict):
    return bool(verdict) and verdict.get("keep") is False and verdict.get("type") in DROP_TYPES


def norm_prefix(text):
    return re.sub(r"\s+", " ", text[:160].lower().strip())


def call_llm(endpoint, model, text, extra, api_key=None, max_tokens=None):
    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": text[:3000]},
        ],
        "temperature": 0,
        "response_format": {"type": "json_object"},
    }
    if max_tokens:
        body["max_tokens"] = max_tokens
    body.update(extra or {})
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    req = urllib.request.Request(
        endpoint, data=json.dumps(body).encode(), headers=headers)
    with urllib.request.urlopen(req, timeout=120) as resp:
        out = json.load(resp)
    content = out["choices"][0]["message"]["content"]
    m = re.search(r"\{.*\}", content, re.S)
    if not m:
        return None
    obj = json.loads(m.group(0))     # parse failure -> caller defaults to keep
    return obj


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input", help="chunks.json from prep.py")
    ap.add_argument("--endpoint", help="OpenAI-compatible /v1/chat/completions URL")
    ap.add_argument("--model", default="qwen2.5")
    ap.add_argument("--api-key", default=os.environ.get("LLM_API_KEY"),
                    help="sent as Authorization: Bearer <key>; defaults to the "
                         "LLM_API_KEY env var; never printed or cached")
    ap.add_argument("--max-tokens", type=int, default=None,
                    help="cap completion length (e.g. when the model emits thinking text)")
    ap.add_argument("--extra-json", default=None,
                    help="extra request-body JSON, e.g. Qwen thinking off: "
                         '{"chat_template_kwargs":{"enable_thinking":false}}')
    ap.add_argument("--max-suspects", type=int, default=100)
    ap.add_argument("--all", action="store_true", help="send ALL chunks (not just suspects)")
    ap.add_argument("--dry-run", action="store_true", help="list suspects, make no API calls")
    args = ap.parse_args()

    with open(args.input, encoding="utf-8") as f:
        chunks = json.load(f)
    in_base = os.path.basename(args.input).replace(".chunks.json", "")
    outdir = os.path.dirname(os.path.abspath(args.input))
    cache_path = os.path.join(outdir, in_base + ".llmcache.json")
    cache = {}
    if os.path.exists(cache_path):
        cache = json.load(open(cache_path, encoding="utf-8"))

    lens = [len(c["text"]) for c in chunks]
    med_len = sorted(lens)[len(lens) // 2] if lens else 0
    seen, suspects = {}, []
    for c in chunks:
        reasons = ["all"] if args.all else suspect_reasons(c, med_len)
        np = norm_prefix(c["text"])
        if seen.get(np):
            c["_dup"] = np
            if not args.all:
                reasons.append("near-duplicate")
        else:
            seen[np] = True
        if reasons:
            suspects.append((c, reasons))

    print(f"chunks: {len(chunks)} | suspect: {len(suspects)} "
          f"(median len {med_len})")
    if args.dry_run:
        for c, r in suspects[:50]:
            print(f"  {c['id']} ({len(c['text'])} ch, sha {c['sha256']}): "
                  f"{', '.join(r)}")
        print(f"... ({len(suspects)} total; --dry-run, no API calls made)")
        return

    if not suspects:
        print("no suspect chunks — writing unfiltered copy")
    else:
        if not args.endpoint:
            sys.exit("suspects found but --endpoint missing (or use --dry-run)")
        extra = json.loads(args.extra_json) if args.extra_json else None
        to_send = suspects[:args.max_suspects]
        if len(suspects) > args.max_suspects:
            print(f"NOTE: processing first {args.max_suspects} suspects only")
        n_err, consec_err = 0, 0
        for c, reasons in to_send:
            key = cache_key(c, args.model)
            if key in cache:
                verdict = cache[key]
                print(f"  {c['id']}: cache hit ({verdict.get('type')})")
                continue
            print(f"  {c['id']}: calling LLM ({', '.join(reasons)})...")
            try:
                verdict = call_llm(args.endpoint, args.model, c["text"], extra,
                                   args.api_key, args.max_tokens)
                # successful calls are cached (even malformed-JSON -> keep),
                # transient errors are NOT (rerun retries them)
                cache[key] = verdict if verdict is not None else {
                    "keep": True, "type": "unknown", "summary": "", "keywords": []}
                consec_err = 0
            except urllib.error.HTTPError as e:
                if e.code in (401, 403):
                    sys.exit(f"AUTH ERROR HTTP {e.code}: check --api-key / LLM_API_KEY. "
                             "Nothing was filtered; no output written.")
                n_err += 1; consec_err += 1
                print(f"    ERROR: {e} -> defaulting to keep (NOT cached — rerun retries)")
                verdict = None
            except Exception as e:
                n_err += 1; consec_err += 1
                print(f"    ERROR: {e} -> defaulting to keep (NOT cached — rerun retries)")
                verdict = None
            if consec_err >= 3:
                with open(cache_path, "w", encoding="utf-8") as f:
                    json.dump(cache, f)        # keep verdicts already paid for
                sys.exit("STOPPED: 3 failures in a row (endpoint down or wrong URL/model). "
                         "No filtered output written; earlier verdicts were cached.")
            if verdict is None:
                verdict = {"keep": True, "type": "unknown",
                           "summary": "", "keywords": []}
            print(f"    -> keep={verdict.get('keep')} type={verdict.get('type')}")

    dropped_path = os.path.join(outdir, in_base + ".dropped.jsonl")
    open(dropped_path, "w", encoding="utf-8").close()
    kept, n_drop = [], 0
    sent = {c["sha256"] for c, _ in suspects[:args.max_suspects]} if args.endpoint else set()
    for c in chunks:
        v = cache.get(cache_key(c, args.model)) if c["sha256"] in sent else None
        if v is None and c["sha256"] in sent:
            v = {"keep": True, "type": "unknown", "summary": "", "keywords": []}
        if should_drop(v):
            with open(dropped_path, "a", encoding="utf-8") as f:
                f.write(json.dumps({"id": c["id"], "sha256": c["sha256"],
                                    "type": v.get("type"),
                                    "summary": v.get("summary", ""),
                                    "text_head": c["text"][:200]},
                                   ensure_ascii=False) + "\n")
            n_drop += 1
            continue
        kc = dict(c)
        if v:
            kc["llm_type"] = v.get("type")
            kc["llm_summary"] = v.get("summary", "")
            kc["llm_keywords"] = v.get("keywords", [])
        kept.append(kc)
    with open(cache_path, "w", encoding="utf-8") as f:
        json.dump(cache, f)
    filtered_path = os.path.join(outdir, in_base + ".chunks.filtered.json")
    with open(filtered_path, "w", encoding="utf-8") as f:
        json.dump(kept, f, ensure_ascii=False, indent=1)
    print(f"\nkept {len(kept)}/{len(chunks)} | dropped {n_drop} -> {dropped_path}")
    print(f"filtered chunks -> {filtered_path}")
    print(f"cache ({len(cache)} entries) -> {cache_path}  [reruns are free]")
    if suspects and args.endpoint and n_err:
        print(f"WARNING: {n_err} call(s) failed and were kept unfiltered — INCOMPLETE; rerun.")
        sys.exit(3)


if __name__ == "__main__":
    main()
