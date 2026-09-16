import hashlib
import io
import json
import threading
import time
import urllib.error
import urllib.request
import zipfile

import pytest

from joakindex.db import get_document_by_md5, upsert_documents_batch
from joakindex.server import ConferenciaServer, ReusableThreadingHTTPServer, create_handler


@pytest.fixture
def running_server(tmp_path, monkeypatch):
    # Garante que um JOAKINDEX_AUTH_TOKEN do .env local do desenvolvedor não vaze para o teste.
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


def test_batch_status_idle_by_default(running_server):
    base, _ = running_server
    status = _get_json(base + "/api/batch/status")
    assert status["is_running"] is False
    assert status["status"] == "idle"


def test_batch_aprovar_updates_document_status(running_server):
    base, ctx = running_server
    doc = {"md5": "aaaa1111bbbb2222cccc3333dddd4444", "nome_arquivo": "doc1.pdf", "status": "sucesso"}
    upsert_documents_batch(ctx.db_path, [doc])

    resp = _post_json(base + "/api/batch/aprovar", {"md5s": [doc["md5"]]})
    assert resp["status"] == "sucesso"
    assert resp["count"] == 1

    updated = get_document_by_md5(ctx.db_path, doc["md5"])
    assert updated["status_conferencia"] == "aprovado"


def test_batch_aprovar_without_md5s_returns_400(running_server):
    base, _ = running_server
    req = urllib.request.Request(
        base + "/api/batch/aprovar",
        data=json.dumps({"md5s": []}).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with pytest.raises(urllib.error.HTTPError) as exc:
        urllib.request.urlopen(req)
    assert exc.value.code == 400


def test_batch_alterar_tipo_updates_fields(running_server):
    base, ctx = running_server
    doc = {"md5": "bbbb1111cccc2222dddd3333eeee4444", "nome_arquivo": "doc2.pdf", "status": "sucesso", "tipo_documento": "Documento Diverso"}
    upsert_documents_batch(ctx.db_path, [doc])

    resp = _post_json(base + "/api/batch/alterar-tipo", {
        "md5s": [doc["md5"]],
        "tipo_documento": "Boleto Bancário",
        "dominio": "financeiro",
    })
    assert resp["status"] == "sucesso"
    assert resp["count"] == 1

    updated = get_document_by_md5(ctx.db_path, doc["md5"])
    assert updated["tipo_documento"] == "Boleto Bancário"
    assert updated["dominio"] == "financeiro"


def test_batch_exportar_zip_get_contains_indexed_file(running_server, tmp_path):
    base, ctx = running_server
    file_path = tmp_path / "pdf" / "arquivo_teste.pdf"
    content = b"%PDF-1.4 conteudo de teste"
    file_path.write_bytes(content)
    md5 = hashlib.md5(content).hexdigest()
    ctx.build_pdf_index()
    assert ctx.md5_to_file.get(md5) == file_path

    resp = urllib.request.urlopen(base + f"/api/batch/exportar-zip?md5s={md5}")
    assert resp.headers.get("Content-Type") == "application/zip"
    zip_bytes = resp.read()
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        names = zf.namelist()
        assert "arquivo_teste.pdf" in names
        assert zf.read("arquivo_teste.pdf") == content


def test_batch_exportar_zip_post_contains_indexed_file(running_server, tmp_path):
    base, ctx = running_server
    file_path = tmp_path / "pdf" / "arquivo_teste2.pdf"
    content = b"%PDF-1.4 outro conteudo"
    file_path.write_bytes(content)
    md5 = hashlib.md5(content).hexdigest()
    ctx.build_pdf_index()

    req = urllib.request.Request(
        base + "/api/batch/exportar-zip",
        data=json.dumps({"md5s": [md5]}).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    resp = urllib.request.urlopen(req)
    assert resp.headers.get("Content-Type") == "application/zip"
    zip_bytes = resp.read()
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        assert "arquivo_teste2.pdf" in zf.namelist()


def test_batch_stop_without_running_batch_returns_aviso(running_server):
    base, _ = running_server
    resp = _post_json(base + "/api/batch/stop", {})
    assert resp["status"] == "aviso"
    assert resp["batch_status"]["is_running"] is False


def test_batch_start_and_stop_lifecycle(running_server):
    base, ctx = running_server
    # Diretório vazio: o processamento em lote termina rapidamente por não haver arquivos.
    resp = _post_json(base + "/api/batch/start", {})
    assert resp["status"] == "sucesso"
    assert resp["batch_status"]["is_running"] is True

    deadline = time.time() + 10
    while time.time() < deadline:
        status = _get_json(base + "/api/batch/status")
        if not status["is_running"]:
            break
        time.sleep(0.2)
    else:
        pytest.fail("Processamento em lote não finalizou a tempo")
