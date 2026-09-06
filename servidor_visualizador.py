#!/usr/bin/env python3
"""
Servidor Web Local para Conferência Humana de Diplomas e Certificados.
Permite visualizar o PDF lado a lado com o JSON extraído, editar dados e salvar alterações.
"""

import os
import sys
import json
import time
import hashlib
import argparse
import threading
from pathlib import Path
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
import urllib.parse
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple, Union

try:
    from classificador import (
        process_single_pdf,
        OllamaClient,
        OpenAIClient,
        run_batch_classification,
        detect_ollama_environments,
        get_available_ollama_models
    )
except Exception:
    import importlib.util
    spec = importlib.util.spec_from_file_location("classificador", Path(__file__).parent / "joaclassificador-pdf.py")
    classificador = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(classificador)
    process_single_pdf = classificador.process_single_pdf
    OllamaClient = classificador.OllamaClient
    OpenAIClient = classificador.OpenAIClient
    run_batch_classification = getattr(classificador, "run_batch_classification", None)
    detect_ollama_environments = getattr(classificador, "detect_ollama_environments", None)
    get_available_ollama_models = getattr(classificador, "get_available_ollama_models", None)

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


def resolve_pdf_dir(specified_dir: str = None) -> str:
    """Retorna o diretório de PDFs padrão neutro ou o caminho especificado."""
    if specified_dir and specified_dir not in ["./pdf", "pdf"]:
        return str(specified_dir)
    return "./pdf"


def resolve_json_path(specified_json: str = None) -> str:
    """
    Resolve o caminho do arquivo JSON. Se for informado um diretório,
    retorna o caminho esperado de classificacao_diplomas.json.
    """
    if specified_json:
        p = Path(specified_json).expanduser()
        if p.is_dir():
            return str(p / "classificacao_diplomas.json")
        if p.suffix.lower() == ".json":
            return str(p)
        return str(p / "classificacao_diplomas.json")
    return "./saida/classificacao_diplomas.json"


