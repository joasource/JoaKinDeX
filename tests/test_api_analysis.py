import json
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

import pytest

from joakindex.db import upsert_documents_batch
from joakindex.server import ConferenciaServer, ReusableThreadingHTTPServer, create_handler


@pytest.fixture
def running_server(tmp_path, monkeypatch):
    monkeypatch.delenv("JOAKINDEX_AUTH_TOKEN", raising=False)
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


def test_get_duplicatas_empty_base(running_server):
    base, _ = running_server
    resp = _get_json(base + "/api/duplicatas")
    assert resp == []


def test_get_duplicatas_comparar_unknown_md5_returns_erro(running_server):
    base, _ = running_server
    url = base + "/api/duplicatas/comparar?" + urllib.parse.urlencode({"base": "aaa", "copia": "bbb"})
    try:
        resp = urllib.request.urlopen(url)
        data = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        data = json.loads(e.read())
    assert "erro" in data


def test_post_duplicatas_resolver_unknown_md5_is_graceful(running_server):
    base, _ = running_server
    resp = _post_json(base + "/api/duplicatas/resolver", {"md5": "naoexiste", "descartar": True})
    assert resp["status"] in ("sucesso", "erro")


def test_get_dossies_empty_base(running_server):
    base, _ = running_server
    resp = _get_json(base + "/api/dossies")
    assert resp == []


def test_post_dossies_gerar_empty_base(running_server):
    base, _ = running_server
    resp = _post_json(base + "/api/dossies/gerar", {})
    assert resp["status"] == "sucesso"
    assert resp["total_dossies"] == 0


def test_post_dossies_exportar_unknown_dossie_is_graceful(running_server):
    base, _ = running_server
    resp = _post_json(base + "/api/dossies/exportar", {"dossie_id": "naoexiste"})
    assert resp["status"] in ("sucesso", "erro")


def test_get_estatisticas_gerenciais_empty_base(running_server):
    base, _ = running_server
    resp = _get_json(base + "/api/estatisticas_gerenciais")
    assert resp["total_docs"] == 0


def test_get_estatisticas_gerenciais_counts_documents(running_server):
    base, ctx = running_server
    upsert_documents_batch(ctx.db_path, [
        {"md5": "doc1", "status": "sucesso", "dominio": "financeiro"},
        {"md5": "doc2", "status": "sucesso", "dominio": "academico"},
    ])
    resp = _get_json(base + "/api/estatisticas_gerenciais")
    assert resp["total_docs"] == 2


def test_get_relatorio_pdf_generates_pdf(running_server):
    base, _ = running_server
    resp = urllib.request.urlopen(base + "/api/relatorio/pdf")
    assert resp.headers.get("Content-Type") == "application/pdf"
    content = resp.read()
    assert content.startswith(b"%PDF")


def test_get_inspecionar_unknown_md5_returns_erro(running_server):
    base, _ = running_server
    resp = _get_json(base + "/api/inspecionar/naoexiste")
    assert "erro" in resp
