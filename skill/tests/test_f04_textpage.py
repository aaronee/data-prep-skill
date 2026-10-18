"""Step 4: text mode must drop bare page-number lines (and explicit
'Page N' lines) without eating them into the surrounding paragraph."""
import json
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
PREP = os.path.join(HERE, "..", "scripts", "prep.py")
from fixtures import run_prep

TXT = """# Vol Book

alpha beta gamma sentence one.
12
delta epsilon zeta sentence two.

foo bar baz sentence three.
Page 34
qux quux corge sentence four.

In 1987 the market fell sharply.
2008
The crisis continued after that.
"""


def txt_prep(tmp, name, text, extra=()):
    path = os.path.join(tmp, name + ".txt")
    with open(path, "w") as f:
        f.write(text)
    subprocess.run([sys.executable, PREP, path, "--outdir", tmp, *extra],
                   check=True, capture_output=True)
    base = os.path.join(tmp, name)
    with open(base + ".clean.txt") as f:
        clean = f.read()
    with open(base + ".removed.jsonl") as f:
        removed = [json.loads(l) for l in f]
    return dict(clean=clean, removed=removed)


class TestTextBarePageNumbers(unittest.TestCase):
    def test_bare_and_label_dropped(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = txt_prep(tmp, "t1", TXT)
        dropped = [r["text"] for r in out["removed"] if r["rule"].startswith("R2")]
        self.assertIn("12", dropped)
        self.assertIn("Page 34", dropped)
        self.assertNotIn("2008", dropped, "year-like value must be kept")
        self.assertIn("2008", out["clean"])
        self.assertIn("alpha beta gamma sentence one.", out["clean"])
        self.assertIn("delta epsilon zeta sentence two.", out["clean"])
        # the number must not be glued into a paragraph
        self.assertNotIn("one. 12 delta", out["clean"])

    def test_disable_r2_keeps(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = txt_prep(tmp, "t2", TXT, extra=("--disable", "R2"))
        self.assertNotIn("12", [r["text"] for r in out["removed"]
                                if r["rule"].startswith("R2")])

    def test_md_mode_too(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = run_prep(tmp, "t3", text=TXT)
        dropped = [r["text"] for r in out["removed"] if r["rule"].startswith("R2")]
        self.assertIn("12", dropped)


if __name__ == "__main__":
    unittest.main()
