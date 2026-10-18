import random, tempfile, unittest
from fixtures import run_prep, line, head, page, WORDS

# digit-free unique filler words so the per-page repeated row text is NOT a
# recurring line (the spec's literal fixture "L{row} words" repeated 8x on 8
# pages would trip R1 with thr = max(5, 0.15*8) = 5; 16 rows/page also
# satisfies find_gutter's n_lines >= 15, which the spec's 14-row fixture would
# not meet). Row keys "l{i} {word} words" are unique per page and across pages.
WA = WORDS


def build_cols(seed=5):
    rng = random.Random(seed)
    pages = []
    for pg in range(1, 9):
        items = []
        if pg == 1:
            items = head("Full Width Title Above Columns", 60)
        for i in range(16):
            y = 100 + i * 12
            items += line(f"L{i} {WA[(pg * 16 + i) % len(WA)]} words and more", y, x=50)
            items += line(f"R{i} {WA[(pg * 32 + i) % len(WA)]} words and more", y, x=330)
        pages.append(page(pg, items))
    return pages


class TestStep4(unittest.TestCase):
    def test_footnote_removed(self):
        items = line("The previous sentence needs a note here.", 400)
        items += line("1 This footnote explains the previous sentence.", 780, h=8)
        with tempfile.TemporaryDirectory() as tmp:
            r = run_prep(tmp, "f1", pages=[page(1, items)])
        self.assertNotIn("footnote explains", r["clean"])
        self.assertIn("R8 footnote", {x["rule"] for x in r["removed"]})
        self.assertIn("The previous sentence needs a note here.", r["clean"])

    def test_two_column_order_and_no_pipe(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = run_prep(tmp, "c1", pages=build_cols())
        c = r["clean"]
        self.assertNotIn(" | ", c)
        self.assertNotIn("two-column", r["report"].lower())
        for pg in range(1, 9):
            for i in range(16):
                self.assertIn(f"L{i} {WA[(pg * 16 + i) % len(WA)]} words and more", c)
                self.assertIn(f"R{i} {WA[(pg * 32 + i) % len(WA)]} words and more", c)
            self.assertLess(c.find(f"L15 {WA[(pg * 16 + 15) % len(WA)]} words and more"),
                            c.find(f"R0 {WA[(pg * 32) % len(WA)]} words and more"),
                            f"page {pg}: left column must precede right column")
        self.assertIn("Full Width Title Above Columns", c)
        self.assertLess(c.find("Full Width Title Above Columns"), c.find("L0 "))


if __name__ == "__main__":
    unittest.main()
