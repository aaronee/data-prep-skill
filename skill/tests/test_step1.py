import os, tempfile, unittest
from fixtures import run_prep

W1 = ["red", "blue", "green", "gold", "gray", "dark", "soft", "hard", "wide", "thin", "cold", "warm"]
W2 = ["first", "second", "third", "fourth", "fifth", "sixth", "seventh", "eighth", "ninth", "tenth", "eleventh", "twelfth"]


class TestStep1TextMode(unittest.TestCase):
    def test_recurring_header_removed_and_hyphen_joined(self):
        # 12 repeated headers + per-block content. Content lines vary by WORD
        # (not by digit: text-mode R1 collapses digits to #, so digit variation
        # would make the lines recurring too — the spec's literal test text
        # (identical content lines x12) is unsatisfiable for the same reason).
        blocks = []
        for p in range(12):
            n = p + 1
            blocks.append(f"Trading Volatility | Page {n}\n\n"
                          f"Real content {W1[p]} about risk-\n"
                          f"neutral pricing {W2[p]} and Black-\n"
                          f"Scholes models, take {W1[p]}.")
        text = "\n\n".join(blocks)
        with tempfile.TemporaryDirectory() as tmp:
            r = run_prep(tmp, "t1", text=text)
        self.assertNotIn("Trading Volatility | Page", r["clean"])
        self.assertIn("risk-neutral", r["clean"])
        self.assertIn("Black-Scholes", r["clean"])
        self.assertNotIn("risk- neutral", r["clean"])
        self.assertIn("R1 recurring line (text)", {x["rule"] for x in r["removed"]})
        self.assertIn("Scholes models, take gold.", r["clean"])
        # the content lines must NOT have been caught by R1 (they are unique per block)
        self.assertEqual(len([x for x in r["removed"] if "Real content" in x["text"]]), 0)

    def test_markdown_table_unchanged(self):
        table = ["| a | b |", "|---|---|"] + [f"| d{i} | e{i} |" for i in range(1, 11)]
        text = "\n\n".join("\n".join(table) for _ in range(10))
        with tempfile.TemporaryDirectory() as tmp:
            r = run_prep(tmp, "t2", text=text)
        for i in range(1, 11):
            self.assertIn(f"d{i}", r["clean"])
            self.assertIn(f"e{i}", r["clean"])
        self.assertEqual(r["clean"].count("|---|---|"), 10)
        self.assertEqual(len([x for x in r["removed"] if "R1" in x["rule"]]), 0)

    def test_disable_r1_keeps_headers(self):
        blocks = [f"Trading Volatility | Page {p}\n\n"
                  f"Body text, the {W2[p-1]} kind, for page {p}.\n" for p in range(1, 13)]
        text = "\n".join(blocks)
        with tempfile.TemporaryDirectory() as tmp:
            r = run_prep(tmp, "t3", text=text, extra=("--disable", "R1"))
        self.assertIn("Trading Volatility | Page 7", r["clean"])


if __name__ == "__main__":
    unittest.main()
