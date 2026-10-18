"""Step 5: STRICT (page AND phrase) vs LENIENT (page OR phrase) eval + --min-hit."""
import contextlib
import importlib.util
import importlib.machinery
import io
import os
import re
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SD = os.path.join(HERE, "..", "scripts")


def load_prep():
    loader = importlib.machinery.SourceFileLoader("prep5", os.path.join(SD, "prep.py"))
    spec = importlib.util.spec_from_loader("prep5", loader)
    prep = importlib.util.module_from_spec(spec)
    with __import__("unittest.mock", fromlist=["patch"]).patch.object(sys, "argv", ["x"]):
        spec.loader.exec_module(prep)
    return prep


CHUNKS = [
    {"text": "Alpha beta gamma defines the retention metric for RAG systems. "
             "Only phrase no page sentence here too.",
     "page": [5, 6], "path": ["Ch 1", "Retention"]},
    {"text": "Completely unrelated content about volatility surfaces and smiles.",
     "page": [20, 21], "path": ["Ch 2", "Surfaces"]},
    {"text": "Another unrelated passage with different words entirely.",
     "page": [30, 31], "path": None},
]

QFILE = """Q1 | alpha beta gamma | 5
Q2 | alpha beta gamma | 99
Q3 | zzz unique phrase | 5
Q4 plain question no gold
Q5 | alpha beta gamma
"""


def run_eval_capture(prep, qfile_text, min_hit=None, min_questions=1):
    with tempfile.TemporaryDirectory() as td:
        qf = os.path.join(td, "q.txt")
        with open(qf, "w") as f:
            f.write(qfile_text)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            ok = prep.run_eval(qf, CHUNKS, None, min_hit, min_questions)
    return buf.getvalue(), ok


class TestStrictEval(unittest.TestCase):
    def test_strict_vs_lenient(self):
        prep = load_prep()
        out, ok = run_eval_capture(prep, QFILE)
        m_len = re.search(r"== LENIENT.*hit@3 = (\d+)/(\d+)", out)
        m_str = re.search(r"== STRICT.*hit@3 = (\d+)/(\d+)", out)
        self.assertIsNotNone(m_len, out)
        self.assertIsNotNone(m_str, out)
        # LENIENT: 4 gold (Q1,Q2,Q3,Q5), all hit: Q1 phrase+page, Q2 phrase,
        # Q3 page, Q5 phrase
        self.assertEqual((m_len.group(1), m_len.group(2)), ("4", "4"))
        # STRICT: 3 gradable (Q1,Q2,Q3) — only Q1 has both phrase AND page right
        self.assertEqual((m_str.group(1), m_str.group(2)), ("1", "3"))
        self.assertIn("1 questions ungraded", out)   # Q5 (phrase only)
        self.assertIsNone(ok)                        # no gate -> None

    def test_min_hit_gate(self):
        prep = load_prep()
        _, ok_fail = run_eval_capture(prep, QFILE, min_hit=0.5)   # 33% < 50%
        out_pass, ok_pass = run_eval_capture(prep, QFILE, min_hit=0.3)
        self.assertFalse(ok_fail)
        self.assertTrue(ok_pass)
        self.assertNotIn("min-hit FAIL", out_pass)
        self.assertIn("min-hit PASS", out_pass)


if __name__ == "__main__":
    unittest.main()
