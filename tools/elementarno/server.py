"""HTTP API поверх движка ЭЛЕМЕНТАРНО.

Слой сети тонкий: он только раздаёт JSON. Вся работа живёт в чистых
функциях `handle_*`, которые принимают словарь и возвращают словарь, —
их проверяют без сервера и без сети.

Ошибка никогда не роняет сервер и никогда не остаётся в HTML: клиент
получает `{"error": ..., "detail": ...}` и код 4xx/5xx.
"""

import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from . import __version__
from .dialog import Session
from .ledger import score_hypotheses, validate
from .ledger import verdict as decide_verdict
from .nextshot import hypothesis_tags, kind_tags_from_rules, rank_questions
from .perception import MiniMaxPerception, PerceptionError
from .puzzle import build_claims
from .reasoning import MiniMaxReasoner
from .render import render
from .rules import evaluate_all, load_packs

VERSION = __version__
REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RULES_DIR = REPO_ROOT / "rules"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8733
DEFAULT_MODEL = "MiniMax-M3"
PERSONA_NAMES = ("plain", "doyle", "forensic")
MODE_NAMES = ("detective", "audit", "forensic", "solve", "nextshot")


class ApiError(Exception):
    """Ошибка запроса: код ответа, машинный код и понятная деталь."""

    def __init__(self, status, error, detail):
        super().__init__(detail)
        self.status = status
        self.error = error
        self.detail = detail


def _as_dict(payload):
    if payload is None:
        return {}
    if not isinstance(payload, dict):
        raise ApiError(400, "bad_request", "тело запроса должно быть JSON-объектом")
    return payload


def _choice(payload, key, allowed, default):
    value = payload.get(key)
    if value is None:
        return default
    if value not in allowed:
        raise ApiError(400, "bad_request",
                       f"недопустимое значение {key}={value!r}; допустимо: {', '.join(allowed)}")
    return value


def _count(payload, key, default):
    value = payload.get(key, default)
    if isinstance(value, bool) or not isinstance(value, int):
        try:
            value = int(value)
        except (TypeError, ValueError):
            raise ApiError(400, "bad_request", f"{key} должно быть целым числом") from None
    return value


def _rules_for(payload):
    directory = payload.get("rules_dir") or os.environ.get("ELEMENTARNO_RULES") or str(DEFAULT_RULES_DIR)
    try:
        rules = load_packs(directory)
    except (OSError, ValueError) as exc:
        raise ApiError(500, "rules_unavailable",
                       f"не удалось загрузить правила из {directory}: {exc}") from exc
    packs = payload.get("packs") or []
    if isinstance(packs, str):
        packs = [packs]
    if packs:
        wanted = set(packs)
        rules = [rule for rule in rules if rule.pack in wanted]
    return rules


