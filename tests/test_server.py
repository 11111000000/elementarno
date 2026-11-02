import json
import os
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from elementarno import server as srv  # noqa: E402

SCENE = ROOT / "eval" / "benchmarks" / "protocol-core" / "scenes" / "absence-dust-outline.json"


class ServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.previous_quiet = os.environ.get("ELEMENTARNO_API_QUIET")
        os.environ["ELEMENTARNO_API_QUIET"] = "1"
        cls.httpd = srv.create_server(host="127.0.0.1", port=0)
        cls.port = cls.httpd.server_address[1]
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()
        cls.thread.join(timeout=5)
        if cls.previous_quiet is None:
            os.environ.pop("ELEMENTARNO_API_QUIET", None)
        else:
            os.environ["ELEMENTARNO_API_QUIET"] = cls.previous_quiet

    def url(self, path):
        return f"http://127.0.0.1:{self.port}{path}"

    def get(self, path):
        with urllib.request.urlopen(self.url(path), timeout=10) as response:
            return response.status, json.loads(response.read().decode("utf-8"))

    def post(self, path, payload, raw=None):
        body = raw if raw is not None else json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(self.url(path), data=body,
                                         headers={"Content-Type": "application/json"},
                                         method="POST")
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                return response.status, json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            return exc.code, json.loads(exc.read().decode("utf-8"))

    def test_health_endpoint(self):
        status, body = self.get("/health")
        self.assertEqual(status, 200)
        self.assertTrue(body["ok"])
        self.assertTrue(body["version"])

    def test_health_handler_is_pure(self):
        body = srv.handle_health()
        self.assertEqual(body["ok"], True)
        self.assertIn("version", body)

    def test_unknown_path_returns_404_json(self):
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(self.url("/nope"), timeout=10)
        self.assertEqual(ctx.exception.code, 404)
        with ctx.exception:
            body = json.loads(ctx.exception.read().decode("utf-8"))
        self.assertEqual(body["error"], "not_found")
        self.assertTrue(body["detail"])

    def test_server_survives_unknown_path(self):
        with self.assertRaises(urllib.error.HTTPError):
            urllib.request.urlopen(self.url("/nope"), timeout=10)
        status, body = self.get("/health")
        self.assertEqual(status, 200)
        self.assertTrue(body["ok"])

    def test_method_not_allowed_returns_json(self):
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(self.url("/analyze"), timeout=10)
        self.assertEqual(ctx.exception.code, 405)
        with ctx.exception:
            body = json.loads(ctx.exception.read().decode("utf-8"))
        self.assertEqual(body["error"], "method_not_allowed")

    def test_bad_json_body_returns_400(self):
        status, body = self.post("/analyze", None, raw=b"{not json")
        self.assertEqual(status, 400)
        self.assertEqual(body["error"], "bad_request")
        self.assertTrue(body["detail"])

    def test_missing_field_returns_400(self):
        status, body = self.post("/analyze", {})
        self.assertEqual(status, 400)
        self.assertEqual(body["error"], "bad_request")

    def test_unknown_scene_returns_404(self):
        status, body = self.post("/analyze", {"scene_path": str(ROOT / "нет-такого.json")})
        self.assertEqual(status, 404)
        self.assertEqual(body["error"], "scene_not_found")

    def test_analyze_handler_on_ready_scene(self):
        result = srv.handle_analyze({"scene_path": str(SCENE)})
        self.assertEqual([f["finding_id"] for f in result["findings"]], ["F-ABS-001"])
        self.assertTrue(result["claims"])
        self.assertEqual(result["report"]["errors"], [])
        self.assertEqual(result["verdict"], "sufficient_evidence")
        self.assertTrue(result["text"])
        self.assertIn("ABS-001", result["text"])

    def test_analyze_over_http_without_model(self):
        status, body = self.post("/analyze", {"scene_path": str(SCENE), "persona": "plain"})
        self.assertEqual(status, 200)
        self.assertEqual([f["rule_id"] for f in body["findings"]], ["ABS-001"])
        self.assertEqual(body["claims"][0]["claim_id"], "C-ABS-001")
        self.assertEqual(body["report"]["errors"], [])
        self.assertTrue(body["text"])

    def test_analyze_rejects_unknown_persona(self):
        status, body = self.post("/analyze", {"scene_path": str(SCENE), "persona": "watson"})
        self.assertEqual(status, 400)
        self.assertEqual(body["error"], "bad_request")

    def test_nextshot_over_http(self):
        status, body = self.post("/nextshot", {"scene_path": str(SCENE)})
        self.assertEqual(status, 200)
        self.assertTrue(body["questions"])
        for question in body["questions"]:
            self.assertTrue(question["question"])
            self.assertTrue(question["why"])
            self.assertIn("eig", question)

    def test_session_over_http_accumulates_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = Path(tmp) / "session.json"
            status, body = self.post("/session", {"state_path": str(state), "scene_path": str(SCENE)})
            self.assertEqual(status, 200)
            self.assertEqual(body["rounds"], 1)
            self.assertEqual(body["verdict"], "sufficient_evidence")
            self.assertTrue(body["findings"])
            self.assertTrue(body["questions"])
            self.assertTrue(state.exists())

            status, again = self.post("/session", {"state_path": str(state), "scene_path": str(SCENE)})
            self.assertEqual(status, 200)
            self.assertEqual(again["rounds"], 2)

    def test_port_comes_from_environment(self):
        import socket

        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            free_port = probe.getsockname()[1]

        previous = os.environ.get("ELEMENTARNO_PORT")
        os.environ["ELEMENTARNO_PORT"] = str(free_port)
        try:
            httpd = srv.create_server()
            self.assertEqual(httpd.server_address[1], free_port)
            httpd.server_close()
        finally:
            if previous is None:
                os.environ.pop("ELEMENTARNO_PORT", None)
            else:
                os.environ["ELEMENTARNO_PORT"] = previous


if __name__ == "__main__":
    unittest.main()
