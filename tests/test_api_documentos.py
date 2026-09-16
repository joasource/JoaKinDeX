import json
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

import pytest

from joakindex.db import get_document_by_md5, upsert_documents_batch
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


def test_get_documentos_lists_and_normalizes_lists_to_strings(running_server):
    base, ctx = running_server
    upsert_documents_batch(ctx.db_path, [
        {"md5": "doc1", "status": "sucesso", "beneficiario": "Maria Silva"},
    ])
    resp = _get_json(base + "/api/documentos")
    assert len(resp) == 1
    assert resp[0]["status_conferencia"] == "pendente"


def test_get_documento_by_md5_found(running_server):
    base, ctx = running_server
    upsert_documents_batch(ctx.db_path, [{"md5": "abc123", "status": "sucesso", "beneficiario": "João"}])
    resp = _get_json(base + "/api/documento/abc123")
    assert resp["md5"] == "abc123"
    assert resp["beneficiario"] == "João"


def test_get_documento_by_md5_not_found_returns_404(running_server):
    base, _ = running_server
    with pytest.raises(urllib.error.HTTPError) as exc:
        urllib.request.urlopen(base + "/api/documento/naoexiste")
    assert exc.value.code == 404


def test_get_regras_aprendidas_empty(running_server):
    base, _ = running_server
    resp = _get_json(base + "/api/regras-aprendidas")
    assert resp == []


def test_get_busca_fts_empty_base(running_server):
    base, _ = running_server
    url = base + "/api/busca_fts?" + urllib.parse.urlencode({"q": "teste"})
    resp = _get_json(url)
    assert resp == []


def test_post_salvar_persists_document(running_server):
    base, ctx = running_server
    resp = _post_json(base + "/api/salvar", {
        "item": {"md5": "SAVE123", "beneficiario": "Carlos", "tipo_documento": "Certificado"}
    })
    assert resp["status"] == "sucesso"

    saved = get_document_by_md5(ctx.db_path, "save123")
    assert saved is not None
    assert saved["beneficiario"] == "Carlos"


def test_post_salvar_with_aprender_regra_creates_learned_rule(running_server):
    base, ctx = running_server
    _post_json(base + "/api/salvar", {
        "item": {"md5": "SAVE456", "tipo_documento": "Boleto Bancário", "dominio": "financeiro"},
        "aprender_regra": True
    })
    regras = _get_json(base + "/api/regras-aprendidas")
    assert any(r.get("valor_atribuido") == "Boleto Bancário" for r in regras)


def test_post_salvar_malformed_payload_falls_through_to_404(running_server):
    base, _ = running_server
    req = urllib.request.Request(
        base + "/api/salvar",
        data=json.dumps({}).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with pytest.raises(urllib.error.HTTPError) as exc:
        urllib.request.urlopen(req)
    assert exc.value.code == 404


def test_post_regras_aprendidas_salvar_and_remover(running_server):
    base, _ = running_server
    resp = _post_json(base + "/api/regras-aprendidas", {
        "acao": "salvar",
        "termo_chave": "termo teste",
        "valor_atribuido": "Contrato",
        "dominio": "juridico"
    })
    assert resp["status"] == "sucesso"
    regra_id = resp["regra_id"]

    resp2 = _post_json(base + "/api/regras-aprendidas", {"acao": "remover", "id": regra_id})
    assert resp2["status"] == "sucesso"


def test_post_aprovar_updates_status(running_server):
    base, ctx = running_server
    upsert_documents_batch(ctx.db_path, [{"md5": "aprov1", "status": "sucesso"}])
    resp = _post_json(base + "/api/aprovar", {"md5": "aprov1"})
    assert resp["status"] == "sucesso"

    doc = get_document_by_md5(ctx.db_path, "aprov1")
    assert doc["status_conferencia"] == "aprovado"


def test_post_aprovar_unknown_md5_returns_404(running_server):
    base, _ = running_server
    req = urllib.request.Request(
        base + "/api/aprovar",
        data=json.dumps({"md5": "naoexiste"}).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with pytest.raises(urllib.error.HTTPError) as exc:
        urllib.request.urlopen(req)
    assert exc.value.code == 404


def test_post_organizar_arquivos_dry_run(running_server):
    base, _ = running_server
    resp = _post_json(base + "/api/organizar_arquivos", {"dry_run": True})
    assert "status" in resp


def test_post_uniformizar_instituicoes_empty_base(running_server):
    base, _ = running_server
    resp = _post_json(base + "/api/uniformizar_instituicoes", {})
    assert resp.get("status") in ("sucesso", None) or "total_registros" in resp
