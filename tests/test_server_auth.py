import json
import threading
import time
import urllib.error
import urllib.request

import pytest

from joakindex.server import (
    ConferenciaServer,
    ReusableThreadingHTTPServer,
    create_handler,
    extract_provided_token,
    token_matches,
)


def test_token_matches_disabled_when_no_expected():
    assert token_matches(None, None) is True
    assert token_matches("qualquer-coisa", "") is True


def test_token_matches_requires_provided():
    assert token_matches(None, "secret") is False
    assert token_matches("", "secret") is False


def test_token_matches_compares_values():
    assert token_matches("wrong", "secret") is False
    assert token_matches("secret", "secret") is True


def test_extract_provided_token_from_header():
    headers = {"X-Auth-Token": " abc "}
    assert extract_provided_token(headers) == "abc"


def test_extract_provided_token_from_bearer():
    headers = {"Authorization": "Bearer xyz"}
    assert extract_provided_token(headers) == "xyz"


def test_extract_provided_token_from_cookie():
    headers = {"Cookie": "joakindex_token=cookieval; outro=1"}
    assert extract_provided_token(headers) == "cookieval"


def test_extract_provided_token_missing():
    assert extract_provided_token({}) is None


@pytest.fixture
def running_server(tmp_path):
    pdf_dir = tmp_path / "pdf"
    pdf_dir.mkdir()
    json_path = tmp_path / "saida" / "joakindex.json"
    json_path.parent.mkdir()
    json_path.write_text("[]", encoding="utf-8")
    html_path = tmp_path / "visualizador.html"
    html_path.write_text("<html>ok</html>", encoding="utf-8")

    ctx = ConferenciaServer(
        json_path=str(json_path),
        pdf_dir=str(pdf_dir),
        html_path=str(html_path),
        auth_token="s3cr3t",
    )
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


def test_api_without_token_is_rejected(running_server):
    with pytest.raises(urllib.error.HTTPError) as exc:
        urllib.request.urlopen(running_server + "/api/documentos")
    assert exc.value.code == 401


def test_html_without_token_redirects_to_login(running_server):
    resp = urllib.request.urlopen(running_server + "/")
    assert resp.status == 200
    assert resp.url.endswith("/login")


def test_login_with_wrong_token_is_rejected(running_server):
    data = json.dumps({"token": "errado"}).encode()
    req = urllib.request.Request(
        running_server + "/api/login",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with pytest.raises(urllib.error.HTTPError) as exc:
        urllib.request.urlopen(req)
    assert exc.value.code == 401


def test_login_with_correct_token_sets_cookie_and_unlocks_api(running_server):
    data = json.dumps({"token": "s3cr3t"}).encode()
    req = urllib.request.Request(
        running_server + "/api/login",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    resp = urllib.request.urlopen(req)
    cookie = resp.headers.get("Set-Cookie")
    assert cookie is not None
    cookie_value = cookie.split(";")[0]

    req = urllib.request.Request(
        running_server + "/api/documentos",
        headers={"Cookie": cookie_value},
    )
    resp = urllib.request.urlopen(req)
    assert resp.status == 200
    assert json.loads(resp.read()) == []


def test_header_token_unlocks_api(running_server):
    req = urllib.request.Request(
        running_server + "/api/documentos",
        headers={"X-Auth-Token": "s3cr3t"},
    )
    resp = urllib.request.urlopen(req)
    assert resp.status == 200
