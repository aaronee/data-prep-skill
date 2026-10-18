"""v6: eval gate rejects leaky/duplicate rows and low chunk diversity; --min-hit needs --eval;
filter_llm keeps already-paid verdicts when it aborts after 3 failures."""
import contextlib, importlib.util, io, json, os, subprocess, sys, tempfile, threading, unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from fixtures import *

spec = importlib.util.spec_from_file_location("prep_mod7", PREP)
prep = importlib.util.module_from_spec(spec); spec.loader.exec_module(prep)

CH = [dict(id=f"c{i:04d}", page=[i + 1, i + 1], path="", sha256=f"s{i}",
           text=f"alpha{i} beta gamma word{i} filler text about topic number {i}")
      for i in range(30)]


def run_eval(rows, min_hit=0.8, min_q=20, min_c=10):
    with tempfile.TemporaryDirectory() as td:
        qf = os.path.join(td, "q.txt")
        with open(qf, "w", encoding="utf-8") as f:
            f.write("\n".join(rows) + "\n")
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            ok = prep.run_eval(qf, CH, None, min_hit, min_q, min_c)
    return ok, buf.getvalue()


def good(i):
    return f"what is said about topic number {i} | word{i} | {i + 1} | c{i:04d}"


class TestGateHardening(unittest.TestCase):
    def test_20_good_distinct_rows_pass(self):
        ok, out = run_eval([good(i) for i in range(20)])
        self.assertIs(ok, True, out)

    def test_duplicate_questions_fail(self):
        ok, out = run_eval([good(3)] * 20)
        self.assertIs(ok, False, out)
        self.assertIn("duplicate of Q1", out)

    def test_leaky_rows_fail(self):
        ok, out = run_eval([f"tell me about word{i} | word{i} | {i + 1} | c{i:04d}" for i in range(20)])
        self.assertIs(ok, False, out)
        self.assertIn("appears in the question (leak)", out)

    def test_one_chunk_cited_many_times_fails(self):
        rows = [f"question {i} about topic number 3 | word3 | 4 | c0003" for i in range(20)]
        ok, out = run_eval(rows)
        self.assertIs(ok, False, out)
        self.assertIn("distinct chunk", out)

    def test_threeCol_rows_skip_chunk_check_and_warn(self):
        rows = [f"what is said about topic number {i} | word{i} | {i + 1}" for i in range(20)]
        ok, out = run_eval(rows)
        self.assertIs(ok, True, out)
        self.assertIn("no chunk id", out)

    def test_min_hit_without_eval_is_an_error(self):
        with tempfile.TemporaryDirectory() as td:
            md = os.path.join(td, "t.md")
            with open(md, "w", encoding="utf-8") as f:
                f.write("# A\n\nSome text.\n")
            r = subprocess.run([sys.executable, PREP, md, "--outdir", td, "--min-hit", "0.8"],
                               capture_output=True, text=True)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("--min-hit needs --eval", r.stderr)


class H(BaseHTTPRequestHandler):
    calls = 0

    def do_POST(self):
        H.calls += 1
        self.rfile.read(int(self.headers.get("Content-Length", 0)))
        if H.calls <= 2:
            v = {"keep": False, "type": "legal", "summary": "s", "keywords": []}
            data = json.dumps({"choices": [{"message": {"content": json.dumps(v)}}]}).encode()
            self.send_response(200)
        else:
            data = b"{}"
            self.send_response(500)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *a):
        pass


class TestAbortKeepsCache(unittest.TestCase):
    def test_cache_saved_when_aborting(self):
        srv = HTTPServer(("127.0.0.1", 0), H)
        t = threading.Thread(target=srv.serve_forever, daemon=True); t.start()
        H.calls = 0
        try:
            with tempfile.TemporaryDirectory() as td:
                chunks = [dict(id=f"c{i:04d}", source="x", chunk_index=i, page=[i + 1, i + 1],
                               page_label=None, path=["A"], embed_text="x", sha256=f"h{i}",
                               text=f"All rights reserved {i}. " + "x " * 60) for i in range(6)]
                with open(os.path.join(td, "c.chunks.json"), "w", encoding="utf-8") as f:
                    json.dump(chunks, f)
                env = {k: v for k, v in os.environ.items() if k != "LLM_API_KEY"}
                r = subprocess.run([sys.executable, os.path.join(os.path.dirname(PREP), "filter_llm.py"),
                                    os.path.join(td, "c.chunks.json"), "--endpoint",
                                    "http://127.0.0.1:%d/v1/chat/completions" % srv.server_port,
                                    "--model", "m"], capture_output=True, text=True, env=env)
                self.assertNotEqual(r.returncode, 0)
                self.assertEqual(H.calls, 5)       # 2 good + 3 failures, then stop
                self.assertFalse(os.path.exists(os.path.join(td, "c.chunks.filtered.json")))
                with open(os.path.join(td, "c.llmcache.json"), encoding="utf-8") as f:
                    self.assertEqual(len(json.load(f)), 2)
        finally:
            srv.shutdown(); srv.server_close()


if __name__ == "__main__":
    unittest.main()
