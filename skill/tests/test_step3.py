import tempfile, unittest
from fixtures import run_prep, line, page


class TestStep3Unicode(unittest.TestCase):
    def test_geometry_cid_ligature_invisible_control(self):
        # line 1 supplies the word "volatility" to the document vocabulary so the
        # line-break hyphen on line 2 (vol-/ility) can merge. The spec's literal
        # fixture (a single item "vol-ility") cannot transform under its own 3a
        # rules (a real hyphen inside one word is not a line-break hyphen).
        items = line("The final efficient ratio of volatility is high.", 100)
        a = []
        for i, w in enumerate(["The", "ﬁnal", "eﬃcient", "ratio\u200b", "of", "vol-"]):
            a.append(dict(text=w, x=50 + i * 30, y=120, width=25, height=10, font_name="Times"))
        b = []
        for i, w in enumerate(["ility", "(cid:123)", "was\x07", "high."]):
            b.append(dict(text=w, x=50 + i * 30, y=135, width=25, height=10, font_name="Times"))
        with tempfile.TemporaryDirectory() as tmp:
            r = run_prep(tmp, "u1", pages=[page(1, items + a + b)])
        c = r["clean"]
        self.assertIn("final efficient ratio of volatility", c)
        self.assertNotIn("(cid:", c)
        self.assertNotIn("\u00ad", c)
        self.assertNotIn("\ufeff", c)
        self.assertNotIn("\u200b", c)
        self.assertNotIn("vol-ility", c)

    def test_text_mode(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = run_prep(tmp, "u2", text="e\ufb03cient soft\u00ADhyphen and vol\x01atility.\n")
        self.assertIn("efficient soft", r["clean"])
        self.assertNotIn("\u00ad", r["clean"])
        self.assertNotIn("\x01", r["clean"])
        self.assertNotIn("\ufb03", r["clean"])


if __name__ == "__main__":
    unittest.main()
