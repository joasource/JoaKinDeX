#!/usr/bin/env python3
"""
JoaKinDeX - Processamento em Lote (Batch) e Exportação em Massa
Criado por: Joaquim Ferreira Silva Neto <joaquimfsneto@gmail.com>

Gerencia a execução assíncrona de processamento em lote em background
(BatchManager) e as rotas HTTP relacionadas: status, iniciar, interromper,
aprovação em massa, alteração em massa de metadados e exportação de
documentos selecionados em ZIP.
"""

__project__ = "JoaKinDeX"
__author__ = "Joaquim Ferreira Silva Neto"
__email__ = "joaquimfsneto@gmail.com"
__version__ = "1.0.0"

import io
import json
import threading
import time
import urllib.parse
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from joakindex.db import (
    batch_update_conference_status,
    batch_update_tag_domain,
    get_all_documents,
    get_db_path,
    init_database,
    sync_to_json,
)
from joakindex.normalizer import normalizar_instituicao

try:
    from joakindex.cli import run_batch_classification
except ImportError:
    run_batch_classification = None


class BatchManager:
    """Gerencia a execução assíncrona de processamento em lote em background."""
    def __init__(self, server_ctx):
        self.server_ctx = server_ctx
        self.lock = threading.Lock()
        self.thread: Optional[threading.Thread] = None
        self.stop_requested = False
        self.is_running = False
        self.state: Dict[str, Any] = {
            "is_running": False,
            "status": "idle",  # idle, indexing, running, completed, stopped, error
            "message": "Nenhum lote em andamento.",
            "total_files": 0,
            "already_done_count": 0,
            "to_process_count": 0,
            "processed_count": 0,
            "success_count": 0,
            "error_count": 0,
            "current_file": "",
            "percentage": 0.0,
            "start_time": None,
            "start_time_epoch": None,
            "elapsed_seconds": 0,
            "logs": [],
            "last_summary": None
        }

    def _add_log(self, text: str):
        ts = datetime.now().strftime("%H:%M:%S")
        with self.lock:
            logs = self.state.setdefault("logs", [])
            logs.append(f"[{ts}] {text}")
            if len(logs) > 120:
                self.state["logs"] = logs[-120:]

    def get_status(self) -> Dict[str, Any]:
        with self.lock:
            st = dict(self.state)
            if self.is_running and st.get("start_time_epoch"):
                st["elapsed_seconds"] = int(time.time() - st["start_time_epoch"])
            return st

    def stop(self) -> Tuple[bool, str]:
        with self.lock:
            if not self.is_running:
                return False, "Nenhum lote em andamento para interromper."
            self.stop_requested = True
            self.state["message"] = "Interrupção solicitada pelo usuário. Finalizando arquivos em andamento..."
        self._add_log("🛑 Interrupção solicitada pelo usuário. Gravando progresso e cancelando fila...")
        return True, "Sinal de interrupção enviado com sucesso. O processamento será finalizado com segurança."

    def start(self, params: Dict[str, Any]) -> Tuple[bool, str]:
        with self.lock:
            if self.is_running:
                return False, "Já existe um processamento em lote em andamento."
            self.is_running = True
            self.stop_requested = False
            now_dt = datetime.now()
            self.state = {
                "is_running": True,
                "status": "indexing",
                "message": "Iniciando verificação de arquivos e modelos...",
                "total_files": 0,
                "already_done_count": 0,
                "to_process_count": 0,
                "processed_count": 0,
                "success_count": 0,
                "error_count": 0,
                "current_file": "",
                "percentage": 0.0,
                "start_time": now_dt.isoformat(),
                "start_time_epoch": time.time(),
                "elapsed_seconds": 0,
                "logs": [],
                "last_summary": None
            }

        self._add_log("🚀 Iniciando processamento em lote...")
        self.thread = threading.Thread(target=self._run_worker, args=(params,), daemon=True)
        self.thread.start()
        return True, "Processamento em lote iniciado com sucesso!"

    def _run_worker(self, params: Dict[str, Any]):
        try:
            input_dir = params.get("input") or params.get("pdf_dir") or str(self.server_ctx.pdf_dir)
            out_dir = params.get("output_dir") or params.get("json_path")
            if out_dir:
                p_out = Path(out_dir).expanduser()
                if p_out.suffix.lower() == ".json":
                    out_dir = str(p_out.parent)
                else:
                    out_dir = str(p_out)
            else:
                out_dir = str(self.server_ctx.json_path.parent)

            provider = params.get("provider") or self.server_ctx.provider
            model = params.get("model") or self.server_ctx.model
            ollama_url = params.get("ollama_url") or self.server_ctx.ollama_url
            docker = params.get("docker")
            openai_key = params.get("openai_key")
            openai_base_url = params.get("openai_base_url")

            workers = int(params.get("workers", 1))
            max_pages = int(params.get("max_pages", 4))
            skip_ocr = bool(params.get("skip_ocr", False))
            reprocess_ocr = bool(params.get("reprocess_ocr", False))
            force = bool(params.get("force", False))
            no_individual = bool(params.get("no_individual", False))
            hybrid = bool(params.get("hybrid", getattr(self.server_ctx, "hybrid", False)))
            hybrid_cloud_model = str(params.get("hybrid_cloud_model") or getattr(self.server_ctx, "hybrid_cloud_model", "gpt-4o-mini"))

            mode_label = "Forçar Todos" if force else ("Reprocessar OCR" if reprocess_ocr else "Incremental")
            h_info = f" | Híbrido (Fallback -> {hybrid_cloud_model})" if hybrid else ""
            self._add_log(f"Parâmetros: Modo={mode_label} | Provedor={provider} | Modelo={model or 'padrão'}{h_info} | Workers={workers}")
            self._add_log(f"Diretórios: Entrada='{input_dir}' | Saída='{out_dir}'")

            def progress_callback(event: Dict[str, Any]):
                ev_type = event.get("event")
                with self.lock:
                    if ev_type == "init":
                        tot = event.get("total_files", 0)
                        self.state["total_files"] = tot
                        self.state["message"] = f"Identificados {tot} arquivos PDF."
                    elif ev_type == "indexing":
                        self.state["status"] = "indexing"
                        self.state["message"] = event.get("message", "Indexando integridade (MD5)...")
                    elif ev_type == "indexing_progress":
                        idx = event.get("indexed", 0)
                        tot = event.get("total", 0)
                        self.state["message"] = f"Indexando MD5: {idx}/{tot} PDFs..."
                    elif ev_type == "ready":
                        self.state["status"] = "running"
                        self.state["total_files"] = event.get("total_files", 0)
                        self.state["already_done_count"] = event.get("already_done", 0)
                        self.state["to_process_count"] = event.get("to_process", 0)
                        to_proc = event.get("to_process", 0)
                        alr_done = event.get("already_done", 0)
                        tot = event.get("total_files", 0)
                        self.state["message"] = f"{to_proc} PDFs a processar ({alr_done} já prontos)."
                        if tot > 0:
                            self.state["percentage"] = round((alr_done / tot) * 100, 1)
                    elif ev_type == "file_start":
                        self.state["current_file"] = event.get("current_file", "")
                        self.state["message"] = f"Processando {event.get('current_file', '')}..."
                    elif ev_type == "file_done":
                        self.state["status"] = "running"
                        cur_f = event.get("current_file", "")
                        self.state["current_file"] = cur_f
                        proc = event.get("processed_count", 0)
                        to_proc = event.get("to_process_count", 1)
                        tot = event.get("total_files", 0)
                        alr = self.state.get("already_done_count", 0)
                        self.state["processed_count"] = proc
                        self.state["success_count"] = event.get("success_count", 0)
                        self.state["error_count"] = event.get("error_count", 0)

                        if tot > 0:
                            pct = min(100.0, round(((alr + proc) / tot) * 100, 1))
                            self.state["percentage"] = pct

                        self.state["message"] = f"Processados {proc}/{to_proc} ({self.state['percentage']}%) - Último: {cur_f}"
                    elif ev_type == "periodic_save":
                        self.state["message"] = f"Progresso salvo no banco consolidado ({event.get('total_saved')} docs)."
                    elif ev_type == "up_to_date":
                        self.state["percentage"] = 100.0
                        self.state["message"] = "Todos os documentos já estão atualizados."
                    elif ev_type == "stopped":
                        self.state["status"] = "stopped"
                        self.state["message"] = event.get("message", "Processamento interrompido.")
                    elif ev_type == "completed":
                        self.state["status"] = "completed"
                        self.state["percentage"] = 100.0
                        self.state["message"] = event.get("message", "Processamento concluído com sucesso!")
                    elif ev_type == "error":
                        self.state["status"] = "error"
                        self.state["message"] = event.get("error", "Erro durante o processamento.")

                if ev_type == "file_done":
                    res_item = event.get("item", {})
                    s_icon = "✓" if res_item.get("status") == "sucesso" else "✗"
                    ben = res_item.get("beneficiario") or res_item.get("curso") or ""
                    extra = f" ({ben})" if ben else ""
                    self._add_log(f"[{s_icon}] {event.get('current_file')}{extra} -> {res_item.get('tipo_documento', 'N/D')}")
                elif ev_type in ["ready", "periodic_save", "completed", "stopped", "up_to_date"]:
                    self._add_log(f"ℹ️ {self.state['message']}")

            if not run_batch_classification:
                raise RuntimeError("Função run_batch_classification não pôde ser importada de joakindex.py")

            summary = run_batch_classification(
                input_path=input_dir,
                output_dir=out_dir,
                provider=provider,
                model=model,
                ollama_url=ollama_url,
                docker=docker,
                openai_key=openai_key,
                openai_base_url=openai_base_url,
                workers=workers,
                max_pages=max_pages,
                skip_ocr=skip_ocr,
                reprocess_ocr=reprocess_ocr,
                force=force,
                no_individual=no_individual,
                progress_callback=progress_callback,
                stop_checker=lambda: self.stop_requested,
                use_tqdm=False,
                hybrid=hybrid,
                hybrid_cloud_model=hybrid_cloud_model
            )

            with self.lock:
                self.state["last_summary"] = summary
                if summary.get("status") == "interrompido":
                    self.state["status"] = "stopped"
                    self.state["message"] = "Processamento interrompido pelo usuário."
                elif summary.get("status") == "erro":
                    self.state["status"] = "error"
                    self.state["message"] = summary.get("mensagem", "Erro no processamento.")
                else:
                    self.state["status"] = "completed"
                    self.state["percentage"] = 100.0
                    self.state["message"] = "Processamento concluído com sucesso!"

            self._add_log(f"🏁 Conclusão do lote: {self.state['message']}")

        except Exception as e:
            with self.lock:
                self.state["status"] = "error"
                self.state["message"] = f"Erro inesperado no lote: {e}"
            self._add_log(f"❌ Erro fatal: {e}")
        finally:
            with self.lock:
                self.is_running = False
                self.state["is_running"] = False
                self.stop_requested = False
            try:
                self.server_ctx.build_pdf_index()
                self.server_ctx.load_data()
            except Exception:
                pass


