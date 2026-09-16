#!/usr/bin/env python3
"""
JoaKinDeX - Navegador de Diretórios do Sistema
Criado por: Joaquim Ferreira Silva Neto <joaquimfsneto@gmail.com>

Rotas HTTP para o seletor de pastas da interface web: listar diretórios,
criar subpastas e (quando disponível) abrir o diálogo nativo de seleção
de pasta via Zenity (Linux).
"""

__project__ = "JoaKinDeX"
__author__ = "Joaquim Ferreira Silva Neto"
__email__ = "joaquimfsneto@gmail.com"
__version__ = "1.0.0"

import json
import os
import subprocess
import urllib.parse
from pathlib import Path

from joakindex.cli import SUPPORTED_EXTENSIONS


def handle_get_browse_dirs(handler, server_ctx, parsed):
    params = urllib.parse.parse_qs(parsed.query)
    req_path = params.get("path", [""])[0].strip()
    mode = params.get("mode", [""])[0].strip()

    if req_path:
        p = Path(req_path).expanduser()
    else:
        if mode == "pdf":
            p = Path(server_ctx.pdf_dir).expanduser()
        elif server_ctx.json_path:
            p = Path(server_ctx.json_path).expanduser().parent
        else:
            p = Path.cwd()

    if not p.exists() or not p.is_dir():
        if p.parent.exists() and p.parent.is_dir():
            p = p.parent
        elif Path.home().exists():
            p = Path.home()
        else:
            p = Path.cwd()

    try:
        p = p.resolve()
    except Exception:
        pass

    # Atalhos rápidos inteligentes
    quick = [
        {"name": "Projeto", "path": str(Path.cwd().resolve()), "icon": "fa-folder-tree"},
        {"name": "Início (~)", "path": str(Path.home().resolve()), "icon": "fa-house"}
    ]

    # Checa /media e /media/usuario
    media_base = Path("/media")
    try:
        user_media = media_base / Path.home().name
        if user_media.exists() and user_media.is_dir():
            quick.append({"name": f"Mídias ({user_media.name})", "path": str(user_media.resolve()), "icon": "fa-hard-drive"})
        elif media_base.exists() and media_base.is_dir():
            quick.append({"name": "Mídias (/media)", "path": str(media_base.resolve()), "icon": "fa-hard-drive"})
    except Exception:
        pass

    try:
        mnt_p = Path("/mnt")
        if mnt_p.exists() and mnt_p.is_dir() and any(mnt_p.iterdir()):
            quick.append({"name": "Montagens (/mnt)", "path": "/mnt", "icon": "fa-server"})
    except Exception:
        pass

    quick.append({"name": "Raiz (/)", "path": "/", "icon": "fa-database"})

    dirs = []
    files_pdf_count = 0
    is_readable = True
    try:
        is_readable = os.access(p, os.R_OK)
        if is_readable:
            for entry in sorted(p.iterdir(), key=lambda x: x.name.lower()):
                # Ignora arquivos/pastas ocultos ou de lixeira do Windows por padrão
                if entry.name.startswith(".") or entry.name.startswith("$") or entry.name == "System Volume Information":
                    continue
                try:
                    if entry.is_dir():
                        sub_pdf_count = 0
                        if mode == "pdf":
                            try:
                                sub_pdf_count = sum(1 for f in entry.iterdir() if f.is_file() and f.suffix.lower() in SUPPORTED_EXTENSIONS)
                            except Exception:
                                sub_pdf_count = 0
                        dirs.append({
                            "name": entry.name,
                            "path": str(entry.resolve()),
                            "pdf_count": sub_pdf_count,
                            "readable": os.access(entry, os.R_OK)
                        })
                except (PermissionError, OSError):
                    continue

            if mode == "pdf":
                try:
                    files_pdf_count = sum(1 for f in p.iterdir() if f.is_file() and f.suffix.lower() in SUPPORTED_EXTENSIONS)
                except Exception:
                    files_pdf_count = 0
    except (PermissionError, OSError):
        is_readable = False

    parent_path = str(p.parent.resolve()) if p != p.parent else None
    zenity_avail = bool(os.path.exists("/usr/bin/zenity") and os.environ.get("DISPLAY"))

    resp_obj = {
        "current_path": str(p),
        "parent_path": parent_path,
        "quick_access": quick,
        "directories": dirs,
        "files_pdf_count": files_pdf_count,
        "is_writable": os.access(p, os.W_OK) if p.exists() else False,
        "is_readable": is_readable,
        "zenity_available": zenity_avail
    }
    body = json.dumps(resp_obj, ensure_ascii=False).encode("utf-8")
    handler.send_response(200)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def handle_post_browse_mkdir(handler, server_ctx, payload):
    parent_str = payload.get("parent", "").strip()
    name_str = payload.get("name", "").strip()
    if not parent_str or not name_str:
        handler.send_error(400, "Parâmetros 'parent' e 'name' são obrigatórios.")
        return
    if "/" in name_str or "\\" in name_str or name_str.startswith(".."):
        handler.send_error(400, "Nome de pasta inválido.")
        return
    parent_p = Path(parent_str).expanduser().resolve()
    if not parent_p.exists() or not parent_p.is_dir():
        handler.send_error(400, f"Pasta pai '{parent_p}' não existe.")
        return
    target_new = parent_p / name_str
    try:
        target_new.mkdir(parents=True, exist_ok=True)
        resp = json.dumps({
            "status": "sucesso",
            "mensagem": f"Pasta '{name_str}' criada com sucesso!",
            "path": str(target_new.resolve())
        }, ensure_ascii=False).encode("utf-8")
        handler.send_response(200)
        handler.send_header("Content-Type", "application/json; charset=utf-8")
        handler.send_header("Content-Length", str(len(resp)))
        handler.end_headers()
        handler.wfile.write(resp)
    except Exception as ex_mk:
        handler.send_error(500, f"Erro ao criar pasta: {ex_mk}")


