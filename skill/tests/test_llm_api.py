"""Step 2: filter_llm.py must send the API key (flag or LLM_API_KEY env),
never print/store it, not cache transient 401s, and rerun from cache with
zero server calls."""
import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import threading
import unittest
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
FILTER = os.path.join(HERE, "..", "scripts", "filter_llm.py")

CHUNK = {
    "id": "c0001", "source": "x.md", "chunk_index": 0, "page": [3, 3],
    "page_label": None, "path": ["A"], "text": "All rights reserved. " + "x " * 60,
    "embed_text": "x", "sha256": "deadbeef",
}


class Handler(BaseHTTPRequestHandler):
    mode = "ok"          # "ok" | "401" | "drop"
    verdict = {"keep": True, "type": "content", "summary": "s", "keywords": ["k"]}
    calls = 0
    auth = None

    def do_POST(self):
        Handler.calls += 1
        Handler.auth = self.headers.get("Authorization")
        length = int(self.headers.get("Content-Length", 0))
        self.rfile.read(length)
        if Handler.mode in ("401", "500"):
            self.send_response(int(Handler.mode))
            self.send_header("Content-Length", "2")
            self.end_headers()
            self.wfile.write(b"{}")
            return
        v = Handler.verdict
        if Handler.mode == "drop":
            v = {"keep": False, "type": "legal", "summary": "legal",
                 "keywords": ["rights"]}
        if Handler.mode == "contradict":     # keep=false but type=content -> must be KEPT
            v = {"keep": False, "type": "content", "summary": "s", "keywords": []}
        body = json.dumps({"choices": [{"message": {"content": json.dumps(v)}}]})
        data = body.encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *a):
        pass


def run_filter(td, extra, env_extra=None):
    env = {k: v for k, v in os.environ.items() if k != "LLM_API_KEY"}
    if env_extra:
        env.update(env_extra)
    return subprocess.run(
        [sys.executable, FILTER, os.path.join(td, "c.chunks.json"),
         "--endpoint", "http://127.0.0.1:%d/v1/chat/completions" % PORT,
         "--model", "m", *extra],
        capture_output=True, text=True, env=env)


