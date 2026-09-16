#!/usr/bin/env python3
"""
JoaKinDeX - Rotas de CRUD de Documentos e Regras Aprendidas
Criado por: Joaquim Ferreira Silva Neto <joaquimfsneto@gmail.com>

Rotas HTTP centrais de conferência: listar documentos, obter um documento
por MD5, salvar edições, aprovar conferência, gerenciar regras aprendidas,
busca full-text (FTS5), organização física de arquivos e uniformização de
nomes de instituições.
"""

__project__ = "JoaKinDeX"
__author__ = "Joaquim Ferreira Silva Neto"
__email__ = "joaquimfsneto@gmail.com"
__version__ = "1.0.0"

import json
import sqlite3
from datetime import datetime

from joakindex.db import (
    upsert_document,
    sync_to_json,
    get_all_documents,
    get_document_by_md5,
    update_conference_status,
    aprender_com_paginas_dossie,
    salvar_regra_aprendida,
    remover_regra_aprendida,
    obter_regras_aprendidas,
)
from joakindex.normalizer import normalizar_instituicao, uniformizar_base_dados


def handle_get_documentos(handler, server_ctx):
    dados = server_ctx.load_data()
    for item in dados:
        if "status_conferencia" not in item:
            item["status_conferencia"] = "pendente"
        for k in ["curso", "beneficiario", "faculdade", "natureza_curso", "tipo_documento", "carga_horaria", "cpf", "rg", "data", "valor_monetario", "dominio"]:
            v = item.get(k)
            if isinstance(v, list):
                item[k] = ", ".join(str(x) for x in v if x)
    body = json.dumps(dados, ensure_ascii=False).encode("utf-8")
    handler.send_response(200)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def handle_get_documento(handler, server_ctx, path):
    prefix = "/api/documento/" if path.startswith("/api/documento/") else "/api/document/"
    md5_req = path.split(prefix)[-1].strip().lower()
    dados = server_ctx.load_data()
    doc_found = next((item for item in dados if item.get("md5", "").lower() == md5_req), None)
    if not doc_found and server_ctx.db_path and server_ctx.db_path.exists():
        try:
            with sqlite3.connect(server_ctx.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cur = conn.cursor()
                row = cur.execute("SELECT * FROM documentos WHERE LOWER(md5) = ?", (md5_req,)).fetchone()
                if row:
                    doc_found = dict(row)
                    for col in ["metadados_adicionais", "assinaturas", "dados_extras", "todos_tipos", "todos_dominios", "paginas_detalhes"]:
                        if col in doc_found and isinstance(doc_found[col], str):
                            try:
                                doc_found[col] = json.loads(doc_found[col])
                            except Exception:
                                pass
        except Exception:
            pass
    if doc_found:
        body = json.dumps(doc_found, ensure_ascii=False).encode("utf-8")
        handler.send_response(200)
        handler.send_header("Content-Type", "application/json; charset=utf-8")
        handler.send_header("Content-Length", str(len(body)))
        handler.end_headers()
        handler.wfile.write(body)
    else:
        handler.send_error(404, f"Documento com MD5 {md5_req} não encontrado.")


def handle_get_regras_aprendidas(handler, server_ctx):
    try:
        regras = obter_regras_aprendidas(server_ctx.db_path)
    except Exception:
        regras = []
    body = json.dumps(regras, ensure_ascii=False).encode("utf-8")
    handler.send_response(200)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def handle_get_busca_fts(handler, server_ctx, parsed):
    import urllib.parse
    query = urllib.parse.parse_qs(parsed.query)
    q_termo = query.get("q", [""])[0].strip()
    limit = int(query.get("limit", [50])[0]) if query.get("limit", [""])[0].isdigit() else 50
    try:
        from joakindex.db import search_fts
        resultados = search_fts(server_ctx.db_path, q_termo, limit=limit)
    except Exception:
        resultados = []
    body = json.dumps(resultados, ensure_ascii=False).encode("utf-8")
    handler.send_response(200)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def handle_post_salvar(handler, server_ctx, payload) -> bool:
    """Retorna True se uma resposta HTTP foi enviada (payload válido), False caso contrário
    — quando False, o chamador deve deixar o roteamento cair no 404 padrão, igual ao
    comportamento original de não haver nenhum `return` dentro do bloco condicional."""
    item_editado = payload.get("item")
    if item_editado and "md5" in item_editado:
        item_editado.pop("data_criacao", None)
        if item_editado.get("faculdade"):
            item_editado["faculdade"] = normalizar_instituicao(item_editado.get("faculdade"))
        target_md5 = str(item_editado["md5"]).strip().lower()
        item_editado["md5"] = target_md5
        item_editado["revisado_em"] = datetime.now().isoformat()

        # 1. Gravação instantânea no SQLite WAL
        upsert_document(server_ctx.db_path, item_editado)

        # 2. Se existir pasta 'individuais' correspondente, atualiza o arquivo individual também
        indiv_dir = server_ctx.json_path.parent / "individuais"
        if indiv_dir.exists():
            indiv_file = indiv_dir / f"{target_md5}.json"
            try:
                with open(indiv_file, "w", encoding="utf-8") as fi:
                    json.dump(item_editado, fi, ensure_ascii=False, indent=2)
            except Exception:
                pass

        # 3. Sincronização atômica para JSON e TXT consolidado
        sync_to_json(server_ctx.db_path, server_ctx.json_path, only_processed=True)
        all_processed = get_all_documents(server_ctx.db_path, only_processed=True)
        server_ctx.update_txt_report(all_processed)

        # 4. Aprendizado Incremental se solicitado pelo usuário (Nível de Página e Documento)
        if payload.get("aprender_regra"):
            try:
                dossie_pgs = item_editado.get("dossie_paginas", [])
                if dossie_pgs:
                    aprender_com_paginas_dossie(
                        server_ctx.db_path,
                        target_md5,
                        dossie_pgs,
                        item_editado=item_editado
                    )

                termo = (item_editado.get("tipo_documento") or "").strip()
                if termo:
                    salvar_regra_aprendida(
                        server_ctx.db_path,
                        termo_chave=termo,
                        valor_atribuido=termo,
                        dominio=item_editado.get("dominio", "academico"),
                        campo_alvo="tipo_documento",
                        remover_pix=(item_editado.get("dominio") != "financeiro"),
                        origem_md5=target_md5
                    )
            except Exception as e:
                print(f"[Aviso] Falha ao registrar regra aprendida: {e}")

        resp = json.dumps({"status": "sucesso", "mensagem": "Documento salvo com sucesso!"}).encode("utf-8")
        handler.send_response(200)
        handler.send_header("Content-Type", "application/json; charset=utf-8")
        handler.send_header("Content-Length", str(len(resp)))
        handler.end_headers()
        handler.wfile.write(resp)
        return True
    return False


def handle_post_regras_aprendidas(handler, server_ctx, payload):
    action = payload.get("acao", "salvar")
    if action == "salvar":
        rid = salvar_regra_aprendida(
            server_ctx.db_path,
            termo_chave=payload.get("termo_chave", ""),
            valor_atribuido=payload.get("valor_atribuido", ""),
            dominio=payload.get("dominio", "academico"),
            campo_alvo=payload.get("campo_alvo", "tipo_documento"),
            remover_pix=bool(payload.get("remover_pix")),
            origem_md5=payload.get("origem_md5")
        )
        resp = json.dumps({"status": "sucesso", "regra_id": rid}).encode("utf-8")
    elif action == "remover":
        ok = remover_regra_aprendida(server_ctx.db_path, payload.get("id"))
        resp = json.dumps({"status": "sucesso" if ok else "erro"}).encode("utf-8")
    else:
        resp = json.dumps({"status": "erro", "mensagem": "Ação desconhecida"}).encode("utf-8")
    handler.send_response(200)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(resp)))
    handler.end_headers()
    handler.wfile.write(resp)


