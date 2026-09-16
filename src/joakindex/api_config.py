#!/usr/bin/env python3
"""
JoaKinDeX - Rotas de Configuração do Servidor
Criado por: Joaquim Ferreira Silva Neto <joaquimfsneto@gmail.com>

Rotas HTTP para consultar e alterar as configurações persistentes do
classificador e do visualizador (pastas, provedor de LLM, modo híbrido
etc.), listar os ambientes Ollama detectados e restaurar os padrões de
fábrica.
"""

__project__ = "JoaKinDeX"
__author__ = "Joaquim Ferreira Silva Neto"
__email__ = "joaquimfsneto@gmail.com"
__version__ = "1.0.0"

import json
import os
from pathlib import Path

from joakindex.config import (
    get_classifier_config,
    get_visualizer_config,
    save_classifier_config,
    save_visualizer_config,
    reset_all_config,
    get_factory_defaults,
)
from joakindex.db import get_db_path, init_database
from joakindex.llm_clients import detect_ollama_environments


def handle_get_config(handler, server_ctx):
    cfg_classificador = get_classifier_config()
    cfg_vis = get_visualizer_config()
    clean_classificador = dict(cfg_classificador)
    clean_vis = dict(cfg_vis)

    active_key = (
        clean_classificador.get("openai_key")
        or clean_vis.get("openai_key")
        or server_ctx.openai_key
        or os.environ.get("OPENAI_API_KEY")
    )
    has_key = bool(active_key)
    masked_key = ""
    if active_key:
        masked_key = active_key[:7] + "..." + active_key[-4:] if len(active_key) > 12 else "***"

    clean_classificador["openai_key_masked"] = masked_key
    clean_classificador["has_openai_key"] = has_key
    if clean_classificador.get("openai_key"):
        del clean_classificador["openai_key"]

    clean_vis["openai_key_masked"] = masked_key
    clean_vis["has_openai_key"] = has_key
    clean_vis["provider"] = server_ctx.provider
    clean_vis["model"] = server_ctx.model
    clean_vis["ollama_url"] = server_ctx.ollama_url
    clean_vis["hybrid"] = getattr(server_ctx, "hybrid", clean_vis.get("hybrid", False))
    clean_vis["hybrid_cloud_model"] = getattr(server_ctx, "hybrid_cloud_model", clean_vis.get("hybrid_cloud_model", "gpt-4o-mini"))
    if clean_vis.get("openai_key"):
        del clean_vis["openai_key"]

    envs = []
    if detect_ollama_environments:
        try:
            envs = detect_ollama_environments(clean_classificador.get("ollama_url") or server_ctx.ollama_url or "http://localhost:11434")
        except Exception as ex_env:
            print(f"[Aviso] Falha ao detectar ambientes Ollama: {ex_env}")

    resp_obj = {
        "classificador": clean_classificador,
        "visualizador": clean_vis,
        "environments": envs,
        "batch_status": server_ctx.batch_manager.get_status(),
        "pdf_count": len(server_ctx.md5_to_file),
        "doc_count": len(server_ctx.load_data()),
        "current_pdf_dir": str(server_ctx.pdf_dir),
        "current_json_path": str(server_ctx.json_path)
    }
    body = json.dumps(resp_obj, ensure_ascii=False).encode("utf-8")
    handler.send_response(200)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def handle_get_environments(handler, server_ctx):
    envs = []
    if detect_ollama_environments:
        try:
            url = server_ctx.ollama_url or "http://localhost:11434"
            envs = detect_ollama_environments(url)
        except Exception as ex_env:
            print(f"[Aviso] Falha ao detectar ambientes Ollama: {ex_env}")

    body = json.dumps(envs, ensure_ascii=False).encode("utf-8")
    handler.send_response(200)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def handle_post_config(handler, server_ctx, payload):
    # Import tardio para evitar dependência circular com joakindex.server no carregamento do módulo.
    from joakindex.server import resolve_pdf_dir, resolve_json_path

    updates_classificador = payload.get("classificador", {})
    updates_visualizador = payload.get("visualizador", {})

    if not updates_classificador and not updates_visualizador:
        for k in ["input", "output_dir", "provider", "model", "workers", "max_pages", "skip_ocr", "docker", "ollama_url", "openai_key", "openai_base_url", "hybrid", "hybrid_cloud_model"]:
            if k in payload:
                updates_classificador[k] = payload[k]
        for k in ["pdf_dir", "json_path", "port", "provider", "model", "ollama_url", "openai_key", "openai_base_url", "hybrid", "hybrid_cloud_model"]:
            if k in payload:
                updates_visualizador[k] = payload[k]

    if "openai_key" in updates_classificador:
        val = updates_classificador["openai_key"]
        if not val or "***" in val or "..." in val:
            del updates_classificador["openai_key"]

    if "openai_key" in updates_visualizador:
        val = updates_visualizador["openai_key"]
        if not val or "***" in val or "..." in val:
            del updates_visualizador["openai_key"]

    if updates_classificador:
        save_classifier_config(updates_classificador)
    if updates_visualizador:
        save_visualizer_config(updates_visualizador)

    new_pdf = (
        updates_visualizador.get("docs_dir")
        or updates_visualizador.get("input_dir")
        or updates_visualizador.get("pdf_dir")
        or updates_classificador.get("input")
    )
    new_json = (
        updates_visualizador.get("data_path")
        or updates_visualizador.get("json_path")
        or updates_classificador.get("output_dir")
    )

    if new_pdf:
        p_pdf = Path(resolve_pdf_dir(new_pdf)).expanduser().resolve()
        if p_pdf != server_ctx.pdf_dir:
            server_ctx.pdf_dir = p_pdf
            server_ctx.build_pdf_index()

    if new_json:
        p_json = Path(resolve_json_path(new_json)).expanduser().resolve()
        if p_json != server_ctx.json_path:
            server_ctx.json_path = p_json
            server_ctx.db_path = get_db_path(p_json)
            init_database(server_ctx.db_path, initial_json_path=server_ctx.json_path)
            server_ctx.load_data()

    new_prov = updates_visualizador.get("provider") or updates_classificador.get("provider")
    if new_prov:
        server_ctx.provider = new_prov
        server_ctx._llm_client = None

    new_model = updates_visualizador.get("model") or updates_classificador.get("model")
    if new_model:
        server_ctx.model = new_model
        server_ctx._llm_client = None

    new_url = updates_visualizador.get("ollama_url") or updates_classificador.get("ollama_url")
    if new_url:
        server_ctx.ollama_url = new_url
        server_ctx._llm_client = None

    new_key = updates_visualizador.get("openai_key") or updates_classificador.get("openai_key")
    if new_key:
        server_ctx.openai_key = new_key
        server_ctx._llm_client = None

    new_base_url = updates_visualizador.get("openai_base_url") or updates_classificador.get("openai_base_url")
    if new_base_url is not None:
        server_ctx.openai_base_url = new_base_url
        server_ctx._llm_client = None

    if "hybrid" in updates_visualizador or "hybrid" in updates_classificador:
        h_val = updates_visualizador.get("hybrid")
        if h_val is None:
            h_val = updates_classificador.get("hybrid")
        if h_val is not None:
            server_ctx.hybrid = bool(h_val)

    if "hybrid_cloud_model" in updates_visualizador or "hybrid_cloud_model" in updates_classificador:
        m_val = updates_visualizador.get("hybrid_cloud_model") or updates_classificador.get("hybrid_cloud_model")
        if m_val:
            server_ctx.hybrid_cloud_model = str(m_val).strip()

    resp = json.dumps({
        "status": "sucesso",
        "mensagem": "Configurações salvas e aplicadas com sucesso!",
        "pdf_count": len(server_ctx.md5_to_file),
        "doc_count": len(server_ctx.load_data()),
        "pdf_dir": str(server_ctx.pdf_dir),
        "json_path": str(server_ctx.json_path),
        "db_path": str(server_ctx.db_path),
        "provider": server_ctx.provider,
        "model": server_ctx.model
    }, ensure_ascii=False).encode("utf-8")
    handler.send_response(200)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(resp)))
    handler.end_headers()
    handler.wfile.write(resp)


