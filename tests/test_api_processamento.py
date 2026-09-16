import hashlib
import json
import threading
import time
import urllib.error
import urllib.request

import pytest

import joakindex.api_processamento as api_processamento
from joakindex.db import get_document_by_md5, upsert_documents_batch
from joakindex.server import ConferenciaServer, ReusableThreadingHTTPServer, create_handler


class DummyLLMClient:
    model = "modelo-fake"


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
    monkeypatch.setattr(ctx, "get_llm_client", lambda **kwargs: DummyLLMClient())

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


def _post_json(url, payload):
    data = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    return json.loads(urllib.request.urlopen(req).read())


def _write_pdf(tmp_path, ctx, name="doc_teste.pdf", content=b"%PDF-1.4 conteudo de teste do arquivo"):
    file_path = tmp_path / "pdf" / name
    file_path.write_bytes(content)
    ctx.build_pdf_index()
    return hashlib.md5(content).hexdigest()


def test_post_processar_documento_missing_md5_returns_400(running_server):
    base, _ = running_server
    req = urllib.request.Request(
        base + "/api/processar-documento",
        data=json.dumps({}).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with pytest.raises(urllib.error.HTTPError) as exc:
        urllib.request.urlopen(req)
    assert exc.value.code == 400


def test_post_processar_documento_unknown_md5_returns_404(running_server):
    base, _ = running_server
    req = urllib.request.Request(
        base + "/api/processar-documento",
        data=json.dumps({"md5": "naoexiste"}).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with pytest.raises(urllib.error.HTTPError) as exc:
        urllib.request.urlopen(req)
    assert exc.value.code == 404


def test_post_ocr_alias_accepts_same_payload_as_processar_documento(running_server, tmp_path, monkeypatch):
    base, ctx = running_server
    md5 = _write_pdf(tmp_path, ctx)

    def fake_process_single_pdf(pdf_file, client, force_ocr=False, hybrid=False, hybrid_cloud_client=None):
        return {"md5": md5, "status": "sucesso", "tipo_documento": "Certificado", "beneficiario": "Ana"}

    monkeypatch.setattr(api_processamento, "process_single_pdf", fake_process_single_pdf)

    resp = _post_json(base + "/api/ocr", {"md5": md5})
    assert resp["status"] == "sucesso"
    assert resp["item"]["beneficiario"] == "Ana"


def test_post_processar_documento_success_persists_and_syncs(running_server, tmp_path, monkeypatch):
    base, ctx = running_server
    md5 = _write_pdf(tmp_path, ctx)

    def fake_process_single_pdf(pdf_file, client, force_ocr=False, hybrid=False, hybrid_cloud_client=None):
        assert force_ocr is True
        return {
            "md5": md5,
            "status": "sucesso",
            "tipo_documento": ["Certificado", "Anexo"],
            "beneficiario": "Carlos",
        }

    monkeypatch.setattr(api_processamento, "process_single_pdf", fake_process_single_pdf)

    resp = _post_json(base + "/api/processar-documento", {"md5": md5})
    assert resp["status"] == "sucesso"
    assert resp["model"] == "modelo-fake"
    # Listas devem ser normalizadas para string para compatibilidade com o visualizador
    assert resp["item"]["tipo_documento"] == "Certificado, Anexo"

    saved = get_document_by_md5(ctx.db_path, md5)
    assert saved is not None
    assert saved["beneficiario"] == "Carlos"
    assert saved["status_conferencia"] == "pendente"


def test_post_processar_documento_preserves_previous_conferencia_status(running_server, tmp_path, monkeypatch):
    base, ctx = running_server
    md5 = _write_pdf(tmp_path, ctx)
    upsert_documents_batch(ctx.db_path, [
        {"md5": md5, "status": "sucesso", "status_conferencia": "aprovado", "observacoes_conferencia": "ok revisado"}
    ])

    def fake_process_single_pdf(pdf_file, client, force_ocr=False, hybrid=False, hybrid_cloud_client=None):
        return {"md5": md5, "status": "sucesso", "beneficiario": "Novo Nome"}

    monkeypatch.setattr(api_processamento, "process_single_pdf", fake_process_single_pdf)

    resp = _post_json(base + "/api/processar-documento", {"md5": md5})
    assert resp["item"]["status_conferencia"] == "aprovado"
    assert resp["item"]["observacoes_conferencia"] == "ok revisado"

    saved = get_document_by_md5(ctx.db_path, md5)
    assert saved["status_conferencia"] == "aprovado"


def test_post_processar_documento_llm_failure_returns_500_with_erro_status(running_server, tmp_path, monkeypatch):
    base, ctx = running_server
    md5 = _write_pdf(tmp_path, ctx)

    def fake_process_single_pdf(pdf_file, client, force_ocr=False, hybrid=False, hybrid_cloud_client=None):
        raise RuntimeError("falha simulada de OCR")

    monkeypatch.setattr(api_processamento, "process_single_pdf", fake_process_single_pdf)

    req = urllib.request.Request(
        base + "/api/processar-documento",
        data=json.dumps({"md5": md5}).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with pytest.raises(urllib.error.HTTPError) as exc:
        urllib.request.urlopen(req)
    assert exc.value.code == 500
    body = json.loads(exc.value.read())
    assert body["status"] == "erro"
    assert "falha simulada de OCR" in body["mensagem"]