def handle_post_aprovar(handler, server_ctx, payload):
    target_md5 = str(payload.get("md5") or "").strip().lower()
    obs = payload.get("observacoes_conferencia")

    # 1. Atualização instantânea no SQLite WAL (< 0.1ms)
    updated = update_conference_status(server_ctx.db_path, target_md5, "aprovado", obs)

    if updated:
        # 2. Se existir pasta 'individuais' correspondente, atualiza o arquivo individual também
        indiv_dir = server_ctx.json_path.parent / "individuais"
        if indiv_dir.exists():
            indiv_file = indiv_dir / f"{target_md5}.json"
            if indiv_file.exists():
                try:
                    with open(indiv_file, "r", encoding="utf-8") as fi:
                        indiv_data = json.load(fi)
                    if isinstance(indiv_data, dict):
                        indiv_data["status_conferencia"] = "aprovado"
                        indiv_data["conferido_em"] = datetime.now().isoformat()
                        if obs is not None:
                            indiv_data["observacoes_conferencia"] = obs
                        with open(indiv_file, "w", encoding="utf-8") as fi:
                            json.dump(indiv_data, fi, ensure_ascii=False, indent=2)
                except Exception:
                    pass

        # 3. Sincronização atômica para JSON e TXT consolidado
        sync_to_json(server_ctx.db_path, server_ctx.json_path, only_processed=True)
        all_processed = get_all_documents(server_ctx.db_path, only_processed=True)
        server_ctx.update_txt_report(all_processed)

        # 4. Aprendizado Incremental se solicitado na aprovação
        if payload.get("aprender_regra"):
            try:
                doc_appr = get_document_by_md5(server_ctx.db_path, target_md5)
                if doc_appr:
                    dossie_pgs = doc_appr.get("dossie_paginas", [])
                    if isinstance(dossie_pgs, str):
                        try:
                            dossie_pgs = json.loads(dossie_pgs)
                        except Exception:
                            dossie_pgs = []
                    if dossie_pgs:
                        aprender_com_paginas_dossie(
                            server_ctx.db_path,
                            target_md5,
                            dossie_pgs,
                            item_editado=doc_appr
                        )
                    termo = (doc_appr.get("tipo_documento") or "").strip()
                    if termo:
                        salvar_regra_aprendida(
                            server_ctx.db_path,
                            termo_chave=termo,
                            valor_atribuido=termo,
                            dominio=doc_appr.get("dominio", "academico"),
                            campo_alvo="tipo_documento",
                            remover_pix=(doc_appr.get("dominio") != "financeiro"),
                            origem_md5=target_md5
                        )
            except Exception as e:
                print(f"[Aviso] Falha ao registrar regra aprendida na aprovação: {e}")

        resp = json.dumps({"status": "sucesso", "mensagem": "Conferência aprovada com sucesso!"}).encode("utf-8")
        handler.send_response(200)
        handler.send_header("Content-Type", "application/json; charset=utf-8")
        handler.send_header("Content-Length", str(len(resp)))
        handler.end_headers()
        handler.wfile.write(resp)
    else:
        handler.send_error(404, f"Documento MD5 {target_md5} não encontrado.")