def handle_post_config_reset(handler, server_ctx):
    reset_all_config()
    factory = get_factory_defaults()
    server_ctx.pdf_dir = Path(factory["visualizador"]["pdf_dir"]).resolve()
    server_ctx.json_path = Path(factory["visualizador"]["json_path"]).resolve()
    server_ctx.db_path = get_db_path(server_ctx.json_path)
    init_database(server_ctx.db_path, initial_json_path=server_ctx.json_path)
    server_ctx.provider = factory["visualizador"]["provider"]
    server_ctx.model = factory["visualizador"]["model"]
    server_ctx.ollama_url = factory["visualizador"]["ollama_url"]
    server_ctx.openai_key = factory["visualizador"].get("openai_key")
    server_ctx.openai_base_url = factory["visualizador"].get("openai_base_url")
    server_ctx._llm_client = None
    server_ctx.build_pdf_index()
    server_ctx.load_data()

    resp = json.dumps({
        "status": "sucesso",
        "mensagem": "Padrões de fábrica neutros restaurados!",
        "classificador": factory["classificador"],
        "visualizador": factory["visualizador"],
        "pdf_count": len(server_ctx.md5_to_file),
        "doc_count": len(server_ctx.load_data()),
        "pdf_dir": str(server_ctx.pdf_dir),
        "json_path": str(server_ctx.json_path)
    }, ensure_ascii=False).encode("utf-8")
    handler.send_response(200)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(resp)))
    handler.end_headers()
    handler.wfile.write(resp)
