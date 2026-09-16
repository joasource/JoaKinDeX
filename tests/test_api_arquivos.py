import hashlib
import json
import threading
import time
import urllib.error
import urllib.request

import pytest

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


def test_get_info_returns_paths_and_counts(running_server):
    base, ctx = running_server
    resp = _get_json(base + "/api/info")
    assert resp["pdf_dir"] == str(ctx.pdf_dir)
    assert resp["json_name"] == "joakindex.json"
    assert resp["pdf_count"] == 0
    assert resp["doc_count"] == 0


def test_get_thumbnail_unknown_md5_returns_404(running_server):
    base, _ = running_server
    with pytest.raises(urllib.error.HTTPError) as exc:
        urllib.request.urlopen(base + "/api/thumbnail/naoexiste")
    assert exc.value.code == 404


def test_get_texto_unknown_md5_returns_404(running_server):
    base, _ = running_server
    with pytest.raises(urllib.error.HTTPError) as exc:
        urllib.request.urlopen(base + "/api/texto/naoexiste")
    assert exc.value.code == 404


def test_get_arquivo_serves_pdf_by_md5(running_server, tmp_path):
    base, ctx = running_server
    content = b"%PDF-1.4 conteudo de teste do arquivo"
    file_path = tmp_path / "pdf" / "doc_teste.pdf"
    file_path.write_bytes(content)
    md5 = hashlib.md5(content).hexdigest()
    ctx.build_pdf_index()

    resp = urllib.request.urlopen(base + f"/api/pdf/{md5}")
    assert resp.headers.get("Content-Type") == "application/pdf"
    assert 'filename="' + md5 + '.pdf"' in resp.headers.get("Content-Disposition")
    assert resp.read() == content


def test_get_arquivo_unknown_md5_returns_404(running_server):
    base, _ = running_server
    with pytest.raises(urllib.error.HTTPError) as exc:
        urllib.request.urlopen(base + "/api/arquivo/naoexiste")
    assert exc.value.code == 404