def load_scene(path):
    file = Path(path)
    if not file.exists():
        raise ApiError(404, "scene_not_found", f"файл сцены не найден: {path}")
    try:
        data = json.loads(file.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ApiError(400, "bad_scene", f"сцена не является корректным JSON: {exc}") from exc
    except OSError as exc:
        raise ApiError(400, "bad_scene", f"не удалось прочитать сцену: {exc}") from exc
    if not isinstance(data, dict):
        raise ApiError(400, "bad_scene", "сцена должна быть JSON-объектом")
    return data


def perceive_scene(image_path, model=None, think=False):
    file = Path(image_path)
    if not file.exists():
        raise ApiError(404, "image_not_found", f"файл изображения не найден: {image_path}")
    try:
        perception = MiniMaxPerception(model=model or DEFAULT_MODEL, think=bool(think))
    except PerceptionError as exc:
        raise ApiError(503, "model_unavailable", str(exc)) from exc
    try:
        scene, meta = perception.scene_graph(str(file))
    except PerceptionError as exc:
        raise ApiError(502, "perception_failed", str(exc)) from exc
    except OSError as exc:
        raise ApiError(400, "bad_image", f"не удалось прочитать изображение: {exc}") from exc
    return scene, meta


def _scene_for(payload):
    """Сцена из запроса: готовая сцена-граф или кадр, разобранный моделью."""
    if payload.get("scene_path"):
        return load_scene(payload["scene_path"]), {"source": "scene_path"}
    if payload.get("image_path"):
        scene, meta = perceive_scene(payload["image_path"], payload.get("model"), payload.get("think"))
        return scene, {**meta, "source": "image_path"}
    raise ApiError(400, "bad_request", "не указан image_path или scene_path")


def _usable_claims(claims, report):
    return [claim for claim in claims
            if not any(error.get("claim_id") == claim["claim_id"] for error in report["errors"])]


def handle_health(payload=None):
    return {"ok": True, "version": VERSION}


def handle_perceive(payload):
    payload = _as_dict(payload)
    image_path = payload.get("image_path")
    if not image_path:
        raise ApiError(400, "bad_request", "не указан image_path")
    scene, meta = perceive_scene(image_path, payload.get("model"), payload.get("think"))
    return {**scene, "perception_meta": meta}


def handle_analyze(payload):
    payload = _as_dict(payload)
    scene, meta = _scene_for(payload)
    rules = _rules_for(payload)
    mode = _choice(payload, "mode", MODE_NAMES, "detective")
    persona = _choice(payload, "persona", PERSONA_NAMES, "doyle")
    min_findings = _count(payload, "min_findings", 1)

    findings = evaluate_all(rules, scene)
    claims = build_claims(findings)
    report = validate(findings, {"claims": claims, "hypotheses": []})
    usable = _usable_claims(claims, report)
    hypotheses = score_hypotheses(findings, usable, [])
    state = decide_verdict(findings, usable, min_findings, mode)
    text = render(mode, findings, usable, hypotheses, state, persona, report)
    return {
        "findings": findings,
        "claims": usable,
        "hypotheses": hypotheses,
        "report": report,
        "text": text,
        "verdict": state,
        "meta": meta,
    }


def handle_reason(payload):
    payload = _as_dict(payload)
    scene_path = payload.get("scene_path")
    if not scene_path:
        raise ApiError(400, "bad_request", "не указан scene_path")
    scene = load_scene(scene_path)
    rules = _rules_for(payload)
    mode = _choice(payload, "mode", MODE_NAMES, "detective")
    persona = _choice(payload, "persona", PERSONA_NAMES, "doyle")
    min_findings = _count(payload, "min_findings", 1)

    findings = evaluate_all(rules, scene)
    try:
        reasoner = MiniMaxReasoner(model=payload.get("model") or DEFAULT_MODEL,
                                    think=not payload.get("no_think"))
    except PerceptionError as exc:
        raise ApiError(503, "model_unavailable", str(exc)) from exc
    try:
        ledger, meta = reasoner.reason(scene, findings, extra_instruction=payload.get("instruction"))
    except (RuntimeError, OSError) as exc:
        raise ApiError(502, "reasoning_failed", str(exc)) from exc
    report = validate(findings, ledger)
    usable = _usable_claims(ledger.get("claims", []), report)
    hypotheses = score_hypotheses(findings, usable, ledger.get("hypotheses", []))
    state = decide_verdict(findings, usable, min_findings, mode)
    text = render(mode, findings, usable, hypotheses, state, persona, report)
    return {
        "claims": usable,
        "hypotheses": hypotheses,
        "report": report,
        "text": text,
        "meta": meta,
    }


def handle_nextshot(payload):
    payload = _as_dict(payload)
    scene_path = payload.get("scene_path")
    if not scene_path:
        raise ApiError(400, "bad_request", "не указан scene_path")
    scene = load_scene(scene_path)
    rules = _rules_for(payload)
    limit = _count(payload, "limit", 3)

    findings = evaluate_all(rules, scene)
    claims = build_claims(findings)
    hypotheses = score_hypotheses(findings, claims, [])
    found_kinds = {region.get("kind") for region in scene.get("regions", []) if isinstance(region, dict)}
    questions = rank_questions(
        hypotheses,
        hypothesis_tags(hypotheses, findings),
        kind_tags_from_rules(rules),
        found_kinds,
        limit=limit,
    )
    return {
        "questions": questions,
        "count": len(questions),
        "hypotheses": len(hypotheses),
        "found_kinds": sorted(k for k in found_kinds if k),
    }


def handle_session(payload):
    payload = _as_dict(payload)
    rules = _rules_for(payload)
    state_path = payload.get("state_path")

    if state_path and Path(state_path).exists():
        try:
            session = Session.load(state_path, rules)
        except (OSError, json.JSONDecodeError) as exc:
            raise ApiError(400, "bad_state",
                           f"не удалось прочитать состояние сессии: {exc}") from exc
    else:
        session = Session(rules, [])

    meta = {"source": None}
    if payload.get("image_path"):
        scene, perception_meta = perceive_scene(payload["image_path"],
                                                 payload.get("model"), payload.get("think"))
        session.add_scene(scene, source=payload["image_path"])
        meta = {**perception_meta, "source": "image_path"}
    elif payload.get("scene_path"):
        scene = load_scene(payload["scene_path"])
        session.add_scene(scene, source=payload["scene_path"])
        meta = {"source": "scene_path"}

    result = session.analyze()
    if state_path:
        try:
            target = Path(state_path)
            if target.parent and not target.parent.exists():
                target.parent.mkdir(parents=True, exist_ok=True)
            session.save(state_path)
        except OSError as exc:
            raise ApiError(500, "state_not_saved",
                       f"не удалось сохранить состояние сессии: {exc}") from exc

    return {
        "state": session.to_dict(),
        "rounds": len(session.rounds),
        "findings": result["findings"],
        "claims": result["claims"],
        "hypotheses": result["hypotheses"],
        "participants": result.get("participants", []),
        "questions": result["questions"],
        "verdict": result["verdict"],
        "meta": meta,
    }


GET_ROUTES = {
    "/health": handle_health,
}

POST_ROUTES = {
    "/perceive": handle_perceive,
    "/analyze": handle_analyze,
    "/reason": handle_reason,
    "/nextshot": handle_nextshot,
    "/session": handle_session,
}


class ElementarnoHandler(BaseHTTPRequestHandler):
    server_version = "ElementarnoAPI/1.0"
    protocol_version = "HTTP/1.1"

    def do_GET(self):
        path = _path_of(self.path)
        handler = GET_ROUTES.get(path)
        if handler is None:
            self._reject_path(path)
            return
        self._dispatch(handler, {})

    def do_POST(self):
        path = _path_of(self.path)
        handler = POST_ROUTES.get(path)
        if handler is None:
            self._reject_path(path)
            return
        try:
            payload = self._read_payload()
        except ApiError as exc:
            self._fail(exc.status, exc.error, exc.detail)
            return
        self._dispatch(handler, payload)

    def do_HEAD(self):
        self._fail(405, "method_not_allowed", "метод HEAD не поддерживается", body=False)

    def do_PUT(self):
        self._fail(405, "method_not_allowed", "метод PUT не поддерживается")

    def do_PATCH(self):
        self._fail(405, "method_not_allowed", "метод PATCH не поддерживается")

    def do_DELETE(self):
        self._fail(405, "method_not_allowed", "метод DELETE не поддерживается")

    def _reject_path(self, path):
        if path in POST_ROUTES:
            self._fail(405, "method_not_allowed", f"для {path} нужен метод POST")
        elif path in GET_ROUTES:
            self._fail(405, "method_not_allowed", f"для {path} нужен метод GET")
        else:
            self._fail(404, "not_found", f"неизвестный путь: {path}")

    def _dispatch(self, handler, payload):
        try:
            body = handler(payload)
        except ApiError as exc:
            self._fail(exc.status, exc.error, exc.detail)
            return
        except Exception as exc:
            self._fail(500, "internal_error", f"{type(exc).__name__}: {exc}")
            return
        self._send(200, body)

    def _read_payload(self):
        header = self.headers.get("Content-Length")
        try:
            size = int(header) if header else 0
        except ValueError:
            raise ApiError(400, "bad_request", "некорректный Content-Length") from None
        if size <= 0:
            return {}
        raw = self.rfile.read(size)
        try:
            data = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ApiError(400, "bad_request", f"тело запроса не является JSON: {exc}") from exc
        if not isinstance(data, dict):
            raise ApiError(400, "bad_request", "тело запроса должно быть JSON-объектом")
        return data

    def _send(self, status, body, send_body=True):
        payload = json.dumps(body, ensure_ascii=False, default=str).encode("utf-8")
        try:
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            if send_body:
                self.wfile.write(payload)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def _fail(self, status, error, detail, body=True):
        self._send(status, {"error": error, "detail": detail}, send_body=body)

    def log_message(self, fmt, *args):
        if os.environ.get("ELEMENTARNO_API_QUIET") == "1":
            return
        sys.stderr.write(f"[elementarno-api] {self.address_string()} {fmt % args}\n")


def _path_of(raw):
    path = urlparse(raw).path or "/"
    if len(path) > 1:
        path = path.rstrip("/") or "/"
    return path


def create_server(host=None, port=None):
    if host is None:
        host = os.environ.get("ELEMENTARNO_HOST", DEFAULT_HOST)
    if port is None:
        port = int(os.environ.get("ELEMENTARNO_PORT", DEFAULT_PORT))
    httpd = ThreadingHTTPServer((host, int(port)), ElementarnoHandler)
    httpd.daemon_threads = True
    return httpd


def main(argv=None):
    import argparse

    parser = argparse.ArgumentParser(prog="elementarno-server",
                                     description="HTTP API движка ЭЛЕМЕНТАРНО")
    parser.add_argument("--host", default=os.environ.get("ELEMENTARNO_HOST", DEFAULT_HOST))
    parser.add_argument("--port", type=int, default=int(os.environ.get("ELEMENTARNO_PORT", DEFAULT_PORT)))
    args = parser.parse_args(argv)

    httpd = create_server(args.host, args.port)
    host, port = httpd.server_address[:2]
    print(f"ЭЛЕМЕНТАРНО API слушает http://{host}:{port}", flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