class TestApiKey(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        global PORT
        cls.server = HTTPServer(("127.0.0.1", 0), Handler)
        PORT = cls.server.server_address[1]
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def fresh_td(self, n=1):
        td = tempfile.mkdtemp()
        chunks = [dict(CHUNK, id=f"c{i + 1:04d}", sha256="deadbeef" + (str(i) if i else ""),
                       text=f"All rights reserved {i}. " + "x " * 60) for i in range(n)]
        with open(os.path.join(td, "c.chunks.json"), "w") as f:
            json.dump(chunks, f)
        return td

    def state(self, td):
        drop = os.path.join(td, "c.dropped.jsonl")
        cache = os.path.join(td, "c.llmcache.json")
        filt = os.path.join(td, "c.chunks.filtered.json")
        dropped = ""
        if os.path.exists(drop):
            with open(drop) as f:
                dropped = f.read()
        if os.path.exists(cache):
            with open(cache) as f:
                cache = json.load(f)
        else:
            cache = {}
        kept = None
        if os.path.exists(filt):
            with open(filt) as f:
                kept = len(json.load(f))
        return dropped, cache, kept

    def test_flag_key_sent(self):
        Handler.calls, Handler.auth, Handler.mode = 0, None, "ok"
        td = self.fresh_td()
        r = run_filter(td, ["--api-key", "k1"])
        self.assertEqual(Handler.auth, "Bearer k1")
        self.assertNotIn("k1", r.stdout + r.stderr, "key must not be printed")

    def test_env_key_used(self):
        Handler.calls, Handler.auth, Handler.mode = 0, None, "ok"
        td = self.fresh_td()
        r = run_filter(td, [], env_extra={"LLM_API_KEY": "k2"})
        self.assertEqual(Handler.auth, "Bearer k2")

    def test_no_key_no_header(self):
        Handler.calls, Handler.auth, Handler.mode = 0, "sentinel", "ok"
        td = self.fresh_td()
        run_filter(td, [])
        self.assertIsNone(Handler.auth)

    def test_401_aborts_no_output(self):
        Handler.calls, Handler.auth, Handler.mode = 0, None, "401"
        td = self.fresh_td(5)
        r = run_filter(td, ["--api-key", "k1"])
        dropped, cache, kept = self.state(td)
        self.assertNotEqual(r.returncode, 0)
        self.assertEqual(Handler.calls, 1, "must stop at the first 401")
        self.assertIsNone(kept, "no filtered file may be written after an auth error")
        self.assertEqual(cache, {})
        self.assertIn("AUTH ERROR", r.stdout + r.stderr)

    def test_three_failures_in_a_row_abort(self):
        Handler.calls, Handler.auth, Handler.mode = 0, None, "500"
        td = self.fresh_td(6)
        r = run_filter(td, [])
        _, cache, kept = self.state(td)
        self.assertNotEqual(r.returncode, 0)
        self.assertEqual(Handler.calls, 3)
        self.assertIsNone(kept)
        self.assertEqual(cache, {})

    def test_content_type_never_dropped(self):
        Handler.calls, Handler.auth, Handler.mode = 0, None, "contradict"
        td = self.fresh_td()
        run_filter(td, [])
        dropped, _, kept = self.state(td)
        self.assertEqual(kept, 1)
        self.assertEqual(dropped.strip(), "")

    def test_cache_depends_on_model(self):
        Handler.calls, Handler.auth, Handler.mode = 0, None, "drop"
        td = self.fresh_td()
        run_filter(td, [])
        self.assertEqual(Handler.calls, 1)
        env = {k: v for k, v in os.environ.items() if k != "LLM_API_KEY"}
        subprocess.run([sys.executable, FILTER, os.path.join(td, "c.chunks.json"),
                        "--endpoint", "http://127.0.0.1:%d/v1/chat/completions" % PORT,
                        "--model", "OTHER"], capture_output=True, text=True, env=env)
        self.assertEqual(Handler.calls, 2, "a different model must not reuse the cache")

    def test_index_like_chunk_is_suspect(self):
        td = tempfile.mkdtemp()
        idx = "Black-Scholes, 12, 45-47, 88; delta hedging, 101, 102, 130; skew, 7, 9, 15; " * 4
        prose = ("This is ordinary running prose about option pricing and it goes on for "
                 "quite a long time without any page numbers at all in it. ") * 3
        chunks = [dict(CHUNK, id="c1", sha256="s1", text=idx),
                  dict(CHUNK, id="c2", sha256="s2", text=prose)]
        with open(os.path.join(td, "c.chunks.json"), "w") as f:
            json.dump(chunks, f)
        r = subprocess.run([sys.executable, FILTER, os.path.join(td, "c.chunks.json"),
                            "--dry-run"], capture_output=True, text=True)
        self.assertIn("c1", r.stdout)
        self.assertIn("index-like", r.stdout)
        self.assertNotIn("c2 (", r.stdout)

    def test_drop_verdict_cached(self):
        Handler.calls, Handler.auth, Handler.mode = 0, None, "drop"
        td = self.fresh_td()
        run_filter(td, ["--api-key", "k1"])
        dropped, cache, kept = self.state(td)
        self.assertEqual(kept, 0)
        self.assertIn("c0001", dropped)
        self.assertEqual(len(cache), 1)
        self.assertNotIn(CHUNK["sha256"], cache, "cache key must include model + prompt")
        self.assertNotIn("k1", json.dumps(cache))

    def test_rerun_zero_calls(self):
        Handler.calls, Handler.auth, Handler.mode = 0, None, "drop"
        td = self.fresh_td()
        run_filter(td, ["--api-key", "k1"])
        self.assertEqual(Handler.calls, 1)
        Handler.calls = 0
        Handler.mode = "401"            # server would fail — must not be reached
        run_filter(td, ["--api-key", "k1"])
        self.assertEqual(Handler.calls, 0, "rerun must be served from cache")
        _, _, kept = self.state(td)
        self.assertEqual(kept, 0)       # verdict still applied


if __name__ == "__main__":
    unittest.main()
