#!/usr/bin/env python3
"""
JoaKinDeX - Rotas de Análise, Duplicatas, Dossiês e Relatórios
Criado por: Joaquim Ferreira Silva Neto <joaquimfsneto@gmail.com>

Rotas HTTP de análise sobre a base já indexada: detecção e resolução de
duplicatas, agrupamento e exportação de dossiês por entidade, estatísticas
gerenciais e relatório executivo em PDF, e inspeção forense (assinaturas
digitais / PAdES) de um documento específico.
"""

__project__ = "JoaKinDeX"
__author__ = "Joaquim Ferreira Silva Neto"
__email__ = "joaquimfsneto@gmail.com"
__version__ = "1.0.0"

import json
import logging
import urllib.parse


def _send_json(handler, status: int, obj):
    body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def handle_get_duplicatas(handler, server_ctx):
    try:
        from joakindex.deduplication import detect_duplicates
        dups = detect_duplicates(server_ctx.db_path)
    except Exception:
        dups = []
    _send_json(handler, 200, dups)


def handle_get_duplicatas_comparar(handler, server_ctx, parsed):
    query_params = urllib.parse.parse_qs(parsed.query)
    base_md5 = query_params.get("base", [""])[0].strip().lower()
    copia_md5 = query_params.get("copia", [""])[0].strip().lower()
    try:
        from joakindex.deduplication import compare_duplicate_pair
        comp_res = compare_duplicate_pair(server_ctx.db_path, base_md5, copia_md5)
    except Exception as e:
        comp_res = {"erro": str(e)}
    _send_json(handler, 200 if "erro" not in comp_res else 400, comp_res)


def handle_post_duplicatas_resolver(handler, server_ctx, payload):
    target_md5 = str(payload.get("md5") or "").strip().lower()
    descartar = bool(payload.get("descartar", False))
    try:
        from joakindex.deduplication import resolve_duplicate
        ok = resolve_duplicate(server_ctx.db_path, target_md5, descartar=descartar)
        res_dup = {"status": "sucesso" if ok else "erro"}
    except Exception as e:
        res_dup = {"status": "erro", "mensagem": str(e)}
    _send_json(handler, 200, res_dup)


def handle_get_dossies(handler, server_ctx):
    try:
        from joakindex.dossier import get_all_dossiers
        dossiers = get_all_dossiers(server_ctx.db_path)
    except Exception:
        dossiers = []
    _send_json(handler, 200, dossiers)


def handle_post_dossies_gerar(handler, server_ctx):
    try:
        from joakindex.dossier import build_and_save_dossiers
        dossiers = build_and_save_dossiers(server_ctx.db_path)
        res_dos = {"status": "sucesso", "total_dossies": len(dossiers), "dossies": dossiers}
    except Exception as e:
        res_dos = {"status": "erro", "mensagem": str(e)}
    _send_json(handler, 200, res_dos)


def handle_post_dossies_exportar(handler, server_ctx, payload):
    dossie_id = str(payload.get("dossie_id") or "").strip()
    out_name = f"{dossie_id}_unificado.pdf"
    out_path = server_ctx.db_path.parent / "dossies_exportados" / out_name
    try:
        from joakindex.dossier import export_dossier_pdf
        ok, msg = export_dossier_pdf(server_ctx.db_path, dossie_id, out_path, pdf_base_dir=server_ctx.pdf_dir)
        res_exp = {"status": "sucesso" if ok else "erro", "mensagem": msg, "caminho": str(out_path)}
    except Exception as e:
        res_exp = {"status": "erro", "mensagem": str(e)}
    _send_json(handler, 200, res_exp)


def handle_get_estatisticas_gerenciais(handler, server_ctx, parsed):
    query_params = urllib.parse.parse_qs(parsed.query)
    b_str = query_params.get("brackets", [""])[0]
    brackets = None
    if b_str:
        try:
            brackets = [float(x.strip()) for x in b_str.split(",") if x.strip()]
        except Exception:
            brackets = None
    try:
        from joakindex.audit_report import get_management_statistics
        stats = get_management_statistics(server_ctx.db_path, brackets=brackets)
    except Exception as e:
        stats = {"erro": str(e)}
    _send_json(handler, 200, stats)


def handle_get_relatorio_pdf(handler, server_ctx, parsed):
    try:
        from joakindex.audit_report import generate_executive_audit_report
        temp_pdf = server_ctx.db_path.parent / "relatorio_auditoria_joakindex.pdf"
        query = urllib.parse.parse_qs(parsed.query)
        brackets_param = query.get("brackets", [None])[0]
        brackets = None
        if brackets_param:
            try:
                brackets = [float(x.strip()) for x in brackets_param.split(",") if x.strip()]
            except Exception:
                brackets = None
        generate_executive_audit_report(server_ctx.db_path, temp_pdf, brackets=brackets)
        content = temp_pdf.read_bytes()
        handler.send_response(200)
        handler.send_header("Content-Type", "application/pdf")
        handler.send_header("Content-Disposition", 'attachment; filename="relatorio_auditoria_joakindex.pdf"')
        handler.send_header("Content-Length", str(len(content)))
        handler.end_headers()
        handler.wfile.write(content)
    except Exception as e:
        handler.send_error(500, f"Erro ao gerar relatório de auditoria: {e}")


def handle_get_inspecionar(handler, server_ctx, path):
    md5_req = path.split("/api/inspecionar/")[-1].strip().lower()
    pdf_file = server_ctx.md5_to_file.get(md5_req)
    if pdf_file and pdf_file.exists():
        try:
            from joakindex.inspector import inspect_pdf
            res_insp = inspect_pdf(pdf_file)
            if server_ctx.db_path and "erro" not in res_insp:
                try:
                    from joakindex.db import update_inspection_status
                    update_inspection_status(
                        server_ctx.db_path,
                        md5_req,
                        eh_nativo_digital=res_insp.get("eh_nativo_digital", False),
                        tem_assinatura_digital=res_insp.get("tem_assinatura_digital", False),
                        info_assinaturas=res_insp.get("info_assinaturas") or res_insp.get("assinaturas", [])
                    )
                except Exception as db_err:
                    logging.warning("Falha ao salvar inspeção no banco: %s", db_err)
        except Exception as e:
            res_insp = {"erro": str(e)}
    else:
        res_insp = {"erro": "Arquivo PDF não encontrado no disco"}
    _send_json(handler, 200, res_insp)