def prompt_interactive_config(default_pdf_dir: str, default_json_path: str, default_port: int):
    """
    Exibe menu interativo no console permitindo ao usuário escolher ou alterar
    as pastas de entrada de PDFs e de saída de JSONs antes de iniciar o servidor.
    """
    print("\n" + "=" * 70)
    print("⚙️  CONFIGURAÇÃO DO VISUALIZADOR DE DIPLOMAS E CERTIFICADOS")
    print("=" * 70)
    print("Pressione ENTER para aceitar o valor padrão sugerido entre colchetes.\n")

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
                default_pdf_dir = factory["pdf_dir"]
                default_json_path = factory["json_path"]
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

        if resp_pdf.lower() in ["reset", "resetar", "padrao", "fábrica", "fabrica"]:
            reset_visualizer_config()
            factory = get_factory_defaults()["visualizador"]
            default_pdf_dir = factory["pdf_dir"]
            default_json_path = factory["json_path"]
            default_port = factory["port"]
            print("   [✓] Configurações restauradas para os padrões de fábrica neutros!")
            continue

        if not resp_pdf:
            chosen_pdf_dir = default_pdf_dir
            break
        else:
            p = Path(resp_pdf).expanduser().resolve()
            if not p.exists() or not p.is_dir():
                print(f"   ⚠️  Aviso: Diretório '{p}' não existe ou não é uma pasta.")
                try:
                    conf = input("   Deseja utilizar esse caminho mesmo assim? (s/N): ").strip().lower()
                except (EOFError, KeyboardInterrupt):
                    sys.exit(0)
                if conf in ["s", "sim", "y", "yes"]:
                    chosen_pdf_dir = str(resp_pdf)
                    break
            else:
                chosen_pdf_dir = str(resp_pdf)
                break

    # 2. Pasta de saída ou arquivo JSON
    chosen_json_path = default_json_path
    while True:
        try:
            resp_json = input(f"\n📄 Pasta de saída ou arquivo JSON [{default_json_path}]: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n[Operação cancelada pelo usuário]")
            sys.exit(0)

        if not resp_json:
            chosen_json_path = default_json_path
            break
        else:
            p_str = resolve_json_path(resp_json)
            p = Path(p_str).expanduser().resolve()
            if not p.exists():
                print(f"   ℹ️  Arquivo '{p_str}' ainda não existe (será criado ao salvar).")
            chosen_json_path = str(resp_json)
            break

    # 3. Porta
    chosen_port = default_port
    while True:
        try:
            resp_port = input(f"\n🌐 Porta HTTP [{default_port}]: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n[Operação cancelada pelo usuário]")
            sys.exit(0)

        if not resp_port:
            chosen_port = default_port
            break
        try:
            p_val = int(resp_port)
            if 1 <= p_val <= 65535:
                chosen_port = p_val
                break
            else:
                print("   ⚠️  Porta inválida (deve estar entre 1 e 65535).")
        except ValueError:
            print("   ⚠️  Digite um número de porta válido.")

    # Salva opções configuradas no visualizador
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
                raise RuntimeError("Função run_batch_classification não pôde ser importada de joaclassificador-pdf.py")

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
        ollama_url: str = "http://localhost:11434"
    ):
        self.json_path = Path(json_path).resolve()
        self.pdf_dir = Path(pdf_dir).resolve()
        self.html_path = Path(html_path).resolve()
        self.provider = provider or "ollama"
        self.model = model
        self.ollama_url = ollama_url
        self._llm_client = None
        self.md5_to_file = {}
        self.batch_manager = BatchManager(self)
        self.build_pdf_index()

    def get_llm_client(self):
        if self._llm_client is not None:
            return self._llm_client

        if self.provider == "ollama":
            model_name = self.model or "gemma4:e4b"
            url = self.ollama_url or "http://localhost:11434"
            print(f"[*] Inicializando cliente Ollama para OCR visual sob demanda (modelo: {model_name})...")
            self._llm_client = OllamaClient(model=model_name, base_url=url)
        else:
            model_name = self.model or "gpt-4o-mini"
            print(f"[*] Inicializando cliente OpenAI para OCR visual sob demanda (modelo: {model_name})...")
            self._llm_client = OpenAIClient(model=model_name)

        return self._llm_client

    def build_pdf_index(self):
        """Indexa os arquivos PDFs da pasta mapeando seus MD5."""
        self.md5_to_file.clear()
        if not self.pdf_dir.exists():
            print(f"[Aviso] Pasta de PDFs não encontrada: {self.pdf_dir}")
            return

        pdf_set = set(self.pdf_dir.glob("*.pdf")) | set(self.pdf_dir.glob("*.PDF"))
        if not pdf_set:
            pdf_set = set(self.pdf_dir.rglob("*.pdf")) | set(self.pdf_dir.rglob("*.PDF"))
        pdf_files = sorted(pdf_set)
        print(f"[*] Indexando {len(pdf_files)} PDFs na pasta {self.pdf_dir}...")
        for p in pdf_files:
            try:
                h = calculate_md5(p)
                self.md5_to_file[h] = p
            except Exception as e:
                print(f"[Erro] Falha ao ler {p.name}: {e}")
        print(f"[*] {len(self.md5_to_file)} PDFs indexados com sucesso pelo hash MD5.")

    def load_data(self):
        data = []
        existing_by_md5 = {}
        if self.json_path.exists():
            try:
                with open(self.json_path, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                    if isinstance(loaded, list):
                        data = loaded
                        for item in data:
                            if isinstance(item, dict) and "md5" in item:
                                existing_by_md5[item["md5"]] = item
            except Exception as e:
                print(f"[Erro] Falha ao ler JSON: {e}")
                data = []

        # Reconciliação com arquivos da pasta individuais caso existam documentos não consolidados
        indiv_dir = self.json_path.parent / "individuais"
        if indiv_dir.exists():
            recovered = 0
            try:
                for entry in os.scandir(indiv_dir):
                    if entry.is_file() and entry.name.endswith(".json") and not entry.name.startswith("."):
                        h = entry.name[:-5].lower()
                        if h not in existing_by_md5:
                            try:
                                with open(entry.path, "r", encoding="utf-8") as f:
                                    item = json.load(f)
                                    if isinstance(item, dict) and item.get("md5"):
                                        existing_by_md5[item["md5"]] = item
                                        data.append(item)
                                        recovered += 1
                            except Exception:
                                continue
            except Exception as e:
                print(f"[Erro] Falha ao escanear pasta individuais: {e}")

            if recovered > 0:
                print(f"[*] Visualizador sincronizou {recovered} documento(s) da pasta 'individuais/' para o relatório consolidado.")
                self.save_data(data)

        return data

    def save_data(self, data):
        self.json_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_json = self.json_path.parent / f".tmp_{self.json_path.name}"
        with open(tmp_json, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        tmp_json.replace(self.json_path)
        # Atualiza também o relatório TXT consolidado correspondente
        self.update_txt_report(data)

    def update_txt_report(self, results):
        txt_path = self.json_path.with_suffix(".txt")
        total = len(results)
        sucesso = sum(1 for r in results if r.get("status") == "sucesso")
        erros = total - sucesso
        now_str = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

        lines = [
            "=" * 80,
            "RELATÓRIO CONSOLIDADO DE CLASSIFICAÇÃO DE DIPLOMAS E CERTIFICADOS (REVISADO)",
            f"Data/Hora de Revisão : {now_str}",
            f"Total de Documentos  : {total}",
            f"Classificados com OK : {sucesso}",
            f"Falhas / Erros       : {erros}",
            "=" * 80,
            ""
        ]

        for idx, item in enumerate(results, 1):
            conf = item.get("status_conferencia", "PENDENTE")
            lines.append(f"[{idx}/{total}] MD5: {item.get('md5')}")
            lines.append(f"  • Conferência        : {conf.upper()}")
            lines.append(f"  • Status             : {item.get('status', '').upper()}")
            lines.append(f"  • Data de Criação    : {item.get('data_criacao')}")
            lines.append(f"  • Data de Modificação: {item.get('data_modificacao')}")
            lines.append(f"  • Tipo Documento     : {item.get('tipo_documento') or 'Não identificado'}")
            lines.append(f"  • Beneficiário       : {item.get('beneficiario') or 'Não informado'}")
            lines.append(f"  • CPF                : {item.get('cpf') or 'Não informado'}")
            lines.append(f"  • RG / Identidade    : {item.get('rg') or 'Não informado'}")
            lines.append(f"  • Curso              : {item.get('curso') or 'Não informado'}")
            lines.append(f"  • Natureza do Curso  : {item.get('natureza_curso') or 'Não identificada'}")
            lines.append(f"  • Carga Horária      : {item.get('carga_horaria') or 'Não informada'}")
            lines.append(f"  • Faculdade          : {item.get('faculdade') or 'Não informada'}")
            lines.append(f"  • Data do Documento  : {item.get('data') or 'Não informada'}")
            if item.get("observacoes_conferencia"):
                lines.append(f"  • Obs. Conferência   : {item.get('observacoes_conferencia')}")
            if item.get("erro"):
                lines.append(f"  • Detalhe do Erro    : {item.get('erro')}")
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


def create_handler(server_ctx: ConferenciaServer):
    class RequestHandler(SimpleHTTPRequestHandler):
        def end_headers(self):
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS, HEAD")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
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
            elif path.startswith("/api/pdf/"):
                md5_req = path.split("/api/pdf/")[-1].strip().lower()
                pdf_file = server_ctx.md5_to_file.get(md5_req)
                if pdf_file and pdf_file.exists():
                    self.send_response(200)
                    self.send_header("Content-Type", "application/pdf")
                    self.send_header("Content-Length", str(pdf_file.stat().st_size))
                    self.end_headers()
                    return
            super().do_HEAD()

        def do_GET(self):
            parsed = urllib.parse.urlparse(self.path)
            path = parsed.path

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
                    for k in ["curso", "beneficiario", "faculdade", "natureza_curso", "tipo_documento", "carga_horaria", "cpf", "rg", "data"]:
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

            # API para servir o PDF por Hash MD5
            if path.startswith("/api/pdf/"):
                md5_req = path.split("/api/pdf/")[-1].strip().lower()
                pdf_file = server_ctx.md5_to_file.get(md5_req)

                if not pdf_file or not pdf_file.exists():
                    server_ctx.build_pdf_index()
                    pdf_file = server_ctx.md5_to_file.get(md5_req)

                if pdf_file and pdf_file.exists():
                    size = pdf_file.stat().st_size
                    self.send_response(200)
                    self.send_header("Content-Type", "application/pdf")
                    self.send_header("Content-Disposition", f'inline; filename="{md5_req}.pdf"')
                    self.send_header("Content-Length", str(size))
                    self.end_headers()
                    with open(pdf_file, "rb") as f:
                        self.wfile.write(f.read())
                    return
                else:
                    self.send_error(404, f"Arquivo PDF com MD5 {md5_req} não encontrado.")
                    return

            # API de Configurações do Sistema
            if path == "/api/config":
                cfg_classificador = get_classifier_config()
                cfg_vis = get_visualizer_config()
                clean_classificador = dict(cfg_classificador)
                has_key = bool(clean_classificador.get("openai_key") or os.environ.get("OPENAI_API_KEY"))
                if clean_classificador.get("openai_key"):
                    k = clean_classificador["openai_key"]
                    clean_classificador["openai_key_masked"] = k[:7] + "..." + k[-4:] if len(k) > 12 else "***"
                else:
                    clean_classificador["openai_key_masked"] = ""
                clean_classificador["has_openai_key"] = has_key

                envs = []
                if detect_ollama_environments:
                    try:
                        envs = detect_ollama_environments(clean_classificador.get("ollama_url") or "http://localhost:11434")
                    except Exception as ex_env:
                        print(f"[Aviso] Falha ao detectar ambientes Ollama: {ex_env}")

                resp_obj = {
                    "classificador": clean_classificador,
                    "visualizador": cfg_vis,
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
                dados_atuais = server_ctx.load_data()
                item_editado = payload.get("item")
                if item_editado and "md5" in item_editado:
                    target_md5 = item_editado["md5"]
                    found = False
                    for idx, doc in enumerate(dados_atuais):
                        if doc.get("md5") == target_md5:
                            item_editado["revisado_em"] = datetime.now().isoformat()
                            dados_atuais[idx] = item_editado
                            found = True
                            break
                    if not found:
                        dados_atuais.append(item_editado)

                    server_ctx.save_data(dados_atuais)

                    # Se existir pasta 'individuais' correspondente, atualiza o arquivo individual também
                    indiv_dir = server_ctx.json_path.parent / "individuais"
                    if indiv_dir.exists():
                        indiv_file = indiv_dir / f"{target_md5}.json"
                        try:
                            with open(indiv_file, "w", encoding="utf-8") as fi:
                                json.dump(item_editado, fi, ensure_ascii=False, indent=2)
                        except Exception:
                            pass

                    resp = json.dumps({"status": "sucesso", "mensagem": "Documento salvo com sucesso!"}).encode("utf-8")
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.send_header("Content-Length", str(len(resp)))
                    self.end_headers()
                    self.wfile.write(resp)
                    return

            # Aprovação de conferência
            if path == "/api/aprovar":
                target_md5 = payload.get("md5")
                dados_atuais = server_ctx.load_data()
                found = False
                for doc in dados_atuais:
                    if doc.get("md5") == target_md5:
                        doc["status_conferencia"] = "aprovado"
                        doc["conferido_em"] = datetime.now().isoformat()
                        if "observacoes_conferencia" in payload:
                            doc["observacoes_conferencia"] = payload["observacoes_conferencia"]
                        found = True
                        break

                if found:
                    server_ctx.save_data(dados_atuais)
                    resp = json.dumps({"status": "sucesso", "mensagem": "Conferência aprovada com sucesso!"}).encode("utf-8")
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.send_header("Content-Length", str(len(resp)))
                    self.end_headers()
                    self.wfile.write(resp)
                else:
                    self.send_error(404, f"Documento MD5 {target_md5} não encontrado.")
                return

            # Re-análise via OCR Multimodal com LLM sob demanda
            if path == "/api/ocr":
                target_md5 = payload.get("md5")
                if not target_md5:
                    self.send_error(400, "MD5 do documento não informado.")
                    return

                pdf_file = server_ctx.md5_to_file.get(target_md5)
                if not pdf_file or not pdf_file.exists():
                    server_ctx.build_pdf_index()
                    pdf_file = server_ctx.md5_to_file.get(target_md5)

                if not pdf_file or not pdf_file.exists():
                    self.send_error(404, f"Arquivo PDF com MD5 {target_md5} não encontrado na pasta de PDFs.")
                    return

                try:
                    client = server_ctx.get_llm_client()
                    novo_doc = process_single_pdf(pdf_file, client, force_ocr=True)

                    # Sanitiza listas para strings para compatibilidade com o visualizador
                    for k in ["curso", "beneficiario", "faculdade", "natureza_curso", "tipo_documento", "carga_horaria", "cpf", "rg", "data"]:
                        v = novo_doc.get(k)
                        if isinstance(v, list):
                            novo_doc[k] = ", ".join(str(x) for x in v if x)

                    dados_atuais = server_ctx.load_data()
                    found = False
                    for idx, doc in enumerate(dados_atuais):
                        if doc.get("md5") == target_md5:
                            if "status_conferencia" in doc:
                                novo_doc["status_conferencia"] = doc["status_conferencia"]
                            if "observacoes_conferencia" in doc:
                                novo_doc["observacoes_conferencia"] = doc["observacoes_conferencia"]
                            dados_atuais[idx] = novo_doc
                            found = True
                            break
                    if not found:
                        dados_atuais.append(novo_doc)

                    server_ctx.save_data(dados_atuais)

                    # Se existir pasta 'individuais' correspondente, atualiza o arquivo individual também
                    indiv_dir = server_ctx.json_path.parent / "individuais"
                    if indiv_dir.exists():
                        indiv_file = indiv_dir / f"{target_md5}.json"
                        try:
                            with open(indiv_file, "w", encoding="utf-8") as fi:
                                json.dump(novo_doc, fi, ensure_ascii=False, indent=2)
                        except Exception:
                            pass

                    resp = json.dumps({
                        "status": "sucesso",
                        "item": novo_doc,
                        "mensagem": "OCR via LLM concluído com sucesso!"
                    }, ensure_ascii=False).encode("utf-8")
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.send_header("Content-Length", str(len(resp)))
                    self.end_headers()
                    self.wfile.write(resp)
                    return
                except Exception as e:
                    err_msg = f"Erro ao executar OCR via LLM: {e}"
                    print(f"[Erro OCR API] {err_msg}")
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
                    for k in ["pdf_dir", "json_path", "port", "provider", "model", "ollama_url"]:
                        if k in payload:
                            updates_visualizador[k] = payload[k]

                if "openai_key" in updates_classificador:
                    val = updates_classificador["openai_key"]
                    if not val or "***" in val or "..." in val:
                        del updates_classificador["openai_key"]

                if updates_classificador:
                    save_classifier_config(updates_classificador)
                if updates_visualizador:
                    save_visualizer_config(updates_visualizador)

                new_pdf = updates_visualizador.get("pdf_dir") or updates_classificador.get("input")
                new_json = updates_visualizador.get("json_path") or updates_classificador.get("output_dir")

                if new_pdf:
                    p_pdf = Path(new_pdf).expanduser().resolve()
                    if p_pdf != server_ctx.pdf_dir:
                        server_ctx.pdf_dir = p_pdf
                        server_ctx.build_pdf_index()

                if new_json:
                    p_json = Path(resolve_json_path(new_json)).expanduser().resolve()
                    if p_json != server_ctx.json_path:
                        server_ctx.json_path = p_json
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

                resp = json.dumps({
                    "status": "sucesso",
                    "mensagem": "Configurações salvas e aplicadas com sucesso!",
                    "pdf_count": len(server_ctx.md5_to_file),
                    "doc_count": len(server_ctx.load_data()),
                    "pdf_dir": str(server_ctx.pdf_dir),
                    "json_path": str(server_ctx.json_path),
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
                server_ctx.provider = factory["visualizador"]["provider"]
                server_ctx.model = factory["visualizador"]["model"]
                server_ctx.ollama_url = factory["visualizador"]["ollama_url"]
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
                        p_pdf = Path(new_pdf).expanduser().resolve()
                        if p_pdf != server_ctx.pdf_dir:
                            server_ctx.pdf_dir = p_pdf
                            server_ctx.build_pdf_index()
                    new_json = payload.get("json_path") or payload.get("output_dir")
                    if new_json:
                        p_json = Path(resolve_json_path(new_json)).expanduser().resolve()
                        if p_json != server_ctx.json_path:
                            server_ctx.json_path = p_json
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

            self.send_error(404, "Endpoint não encontrado")

    return RequestHandler


def main():
    parser = argparse.ArgumentParser(
        description="Servidor Web do Visualizador de Conferência Humana de Diplomas e Certificados."
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

    # Carrega configurações salvas prévias como padrões do parser
    saved_cfg = get_visualizer_config()
    parser.set_defaults(
        pdf_dir=saved_cfg.get("pdf_dir", "./pdf"),
        json_path=saved_cfg.get("json_path", "./saida/classificacao_diplomas.json"),
        port=saved_cfg.get("port", 8088),
        html=saved_cfg.get("html", "./visualizador.html"),
        provider=saved_cfg.get("provider", "ollama"),
        model=saved_cfg.get("model", None),
        ollama_url=saved_cfg.get("ollama_url", "http://localhost:11434"),
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

    default_pdf = resolve_pdf_dir(args.pdf_dir)
    default_json = resolve_json_path(args.json_path)
    default_port = args.port

    is_interactive = sys.stdin.isatty()
    explicit_cli_args = [
        arg for arg in sys.argv[1:]
        if arg not in ["--prompt", "--interativo", "-interactive", "-y", "--no-prompt", "--batch", "--reset-config", "--reset", "--factory-reset"]
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
            "ollama_url": args.ollama_url
        })

    ctx = ConferenciaServer(
        json_path=str(json_path_final),
        pdf_dir=str(pdf_dir_final),
        html_path=args.html,
        provider=args.provider,
        model=args.model,
        ollama_url=args.ollama_url
    )
    handler = create_handler(ctx)

    server_address = ("0.0.0.0", port_final)
    httpd = ThreadingHTTPServer(server_address, handler)

    print("\n" + "=" * 70)
    print("🚀 VISUALIZADOR DE CONFERÊNCIA HUMANA INICIADO!")
    print(f"👉 Acesse no seu navegador: http://localhost:{port_final}")
    print(f"   (ou pelo IP da máquina: http://127.0.0.1:{port_final})")
    print(f"📄 Arquivo JSON monitorado : {ctx.json_path}")
    print(f"📁 Pasta de PDFs indexada  : {ctx.pdf_dir} ({len(ctx.md5_to_file)} PDFs)")
    print("=" * 70)
    print("Pressione Ctrl+C a qualquer momento para encerrar o servidor.\n")

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[*] Encerrando servidor visualizador.")
        httpd.server_close()


if __name__ == "__main__":
    main()
