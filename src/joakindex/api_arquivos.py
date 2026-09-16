#!/usr/bin/env python3
"""
JoaKinDeX - Rotas de Informações, Miniaturas, Texto e Arquivos
Criado por: Joaquim Ferreira Silva Neto <joaquimfsneto@gmail.com>

Rotas HTTP para informações gerais do servidor, miniaturas de páginas em
cache, texto/OCR integral de um documento e o download/visualização do
arquivo físico (PDF, imagem ou Word) por MD5.
"""

__project__ = "JoaKinDeX"
__author__ = "Joaquim Ferreira Silva Neto"
__email__ = "joaquimfsneto@gmail.com"
__version__ = "1.0.0"

import json
import urllib.parse

from joakindex.cli import WORD_EXTENSIONS, convert_office_to_pdf


def handle_get_info(handler, server_ctx):
    info = {
        "json_path": str(server_ctx.json_path),
        "json_name": server_ctx.json_path.name,
        "db_path": str(server_ctx.db_path),
        "db_name": server_ctx.db_path.name,
        "pdf_dir": str(server_ctx.pdf_dir),
        "pdf_count": len(server_ctx.md5_to_file),
        "doc_count": len(server_ctx.load_data())
    }
    body = json.dumps(info, ensure_ascii=False).encode("utf-8")
    handler.send_response(200)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def handle_get_thumbnail(handler, server_ctx, parsed, path):
    # Import tardio para evitar dependência circular com joakindex.server no carregamento do módulo.
    from joakindex.server import get_or_create_thumbnail

    query = urllib.parse.parse_qs(parsed.query)
    width_req = int(query["w"][0]) if "w" in query and query["w"][0].isdigit() else 720
    parts = path.split("/api/thumbnail/")[-1].strip("/").split("/")
    md5_req = parts[0].strip().lower()
    page_req = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 1
    data = get_or_create_thumbnail(server_ctx, md5_req, page_num=page_req, target_width=width_req)
    if data:
        handler._custom_cache_control = True
        handler.send_response(200)
        handler.send_header("Content-Type", "image/jpeg")
        handler.send_header("Cache-Control", "public, max-age=604800")
        handler.send_header("Content-Length", str(len(data)))
        handler.end_headers()
        handler.wfile.write(data)
    else:
        handler.send_error(404, "Thumbnail não disponível.")


def handle_get_texto(handler, server_ctx, path):
    # Import tardio para evitar dependência circular com joakindex.server no carregamento do módulo.
    from joakindex.server import extract_document_text_content

    md5_req = path.split("/api/texto/")[-1].strip().lower()
    res = extract_document_text_content(server_ctx, md5_req)
    body = json.dumps(res, ensure_ascii=False).encode("utf-8")
    handler.send_response(200 if res.get("status") == "sucesso" else 404)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def handle_get_arquivo(handler, server_ctx, path):
    prefix = "/api/pdf/" if path.startswith("/api/pdf/") else "/api/arquivo/"
    md5_req = path.split(prefix)[-1].strip().lower()
    pdf_file = server_ctx.md5_to_file.get(md5_req)

    if not pdf_file or not pdf_file.exists():
        server_ctx.build_pdf_index()
        pdf_file = server_ctx.md5_to_file.get(md5_req)

    if pdf_file and pdf_file.exists():
        ext = pdf_file.suffix.lower()
        mime_types = {
            ".pdf": "application/pdf",
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".webp": "image/webp",
            ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ".doc": "application/msword",
            ".odt": "application/vnd.oasis.opendocument.text",
            ".rtf": "application/rtf",
            ".txt": "text/plain; charset=utf-8"
        }
        content_type = mime_types.get(ext, "application/octet-stream")
        file_to_send = pdf_file
        disp_name = f"{md5_req}{ext}"
        disp_mode = "inline"

        # Se a requisição for para /api/pdf/ e o arquivo for Word (.docx, .doc, etc.),
        # entrega o PDF espelho de alta fidelidade gerado em cache pelo LibreOffice!
        if prefix == "/api/pdf/" and ext in WORD_EXTENSIONS and convert_office_to_pdf:
            pdf_cached = convert_office_to_pdf(pdf_file)
            if pdf_cached and pdf_cached.exists():
                file_to_send = pdf_cached
                content_type = "application/pdf"
                disp_name = f"{pdf_file.stem}.pdf"
                disp_mode = "inline"

        size = file_to_send.stat().st_size
        handler.send_response(200)
        handler.send_header("Content-Type", content_type)
        handler.send_header("Content-Disposition", f'{disp_mode}; filename="{disp_name}"')
        handler.send_header("Content-Length", str(size))
        handler.end_headers()
        with open(file_to_send, "rb") as f:
            handler.wfile.write(f.read())
    else:
        handler.send_error(404, f"Arquivo com MD5 {md5_req} não encontrado.")
