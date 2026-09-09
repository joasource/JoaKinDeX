#!/usr/bin/env python3
"""
JoaKinDeX - Central de Indexação & Conferência Documental (Servidor Web)
Criado por: Joaquim Ferreira Silva Neto <joaquimfsneto@gmail.com>

Permite visualizar o PDF lado a lado com o JSON extraído, editar dados e salvar alterações.
"""

__project__ = "JoaKinDeX"
__author__ = "Joaquim Ferreira Silva Neto"
__email__ = "joaquimfsneto@gmail.com"
__version__ = "1.0.0"

import os
import sys
import json
import time
import hashlib
import argparse
import threading
import socket
from pathlib import Path
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
import urllib.parse
import io
import zipfile
import subprocess
import shutil
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple, Union

try:
    import pypdfium2 as pdfium
except ImportError:
    pdfium = None

_PDFIUM_LOCK = threading.Lock()

try:
    from PIL import Image
except ImportError:
    Image = None


class ReusableThreadingHTTPServer(ThreadingHTTPServer):
    allow_reuse_address = True
    daemon_threads = True

try:
    from joakindex import (
        process_single_pdf,
        OllamaClient,
        OpenAIClient,
        run_batch_classification,
        detect_ollama_environments,
        get_available_ollama_models
    )
except Exception:
    import importlib.util
    main_py = Path(__file__).parent / "joakindex.py"
    spec = importlib.util.spec_from_file_location("joakindex", main_py)
    joakindex = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(joakindex)
    process_single_pdf = joakindex.process_single_pdf
    OllamaClient = joakindex.OllamaClient
    OpenAIClient = joakindex.OpenAIClient
    run_batch_classification = getattr(joakindex, "run_batch_classification", None)
    detect_ollama_environments = getattr(joakindex, "detect_ollama_environments", None)
    get_available_ollama_models = getattr(joakindex, "get_available_ollama_models", None)

try:
    from config_manager import (
        get_visualizer_config,
        save_visualizer_config,
        reset_visualizer_config,
        get_classifier_config,
        save_classifier_config,
        reset_classifier_config,
        reset_all_config,
        has_custom_config,
        get_factory_defaults
    )
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from config_manager import (
        get_visualizer_config,
        save_visualizer_config,
        reset_visualizer_config,
        get_classifier_config,
        save_classifier_config,
        reset_classifier_config,
        reset_all_config,
        has_custom_config,
        get_factory_defaults
    )

try:
    from normalizador_instituicoes import normalizar_instituicao, uniformizar_base_dados
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from normalizador_instituicoes import normalizar_instituicao, uniformizar_base_dados

try:
    from db_manager import (
        get_db_path,
        init_database,
        upsert_document,
        upsert_documents_batch,
        get_document_by_md5,
        get_all_documents,
        update_conference_status,
        batch_update_conference_status,
        batch_update_tag_domain,
        sync_to_json
    )
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from db_manager import (
        get_db_path,
        init_database,
        upsert_document,
        upsert_documents_batch,
        get_document_by_md5,
        get_all_documents,
        update_conference_status,
        batch_update_conference_status,
        batch_update_tag_domain,
        sync_to_json
    )


def clean_path_input(raw: Any) -> str:
    """Remove aspas simples/duplas e espaços das extremidades de caminhos colados no console."""
    if not raw:
        return ""
    s = str(raw).strip()
    while (s.startswith('"') and s.endswith('"')) or (s.startswith("'") and s.endswith("'")):
        s = s[1:-1].strip()
    if len(s) > 1 and s.endswith("/"):
        s = s.rstrip("/")
    return s


def resolve_pdf_dir(specified_dir: str = None) -> str:
    """Retorna o diretório de PDFs padrão neutro ou o caminho especificado limpo."""
    if not specified_dir:
        return "./pdf"
    clean = clean_path_input(specified_dir)
    if clean in ["./pdf", "pdf", ""]:
        return "./pdf"
    p = Path(clean).expanduser()
    if p.is_file():
        p = p.parent
    return str(p.resolve())


def resolve_json_path(specified_json: str = None) -> str:
    """
    Resolve o caminho do arquivo JSON. Se for informado um diretório ou pasta de saída,
    retorna o caminho completo para classificacao_diplomas.json.
    """
    if not specified_json:
        return "./saida/classificacao_diplomas.json"
    clean = clean_path_input(specified_json)
    if clean in ["./saida/classificacao_diplomas.json", "saida/classificacao_diplomas.json", "./saida", "saida", ""]:
        return "./saida/classificacao_diplomas.json"
    p = Path(clean).expanduser()
    if p.is_dir():
        return str((p / "classificacao_diplomas.json").resolve())
    if p.suffix.lower() == ".json":
        return str(p.resolve())
    return str((p / "classificacao_diplomas.json").resolve())