def handle_post_organizar_arquivos(handler, server_ctx, payload):
    out_dir = payload.get("output_dir")
    if not out_dir:
        out_dir = str(server_ctx.db_path.parent / "saida_organizada")
    mode = payload.get("mode", "copy")
    dry_run = bool(payload.get("dry_run", True))
    try:
        from joakindex.dispatcher import organize_files
        res_org = organize_files(
            server_ctx.db_path,
            output_dir=out_dir,
            pdf_source_dir=server_ctx.pdf_dir,
            mode=mode,
            dry_run=dry_run
        )
    except Exception as e:
        res_org = {"status": "erro", "mensagem": str(e)}

    body = json.dumps(res_org, ensure_ascii=False).encode("utf-8")
    handler.send_response(200)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def handle_post_uniformizar_instituicoes(handler, server_ctx):
    try:
        res = uniformizar_base_dados(
            str(server_ctx.json_path),
            atualizar_individuais=True
        )
        server_ctx.load_data()
        resp = json.dumps(res, ensure_ascii=False).encode("utf-8")
        handler.send_response(200)
        handler.send_header("Content-Type", "application/json; charset=utf-8")
        handler.send_header("Content-Length", str(len(resp)))
        handler.end_headers()
        handler.wfile.write(resp)
    except Exception as ex_uni:
        err_resp = json.dumps({"status": "erro", "mensagem": str(ex_uni)}, ensure_ascii=False).encode("utf-8")
        handler.send_response(500)
        handler.send_header("Content-Type", "application/json; charset=utf-8")
        handler.send_header("Content-Length", str(len(err_resp)))
        handler.end_headers()
        handler.wfile.write(err_resp)