def create_documents_zip(server_ctx, md5_list: List[str]) -> io.BytesIO:
    """Gera um arquivo ZIP em memória contendo os documentos físicos correspondentes aos MD5s solicitados."""
    zip_buffer = io.BytesIO()
    seen_names: Dict[str, int] = {}
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for m in md5_list:
            md5_clean = str(m).strip().lower()
            if not md5_clean:
                continue
            file_path = server_ctx.md5_to_file.get(md5_clean)
            if not file_path or not file_path.exists():
                server_ctx.build_pdf_index()
                file_path = server_ctx.md5_to_file.get(md5_clean)
            if not file_path or not file_path.exists():
                continue

            base_name = file_path.name
            if base_name in seen_names:
                seen_names[base_name] += 1
                stem = file_path.stem
                suffix = file_path.suffix
                arcname = f"{stem}_{md5_clean[:6]}_{seen_names[base_name]}{suffix}"
            else:
                seen_names[base_name] = 1
                arcname = base_name

            try:
                zf.write(file_path, arcname=arcname)
            except Exception:
                pass

    zip_buffer.seek(0)
    return zip_buffer


# ---------------------------------------------------------------------------
# Rotas HTTP (recebem o RequestHandler como `handler` para responder direto)
# ---------------------------------------------------------------------------
def handle_get_batch_status(handler, server_ctx):
    status = server_ctx.batch_manager.get_status()
    body = json.dumps(status, ensure_ascii=False).encode("utf-8")
    handler.send_response(200)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def handle_get_batch_exportar_zip(handler, server_ctx, parsed):
    query = urllib.parse.parse_qs(parsed.query)
    md5s_raw = query.get("md5s", [""])[0]
    md5_list = [m.strip().lower() for m in md5s_raw.split(",") if m.strip()]
    if not md5_list:
        handler.send_error(400, "Nenhum MD5 fornecido para exportação em lote.")
        return
    zip_buffer = create_documents_zip(server_ctx, md5_list)
    zip_bytes = zip_buffer.getvalue()
    handler.send_response(200)
    handler.send_header("Content-Type", "application/zip")
    handler.send_header("Content-Disposition", f'attachment; filename="joakindex_documentos_lote_{datetime.now().strftime("%Y%m%d_%H%M%S")}.zip"')
    handler.send_header("Content-Length", str(len(zip_bytes)))
    handler.end_headers()
    handler.wfile.write(zip_bytes)


