import io
import threading
import time
import urllib.request
import zipfile

import pytest

from joakindex.db import upsert_document
from joakindex.export_relacional import CSV_COLUMNS
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


def test_get_export_relacional_zip_base_vazia(running_server):
    base, _ = running_server
    resp = urllib.request.urlopen(base + "/api/export/relacional-zip")
    assert resp.headers.get("Content-Type") == "application/zip"
    with zipfile.ZipFile(io.BytesIO(resp.read())) as zf:
        assert set(zf.namelist()) == set(CSV_COLUMNS.keys())


def test_get_export_relacional_zip_com_documentos(running_server):
    base, ctx = running_server
    upsert_document(ctx.db_path, {
        "md5": "abc123", "nome_arquivo": "doc.pdf", "beneficiario": "Fulano de Tal",
        "cpf": "111.444.777-35",
    })
    resp = urllib.request.urlopen(base + "/api/export/relacional-zip")
    assert resp.headers.get("Content-Type") == "application/zip"
    disposition = resp.headers.get("Content-Disposition") or ""
    assert "attachment" in disposition
    with zipfile.ZipFile(io.BytesIO(resp.read())) as zf:
        assert set(zf.namelist()) == set(CSV_COLUMNS.keys())
        content = zf.read("pessoas_fisicas.csv").decode("utf-8-sig")
        assert "11144477735" in content
