import json
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

import pytest

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
        yield f"http://127.0.0.1:{port}"
    finally:
        httpd.shutdown()


def _get_json(url):
    return json.loads(urllib.request.urlopen(url).read())


def _post_json(url, payload):
    data = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    return json.loads(urllib.request.urlopen(req).read())


def test_browse_dirs_lists_subdirectories(running_server, tmp_path):
    base = running_server
    root = tmp_path / "raiz_teste"
    (root / "subpasta_a").mkdir(parents=True)
    (root / "subpasta_b").mkdir(parents=True)
    (root / ".oculta").mkdir(parents=True)

    url = base + "/api/browse/dirs?" + urllib.parse.urlencode({"path": str(root)})
    resp = _get_json(url)

    assert resp["current_path"] == str(root)
    names = {d["name"] for d in resp["directories"]}
    assert names == {"subpasta_a", "subpasta_b"}
    assert resp["is_readable"] is True
    assert any(q["name"] == "Raiz (/)" for q in resp["quick_access"])


def test_browse_dirs_pdf_mode_counts_supported_files(running_server, tmp_path):
    base = running_server
    root = tmp_path / "com_pdfs"
    root.mkdir()
    (root / "a.pdf").write_bytes(b"%PDF-1.4")
    (root / "b.PDF").write_bytes(b"%PDF-1.4")
    (root / "nota.txt").write_text("nao deveria contar como pdf sozinho")

    url = base + "/api/browse/dirs?" + urllib.parse.urlencode({"path": str(root), "mode": "pdf"})
    resp = _get_json(url)
    assert resp["files_pdf_count"] >= 2


def test_browse_dirs_falls_back_to_parent_for_nonexistent_path(running_server, tmp_path):
    base = running_server
    existing_parent = tmp_path / "existe"
    existing_parent.mkdir()
    missing = existing_parent / "nao_existe"

    url = base + "/api/browse/dirs?" + urllib.parse.urlencode({"path": str(missing)})
    resp = _get_json(url)
    assert resp["current_path"] == str(existing_parent.resolve())


def test_browse_mkdir_creates_folder(running_server, tmp_path):
    base = running_server
    parent = tmp_path / "pasta_pai"
    parent.mkdir()

    resp = _post_json(base + "/api/browse/mkdir", {"parent": str(parent), "name": "nova_pasta"})
    assert resp["status"] == "sucesso"
    assert (parent / "nova_pasta").is_dir()


def test_browse_mkdir_rejects_missing_params(running_server):
    base = running_server
    req = urllib.request.Request(
        base + "/api/browse/mkdir",
        data=json.dumps({"parent": "", "name": ""}).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with pytest.raises(urllib.error.HTTPError) as exc:
        urllib.request.urlopen(req)
    assert exc.value.code == 400


def test_browse_mkdir_rejects_path_traversal_in_name(running_server, tmp_path):
    base = running_server
    parent = tmp_path / "pasta_pai2"
    parent.mkdir()
    req = urllib.request.Request(
        base + "/api/browse/mkdir",
        data=json.dumps({"parent": str(parent), "name": "../fuga"}).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with pytest.raises(urllib.error.HTTPError) as exc:
        urllib.request.urlopen(req)
    assert exc.value.code == 400


def test_browse_native_unavailable_without_display(running_server, monkeypatch):
    monkeypatch.delenv("DISPLAY", raising=False)
    base = running_server
    resp = _post_json(base + "/api/browse/native", {})
    assert resp["status"] == "erro"
    assert "zenity" in resp["mensagem"].lower()
