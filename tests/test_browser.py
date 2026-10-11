"""Headless Chromium tests of the R2 UI inside a sandboxed (null-origin) iframe.

The Qollab bridge is MOCKED (dev/mock) with fixtures produced by the real Python
API. This proves UI logic, not real Qollab compatibility.
"""
import functools
import hashlib
import http.server
import json
import os
import subprocess
import sys
import threading
from pathlib import Path

import pytest

pw = pytest.importorskip("playwright.sync_api")
ROOT = Path(__file__).resolve().parent.parent
FIX = ROOT / "dev/fixtures"
SHOTS = ROOT / "results/r2_screens"
CHROMIUM = os.environ.get("CHROMIUM", "/usr/bin/chromium")


class CORSHandler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def log_message(self, *a):
        pass


def serve(directory):
    h = functools.partial(CORSHandler, directory=str(directory))
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), h)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_address[1]}/"


@pytest.fixture(scope="module")
def server():
    if not Path(CHROMIUM).exists():
        pytest.skip("system chromium not available")
    srv, url = serve(ROOT)
    yield url
    srv.shutdown()


@pytest.fixture(scope="module")
def browser():
    with pw.sync_playwright() as p:
        b = p.chromium.launch(executable_path=CHROMIUM, args=["--no-sandbox", "--disable-site-isolation-trials"])
        yield b
        b.close()


def open_app(browser, server, mock, *, backend=True, width=1280, height=900, root=ROOT):
    frag = (Path(root) / "index.html").read_text()
    pre = f"globalThis.__QRG_MOCK__ = {json.dumps(mock)};"
    if backend:
        pre += "globalThis.backend = {name: 'mock-injected-backend'};"
    srcdoc = (f'<!doctype html><meta charset="utf-8"><base href="{server}">'
              '<meta name="viewport" content="width=device-width,initial-scale=1">'
              '<link rel="stylesheet" href="main.css">'
              '<script type="importmap">{"imports":{"qrg.js_api":"./dev/mock/qrg_js_api.js"}}</script>'
              f"<script>{pre}</script>{frag}"
              '<script type="module" src="main.js"></script>')
    parent = ('<!doctype html><style>html,body{margin:0;height:100%}iframe{border:0;width:100%;height:100vh}</style>'
              '<iframe id="app" sandbox="allow-scripts"></iframe>')
    page = browser.new_page(viewport={"width": width, "height": height})
    errors = []
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.set_content(parent)
    page.eval_on_selector("#app", "(f, s) => { f.srcdoc = s; }", srcdoc)
    page.wait_for_timeout(100)
    frame = page.frames[1]
    frame.wait_for_selector("#qrg-status.done, #qrg-status.error", timeout=20000)
    return page, frame, errors


def calls(frame):
    return frame.evaluate("globalThis.__QRG_MOCK_CALLS__.length")


def fixture_env(name):
    return json.loads((FIX / name).read_text())


@pytest.mark.parametrize("fx,verdict", [("envelope_A.json", "ACCEPT"), ("envelope_B.json", "ACCEPT")])
def test_live_run_renders_all_scenes(browser, server, fx, verdict):
    page, f, errors = open_app(browser, server, {"mode": "fixture", "fixture": fx})
    assert "1 backend job" in f.inner_text("#qrg-status-text")
    assert verdict in f.inner_text("#qrg-hero-verdict")
    for sc in "abcdef":
        assert "Waiting for the Run" not in f.inner_text(f"#{sc}-body", timeout=2000) or sc == "a"
    assert f.locator("#c-body .badge.live").count() == 1
    env = fixture_env(fx)
    raw = json.loads(env["evidence_text"])["raw_record"]["counts"]
    assert f.locator("#c-body .bar-row").count() == len(raw)
    assert f.locator("#e-body .demo").count() == len(env["demonstrations"])
    assert "None of them was executed on the backend" in f.inner_text("#e-body")
    assert f.locator("#e-body .badge.live").count() == 1  # only the live verdict is LIVE
    assert calls(f) == 1 and f.evaluate("globalThis.__QRG_MOCK_CALLS__[0].backendPassed")
    assert not errors, errors
    page.close()


def test_no_reexecution_after_any_interaction(browser, server):
    page, f, _ = open_app(browser, server, {"mode": "fixture", "fixture": "envelope_B.json"})
    for _ in range(2):
        for sc in "abcdef":
            f.click(f"#tab-{sc}")
            for btn in f.locator(f"#scene-{sc} button").all():
                if btn.is_enabled():
                    btn.click()
        for _ in range(7):
            if f.is_enabled("#qrg-next"):
                f.click("#qrg-next")
        for _ in range(7):
            if f.is_enabled("#qrg-prev"):
                f.click("#qrg-prev")
    f.click("#tab-a")
    for v in f.eval_on_selector_all("#cf-select option", "os => os.map(o => o.value)"):
        f.select_option("#cf-select", v)
    f.focus("#tab-a")
    for _ in range(6):
        f.press("#tab-a, [role=tab][aria-selected=true]", "ArrowRight")
    assert calls(f) == 1
    page.close()