def handle_post_batch_exportar_zip(handler, server_ctx, payload):
    md5_list = [str(m).strip().lower() for m in payload.get("md5s", []) if m]
    if not md5_list:
        handler.send_error(400, "Nenhum MD5 fornecido para exportação em lote.")
        return
    zip_buffer = create_documents_zip(server_ctx, md5_list)
    zip_bytes = zip_buffer.getvalue()
    handler.send_response(200)
    handler.send_header("Content-Type", "application/zip")
    handler.send_header("Content-Disposition", f'attachment; filename="joakindex_documentos_lote_{datetime.now().strftime("%Y%m%d_%H%M%S")}.zip"')
    handler.send_header("Content-Length", str(len(zip_bytes)))
    handler.end_headers()
    handler.wfile.write(zip_bytes)


def handle_post_batch_aprovar(handler, server_ctx, payload):
    md5_list = [str(m).strip().lower() for m in payload.get("md5s", []) if m]
    obs = payload.get("observacoes_conferencia")
    if not md5_list:
        handler.send_error(400, "Lista de MD5s vazia para aprovação em lote.")
        return

    count = batch_update_conference_status(server_ctx.db_path, md5_list, "aprovado", obs)

    # Atualiza arquivos individuais se existirem
    indiv_dir = server_ctx.json_path.parent / "individuais"
    if indiv_dir.exists():
        now_iso = datetime.now().isoformat()
        for m in md5_list:
            indiv_file = indiv_dir / f"{m}.json"
            if indiv_file.exists():
                try:
                    with open(indiv_file, "r", encoding="utf-8") as fi:
                        indiv_data = json.load(fi)
                    if isinstance(indiv_data, dict):
                        indiv_data["status_conferencia"] = "aprovado"
                        indiv_data["conferido_em"] = now_iso
                        if obs is not None:
                            indiv_data["observacoes_conferencia"] = obs
                        with open(indiv_file, "w", encoding="utf-8") as fi:
                            json.dump(indiv_data, fi, ensure_ascii=False, indent=2)
                except Exception:
                    pass

    sync_to_json(server_ctx.db_path, server_ctx.json_path, only_processed=True)
    all_processed = get_all_documents(server_ctx.db_path, only_processed=True)
    server_ctx.update_txt_report(all_processed)

    resp = json.dumps({
        "status": "sucesso",
        "count": count,
        "mensagem": f"{count} documento(s) aprovado(s) com sucesso!"
    }, ensure_ascii=False).encode("utf-8")
    handler.send_response(200)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(resp)))
    handler.end_headers()
    handler.wfile.write(resp)


