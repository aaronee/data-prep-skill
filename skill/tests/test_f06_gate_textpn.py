"""v5: eval gate must fail closed; text-mode page numbers must not split paragraphs;
R8 recognises more monospace fonts and --code-fonts."""
import contextlib, io, os, tempfile, unittest
from fixtures import *
import importlib.util

spec = importlib.util.spec_from_file_location("prep_mod", PREP)
prep = importlib.util.module_from_spec(spec); spec.loader.exec_module(prep)

CH = [dict(id="c0001", text="alpha volatility surface text", page=[1, 1], path="", sha256="a"),
      dict(id="c0002", text="beta other words here", page=[2, 2], path="", sha256="b")]


def run_eval(qtext, min_hit, min_q=20):
    with tempfile.TemporaryDirectory() as td:
        qf = os.path.join(td, "q.txt")
        with open(qf, "w") as f:
            f.write(qtext)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            ok = prep.run_eval(qf, CH, None, min_hit, min_q)
    return ok, buf.getvalue()


class TestGateFailsClosed(unittest.TestCase):
    def test_zero_gradable_fails(self):
        ok, out = run_eval("what | zzzz | 1 | c9999\n", 0.8, 1)
        self.assertIs(ok, False, out)

    def test_too_few_questions_fails(self):
        ok, out = run_eval("what about volatility | volatility | 1\n", 0.8, 20)
        self.assertIs(ok, False, out)
        self.assertIn("need >= 20", out)

    def test_invalid_row_fails_gate(self):
        q = "a | volatility | 1 | c0001\nb | zzzz | 1 | c0001\n"
        ok, out = run_eval(q, 0.1, 1)
        self.assertIs(ok, False, out)

    def test_no_gate_no_failure(self):
        ok, _ = run_eval("a | volatility | 1\n", None)
        self.assertIsNone(ok)


class TestTodoRows(unittest.TestCase):
    def test_todo_rows_skipped_and_fail_gate(self):
        q = "TODO write a question | volatility | 1 | c0001\n# a comment\nreal q | volatility | 1\n"
        ok, out = run_eval(q, 0.1, 1)
        self.assertIn("1 TODO row(s) skipped", out)
        self.assertNotIn("a comment", out)          # '#' lines are not questions
        self.assertIs(ok, False, out)

    def test_generator_emits_todo_stub_without_phrase(self):
        import json, subprocess, sys
        cand = os.path.join(os.path.dirname(PREP), "make_eval_candidates.py")
        with tempfile.TemporaryDirectory() as td:
            ch = [dict(id=f"c{i:04d}", page=[i + 1, i + 1], path=None, sha256="z",
                       text=f"The calibration procedure number {i} uses stochastic volatility.")
                  for i in range(8)]
            p = os.path.join(td, "s.chunks.json")
            with open(p, "w") as f:
                json.dump(ch, f)
            r = subprocess.run([sys.executable, cand, p, "--count", "4"],
                               capture_output=True, text=True)
        rows = [l for l in r.stdout.splitlines() if l.startswith("TODO")]
        self.assertGreaterEqual(len(rows), 3)
        for row in rows:
            q, phrase = [x.strip() for x in row.split("|")][:2]
            self.assertNotIn(phrase, q.lower())
        self.assertIn("# excerpt", r.stdout)


class TestTextPageNumberKeepsParagraph(unittest.TestCase):
    def test_hyphen_joined_across_page_number(self):
        text = ("# Ch\n\nThe implied volatil-\n12\nity surface is smooth and the word "
                "volatility appears elsewhere.\n\nMore volatility text.\n")
        with tempfile.TemporaryDirectory() as tmp:
            out = run_prep(tmp, "pn", text=text)
        joined = " ".join(c["text"] for c in out["chunks"])
        self.assertIn("volatility surface", joined)
        self.assertNotIn("volatil- ity", joined)
        self.assertTrue(any(r["text"] == "12" for r in out["removed"]))


class TestMonoFonts(unittest.TestCase):
    def _items(self, font, text="import numpy as np"):
        items, y = [], 100
        for i in range(30):
            items += line(f"body sentence number {i} here alpha", y, h=10); y += 16
        items += line(text, 700, h=7, font=font)
        return [page(1, items)]

    def _dropped(self, font, extra=()):
        with tempfile.TemporaryDirectory() as tmp:
            out = run_prep(tmp, "mono", pages=self._items(font), extra=extra)
        return any(r["rule"] == "R8 footnote" and r["text"] == "import numpy as np"
                   for r in out["removed"])

    def test_known_mono_names_kept(self):
        for f in ("Menlo-Regular", "Inconsolata", "CMTT10", "LucidaConsole", "DejaVuSansMono"):
            self.assertFalse(self._dropped(f), f)

    def test_monotype_serif_not_exempt(self):
        self.assertTrue(self._dropped("MonotypeBaskerville"))

    def test_code_fonts_flag(self):
        self.assertTrue(self._dropped("WeirdFont"))
        self.assertFalse(self._dropped("WeirdFont", extra=("--code-fonts", "weird")))


if __name__ == "__main__":
    unittest.main()
