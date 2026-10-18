"""Step 5: eval candidates must be non-circular and non-leaking (questions
never contain the key phrase; only content chunks cited), and run_eval must
accept the 4th chunk_id column, rejecting gold rows whose cited chunk does
not contain the phrase (stale/leaky gold is not counted)."""
import contextlib
import importlib.machinery
import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SD = os.path.join(HERE, "..", "scripts")
CAND = os.path.join(SD, "make_eval_candidates.py")


def load_prep():
    loader = importlib.machinery.SourceFileLoader("prepf5", os.path.join(SD, "prep.py"))
    spec = importlib.util.spec_from_loader("prepf5", loader)
    prep = importlib.util.module_from_spec(spec)
    with __import__("unittest.mock", fromlist=["patch"]).patch.object(sys, "argv", ["x"]):
        spec.loader.exec_module(prep)
    return prep


def synth_chunks(n=24):
    out = []
    for i in range(n):
        text = f"distinct content word z{100 + i} alpha beta gamma sentence {i}."
        if i == 7:
            text = "The superfluously long derivation continues here with detail."
        c = {"id": f"c{i:04d}", "source": "s.txt", "chunk_index": i,
             "page": [i + 1, i + 1], "page_label": None, "path": None,
             "text": text, "embed_text": "x", "sha256": "z" * 64}
        if i % 3 == 0:
            c["path"] = ["Book", f"Section {i}"]
        if i == 20:
            c["llm_type"] = "legal"
            c["text"] = "All rights reserved. Copyright notice for the book."
        out.append(c)
    return out


class TestCandidatesNonCircular(unittest.TestCase):
    def test_no_leak_content_only_four_cols(self):
        with tempfile.TemporaryDirectory() as tmp:
            ch = synth_chunks()
            cpath = os.path.join(tmp, "s.chunks.json")
            with open(cpath, "w") as f:
                json.dump(ch, f)
            r = subprocess.run([sys.executable, CAND, cpath, "--count", "10"],
                               capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            rows = [l for l in r.stdout.splitlines()
                    if l and not l.startswith("#") and "|" in l]
            self.assertGreaterEqual(len(rows), 5)
            by_id = {c["id"]: c for c in ch}
            for row in rows:
                parts = [p.strip() for p in row.split("|")]
                self.assertEqual(len(parts), 4, f"need 4 cols: {row}")
                q, phrase, page, cid = parts
                self.assertIn(cid, by_id, f"unknown chunk id {cid}")
                self.assertEqual(by_id[cid]["page"][0], int(page))
                self.assertIn(phrase, by_id[cid]["text"],
                              f"phrase not in cited chunk: {phrase!r}")
                # leak guard: no phrase word may appear in the question
                pw = set(phrase.lower().split())
                qw = set(w.lower().strip(".,;:?'\"") for w in q.split())
                self.assertFalse(pw & qw, f"leak: {row}")
            cited = {p[3].strip() for p in
                     ([x.strip() for x in l.split("|")] for l in rows)}
            legal = {c["id"] for c in ch if c.get("llm_type") == "legal"}
            self.assertTrue(legal and not (legal & cited),
                            "legal chunk must never be cited")


class TestEvalChunkIdValidation(unittest.TestCase):
    def test_invalid_gold_not_counted(self):
        prep = load_prep()
        chunks = [
            {"id": "c0001", "text": "retention metric for RAG systems alpha beta.",
             "page": [5, 5], "path": ["A"]},
            {"id": "c0002", "text": "unrelated volatility surface content.",
             "page": [6, 6], "path": ["B"]},
        ]
        with tempfile.TemporaryDirectory() as tmp:
            qfile = os.path.join(tmp, "q.txt")
            # valid: phrase is in c0001, page 5. invalid: phrase NOT in c0002.
            with open(qfile, "w") as f:
                f.write(
                    "Q1 | retention metric | 5 | c0001\n"
                    "Q2 | retention metric | 6 | c0002\n")
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                prep.run_eval(qfile, chunks, None)
        out = buf.getvalue()
        self.assertIn("invalid", out.lower())
        self.assertIn("Q2", out)

    def test_three_col_still_works(self):
        prep = load_prep()
        chunks = [
            {"id": "c0001", "text": "retention metric for RAG systems alpha beta.",
             "page": [5, 5], "path": ["A"]},
        ]
        with tempfile.TemporaryDirectory() as tmp:
            qfile = os.path.join(tmp, "q.txt")
            with open(qfile, "w") as f:
                f.write("Q1 | retention metric | 5\n")
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                prep.run_eval(qfile, chunks, None)
        out = buf.getvalue()
        self.assertIn("STRICT", out)
        self.assertIn("100%", out.replace("hit@3 = 1/1 (100%)", "100%"))


if __name__ == "__main__":
    unittest.main()
