#!/usr/bin/env python3
"""
JoaKinDeX - Rota de Leitura e Classificação sob Demanda (OCR multimodal forçado)
Criado por: Joaquim Ferreira Silva Neto <joaquimfsneto@gmail.com>

Rota HTTP que reprocessa um único documento já indexado (por MD5), forçando
OCR/classificação via LLM multimodal, preserva a conferência anterior quando
existir e sincroniza banco SQLite, JSON e TXT consolidados.
"""

__project__ = "JoaKinDeX"
__author__ = "Joaquim Ferreira Silva Neto"
__email__ = "joaquimfsneto@gmail.com"
__version__ = "1.0.0"

import json

from joakindex.classificacao import process_single_pdf, format_single_txt
from joakindex.db import upsert_document, sync_to_json, get_all_documents, get_document_by_md5
from joakindex.normalizer import normalizar_instituicao


def handle_post_processar_documento(handler, server_ctx, payload):
    target_md5 = str(payload.get("md5") or "").strip().lower()
    if not target_md5:
        handler.send_error(400, "MD5 do documento não informado.")
        return

    pdf_file = server_ctx.md5_to_file.get(target_md5)
    if not pdf_file or not pdf_file.exists():
        server_ctx.build_pdf_index()
        pdf_file = server_ctx.md5_to_file.get(target_md5)

    if not pdf_file or not pdf_file.exists():
        # Tenta localizar por nome de arquivo se fornecido
        fname = payload.get("nome_arquivo")
        if fname:
            for p in server_ctx.pdf_dir.rglob(fname):
                if p.is_file():
                    pdf_file = p
                    break

    if not pdf_file or not pdf_file.exists():
        handler.send_error(404, f"Arquivo PDF com MD5 {target_md5} não encontrado na pasta de PDFs ({server_ctx.pdf_dir}).")
        return

    try:
        req_prov = payload.get("provider")
        req_model = payload.get("model")
        req_key = payload.get("openai_key")
        req_base = payload.get("openai_base_url")
        req_ollama_url = payload.get("ollama_url")

        client = server_ctx.get_llm_client(
            provider=req_prov,
            model=req_model,
            openai_key=req_key,
            openai_base_url=req_base,
            ollama_url=req_ollama_url
        )

        req_hybrid = payload.get("hybrid")
        if req_hybrid is None:
            req_hybrid = getattr(server_ctx, "hybrid", False)
        req_hybrid = bool(req_hybrid)
        req_hybrid_cloud_model = payload.get("hybrid_cloud_model") or getattr(server_ctx, "hybrid_cloud_model", "gpt-4o-mini")

        hybrid_cloud_client = None
        if req_hybrid:
            try:
                hybrid_cloud_client = server_ctx.get_llm_client(
                    provider="openai",
                    model=req_hybrid_cloud_model,
                    openai_key=req_key,
                    openai_base_url=req_base
                )
            except Exception as ex_h:
                print(f"[Aviso] Falha ao inicializar cliente de fallback para modo híbrido sob demanda: {ex_h}")
                req_hybrid = False

        # Executa a leitura e classificação completa do documento forçando OCR
        novo_doc = process_single_pdf(
            pdf_file,
            client,
            force_ocr=True,
            hybrid=req_hybrid,
            hybrid_cloud_client=hybrid_cloud_client
        )
        novo_doc.pop("data_criacao", None)

        # Sanitiza listas para strings para compatibilidade com o visualizador
        for k in ["curso", "beneficiario", "faculdade", "natureza_curso", "tipo_documento", "carga_horaria", "cpf", "rg", "data", "dominio", "valor_monetario"]:
            v = novo_doc.get(k)
            if isinstance(v, list):
                novo_doc[k] = ", ".join(str(x) for x in v if x)

        if novo_doc.get("faculdade"):
            novo_doc["faculdade"] = normalizar_instituicao(novo_doc.get("faculdade"))

        # Preserva conferência anterior se houver
        prev_doc = get_document_by_md5(server_ctx.db_path, target_md5)
        if prev_doc:
            prev_conf = prev_doc.get("status_conferencia")
            if prev_conf in ["aprovado", "pendente"]:
                novo_doc["status_conferencia"] = prev_conf
            else:
                novo_doc["status_conferencia"] = "pendente"
            if prev_doc.get("observacoes_conferencia"):
                novo_doc["observacoes_conferencia"] = prev_doc["observacoes_conferencia"]
            if not novo_doc.get("autor") and prev_doc.get("autor"):
                novo_doc["autor"] = prev_doc["autor"]
            if not novo_doc.get("dublin_core") and prev_doc.get("dublin_core"):
                novo_doc["dublin_core"] = prev_doc["dublin_core"]
            if not novo_doc.get("dc_title") and prev_doc.get("dc_title"):
                novo_doc["dc_title"] = prev_doc["dc_title"]
            if not novo_doc.get("dc_subject") and prev_doc.get("dc_subject"):
                novo_doc["dc_subject"] = prev_doc["dc_subject"]
            if not novo_doc.get("dc_creator_tool") and prev_doc.get("dc_creator_tool"):
                novo_doc["dc_creator_tool"] = prev_doc["dc_creator_tool"]
        else:
            novo_doc["status_conferencia"] = "pendente"

        # 1. Salva no banco SQLite WAL
        upsert_document(server_ctx.db_path, novo_doc)

        # 2. Se existir pasta 'individuais' correspondente, atualiza o arquivo individual também
        indiv_dir = server_ctx.json_path.parent / "individuais"
        if indiv_dir.exists():
            indiv_file = indiv_dir / f"{target_md5}.json"
            try:
                with open(indiv_file, "w", encoding="utf-8") as fi:
                    json.dump(novo_doc, fi, ensure_ascii=False, indent=2)
            except Exception:
                pass
            indiv_txt_file = indiv_dir / f"{target_md5}.txt"
            try:
                with open(indiv_txt_file, "w", encoding="utf-8") as ft:
                    ft.write(format_single_txt(novo_doc))
            except Exception:
                pass

        # 3. Sincroniza com JSON e TXT consolidado
        sync_to_json(server_ctx.db_path, server_ctx.json_path, only_processed=True)
        all_processed = get_all_documents(server_ctx.db_path, only_processed=True)
        server_ctx.update_txt_report(all_processed)

        active_prov = req_prov or server_ctx.provider or "ollama"
        provider_label = "OpenAI API" if active_prov == "openai" else "Ollama"
        model_used = getattr(client, "model", req_model or server_ctx.model)

        resp = json.dumps({
            "status": "sucesso",
            "item": novo_doc,
            "provider": active_prov,
            "model": model_used,
            "mensagem": f"Documento lido e classificado com sucesso via {provider_label} ({model_used})!"
        }, ensure_ascii=False).encode("utf-8")
        handler.send_response(200)
        handler.send_header("Content-Type", "application/json; charset=utf-8")
        handler.send_header("Content-Length", str(len(resp)))
        handler.end_headers()
        handler.wfile.write(resp)
    except Exception as e:
        err_msg = f"Erro ao classificar documento: {e}"
        print(f"[Erro Classificação API] {err_msg}")
        resp = json.dumps({"status": "erro", "mensagem": err_msg}, ensure_ascii=False).encode("utf-8")
        handler.send_response(500)
        handler.send_header("Content-Type", "application/json; charset=utf-8")
        handler.send_header("Content-Length", str(len(resp)))
        handler.end_headers()
        handler.wfile.write(resp)
