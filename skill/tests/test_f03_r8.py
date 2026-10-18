"""Step 3: R8 must not drop code listings or figure captions; footnote band/
ratio become flags; R1b gets its own --disable switch (R1 no longer controls it)."""
import tempfile
import unittest
from fixtures import *


def r8_page():
    items = []
    y = 100
    for i in range(30):
        items += line(f"body sentence number {i} here alpha", y, h=10)
        y += 16                      # last body line at y=564, above the 576 band
    # bottom band of H=800: y > 576; small fonts 7-8 <= 0.85*10=8.5
    items += line("def foo(bar):  # == code _line here", 600, h=7, font="Courier")
    items += line("df0=close.loc[df0.index]/close.loc[x].values-1 # daily", 640, h=7)
    items += line("Figure 7.3 Example caption line here", 680, h=8)
    items += line("This is a real footnote sentence here", 720, h=8)
    return [page(1, items)]


class TestR8Exemptions(unittest.TestCase):
    def test_code_and_caption_kept_footnote_dropped(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = run_prep(tmp, "r8", pages=r8_page())
            rm = {r["rule"] for r in out["removed"]}
            self.assertIn("This is a real footnote sentence here",
                          [r["text"] for r in out["removed"] if r["rule"] == "R8 footnote"])
            self.assertFalse(any("def foo(bar)" in r["text"] for r in out["removed"]))
            self.assertIn("def foo(bar):", out["clean"])
            self.assertIn("Figure 7.3 Example caption", out["clean"])
            self.assertFalse(any("Figure 7.3" in r["text"] for r in out["removed"]))
            for i in (0, 15, 29):
                self.assertIn(f"body sentence number {i} here alpha", out["clean"])

    def test_flag_zone(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = run_prep(tmp, "r8z", pages=r8_page(),
                           extra=("--footnote-zone", "0.99"))
            self.assertIn("This is a real footnote sentence here", out["clean"])

    def test_flag_ratio(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = run_prep(tmp, "r8r", pages=r8_page(),
                           extra=("--footnote-ratio", "0.5"))
            self.assertIn("This is a real footnote sentence here", out["clean"])


def margin_pages():
    pages = []
    for i in range(6):
        items = line(f"unique body text {i} alpha", 100)
        if i < 4:
            items += head("RUNNING HEADER X", 20)   # top 8% band, 4 pages
        pages.append(page(i + 1, items))
    return pages


class TestR1bSwitch(unittest.TestCase):
    def test_r1b_is_own_switch(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = run_prep(tmp, "m1", pages=margin_pages())
            r1b = [r for r in out["removed"] if r["rule"] == "R1b margin repeat"]
            self.assertEqual(len(r1b), 4)
        with tempfile.TemporaryDirectory() as tmp:
            out = run_prep(tmp, "m2", pages=margin_pages(), extra=("--disable", "R1b"))
            self.assertNotIn("RUNNING HEADER X",
                             [r["text"] for r in out["removed"]])
            self.assertIn("RUNNING HEADER X", out["clean"])
        with tempfile.TemporaryDirectory() as tmp:
            out = run_prep(tmp, "m3", pages=margin_pages(), extra=("--disable", "R1"))
            self.assertIn("RUNNING HEADER X",
                          [r["text"] for r in out["removed"]
                           if r["rule"] == "R1b margin repeat"])


if __name__ == "__main__":
    unittest.main()