def handle_post_browse_native(handler, server_ctx, payload):
    init_p = payload.get("initial_path", "").strip()
    title = payload.get("title", "Selecione a Pasta")
    if not os.path.exists("/usr/bin/zenity") or not os.environ.get("DISPLAY"):
        resp = json.dumps({
            "status": "erro",
            "mensagem": "Interface gráfica ou comando zenity não disponível neste ambiente."
        }, ensure_ascii=False).encode("utf-8")
        handler.send_response(200)
        handler.send_header("Content-Type", "application/json; charset=utf-8")
        handler.send_header("Content-Length", str(len(resp)))
        handler.end_headers()
        handler.wfile.write(resp)
        return

    cmd = ["zenity", "--file-selection", "--directory", f"--title={title}"]
    if init_p and Path(init_p).exists():
        cmd.append(f"--filename={init_p.rstrip('/')}/")

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if proc.returncode == 0 and proc.stdout.strip():
            chosen = proc.stdout.strip()
            resp = json.dumps({
                "status": "sucesso",
                "path": chosen
            }, ensure_ascii=False).encode("utf-8")
        else:
            resp = json.dumps({
                "status": "cancelado",
                "mensagem": "Seleção cancelada pelo usuário."
            }, ensure_ascii=False).encode("utf-8")
    except subprocess.TimeoutExpired:
        resp = json.dumps({
            "status": "cancelado",
            "mensagem": "Tempo limite para seleção esgotado."
        }, ensure_ascii=False).encode("utf-8")
    except Exception as ex_zen:
        resp = json.dumps({
            "status": "erro",
            "mensagem": f"Erro ao executar zenity: {ex_zen}"
        }, ensure_ascii=False).encode("utf-8")

    handler.send_response(200)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(resp)))
    handler.end_headers()
    handler.wfile.write(resp)
