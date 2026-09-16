import json
import threading
import time
import urllib.request

import pytest

from joakindex.config import get_visualizer_config
from joakindex.server import ConferenciaServer, ReusableThreadingHTTPServer, create_handler


@pytest.fixture
def running_server(tmp_path, monkeypatch):
    # Garante que um JOAKINDEX_AUTH_TOKEN do .env local do desenvolvedor não vaze para o teste,
    # e isola o arquivo de configuração persistente dentro do tmp_path do teste.
    monkeypatch.delenv("JOAKINDEX_AUTH_TOKEN", raising=False)
    monkeypatch.chdir(tmp_path)

    pdf_dir = tmp_path / "pdf"
    pdf_dir.mkdir()
    json_path = tmp_path / "saida" / "joakindex.json"
    json_path.parent.mkdir()
    json_path.write_text("[]", encoding="utf-8")
    html_path = tmp_path / "visualizador.html"
    html_path.write_text("<html>ok</html>", encoding="utf-8")

    ctx = ConferenciaServer(json_path=str(json_path), pdf_dir=str(pdf_dir), html_path=str(html_path))
    handler = create_handler(ctx)
    httpd = ReusableThreadingHTTPServer(("127.0.0.1", 0), handler)
    port = httpd.server_address[1]
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    time.sleep(0.2)
    try:
        yield f"http://127.0.0.1:{port}", ctx
    finally:
        httpd.shutdown()


def _get_json(url):
    return json.loads(urllib.request.urlopen(url).read())


def _post_json(url, payload):
    data = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    return json.loads(urllib.request.urlopen(req).read())


def test_get_config_returns_classificador_and_visualizador(running_server):
    base, ctx = running_server
    resp = _get_json(base + "/api/config")
    assert "classificador" in resp
    assert "visualizador" in resp
    assert resp["visualizador"]["provider"] == ctx.provider
    assert resp["current_pdf_dir"] == str(ctx.pdf_dir)
    # A chave só é removida do payload quando tem valor; sem valor, permanece como None/ausente.
    assert not resp["classificador"].get("openai_key")
    assert not resp["visualizador"].get("openai_key")


def test_get_environments_returns_list(running_server):
    base, _ = running_server
    resp = json.loads(urllib.request.urlopen(base + "/api/environments").read())
    assert isinstance(resp, list)


def test_post_config_updates_provider_and_model(running_server):
    base, ctx = running_server
    resp = _post_json(base + "/api/config", {
        "visualizador": {"provider": "openai", "model": "gpt-4o-mini"}
    })
    assert resp["status"] == "sucesso"
    assert resp["provider"] == "openai"
    assert resp["model"] == "gpt-4o-mini"
    assert ctx.provider == "openai"
    assert ctx.model == "gpt-4o-mini"

    saved = get_visualizer_config()
    assert saved["provider"] == "openai"
    assert saved["model"] == "gpt-4o-mini"


def test_post_config_masks_openai_key_placeholder(running_server):
    base, _ = running_server
    resp = _post_json(base + "/api/config", {
        "visualizador": {"openai_key": "sk-real-secret-key-123"}
    })
    assert resp["status"] == "sucesso"

    cfg = _get_json(base + "/api/config")
    assert cfg["visualizador"]["has_openai_key"] is True
    assert "sk-real-secret-key-123" not in json.dumps(cfg)


def test_post_config_reset_restores_defaults(running_server):
    base, ctx = running_server
    _post_json(base + "/api/config", {"visualizador": {"provider": "openai", "model": "gpt-4o-mini"}})
    assert ctx.provider == "openai"

    resp = _post_json(base + "/api/config/reset", {})
    assert resp["status"] == "sucesso"
    assert ctx.provider == "ollama"
    assert str(ctx.pdf_dir).endswith("pdf")