def handle_post_batch_alterar_tipo(handler, server_ctx, payload):
    md5_list = [str(m).strip().lower() for m in payload.get("md5s", []) if m]
    if not md5_list:
        handler.send_error(400, "Lista de MD5s vazia para alteração em lote.")
        return

    tipo_doc = payload.get("tipo_documento")
    dom = payload.get("dominio")
    fac = payload.get("faculdade")
    if fac:
        fac = normalizar_instituicao(fac)
    conf_st = payload.get("status_conferencia")

    count = batch_update_tag_domain(
        server_ctx.db_path,
        md5_list,
        tipo_documento=tipo_doc,
        dominio=dom,
        faculdade=fac,
        status_conferencia=conf_st
    )

    # Atualiza arquivos individuais se existirem
    indiv_dir = server_ctx.json_path.parent / "individuais"
    if indiv_dir.exists():
        now_iso = datetime.now().isoformat()
        for m in md5_list:
            indiv_file = indiv_dir / f"{m}.json"
            if indiv_file.exists():
                try:
                    with open(indiv_file, "r", encoding="utf-8") as fi:
                        indiv_data = json.load(fi)
                    if isinstance(indiv_data, dict):
                        if tipo_doc:
                            indiv_data["tipo_documento"] = tipo_doc
                            indiv_data["todos_tipos"] = [tipo_doc]
                        if dom:
                            indiv_data["dominio"] = dom
                            indiv_data["todos_dominios"] = [dom]
                        if fac:
                            indiv_data["faculdade"] = fac
                        if conf_st:
                            indiv_data["status_conferencia"] = conf_st
                            if conf_st == "aprovado":
                                indiv_data["conferido_em"] = now_iso
                        indiv_data["revisado_em"] = now_iso
                        with open(indiv_file, "w", encoding="utf-8") as fi:
                            json.dump(indiv_data, fi, ensure_ascii=False, indent=2)
                except Exception:
                    pass

    sync_to_json(server_ctx.db_path, server_ctx.json_path, only_processed=True)
    all_processed = get_all_documents(server_ctx.db_path, only_processed=True)
    server_ctx.update_txt_report(all_processed)

    resp = json.dumps({
        "status": "sucesso",
        "count": count,
        "mensagem": f"{count} documento(s) atualizado(s) com sucesso!"
    }, ensure_ascii=False).encode("utf-8")
    handler.send_response(200)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(resp)))
    handler.end_headers()
    handler.wfile.write(resp)