def test_counterfactual_preview_is_labelled_local(browser, server):
    page, f, _ = open_app(browser, server, {"mode": "fixture", "fixture": "envelope_A.json"})
    f.select_option("#cf-select", "reject-ionq-backend")
    out = f.inner_text("#cf-out")
    assert "REJECT" in out and "no quantum job" in out.lower() and "never authorizes" in out
    page.close()


def test_export_is_verbatim_and_verifies_offline(browser, server, tmp_path):
    page, f, _ = open_app(browser, server, {"mode": "fixture", "fixture": "envelope_B.json"})
    env = fixture_env("envelope_B.json")
    f.click("#tab-d")
    text = f.eval_on_selector("#evidence-text", "t => t.value")
    assert text == env["evidence_text"]
    assert hashlib.sha256(text.encode()).hexdigest() == env["evidence_sha256"]
    assert f.locator("#d-body .checks li.bad").count() == 0
    p = tmp_path / "evidence.json"
    p.write_text(text)
    r = subprocess.run([sys.executable, "-I", "verifier/verify_qrg.py", str(p)], cwd=ROOT, capture_output=True, text=True)
    assert r.returncode == 0 and json.loads(r.stdout)["status"] == "VERIFIED"
    page.close()


def test_copy_fallback_in_sandboxed_iframe(browser, server):
    page, f, _ = open_app(browser, server, {"mode": "fixture", "fixture": "envelope_A.json"})
    f.click("#tab-d")
    f.click("#copy-btn")
    f.wait_for_function("document.getElementById('copy-msg').textContent.length > 0")
    msg = f.inner_text("#copy-msg")
    assert msg in ("Copied to clipboard.", "Copied (fallback).",
                   "Clipboard blocked here — the text is selected: press Ctrl+C / ⌘C.")
    sel = f.evaluate("(() => { const t = document.getElementById('evidence-text'); return [t.selectionStart, t.selectionEnd, t.value.length]; })()")
    if msg != "Copied to clipboard.":
        assert sel[0] == 0 and sel[1] == sel[2]
    f.click("#select-btn")
    sel = f.evaluate("(() => { const t = document.getElementById('evidence-text'); return [t.selectionStart, t.selectionEnd, t.value.length]; })()")
    assert sel[0] == 0 and sel[1] == sel[2]
    assert calls(f) == 1
    page.close()


@pytest.mark.parametrize("mock,backend,code", [
    ({"mode": "fixture", "fixture": "envelope_no_backend.json"}, False, "ERROR_NO_INJECTED_BACKEND"),
    ({"mode": "fixture", "fixture": "envelope_preflight_reject.json"}, True, "PREFLIGHT_REJECT"),
    ({"mode": "fixture", "fixture": "envelope_job_failed.json"}, True, "JOB_FAILED"),
    ({"mode": "fixture", "fixture": "envelope_internal_error.json"}, True, "INTERNAL_ERROR"),
    ({"mode": "reject"}, True, "BRIDGE_ERROR"),
    ({"mode": "malformed"}, True, "BRIDGE_PAYLOAD_INVALID"),
    ({"mode": "null"}, True, "BRIDGE_PAYLOAD_INVALID"),
    ({"mode": "object"}, True, "BRIDGE_PAYLOAD_INVALID"),
])
def test_error_states_show_no_live_data(browser, server, mock, backend, code):
    page, f, _ = open_app(browser, server, mock, backend=backend)
    assert code in f.inner_text("#qrg-status-text")
    assert f.locator("#c-body .badge.live").count() == 0
    assert f.locator("#qrg-hero-verdict").is_hidden()
    assert "nothing is substituted" in f.inner_text("#c-body")
    assert calls(f) == 1
    if not backend:
        assert f.evaluate("globalThis.__QRG_MOCK_CALLS__[0].backendPassed") is False
    page.close()


@pytest.mark.parametrize("width", [320, 375, 768])
@pytest.mark.parametrize("fx", ["envelope_A.json", "envelope_B.json"])
def test_responsive_no_horizontal_overflow(browser, server, fx, width):
    page, f, _ = open_app(browser, server, {"mode": "fixture", "fixture": fx}, width=width, height=820)
    SHOTS.mkdir(parents=True, exist_ok=True)
    for sc in "abcdef":
        f.click(f"#tab-{sc}")
        over = f.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
        assert over <= 0, f"scene {sc} overflows by {over}px at {width}px"
        if width in (375,) or (width == 768 and sc in "ce"):
            page.screenshot(path=str(SHOTS / f"{fx[9]}_{width}_{sc}.png"))
    page.close()


def test_desktop_screenshots(browser, server):
    SHOTS.mkdir(parents=True, exist_ok=True)
    for fx in ("envelope_A.json", "envelope_B.json"):
        page, f, _ = open_app(browser, server, {"mode": "fixture", "fixture": fx}, width=1280, height=1000)
        for sc in "abcdef":
            f.click(f"#tab-{sc}")
            page.screenshot(path=str(SHOTS / f"{fx[9]}_1280_{sc}.png"))
        page.close()
