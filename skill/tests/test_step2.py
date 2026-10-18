import random, tempfile, unittest
from fixtures import run_prep, line, head, page, words

HDR = "Chapter {c}: A Study of Volatility Risk Management and Hedging Techniques"  # >60 chars: escapes the R1 stem key; varies per chapter: <30 = 15% of 200


def build_200(seed=1):
    rng = random.Random(seed)
    pages, bodies = [], []
    p = 0
    for c in range(1, 11):
        for _ in range(20):
            p += 1
            items = line(HDR.format(c=c), 20)
            y = 100
            for i in range(6):
                b = words(6, rng)
                bodies.append(b)
                items += line(b, y)
                y += 12
            pages.append(page(p, items))
    return pages, bodies


class TestStep2MarginRepeat(unittest.TestCase):
    def test_chapter_headers_removed_body_kept(self):
        pages, bodies = build_200()
        with tempfile.TemporaryDirectory() as tmp:
            r = run_prep(tmp, "m1", pages=pages)
        self.assertNotIn("A Study of Volatility Risk Management", r["clean"])
        self.assertNotIn(HDR.format(c=1)[:20], r["clean"])
        missing = [b for b in bodies if b not in r["clean"]]
        self.assertEqual(missing[:5], [], f"{len(missing)} body lines missing")
        self.assertTrue(any("R1b margin repeat" in x["rule"] for x in r["removed"]))

    def test_unique_top_heading_kept(self):
        rng = random.Random(2)
        pages = [
            page(1, head("Unique Study Title Here", 20) + line(words(6, rng), 100)),
            page(2, line(words(6, rng), 100)),
            page(3, line(words(6, rng), 100)),
        ]
        with tempfile.TemporaryDirectory() as tmp:
            r = run_prep(tmp, "m2", pages=pages)
        self.assertIn("Unique Study Title Here", r["clean"])

    def test_disable_r1b_keeps_headers(self):
        """R1b has its own switch: --disable R1b keeps the margin header;
        --disable R1 alone does not (they are no longer coupled)."""
        pages, _ = build_200(seed=3)
        with tempfile.TemporaryDirectory() as tmp:
            r = run_prep(tmp, "m3", pages=pages, extra=("--disable", "R1b"))
        self.assertIn("A Study of Volatility Risk Management", r["clean"])
        with tempfile.TemporaryDirectory() as tmp:
            r = run_prep(tmp, "m4", pages=pages, extra=("--disable", "R1"))
        self.assertNotIn("A Study of Volatility Risk Management", r["clean"])


if __name__ == "__main__":
    unittest.main()