def handle_post_batch_start(handler, server_ctx, payload):
    # Import tardio para evitar dependência circular com joakindex.server no carregamento do módulo.
    from joakindex.server import resolve_pdf_dir, resolve_json_path

    if payload:
        new_pdf = payload.get("docs_dir") or payload.get("input_dir") or payload.get("pdf_dir") or payload.get("input")
        if new_pdf:
            p_pdf = Path(resolve_pdf_dir(new_pdf)).expanduser().resolve()
            if p_pdf != server_ctx.pdf_dir:
                server_ctx.pdf_dir = p_pdf
                server_ctx.build_pdf_index()
        new_json = payload.get("data_path") or payload.get("json_path") or payload.get("output_dir")
        if new_json:
            p_json = Path(resolve_json_path(new_json)).expanduser().resolve()
            if p_json != server_ctx.json_path:
                server_ctx.json_path = p_json
                server_ctx.db_path = get_db_path(p_json)
                init_database(server_ctx.db_path, initial_json_path=server_ctx.json_path)
                server_ctx.load_data()

    ok, msg = server_ctx.batch_manager.start(payload)
    resp = json.dumps({
        "status": "sucesso" if ok else "erro",
        "mensagem": msg,
        "batch_status": server_ctx.batch_manager.get_status()
    }, ensure_ascii=False).encode("utf-8")
    handler.send_response(200 if ok else 400)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(resp)))
    handler.end_headers()
    handler.wfile.write(resp)


def handle_post_batch_stop(handler, server_ctx):
    ok, msg = server_ctx.batch_manager.stop()
    resp = json.dumps({
        "status": "sucesso" if ok else "aviso",
        "mensagem": msg,
        "batch_status": server_ctx.batch_manager.get_status()
    }, ensure_ascii=False).encode("utf-8")
    handler.send_response(200)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(resp)))
    handler.end_headers()
    handler.wfile.write(resp)