def is_port_in_use(port: int, host: str = "0.0.0.0") -> bool:
    """Verifica se uma porta TCP já está em uso na máquina."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind((host, port))
            return False
        except OSError:
            return True


def find_available_port(start_port: int = 8088, host: str = "0.0.0.0", max_tries: int = 50) -> int:
    """Encontra a próxima porta livre a partir de start_port."""
    port = start_port
    for _ in range(max_tries):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                s.bind((host, port))
                return port
            except OSError:
                port += 1
    return start_port


def prompt_interactive_config(default_pdf_dir: str, default_json_path: str, default_port: int):
    """
    Exibe menu interativo no console permitindo ao usuário escolher ou alterar
    as pastas de entrada de PDFs e de saída de JSONs antes de iniciar o servidor.
    """
    print("\n" + "=" * 70)
    print("⚙️  JoaKinDeX - CONFIGURAÇÃO DO VISUALIZADOR")
    print("   Criado por: Joaquim Ferreira Silva Neto <joaquimfsneto@gmail.com>")
    print("=" * 70)
    print("Pressione ENTER para aceitar o valor padrão sugerido entre colchetes.\n")

    default_pdf_dir = resolve_pdf_dir(default_pdf_dir)
    default_json_path = resolve_json_path(default_json_path)

    # Opção inicial se houver configurações personalizadas salvas
    if has_custom_config("visualizador"):
        print("⚙️  Configurações salvas da execução anterior detectadas:")
        print("   1) Continuar e personalizar configurações salvas [Padrão]")
        print("   2) Restaurar todos os padrões de fábrica (limpar configurações salvas)")
        try:
            init_choice = input("Escolha a opção (1 ou 2) [1]: ").strip()
            if init_choice == "2":
                reset_visualizer_config()
                factory = get_factory_defaults()["visualizador"]
                default_pdf_dir = resolve_pdf_dir(factory["pdf_dir"])
                default_json_path = resolve_json_path(factory["json_path"])
                default_port = factory["port"]
                print("   [✓] Configurações do visualizador restauradas para os padrões de fábrica neutros!\n")
        except (EOFError, KeyboardInterrupt):
            print("\n[Operação cancelada pelo usuário]")
            sys.exit(0)

    # 1. Pasta de PDFs
    chosen_pdf_dir = default_pdf_dir
    while True:
        try:
            resp_pdf = input(f"📁 Pasta dos PDFs [{default_pdf_dir}]: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n[Operação cancelada pelo usuário]")
            sys.exit(0)

        clean_pdf = clean_path_input(resp_pdf)
        if clean_pdf.lower() in ["reset", "resetar", "padrao", "fábrica", "fabrica"]:
            reset_visualizer_config()
            factory = get_factory_defaults()["visualizador"]
            default_pdf_dir = resolve_pdf_dir(factory["pdf_dir"])
            default_json_path = resolve_json_path(factory["json_path"])
            default_port = factory["port"]
            print("   [✓] Configurações restauradas para os padrões de fábrica neutros!")
            continue

        if not clean_pdf:
            chosen_pdf_dir = default_pdf_dir
            break
        else:
            p = Path(clean_pdf).expanduser().resolve()
            if p.is_file():
                p = p.parent
            if not p.exists() or not p.is_dir():
                print(f"   ⚠️  Aviso: Diretório '{p}' não existe ou não é uma pasta.")
                try:
                    conf = input("   Deseja utilizar esse caminho mesmo assim? (s/N): ").strip().lower()
                except (EOFError, KeyboardInterrupt):
                    sys.exit(0)
                if conf in ["s", "sim", "y", "yes"]:
                    chosen_pdf_dir = str(p)
                    break
            else:
                chosen_pdf_dir = str(p)
                break

    # 2. Pasta de saída ou arquivo JSON
    chosen_json_path = default_json_path
    while True:
        try:
            resp_json = input(f"\n📄 Pasta de saída ou arquivo JSON [{default_json_path}]: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n[Operação cancelada pelo usuário]")
            sys.exit(0)

        clean_json = clean_path_input(resp_json)
        if clean_json.lower() in ["reset", "resetar", "padrao", "fábrica", "fabrica"]:
            reset_visualizer_config()
            factory = get_factory_defaults()["visualizador"]
            default_json_path = resolve_json_path(factory["json_path"])
            print("   [✓] Caminho do JSON restaurado para o padrão de fábrica neutro!")
            continue

        if not clean_json:
            chosen_json_path = default_json_path
            break
        else:
            p_str = resolve_json_path(clean_json)
            p = Path(p_str).expanduser().resolve()
            if not p.exists():
                print(f"   ℹ️  Arquivo '{p_str}' ainda não existe (será criado ao salvar).")
            else:
                print(f"   ↳ Arquivo de dados JSON identificado: '{p_str}'")
            chosen_json_path = str(p)
            break

    # 3. Porta
    suggested_port = default_port
    if is_port_in_use(suggested_port):
        suggested_port = find_available_port(suggested_port if suggested_port != 8080 else 8088)

    chosen_port = suggested_port
    while True:
        try:
            resp_port = input(f"\n🌐 Porta HTTP [{suggested_port}]: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n[Operação cancelada pelo usuário]")
            sys.exit(0)

        if not resp_port:
            chosen_port = suggested_port
            break
        try:
            p_val = int(resp_port)
            if 1 <= p_val <= 65535:
                if is_port_in_use(p_val):
                    print(f"   ⚠️  Aviso: A porta {p_val} já está em uso por outro serviço na máquina.")
                    alt_free = find_available_port(p_val + 1)
                    print(f"       Recomendamos utilizar a porta {alt_free} ou outra porta livre.")
                    continue
                chosen_port = p_val
                break
            else:
                print("   ⚠️  Porta inválida (deve estar entre 1 e 65535).")
        except ValueError:
            print("   ⚠️  Digite um número de porta válido.")

    # Salva opções configuradas no visualizador de forma garantida
    save_visualizer_config({
        "pdf_dir": str(chosen_pdf_dir),
        "json_path": str(chosen_json_path),
        "port": chosen_port
    })

    print("=" * 70 + "\n")
    return chosen_pdf_dir, chosen_json_path, chosen_port

def calculate_md5(file_path: Path) -> str:
    hasher = hashlib.md5()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()



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

            mode_label = "Forçar Todos" if force else ("Reprocessar OCR" if reprocess_ocr else "Incremental")
            self._add_log(f"Parâmetros: Modo={mode_label} | Provedor={provider} | Modelo={model or 'padrão'} | Workers={workers}")
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
                use_tqdm=False
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


class ConferenciaServer:
    def __init__(
        self,
        json_path: str,
        pdf_dir: str,
        html_path: str,
        provider: str = "ollama",
        model: str = None,
        ollama_url: str = "http://localhost:11434",
        openai_key: str = None,
        openai_base_url: str = None
    ):
        self.json_path = Path(resolve_json_path(json_path)).resolve()
        self.pdf_dir = Path(resolve_pdf_dir(pdf_dir)).resolve()
        if self.json_path.is_dir():
            self.json_path = (self.json_path / "classificacao_diplomas.json").resolve()
        if self.pdf_dir.is_file():
            self.pdf_dir = self.pdf_dir.parent.resolve()
        self.db_path = get_db_path(self.json_path)
        init_database(self.db_path, initial_json_path=self.json_path)
        self.html_path = Path(html_path).resolve()
        self.provider = provider or "ollama"
        self.model = model
        self.ollama_url = ollama_url
        self.openai_key = openai_key
        self.openai_base_url = openai_base_url
        self._llm_client = None
        self.md5_to_file = {}
        self.batch_manager = BatchManager(self)
        self.build_pdf_index()

    def get_llm_client(
        self,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        openai_key: Optional[str] = None,
        openai_base_url: Optional[str] = None,
        ollama_url: Optional[str] = None
    ):
        prov = (provider or self.provider or "ollama").lower().strip()
        mod = model or self.model
        o_url = ollama_url or self.ollama_url or "http://localhost:11434"
        o_key = openai_key or self.openai_key or os.environ.get("OPENAI_API_KEY")
        o_base = openai_base_url or self.openai_base_url or os.environ.get("OPENAI_BASE_URL")

        # Se for a configuração padrão e já estiver em cache, reaproveita
        is_default = (
            prov == (self.provider or "ollama").lower().strip()
            and (not mod or mod == self.model)
            and (not openai_key or openai_key == self.openai_key)
            and (not openai_base_url or openai_base_url == self.openai_base_url)
            and (not ollama_url or ollama_url == self.ollama_url)
        )

        if is_default and self._llm_client is not None:
            return self._llm_client

        if prov == "openai":
            model_name = mod or "gpt-4o-mini"
            if not o_key:
                raise ValueError(
                    "Chave da API da OpenAI não configurada. Configure sua API key nas "
                    "Configurações (ícone de engrenagem) ou defina a variável OPENAI_API_KEY."
                )
            print(f"[*] Inicializando cliente OpenAI para OCR visual sob demanda (modelo: {model_name})...")
            client = OpenAIClient(model=model_name, api_key=o_key, base_url=o_base)
        else:
            model_name = mod or "gemma4:e4b"
            print(f"[*] Inicializando cliente Ollama para OCR visual sob demanda (modelo: {model_name}, url: {o_url})...")
            client = OllamaClient(model=model_name, base_url=o_url)

        if is_default:
            self._llm_client = client
        return client

    def build_pdf_index(self):
        """Indexa os arquivos PDFs e imagens da pasta (inclusive subpastas) mapeando seus MD5."""
        self.md5_to_file.clear()
        if self.pdf_dir.is_file():
            self.pdf_dir = self.pdf_dir.parent.resolve()
        if not self.pdf_dir.exists():
            print(f"[Aviso] Pasta de documentos não encontrada: {self.pdf_dir}")
            return

        found_set = set()
        for ext in [".pdf", ".png", ".jpg", ".jpeg", ".webp"]:
            found_set |= set(self.pdf_dir.rglob(f"*{ext}")) | set(self.pdf_dir.rglob(f"*{ext.upper()}"))
        pdf_files = sorted(found_set)
        print(f"[*] Indexando {len(pdf_files)} documentos (PDFs e Imagens) na pasta {self.pdf_dir}...")
        for p in pdf_files:
            try:
                h = calculate_md5(p).strip().lower()
                self.md5_to_file[h] = p
            except Exception as e:
                print(f"[Erro] Falha ao ler {p.name}: {e}")
        print(f"[*] {len(self.md5_to_file)} documentos indexados com sucesso pelo hash MD5.")

    def load_data(self):
        data = []
        existing_by_md5 = {}
        if self.json_path.is_dir():
            self.json_path = (self.json_path / "classificacao_diplomas.json").resolve()
        self.db_path = get_db_path(self.json_path)
        init_database(self.db_path, initial_json_path=self.json_path)

        # 1. Carrega registros prioritariamente do SQLite
        try:
            db_docs = get_all_documents(self.db_path)
            for item in db_docs:
                if isinstance(item, dict) and item.get("md5"):
                    item.pop("data_criacao", None)
                    h = str(item["md5"]).strip().lower()
                    item["md5"] = h
                    existing_by_md5[h] = item
                    data.append(item)
        except Exception as e:
            print(f"[Erro SQLite] Falha ao ler banco SQLite ({self.db_path}): {e}")

        # Fallback para JSON consolidado caso SQLite esteja vazio
        if not data and self.json_path.exists() and self.json_path.is_file():
            try:
                with open(self.json_path, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                    if isinstance(loaded, list):
                        for item in loaded:
                            if isinstance(item, dict) and item.get("md5"):
                                item.pop("data_criacao", None)
                                h = str(item["md5"]).strip().lower()
                                item["md5"] = h
                                existing_by_md5[h] = item
                                data.append(item)
                        if data:
                            upsert_documents_batch(self.db_path, data)
            except Exception as e:
                print(f"[Erro] Falha ao ler JSON ({self.json_path}): {e}")
                data = []

        # Reconciliação com arquivos da pasta individuais caso existam documentos não consolidados
        indiv_dir = self.json_path.parent / "individuais"
        if indiv_dir.exists():
            recovered = 0
            recovered_docs = []
            try:
                for entry in os.scandir(indiv_dir):
                    if entry.is_file() and entry.name.endswith(".json") and not entry.name.startswith("."):
                        h = entry.name[:-5].strip().lower()
                        if h not in existing_by_md5:
                            try:
                                with open(entry.path, "r", encoding="utf-8") as f:
                                    item = json.load(f)
                                    if isinstance(item, dict) and item.get("md5"):
                                        item.pop("data_criacao", None)
                                        item["md5"] = str(item["md5"]).strip().lower()
                                        existing_by_md5[item["md5"]] = item
                                        data.append(item)
                                        recovered_docs.append(item)
                                        recovered += 1
                            except Exception:
                                continue
            except Exception as e:
                print(f"[Erro] Falha ao escanear pasta individuais: {e}")

            if recovered > 0:
                print(f"[*] Visualizador sincronizou {recovered} documento(s) da pasta 'individuais/' para o banco SQLite e JSON.")
                upsert_documents_batch(self.db_path, recovered_docs)
                sync_to_json(self.db_path, self.json_path, only_processed=True)

        # Complementa com arquivos indexados da pasta que ainda não foram processados
        for h, pdf_file in self.md5_to_file.items():
            if h not in existing_by_md5:
                try:
                    stat = pdf_file.stat()
                    dt_mod = datetime.fromtimestamp(stat.st_mtime).isoformat()
                except Exception:
                    dt_mod = None

                rel_path = str(pdf_file.relative_to(self.pdf_dir)) if self.pdf_dir in pdf_file.parents else pdf_file.name
                ext = pdf_file.suffix.lower()
                is_pix_file = any(k in pdf_file.name.lower() for k in ["pix", "recibo", "comprovante", "pagamento"])
                unprocessed_doc = {
                    "md5": h,
                    "nome_arquivo": pdf_file.name,
                    "caminho_relativo": rel_path,
                    "extensao": ext,
                    "dominio": "financeiro" if is_pix_file else "academico",
                    "data_modificacao": dt_mod,
                    "data": None,
                    "beneficiario": None,
                    "cpf": None,
                    "rg": None,
                    "curso": None,
                    "natureza_curso": None,
                    "carga_horaria": None,
                    "faculdade": None,
                    "tipo_documento": None,
                    "valor_monetario": None,
                    "status": "nao_processado",
                    "status_conferencia": "nao_processado",
                    "metodo_leitura": "nao_processado",
                    "tentativa_ocr_llm": False,
                    "processado_em": None
                }
                existing_by_md5[h] = unprocessed_doc
                data.append(unprocessed_doc)

        # Enriquecimento com nome_arquivo, caminho_relativo e extensao para itens existentes caso estejam vazios
        for item in data:
            h = item.get("md5")
            if h and h in self.md5_to_file:
                pdf_file = self.md5_to_file[h]
                if not item.get("nome_arquivo"):
                    item["nome_arquivo"] = pdf_file.name
                if not item.get("caminho_relativo"):
                    item["caminho_relativo"] = str(pdf_file.relative_to(self.pdf_dir)) if self.pdf_dir in pdf_file.parents else pdf_file.name
                if not item.get("extensao"):
                    item["extensao"] = pdf_file.suffix.lower()

        return data

    def save_data(self, data):
        if self.json_path.is_dir():
            self.json_path = (self.json_path / "classificacao_diplomas.json").resolve()
        self.db_path = get_db_path(self.json_path)
        init_database(self.db_path)

        # No arquivo consolidado em disco, salva apenas os documentos que já foram de fato processados
        processed_data = []
        for d in data:
            if d.get("status") != "nao_processado":
                d.pop("data_criacao", None)
                processed_data.append(d)

        # 1. Salva no banco SQLite com WAL mode e ACID
        upsert_documents_batch(self.db_path, processed_data)

        # 2. Sincroniza para o arquivo JSON consolidado atômico
        sync_to_json(self.db_path, self.json_path, only_processed=True)

        # 3. Atualiza também o relatório TXT consolidado correspondente
        self.update_txt_report(processed_data)

    def update_txt_report(self, results):
        txt_path = self.json_path.with_suffix(".txt")
        total = len(results)
        sucesso = sum(1 for r in results if r.get("status") == "sucesso")
        erros = total - sucesso
        now_str = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

        lines = [
            "=" * 80,
            "JOAKINDEX - RELATÓRIO DE CLASSIFICAÇÃO E CONFERÊNCIA (REVISADO)",
            "Criado por: Joaquim Ferreira Silva Neto <joaquimfsneto@gmail.com>",
            f"Data/Hora de Revisão : {now_str}",
            f"Total de Documentos  : {total}",
            f"Classificados com OK : {sucesso}",
            f"Falhas / Erros       : {erros}",
            "=" * 80,
            ""
        ]

        for idx, item in enumerate(results, 1):
            conf = item.get("status_conferencia", "PENDENTE")
            dom = item.get("dominio") or "academico"
            lines.append(f"[{idx}/{total}] MD5: {item.get('md5')}")
            lines.append(f"  • Conferência             : {conf.upper()}")
            lines.append(f"  • Status                  : {item.get('status', '').upper()}")
            lines.append(f"  • Domínio                 : {dom.upper()}")
            lines.append(f"  • Tipo Documento          : {item.get('tipo_documento') or 'Não identificado'}")
            lines.append(f"  • Data da Última Alteração: {item.get('data_modificacao')}")
            lines.append(f"  • Beneficiário / Titular  : {item.get('beneficiario') or 'Não informado'}")
            lines.append(f"  • CPF                     : {item.get('cpf') or 'Não informado'}")
            lines.append(f"  • RG / Identidade         : {item.get('rg') or 'Não informado'}")
            if dom == "financeiro" or item.get("valor_monetario") or item.get("pix_pagador_nome"):
                lines.append(f"  • Valor Monetário         : {item.get('valor_monetario') or 'Não informado'}")
                lines.append(f"  • Data da Transação       : {item.get('data') or 'Não informada'}")
                lines.append(f"  • Instituição / Banco     : {item.get('faculdade') or 'Não informada'}")
                if item.get("pix_pagador_nome"):
                    lines.append(f"  • Pagador                 : {item.get('pix_pagador_nome')}")
                if item.get("pix_e2e_id"):
                    lines.append(f"  • ID Fim-a-Fim (E2E)      : {item.get('pix_e2e_id')}")
            else:
                lines.append(f"  • Curso                   : {item.get('curso') or 'Não informado'}")
                lines.append(f"  • Natureza do Curso       : {item.get('natureza_curso') or 'Não identificada'}")
                lines.append(f"  • Carga Horária           : {item.get('carga_horaria') or 'Não informada'}")
                lines.append(f"  • Faculdade               : {item.get('faculdade') or 'Não informada'}")
                lines.append(f"  • Data do Documento       : {item.get('data') or 'Não informada'}")
            if item.get("observacoes_conferencia"):
                lines.append(f"  • Obs. Conferência        : {item.get('observacoes_conferencia')}")
            if item.get("erro"):
                lines.append(f"  • Detalhe do Erro         : {item.get('erro')}")
            lines.append("-" * 80)

        lines.append("")
        lines.append("=" * 80)
        lines.append("FIM DO RELATÓRIO")
        lines.append("=" * 80)

        try:
            with open(txt_path, "w", encoding="utf-8") as f:
                f.write("\n".join(lines))
        except Exception:
            pass


def get_or_create_thumbnail(server_ctx: "ConferenciaServer", md5_str: str, page_num: int = 1, target_width: int = 720) -> Optional[bytes]:
    """Gera ou recupera miniatura de alta definição em cache JPEG comprimido (720px padrão)."""
    thumb_dir = server_ctx.json_path.parent / ".thumbnails"
    try:
        thumb_dir.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass

    page_idx = max(0, page_num - 1)
    target_width = max(120, min(1600, int(target_width)))
    cache_name = f"{md5_str}_p{page_num}_w{target_width}.jpg"
    cache_file = thumb_dir / cache_name

    # 1. Verifica cache exato para a largura solicitada (desconsidera arquivos truncados < 5KB)
    if cache_file.exists() and cache_file.stat().st_size > 5000:
        try:
            return cache_file.read_bytes()
        except Exception:
            pass

    # 2. Se a largura for menor ou igual a 720, pode reaproveitar o cache padrão de alta resolução (720px)
    if target_width <= 720:
        cache_720 = thumb_dir / f"{md5_str}_p{page_num}_w720.jpg"
        if cache_720.exists() and cache_720.stat().st_size > 15000:
            try:
                return cache_720.read_bytes()
            except Exception:
                pass

    pdf_file = server_ctx.md5_to_file.get(md5_str)
    if not pdf_file or not pdf_file.exists():
        server_ctx.build_pdf_index()
        pdf_file = server_ctx.md5_to_file.get(md5_str)

    if not pdf_file or not pdf_file.exists():
        return None

    ext = pdf_file.suffix.lower()
    img_data = None

    # 1. Tratamento de imagens nativas (.png, .jpg, .jpeg, .webp, .bmp, .tiff)
    if ext in [".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff", ".tif"]:
        if Image is not None:
            try:
                with Image.open(pdf_file) as im:
                    im = im.convert("RGB")
                    w, h = im.size
                    if w > target_width:
                        target_height = max(1, int(h * (target_width / max(1, w))))
                        resample_filter = getattr(Image, "Resampling", Image).LANCZOS
                        im = im.resize((target_width, target_height), resample_filter)
                    buf = io.BytesIO()
                    im.save(buf, format="JPEG", quality=86, optimize=True)
                    img_data = buf.getvalue()
            except Exception as e:
                print(f"[Aviso Thumbnail] Falha ao processar imagem {pdf_file.name} com PIL: {e}")

        # Fallback para ffmpeg caso PIL falhe
        if not img_data and shutil.which("ffmpeg"):
            try:
                cmd = [
                    "ffmpeg", "-y", "-loglevel", "error",
                    "-i", str(pdf_file),
                    "-vf", f"scale={target_width}:-1",
                    "-q:v", "3",
                    "-f", "image2", "-"
                ]
                res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=10)
                if res.returncode == 0 and len(res.stdout) > 500:
                    img_data = res.stdout
            except Exception:
                pass

    # 2. Tratamento de arquivos PDF
    elif ext == ".pdf":
        # Método Principal: pypdfium2 (ultra-rápido em memória)
        if pdfium is not None:
            try:
                pil_image = None
                with _PDFIUM_LOCK:
                    pdf = pdfium.PdfDocument(str(pdf_file))
                    try:
                        if 0 <= page_idx < len(pdf):
                            page = pdf.get_page(page_idx)
                            try:
                                w, h = page.get_size()
                                scale = float(target_width) / max(1.0, float(w))
                                bitmap = page.render(scale=scale)
                                try:
                                    pil_image = bitmap.to_pil().convert("RGB").copy()
                                finally:
                                    bitmap.close()
                            finally:
                                page.close()
                    finally:
                        pdf.close()

                if pil_image:
                    buf = io.BytesIO()
                    pil_image.save(buf, format="JPEG", quality=86, optimize=True)
                    img_data = buf.getvalue()
            except Exception as e:
                print(f"[Aviso Thumbnail] Falha pypdfium2 em {pdf_file.name}: {e}")

        # Fallback Poppler (pdftoppm): robustez absoluta para qualquer PDF no Linux
        if not img_data and shutil.which("pdftoppm"):
            try:
                cmd = [
                    "pdftoppm",
                    "-jpeg",
                    "-jpegopt", "quality=86,optimize=y",
                    "-f", str(page_num),
                    "-l", str(page_num),
                    "-scale-to-x", str(target_width),
                    "-scale-to-y", "-1",
                    str(pdf_file)
                ]
                res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=12)
                if res.returncode == 0 and len(res.stdout) > 500:
                    img_data = res.stdout
            except Exception as e:
                print(f"[Aviso Thumbnail] Falha pdftoppm em {pdf_file.name}: {e}")

    if img_data:
        try:
            cache_file.write_bytes(img_data)
        except Exception:
            pass

    return img_data


def start_background_thumbnail_generator(server_ctx: "ConferenciaServer", target_width: int = 720):
    """Pré-aquecimento de miniaturas em segundo plano sem bloquear a inicialização."""
    def _worker():
        time.sleep(2.0)
        thumb_dir = server_ctx.json_path.parent / ".thumbnails"
        try:
            thumb_dir.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass

        md5_keys = list(server_ctx.md5_to_file.keys())
        for md5 in md5_keys:
            cache_file = thumb_dir / f"{md5}_p1_w{target_width}.jpg"
            if not cache_file.exists():
                try:
                    get_or_create_thumbnail(server_ctx, md5, page_num=1, target_width=target_width)
                except Exception:
                    pass
                time.sleep(0.01)

    t = threading.Thread(target=_worker, daemon=True, name="JoaKinDeX-ThumbWorker")
    t.start()


def extract_document_text_content(server_ctx: "ConferenciaServer", md5_str: str) -> Dict[str, Any]:
    """Retorna o texto bruto integral do documento para a aba de OCR/Texto."""
    indiv_txt = server_ctx.json_path.parent / "individuais" / f"{md5_str}.txt"
    if indiv_txt.exists():
        try:
            return {"status": "sucesso", "texto": indiv_txt.read_text(encoding="utf-8", errors="replace"), "origem": "ficha_individual"}
        except Exception:
            pass

    pdf_file = server_ctx.md5_to_file.get(md5_str)
    if not pdf_file or not pdf_file.exists():
        server_ctx.build_pdf_index()
        pdf_file = server_ctx.md5_to_file.get(md5_str)

    if not pdf_file or not pdf_file.exists():
        return {"status": "erro", "mensagem": f"Arquivo físico para MD5 {md5_str} não encontrado."}

    if pdf_file.suffix.lower() == ".pdf" and pdfium is not None:
        try:
            texts = []
            with _PDFIUM_LOCK:
                pdf = pdfium.PdfDocument(str(pdf_file))
                try:
                    max_pages = min(50, len(pdf))
                    for page_idx in range(max_pages):
                        page = pdf.get_page(page_idx)
                        try:
                            textpage = page.get_textpage()
                            try:
                                p_text = textpage.get_text_range()
                                if p_text and p_text.strip():
                                    texts.append(f"=== PÁGINA {page_idx + 1} ===\n{p_text.strip()}")
                            finally:
                                textpage.close()
                        finally:
                            page.close()
                finally:
                    pdf.close()
            if texts:
                return {"status": "sucesso", "texto": "\n\n".join(texts), "origem": "camada_digital"}
        except Exception:
            pass

    doc = get_document_by_md5(server_ctx.db_path, md5_str)
    if doc:
        linhas = [f"Metadados Indexados no Acervo (MD5: {md5_str}):\n" + "-" * 50]
        for k, v in doc.items():
            if v and k not in ["dados_extras", "dossie_paginas"]:
                linhas.append(f"{k.replace('_', ' ').title():<25}: {v}")
        return {"status": "sucesso", "texto": "\n".join(linhas), "origem": "metadados_banco"}

    return {"status": "erro", "mensagem": "Texto não disponível para este documento."}


def create_documents_zip(server_ctx: "ConferenciaServer", md5_list: List[str]) -> io.BytesIO:
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


def create_handler(server_ctx: ConferenciaServer):
    class RequestHandler(SimpleHTTPRequestHandler):
        def end_headers(self):
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS, HEAD")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            if not getattr(self, "_custom_cache_control", False):
                self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
            super().end_headers()

        def do_OPTIONS(self):
            self.send_response(200)
            self.end_headers()

        def do_HEAD(self):
            parsed = urllib.parse.urlparse(self.path)
            path = parsed.path
            if path in ["/", "/index.html", "/visualizador", "/visualizador.html"]:
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(server_ctx.html_path.stat().st_size))
                self.end_headers()
                return
            elif path.startswith("/api/thumbnail/"):
                query = urllib.parse.parse_qs(parsed.query)
                width_req = int(query["w"][0]) if "w" in query and query["w"][0].isdigit() else 720
                parts = path.split("/api/thumbnail/")[-1].strip("/").split("/")
                md5_req = parts[0].strip().lower()
                page_req = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 1
                data = get_or_create_thumbnail(server_ctx, md5_req, page_num=page_req, target_width=width_req)
                if data:
                    self._custom_cache_control = True
                    self.send_response(200)
                    self.send_header("Content-Type", "image/jpeg")
                    self.send_header("Cache-Control", "public, max-age=604800")
                    self.send_header("Content-Length", str(len(data)))
                    self.end_headers()
                    return
                else:
                    self.send_error(404, "Thumbnail não disponível.")
                    return
            elif path.startswith("/api/pdf/") or path.startswith("/api/arquivo/"):
                prefix = "/api/pdf/" if path.startswith("/api/pdf/") else "/api/arquivo/"
                md5_req = path.split(prefix)[-1].strip().lower()
                pdf_file = server_ctx.md5_to_file.get(md5_req)
                if pdf_file and pdf_file.exists():
                    ext = pdf_file.suffix.lower()
                    mime_types = {
                        ".pdf": "application/pdf",
                        ".png": "image/png",
                        ".jpg": "image/jpeg",
                        ".jpeg": "image/jpeg",
                        ".webp": "image/webp"
                    }
                    content_type = mime_types.get(ext, "application/octet-stream")
                    self.send_response(200)
                    self.send_header("Content-Type", content_type)
                    self.send_header("Content-Length", str(pdf_file.stat().st_size))
                    self.end_headers()
            elif path == "/favicon.ico":
                self.send_response(204)
                self.end_headers()
                return
            super().do_HEAD()

        def do_GET(self):
            parsed = urllib.parse.urlparse(self.path)
            path = parsed.path

            if path == "/favicon.ico":
                self.send_response(204)
                self.end_headers()
                return

            # Rota da página principal
            if path in ["/", "/index.html", "/visualizador", "/visualizador.html"]:
                if server_ctx.html_path.exists():
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    content = server_ctx.html_path.read_bytes()
                    self.send_header("Content-Length", str(len(content)))
                    self.end_headers()
                    self.wfile.write(content)
                else:
                    self.send_error(404, "Arquivo HTML do visualizador não encontrado.")
                return

            # API de informações das pastas e arquivos ativos
            if path == "/api/info":
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
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return

            # API para listar todos os documentos
            if path == "/api/documentos":
                dados = server_ctx.load_data()
                for item in dados:
                    if "status_conferencia" not in item:
                        item["status_conferencia"] = "pendente"
                    for k in ["curso", "beneficiario", "faculdade", "natureza_curso", "tipo_documento", "carga_horaria", "cpf", "rg", "data", "valor_monetario", "dominio"]:
                        v = item.get(k)
                        if isinstance(v, list):
                            item[k] = ", ".join(str(x) for x in v if x)
                body = json.dumps(dados, ensure_ascii=False).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return

            # API de Miniaturas de Páginas (Thumbnail de Alta Definição com Cache)
            if path.startswith("/api/thumbnail/"):
                query = urllib.parse.parse_qs(parsed.query)
                width_req = int(query["w"][0]) if "w" in query and query["w"][0].isdigit() else 720
                parts = path.split("/api/thumbnail/")[-1].strip("/").split("/")
                md5_req = parts[0].strip().lower()
                page_req = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 1
                data = get_or_create_thumbnail(server_ctx, md5_req, page_num=page_req, target_width=width_req)
                if data:
                    self._custom_cache_control = True
                    self.send_response(200)
                    self.send_header("Content-Type", "image/jpeg")
                    self.send_header("Cache-Control", "public, max-age=604800")
                    self.send_header("Content-Length", str(len(data)))
                    self.end_headers()
                    self.wfile.write(data)
                    return
                else:
                    self.send_error(404, "Thumbnail não disponível.")
                    return

            # API para obter o texto integral / OCR do documento
            if path.startswith("/api/texto/"):
                md5_req = path.split("/api/texto/")[-1].strip().lower()
                res = extract_document_text_content(server_ctx, md5_req)
                body = json.dumps(res, ensure_ascii=False).encode("utf-8")
                self.send_response(200 if res.get("status") == "sucesso" else 404)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return

            # API para servir o Documento (PDF ou Imagem) por Hash MD5
            if path.startswith("/api/pdf/") or path.startswith("/api/arquivo/"):
                prefix = "/api/pdf/" if path.startswith("/api/pdf/") else "/api/arquivo/"
                md5_req = path.split(prefix)[-1].strip().lower()
                pdf_file = server_ctx.md5_to_file.get(md5_req)

                if not pdf_file or not pdf_file.exists():
                    server_ctx.build_pdf_index()
                    pdf_file = server_ctx.md5_to_file.get(md5_req)

                if pdf_file and pdf_file.exists():
                    size = pdf_file.stat().st_size
                    ext = pdf_file.suffix.lower()
                    mime_types = {
                        ".pdf": "application/pdf",
                        ".png": "image/png",
                        ".jpg": "image/jpeg",
                        ".jpeg": "image/jpeg",
                        ".webp": "image/webp"
                    }
                    content_type = mime_types.get(ext, "application/octet-stream")
                    self.send_response(200)
                    self.send_header("Content-Type", content_type)
                    self.send_header("Content-Disposition", f'inline; filename="{md5_req}{ext}"')
                    self.send_header("Content-Length", str(size))
                    self.end_headers()
                    with open(pdf_file, "rb") as f:
                        self.wfile.write(f.read())
                    return
                else:
                    self.send_error(404, f"Arquivo com MD5 {md5_req} não encontrado.")
                    return

            # API de Configurações do Sistema
            if path == "/api/config":
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
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return

            # API para listar ambientes Ollama detectados
            if path == "/api/environments":
                envs = []
                if detect_ollama_environments:
                    try:
                        url = server_ctx.ollama_url or "http://localhost:11434"
                        envs = detect_ollama_environments(url)
                    except Exception as ex_env:
                        print(f"[Aviso] Falha ao detectar ambientes Ollama: {ex_env}")

                body = json.dumps(envs, ensure_ascii=False).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return

            # API de Status do Lote
            if path == "/api/batch/status":
                status = server_ctx.batch_manager.get_status()
                body = json.dumps(status, ensure_ascii=False).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return

            # API para navegar e listar diretórios do sistema
            if path == "/api/browse/dirs":
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
                                            sub_pdf_count = sum(1 for f in entry.glob("*.pdf"))
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
                                files_pdf_count = sum(1 for f in p.glob("*.pdf"))
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
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return

            # Download de lote em ZIP via GET
            if path == "/api/batch/exportar-zip":
                query = urllib.parse.parse_qs(parsed.query)
                md5s_raw = query.get("md5s", [""])[0]
                md5_list = [m.strip().lower() for m in md5s_raw.split(",") if m.strip()]
                if not md5_list:
                    self.send_error(400, "Nenhum MD5 fornecido para exportação em lote.")
                    return
                zip_buffer = create_documents_zip(server_ctx, md5_list)
                zip_bytes = zip_buffer.getvalue()
                self.send_response(200)
                self.send_header("Content-Type", "application/zip")
                self.send_header("Content-Disposition", f'attachment; filename="joakindex_documentos_lote_{datetime.now().strftime("%Y%m%d_%H%M%S")}.zip"')
                self.send_header("Content-Length", str(len(zip_bytes)))
                self.end_headers()
                self.wfile.write(zip_bytes)
                return

            super().do_GET()

        def do_POST(self):
            parsed = urllib.parse.urlparse(self.path)
            path = parsed.path
            length = int(self.headers.get("Content-Length", 0))
            post_body = self.rfile.read(length)

            try:
                payload = json.loads(post_body.decode("utf-8"))
            except Exception as e:
                self.send_error(400, f"Payload JSON inválido: {e}")
                return

            # Salvar edição de um documento
            if path == "/api/salvar":
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

                    resp = json.dumps({"status": "sucesso", "mensagem": "Documento salvo com sucesso!"}).encode("utf-8")
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.send_header("Content-Length", str(len(resp)))
                    self.end_headers()
                    self.wfile.write(resp)
                    return

            # Aprovação de conferência
            if path == "/api/aprovar":
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

                    resp = json.dumps({"status": "sucesso", "mensagem": "Conferência aprovada com sucesso!"}).encode("utf-8")
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.send_header("Content-Length", str(len(resp)))
                    self.end_headers()
                    self.wfile.write(resp)
                else:
                    self.send_error(404, f"Documento MD5 {target_md5} não encontrado.")
                return

            # Exportação de ZIP em lote via POST
            if path == "/api/batch/exportar-zip":
                md5_list = [str(m).strip().lower() for m in payload.get("md5s", []) if m]
                if not md5_list:
                    self.send_error(400, "Nenhum MD5 fornecido para exportação em lote.")
                    return
                zip_buffer = create_documents_zip(server_ctx, md5_list)
                zip_bytes = zip_buffer.getvalue()
                self.send_response(200)
                self.send_header("Content-Type", "application/zip")
                self.send_header("Content-Disposition", f'attachment; filename="joakindex_documentos_lote_{datetime.now().strftime("%Y%m%d_%H%M%S")}.zip"')
                self.send_header("Content-Length", str(len(zip_bytes)))
                self.end_headers()
                self.wfile.write(zip_bytes)
                return

            # Aprovação de conferência em lote
            if path == "/api/batch/aprovar":
                md5_list = [str(m).strip().lower() for m in payload.get("md5s", []) if m]
                obs = payload.get("observacoes_conferencia")
                if not md5_list:
                    self.send_error(400, "Lista de MD5s vazia para aprovação em lote.")
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
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(resp)))
                self.end_headers()
                self.wfile.write(resp)
                return

            # Alteração em lote de Tipo, Domínio e Instituição
            if path == "/api/batch/alterar-tipo":
                md5_list = [str(m).strip().lower() for m in payload.get("md5s", []) if m]
                if not md5_list:
                    self.send_error(400, "Lista de MD5s vazia para alteração em lote.")
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
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(resp)))
                self.end_headers()
                self.wfile.write(resp)
                return

            # Leitura e Classificação completa sob demanda (com OCR multimodal forçado)
            if path in ["/api/processar-documento", "/api/ocr"]:
                target_md5 = str(payload.get("md5") or "").strip().lower()
                if not target_md5:
                    self.send_error(400, "MD5 do documento não informado.")
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
                    self.send_error(404, f"Arquivo PDF com MD5 {target_md5} não encontrado na pasta de PDFs ({server_ctx.pdf_dir}).")
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

                    # Executa a leitura e classificação completa do documento forçando OCR
                    novo_doc = process_single_pdf(pdf_file, client, force_ocr=True)
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
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.send_header("Content-Length", str(len(resp)))
                    self.end_headers()
                    self.wfile.write(resp)
                    return
                except Exception as e:
                    err_msg = f"Erro ao classificar documento: {e}"
                    print(f"[Erro Classificação API] {err_msg}")
                    resp = json.dumps({"status": "erro", "mensagem": err_msg}, ensure_ascii=False).encode("utf-8")
                    self.send_response(500)
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.send_header("Content-Length", str(len(resp)))
                    self.end_headers()
                    self.wfile.write(resp)
                    return

            # Salvar configurações do sistema via Web
            if path == "/api/config":
                updates_classificador = payload.get("classificador", {})
                updates_visualizador = payload.get("visualizador", {})

                if not updates_classificador and not updates_visualizador:
                    for k in ["input", "output_dir", "provider", "model", "workers", "max_pages", "skip_ocr", "docker", "ollama_url", "openai_key", "openai_base_url"]:
                        if k in payload:
                            updates_classificador[k] = payload[k]
                    for k in ["pdf_dir", "json_path", "port", "provider", "model", "ollama_url", "openai_key", "openai_base_url"]:
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

                new_pdf = updates_visualizador.get("pdf_dir") or updates_classificador.get("input")
                new_json = updates_visualizador.get("json_path") or updates_classificador.get("output_dir")

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
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(resp)))
                self.end_headers()
                self.wfile.write(resp)
                return

            # Restaurar configurações de fábrica via Web
            if path == "/api/config/reset":
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
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(resp)))
                self.end_headers()
                self.wfile.write(resp)
                return

            # Iniciar processamento em lote
            if path == "/api/batch/start":
                if payload:
                    new_pdf = payload.get("pdf_dir") or payload.get("input")
                    if new_pdf:
                        p_pdf = Path(resolve_pdf_dir(new_pdf)).expanduser().resolve()
                        if p_pdf != server_ctx.pdf_dir:
                            server_ctx.pdf_dir = p_pdf
                            server_ctx.build_pdf_index()
                    new_json = payload.get("json_path") or payload.get("output_dir")
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
                self.send_response(200 if ok else 400)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(resp)))
                self.end_headers()
                self.wfile.write(resp)
                return

            # Interromper processamento em lote
            if path == "/api/batch/stop":
                ok, msg = server_ctx.batch_manager.stop()
                resp = json.dumps({
                    "status": "sucesso" if ok else "aviso",
                    "mensagem": msg,
                    "batch_status": server_ctx.batch_manager.get_status()
                }, ensure_ascii=False).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(resp)))
                self.end_headers()
                self.wfile.write(resp)
                return

            # Criar nova subpasta
            if path == "/api/browse/mkdir":
                parent_str = payload.get("parent", "").strip()
                name_str = payload.get("name", "").strip()
                if not parent_str or not name_str:
                    self.send_error(400, "Parâmetros 'parent' e 'name' são obrigatórios.")
                    return
                if "/" in name_str or "\\" in name_str or name_str.startswith(".."):
                    self.send_error(400, "Nome de pasta inválido.")
                    return
                parent_p = Path(parent_str).expanduser().resolve()
                if not parent_p.exists() or not parent_p.is_dir():
                    self.send_error(400, f"Pasta pai '{parent_p}' não existe.")
                    return
                target_new = parent_p / name_str
                try:
                    target_new.mkdir(parents=True, exist_ok=True)
                    resp = json.dumps({
                        "status": "sucesso",
                        "mensagem": f"Pasta '{name_str}' criada com sucesso!",
                        "path": str(target_new.resolve())
                    }, ensure_ascii=False).encode("utf-8")
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.send_header("Content-Length", str(len(resp)))
                    self.end_headers()
                    self.wfile.write(resp)
                    return
                except Exception as ex_mk:
                    self.send_error(500, f"Erro ao criar pasta: {ex_mk}")
                    return

            # Diálogo nativo do sistema (Zenity / Linux)
            if path == "/api/browse/native":
                import subprocess
                init_p = payload.get("initial_path", "").strip()
                title = payload.get("title", "Selecione a Pasta")
                if not os.path.exists("/usr/bin/zenity") or not os.environ.get("DISPLAY"):
                    resp = json.dumps({
                        "status": "erro",
                        "mensagem": "Interface gráfica ou comando zenity não disponível neste ambiente."
                    }, ensure_ascii=False).encode("utf-8")
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.send_header("Content-Length", str(len(resp)))
                    self.end_headers()
                    self.wfile.write(resp)
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

                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(resp)))
                self.end_headers()
                self.wfile.write(resp)
                return

            # Uniformizar nomes de instituições em toda a base sem reprocessar PDFs
            if path == "/api/uniformizar_instituicoes":
                try:
                    res = uniformizar_base_dados(
                        str(server_ctx.json_path),
                        atualizar_individuais=True
                    )
                    server_ctx.load_data()
                    resp = json.dumps(res, ensure_ascii=False).encode("utf-8")
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.send_header("Content-Length", str(len(resp)))
                    self.end_headers()
                    self.wfile.write(resp)
                    return
                except Exception as ex_uni:
                    err_resp = json.dumps({"status": "erro", "mensagem": str(ex_uni)}, ensure_ascii=False).encode("utf-8")
                    self.send_response(500)
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.send_header("Content-Length", str(len(err_resp)))
                    self.end_headers()
                    self.wfile.write(err_resp)
                    return

            self.send_error(404, "Endpoint não encontrado")

    return RequestHandler


def main():
    parser = argparse.ArgumentParser(
        description="Servidor Web da Central de Indexação & Conferência Documental (JoaKinDeX)."
    )
    parser.add_argument(
        "-p", "--pdf-dir", "-i", "--input",
        dest="pdf_dir",
        type=str,
        default="./pdf",
        help="Pasta contendo os arquivos PDFs a serem visualizados (padrão: %(default)s)."
    )
    parser.add_argument(
        "-j", "--json", "-o", "--output", "--output-dir", "--saida",
        dest="json_path",
        type=str,
        default="./saida/classificacao_diplomas.json",
        help="Pasta de saída ou arquivo JSON de classificação (padrão: %(default)s)."
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8088,
        help="Porta HTTP do servidor (padrão: %(default)s)."
    )
    parser.add_argument(
        "--html",
        type=str,
        default="./visualizador.html",
        help="Caminho do arquivo HTML da interface (padrão: ./visualizador.html)."
    )
    parser.add_argument(
        "--prompt", "--interativo", "-interactive",
        dest="force_prompt",
        action="store_true",
        help="Força a solicitação interativa de pastas e configurações no console."
    )
    parser.add_argument(
        "--provider",
        choices=["ollama", "openai"],
        default="ollama",
        help="Provedor de LLM para OCR visual sob demanda (padrão: ollama)."
    )
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="Modelo de LLM para OCR visual (padrão: gemma4:e4b para Ollama ou gpt-4o-mini para OpenAI)."
    )
    parser.add_argument(
        "--ollama-url",
        type=str,
        default="http://localhost:11434",
        help="URL base da API do Ollama (padrão: http://localhost:11434)."
    )
    parser.add_argument(
        "-k", "--key", "--openai-key",
        dest="openai_key",
        type=str,
        default=None,
        help="Chave de API da OpenAI (caso opte por OpenAI para OCR sob demanda)."
    )
    parser.add_argument(
        "--openai-base-url",
        dest="openai_base_url",
        type=str,
        default=None,
        help="Base URL personalizada para endpoint compatível com OpenAI (opcional)."
    )
    parser.add_argument(
        "--no-prompt", "-y", "--batch",
        dest="no_prompt",
        action="store_true",
        help="Executa diretamente sem perguntas interativas no console."
    )
    parser.add_argument(
        "--reset-config", "--reset", "--factory-reset",
        dest="reset_config",
        action="store_true",
        help="Restaura todas as configurações salvas do visualizador para os padrões de fábrica neutros."
    )
    parser.add_argument(
        "--uniformizar-instituicoes", "--normalizar-instituicoes",
        dest="uniformizar_instituicoes",
        action="store_true",
        help="Executa a uniformização e consolidação inteligente de nomes de instituições na base de dados e sai."
    )

    # Carrega configurações salvas prévias como padrões do parser
    saved_cfg = get_visualizer_config()
    classif_cfg = get_classifier_config()
    saved_key = saved_cfg.get("openai_key") or classif_cfg.get("openai_key") or os.environ.get("OPENAI_API_KEY")
    saved_base_url = saved_cfg.get("openai_base_url") or classif_cfg.get("openai_base_url") or os.environ.get("OPENAI_BASE_URL")

    parser.set_defaults(
        pdf_dir=saved_cfg.get("pdf_dir", "./pdf"),
        json_path=saved_cfg.get("json_path", "./saida/classificacao_diplomas.json"),
        port=saved_cfg.get("port", 8088),
        html=saved_cfg.get("html", "./visualizador.html"),
        provider=saved_cfg.get("provider", "ollama"),
        model=saved_cfg.get("model", None),
        ollama_url=saved_cfg.get("ollama_url", "http://localhost:11434"),
        openai_key=saved_key,
        openai_base_url=saved_base_url,
    )

    args = parser.parse_args()

    if args.reset_config:
        reset_visualizer_config()
        print("[✓] Configurações do visualizador restauradas para os padrões de fábrica neutros com sucesso.")
        other_flags = [a for a in sys.argv[1:] if a not in ["--reset-config", "--reset", "--factory-reset"]]
        if not other_flags:
            sys.exit(0)
        defaults = get_factory_defaults()["visualizador"]
        for k, v in defaults.items():
            setattr(args, k, v)

    if getattr(args, "uniformizar_instituicoes", False):
        target_json = resolve_json_path(args.json_path)
        print("\n" + "=" * 70)
        print("🎓 JoaKinDeX - UNIFORMIZAÇÃO INTELIGENTE DE INSTITUIÇÕES")
        print("   Criado por: Joaquim Ferreira Silva Neto <joaquimfsneto@gmail.com>")
        print("=" * 70)
        print(f"\n[✨] Processando arquivo em: {target_json}")
        res = uniformizar_base_dados(target_json, atualizar_individuais=True)
        if res.get("status") == "sucesso":
            print(f"[✓] Base de dados consolidada com sucesso!")
            print(f"    • Total de registros analisados : {res.get('total_registros')}")
            print(f"    • Documentos normalizados       : {res.get('total_modificados')}")
            print(f"    • Fichas individuais salvas     : {res.get('individuais_atualizados')}")
            print(f"    • Instituições únicas (antes)   : {res.get('instituicoes_antes')}")
            print(f"    • Instituições canônicas (após) : {res.get('instituicoes_depois')}")
            print(f"    • Variações unificadas          : {res.get('reducao_fragmentacao')}")
            if res.get("amostra_normalizacoes"):
                print("\n[Exemplos de unificações aplicadas]:")
                for orig, norm in list(res.get("amostra_normalizacoes").items())[:8]:
                    print(f"  • '{orig}' ➔ '{norm}'")
        else:
            print(f"[x] Erro: {res.get('mensagem')}")
            sys.exit(1)
        sys.exit(0)

    default_pdf = resolve_pdf_dir(args.pdf_dir)
    default_json = resolve_json_path(args.json_path)
    default_port = args.port

    is_interactive = sys.stdin.isatty()
    explicit_cli_args = [
        arg for arg in sys.argv[1:]
        if arg not in ["--prompt", "--interativo", "-interactive", "-y", "--no-prompt", "--batch", "--reset-config", "--reset", "--factory-reset", "--uniformizar-instituicoes", "--normalizar-instituicoes"]
    ]
    should_prompt = args.force_prompt or (
        is_interactive
        and not args.no_prompt
        and len(explicit_cli_args) == 0
    )

    if should_prompt:
        pdf_dir_final, json_path_final, port_final = prompt_interactive_config(
            default_pdf_dir=default_pdf,
            default_json_path=default_json,
            default_port=default_port
        )
    else:
        pdf_dir_final = default_pdf
        json_path_final = default_json
        port_final = default_port
        save_visualizer_config({
            "pdf_dir": str(pdf_dir_final),
            "json_path": str(json_path_final),
            "port": port_final,
            "provider": args.provider,
            "model": args.model,
            "ollama_url": args.ollama_url,
            "openai_key": args.openai_key,
            "openai_base_url": args.openai_base_url
        })

    ctx = ConferenciaServer(
        json_path=str(json_path_final),
        pdf_dir=str(pdf_dir_final),
        html_path=args.html,
        provider=args.provider,
        model=args.model,
        ollama_url=args.ollama_url,
        openai_key=args.openai_key,
        openai_base_url=args.openai_base_url
    )
    handler = create_handler(ctx)

    if is_port_in_use(port_final):
        old_port = port_final
        port_final = find_available_port(port_final + 1)
        print(f"⚠️  Aviso: A porta {old_port} está ocupada por outro processo no sistema.")
        print(f"    Utilizando automaticamente a porta livre: {port_final}")

    server_address = ("0.0.0.0", port_final)
    httpd = ReusableThreadingHTTPServer(server_address, handler)

    print("\n" + "=" * 70)
    print("🚀 JoaKinDeX - VISUALIZADOR DE CONFERÊNCIA HUMANA")
    print("   Criado por: Joaquim Ferreira Silva Neto <joaquimfsneto@gmail.com>")
    print(f"👉 Acesse no seu navegador: http://localhost:{port_final}")
    print(f"   (ou pelo IP da máquina: http://127.0.0.1:{port_final})")
    print(f"💾 Banco de Dados SQLite   : {ctx.db_path} (WAL mode ativo)")
    print(f"📄 Arquivo JSON espelhado  : {ctx.json_path}")
    print(f"📁 Pasta de PDFs indexada  : {ctx.pdf_dir} ({len(ctx.md5_to_file)} PDFs)")
    print("=" * 70)
    start_background_thumbnail_generator(ctx, target_width=720)
    print("⚡ Miniaturas HD: gerador em alta definição (720px) ativo em segundo plano.")

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[*] Encerrando servidor visualizador.")
        httpd.server_close()


if __name__ == "__main__":
    main()
