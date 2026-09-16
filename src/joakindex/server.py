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
import hmac
import hashlib
import logging
import argparse
import threading
import socket
import http.cookies
from pathlib import Path
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
import urllib.parse
import io
import subprocess
import shutil
from datetime import datetime
from typing import Dict, Any, List, Optional, Union

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


# --- Autenticação por token (protege o servidor ao expor via túnel/rede) ---
AUTH_COOKIE_NAME = "joakindex_token"
AUTH_HEADER_NAME = "X-Auth-Token"
PUBLIC_PATHS = {"/favicon.ico", "/login", "/api/login"}

LOGIN_PAGE_HTML = """<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8">
<title>JoaKinDeX - Acesso</title>
<style>
body{font-family:system-ui,Arial,sans-serif;background:#0f172a;color:#e2e8f0;display:flex;align-items:center;justify-content:center;height:100vh;margin:0}
form{background:#1e293b;padding:2rem;border-radius:12px;box-shadow:0 8px 30px rgba(0,0,0,.4);width:min(90vw,360px)}
h1{font-size:1.1rem;margin:0 0 1rem}
input{width:100%;padding:.6rem;border-radius:6px;border:1px solid #334155;background:#0f172a;color:#e2e8f0;box-sizing:border-box;margin-bottom:.8rem}
button{width:100%;padding:.6rem;border-radius:6px;border:none;background:#6366f1;color:#fff;font-weight:600;cursor:pointer}
button:hover{background:#4f46e5}
#erro{color:#f87171;font-size:.85rem;margin-bottom:.8rem;display:none}
</style></head>
<body>
<form id="loginForm">
  <h1>🔒 JoaKinDeX - Acesso Protegido</h1>
  <div id="erro">Token inválido.</div>
  <input type="password" id="token" placeholder="Token de acesso" autofocus autocomplete="current-password">
  <button type="submit">Entrar</button>
</form>
<script>
document.getElementById("loginForm").addEventListener("submit", async function (ev) {
  ev.preventDefault();
  const erro = document.getElementById("erro");
  erro.style.display = "none";
  try {
    const resp = await fetch("/api/login", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({token: document.getElementById("token").value})
    });
    if (resp.ok) {
      window.location.href = "/";
    } else {
      erro.style.display = "block";
    }
  } catch (e) {
    erro.style.display = "block";
  }
});
</script>
</body></html>"""


def token_matches(provided: Optional[str], expected: Optional[str]) -> bool:
    """Compara o token informado com o configurado em tempo constante.
    Sem token configurado, a autenticação fica desativada (comportamento local padrão)."""
    if not expected:
        return True
    if not provided:
        return False
    return hmac.compare_digest(str(provided), str(expected))


def extract_provided_token(headers, cookie_header: Optional[str] = None) -> Optional[str]:
    """Extrai o token enviado via header dedicado, Authorization Bearer ou cookie de sessão."""
    header_token = headers.get(AUTH_HEADER_NAME)
    if header_token:
        return header_token.strip()
    auth_header = headers.get("Authorization", "") or ""
    if auth_header.startswith("Bearer "):
        return auth_header[len("Bearer "):].strip()
    raw_cookie = cookie_header if cookie_header is not None else headers.get("Cookie", "")
    if raw_cookie:
        jar = http.cookies.SimpleCookie()
        try:
            jar.load(raw_cookie)
        except Exception:
            return None
        if AUTH_COOKIE_NAME in jar:
            return jar[AUTH_COOKIE_NAME].value
    return None

try:
    from joakindex.cli import (
        process_single_pdf,
        format_single_txt,
        extract_file_author,
        extract_file_dublin_core,
        sanitize_llm_transcription,
        extract_tesseract_text_from_pdf,
        OllamaClient,
        OpenAIClient,
        run_batch_classification,
        detect_ollama_environments,
        get_available_ollama_models,
        convert_office_to_pdf,
        WORD_EXTENSIONS,
        TEXT_EXTENSIONS,
        IMAGE_EXTENSIONS,
        SUPPORTED_EXTENSIONS
    )
except Exception:
    try:
        from .cli import (
            process_single_pdf,
            format_single_txt,
            extract_file_author,
            extract_file_dublin_core,
            sanitize_llm_transcription,
            extract_tesseract_text_from_pdf,
            OllamaClient,
            OpenAIClient,
            run_batch_classification,
            detect_ollama_environments,
            get_available_ollama_models,
            convert_office_to_pdf,
            WORD_EXTENSIONS,
            TEXT_EXTENSIONS,
            IMAGE_EXTENSIONS,
            SUPPORTED_EXTENSIONS
        )
    except Exception:
        import importlib.util
        main_py = Path(__file__).resolve().parent.parent.parent / "joakindex.py"
        if not main_py.exists():
            main_py = Path(__file__).parent / "joakindex.py"
        spec = importlib.util.spec_from_file_location("joakindex", main_py)
        joakindex = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(joakindex)
        process_single_pdf = joakindex.process_single_pdf
        extract_file_author = getattr(joakindex, "extract_file_author", lambda p: None)
        extract_file_dublin_core = getattr(joakindex, "extract_file_dublin_core", lambda p: {})
        sanitize_llm_transcription = getattr(joakindex, "sanitize_llm_transcription", lambda t: t)
        extract_tesseract_text_from_pdf = getattr(joakindex, "extract_tesseract_text_from_pdf", None)
        OllamaClient = joakindex.OllamaClient
        OpenAIClient = joakindex.OpenAIClient
        run_batch_classification = getattr(joakindex, "run_batch_classification", None)
        detect_ollama_environments = getattr(joakindex, "detect_ollama_environments", None)
        get_available_ollama_models = getattr(joakindex, "get_available_ollama_models", None)
        convert_office_to_pdf = getattr(joakindex, "convert_office_to_pdf", None)
        WORD_EXTENSIONS = getattr(joakindex, "WORD_EXTENSIONS", {".docx", ".doc", ".odt", ".rtf"})
        TEXT_EXTENSIONS = getattr(joakindex, "TEXT_EXTENSIONS", {".txt"})
        IMAGE_EXTENSIONS = getattr(joakindex, "IMAGE_EXTENSIONS", {".png", ".jpg", ".jpeg", ".webp"})
        SUPPORTED_EXTENSIONS = getattr(joakindex, "SUPPORTED_EXTENSIONS", {".pdf", ".png", ".jpg", ".jpeg", ".webp", ".docx", ".doc", ".odt", ".rtf", ".txt"})

try:
    from joakindex.config import (
        get_visualizer_config,
        save_visualizer_config,
        reset_visualizer_config,
        get_classifier_config,
        save_classifier_config,
        reset_all_config,
        has_custom_config,
        get_factory_defaults
    )
except ImportError:
    try:
        from .config import (
            get_visualizer_config,
            save_visualizer_config,
            reset_visualizer_config,
            get_classifier_config,
            save_classifier_config,
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
            reset_all_config,
            has_custom_config,
            get_factory_defaults
        )

try:
    from joakindex.normalizer import normalizar_instituicao, uniformizar_base_dados
except ImportError:
    try:
        from .normalizer import normalizar_instituicao, uniformizar_base_dados
    except ImportError:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from normalizador_instituicoes import normalizar_instituicao, uniformizar_base_dados

try:
    from joakindex.db import (
        get_db_path,
        init_database,
        upsert_document,
        upsert_documents_batch,
        get_document_by_md5,
        get_all_documents,
        update_conference_status,
        sync_to_json,
        salvar_regra_aprendida,
        aprender_com_paginas_dossie,
        obter_regras_aprendidas,
        remover_regra_aprendida
    )
except ImportError:
    try:
        from .db import (
            get_db_path,
            init_database,
            upsert_document,
            upsert_documents_batch,
            get_document_by_md5,
            get_all_documents,
            update_conference_status,
            sync_to_json,
            salvar_regra_aprendida,
            aprender_com_paginas_dossie,
            obter_regras_aprendidas,
            remover_regra_aprendida
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
            sync_to_json,
            salvar_regra_aprendida,
            aprender_com_paginas_dossie,
            obter_regras_aprendidas,
            remover_regra_aprendida
        )

try:
    from joakindex.api_batch import (
        BatchManager,
        handle_get_batch_status,
        handle_get_batch_exportar_zip,
        handle_post_batch_exportar_zip,
        handle_post_batch_aprovar,
        handle_post_batch_alterar_tipo,
        handle_post_batch_start,
        handle_post_batch_stop
    )
except ImportError:
    from .api_batch import (
        BatchManager,
        handle_get_batch_status,
        handle_get_batch_exportar_zip,
        handle_post_batch_exportar_zip,
        handle_post_batch_aprovar,
        handle_post_batch_alterar_tipo,
        handle_post_batch_start,
        handle_post_batch_stop
    )

try:
    from joakindex.api_browse import (
        handle_get_browse_dirs,
        handle_post_browse_mkdir,
        handle_post_browse_native
    )
except ImportError:
    from .api_browse import (
        handle_get_browse_dirs,
        handle_post_browse_mkdir,
        handle_post_browse_native
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
    retorna o caminho completo para joakindex.json (com fallback para legados).
    """
    if not specified_json:
        return "./saida/joakindex.json"
    clean = clean_path_input(specified_json)
    if clean in [
        "./saida/joakindex.json", "saida/joakindex.json",
        "./saida/classificacao_diplomas.json", "saida/classificacao_diplomas.json",
        "./saida", "saida", ""
    ]:
        p_saida = Path("./saida").resolve()
        if (p_saida / "joakindex.json").exists():
            return str((p_saida / "joakindex.json").resolve())
        if (p_saida / "classificacao_diplomas.json").exists():
            return str((p_saida / "classificacao_diplomas.json").resolve())
        return "./saida/joakindex.json"
    p = Path(clean).expanduser()
    if p.is_dir():
        if (p / "joakindex.json").exists():
            return str((p / "joakindex.json").resolve())
        if (p / "classificacao_diplomas.json").exists():
            return str((p / "classificacao_diplomas.json").resolve())
        return str((p / "joakindex.json").resolve())
    if p.suffix.lower() == ".json":
        if p.name == "classificacao_diplomas.json" and (p.parent / "joakindex.json").exists():
            return str((p.parent / "joakindex.json").resolve())
        return str(p.resolve())
    return str((p / "joakindex.json").resolve())


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


def resolve_html_path(raw: Optional[Union[str, Path]] = None) -> Path:
    """Localiza o arquivo visualizador.html na pasta ui/, raiz do projeto ou caminho customizado."""
    if raw:
        p = Path(raw).expanduser().resolve()
        if p.exists() and p.is_file():
            return p
    candidates = [
        Path(__file__).resolve().parent.parent.parent / "ui" / "visualizador.html",
        Path(__file__).resolve().parent / "ui" / "visualizador.html",
        Path.cwd() / "ui" / "visualizador.html",
        Path(__file__).resolve().parent.parent.parent / "visualizador.html",
        Path.cwd() / "visualizador.html",
    ]
    for c in candidates:
        if c.exists() and c.is_file():
            return c
    return (Path(__file__).resolve().parent.parent.parent / "ui" / "visualizador.html").resolve()


class ConferenciaServer:
    def __init__(
        self,
        json_path: str,
        pdf_dir: str,
        html_path: str = None,
        provider: str = "ollama",
        model: str = None,
        ollama_url: str = "http://localhost:11434",
        openai_key: str = None,
        openai_base_url: str = None,
        hybrid: bool = False,
        hybrid_cloud_model: str = "gpt-4o-mini",
        auth_token: Optional[str] = None
    ):
        self.auth_token = (auth_token or os.environ.get("JOAKINDEX_AUTH_TOKEN") or "").strip() or None
        self.json_path = Path(resolve_json_path(json_path)).resolve()
        self.pdf_dir = Path(resolve_pdf_dir(pdf_dir)).resolve()
        if self.json_path.is_dir():
            target_j = self.json_path / "joakindex.json"
            if not target_j.exists() and (self.json_path / "classificacao_diplomas.json").exists():
                target_j = self.json_path / "classificacao_diplomas.json"
            self.json_path = target_j.resolve()
        if self.pdf_dir.is_file():
            self.pdf_dir = self.pdf_dir.parent.resolve()
        self.db_path = get_db_path(self.json_path)
        init_database(self.db_path, initial_json_path=self.json_path)
        self.html_path = resolve_html_path(html_path)

        self.provider = provider or "ollama"
        self.model = model
        self.ollama_url = ollama_url
        self.openai_key = openai_key
        self.openai_base_url = openai_base_url
        self.hybrid = hybrid
        self.hybrid_cloud_model = hybrid_cloud_model
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
        for ext in sorted(SUPPORTED_EXTENSIONS):
            found_set |= set(self.pdf_dir.rglob(f"*{ext}")) | set(self.pdf_dir.rglob(f"*{ext.upper()}"))
        pdf_files = sorted(found_set)
        print(f"[*] Indexando {len(pdf_files)} documentos (PDFs, Word e Imagens) na pasta {self.pdf_dir}...")
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
            target_j = self.json_path / "joakindex.json"
            if not target_j.exists() and (self.json_path / "classificacao_diplomas.json").exists():
                target_j = self.json_path / "classificacao_diplomas.json"
            self.json_path = target_j.resolve()
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
                is_non_fin = any(x in pdf_file.name.lower() for x in ["cnpj", "inscricao", "inscrição", "cadastral", "matricula", "matrícula", "residencia", "residência", "votação", "votacao", "rendimento"])
                is_pix_file = not is_non_fin and any(k in pdf_file.name.lower() for k in ["pix", "comprovante de pagamento", "comprovante pix", "recibo de pagamento", "boleto"])
                dc_meta = extract_file_dublin_core(pdf_file)
                unprocessed_doc = {
                    "md5": h,
                    "nome_arquivo": pdf_file.name,
                    "caminho_relativo": rel_path,
                    "extensao": ext,
                    "dominio": "financeiro" if is_pix_file else "academico",
                    "data_modificacao": dt_mod,
                    "autor": dc_meta.get("creator") or extract_file_author(pdf_file),
                    "dublin_core": dc_meta,
                    "dc_title": dc_meta.get("title"),
                    "dc_subject": dc_meta.get("subject"),
                    "dc_creator_tool": dc_meta.get("creator_tool"),
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
            target_j = self.json_path / "joakindex.json"
            if not target_j.exists() and (self.json_path / "classificacao_diplomas.json").exists():
                target_j = self.json_path / "classificacao_diplomas.json"
            self.json_path = target_j.resolve()
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
            lines.append(f"  • dc:creator              : {item.get('autor') or 'Não informado'}")
            if item.get("dc_title"):
                lines.append(f"  • dc:title                : {item.get('dc_title')}")
            if item.get("dc_creator_tool"):
                lines.append(f"  • dc:tool                 : {item.get('dc_creator_tool')}")
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


def render_pdf_file_thumbnail(pdf_path: Path, page_num: int = 1, target_width: int = 720) -> Optional[bytes]:
    """Renderiza uma página específica de um arquivo PDF como JPEG comprimido em memória."""
    page_idx = max(0, page_num - 1)
    target_width = max(120, min(1600, int(target_width)))
    img_data = None

    # Método Principal: pypdfium2 (ultra-rápido em memória)
    if pdfium is not None:
        try:
            pil_image = None
            with _PDFIUM_LOCK:
                pdf = pdfium.PdfDocument(str(pdf_path))
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
            print(f"[Aviso Thumbnail] Falha pypdfium2 em {pdf_path.name}: {e}")

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
                str(pdf_path)
            ]
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=12)
            if res.returncode == 0 and len(res.stdout) > 500:
                img_data = res.stdout
        except Exception as e:
            print(f"[Aviso Thumbnail] Falha pdftoppm em {pdf_path.name}: {e}")

    return img_data


# Alias para compatibilidade
get_pdf_thumbnail = render_pdf_file_thumbnail


def get_or_create_thumbnail(server_ctx: "ConferenciaServer", md5_str: str, page_num: int = 1, target_width: int = 720) -> Optional[bytes]:
    """Gera ou recupera miniatura de alta definição em cache JPEG comprimido (720px padrão)."""
    thumb_dir = server_ctx.json_path.parent / ".thumbnails"
    try:
        thumb_dir.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass

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

    # 2. Tratamento de arquivos Word / OpenOffice (.docx, .doc, .odt, .rtf)
    elif ext in WORD_EXTENSIONS:
        if convert_office_to_pdf:
            pdf_cached = convert_office_to_pdf(pdf_file)
            if pdf_cached and pdf_cached.exists():
                img_data = render_pdf_file_thumbnail(pdf_cached, page_num=page_num, target_width=target_width)

    # 3. Tratamento de arquivos PDF
    elif ext == ".pdf":
        img_data = render_pdf_file_thumbnail(pdf_file, page_num=page_num, target_width=target_width)

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
    """
    Retorna o texto bruto integral do documento para a aba de OCR/Texto (Zero Noise).
    Aplica rigorosamente a Hierarquia de Verdade Textual (Ground Truth First - Pilar 2):
    1. Camada Digital Nativa do Arquivo (PDFium / Arquivo .txt / Word)
    2. OCR Óptico Estruturado (Tesseract Local)
    3. Transcrição IA (VLM / LLM) somente se higienizada (livre de repetições e loops)
    4. Transcrição Manuscrita
    """
    doc = get_document_by_md5(server_ctx.db_path, md5_str)
    de = {}
    if doc:
        de = doc.get("dados_extras") if isinstance(doc.get("dados_extras"), dict) else {}
        if isinstance(de, str):
            try:
                de = json.loads(de)
            except Exception:
                de = {}

    pdf_file = server_ctx.md5_to_file.get(md5_str)
    if not pdf_file or not pdf_file.exists():
        server_ctx.build_pdf_index()
        pdf_file = server_ctx.md5_to_file.get(md5_str)

    # -------------------------------------------------------------------------
    # 1ª Prioridade: Camada Digital Nativa do Arquivo (Ground Truth Absoluto)
    # -------------------------------------------------------------------------
    if pdf_file and pdf_file.exists():
        # Arquivo de texto puro (.txt)
        if pdf_file.suffix.lower() == ".txt":
            try:
                txt_content = pdf_file.read_text(encoding="utf-8", errors="replace").strip()
                if txt_content:
                    return {"status": "sucesso", "texto": txt_content, "origem": "arquivo_txt"}
            except Exception:
                pass

        # Camada digital do PDF via pdfium
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
                    joined = "\n\n".join(texts).strip()
                    if len(joined) >= 30:
                        return {"status": "sucesso", "texto": joined, "origem": "camada_digital"}
            except Exception:
                pass

    # Texto digital previamente indexado
    if de.get("texto_digital") and len(str(de.get("texto_digital")).strip()) >= 30:
        return {"status": "sucesso", "texto": str(de.get("texto_digital")).strip(), "origem": "camada_digital"}

    # -------------------------------------------------------------------------
    # 2ª Prioridade: OCR Óptico Estruturado (Tesseract Local)
    # -------------------------------------------------------------------------
    if de.get("texto_tesseract") and len(str(de.get("texto_tesseract")).strip()) >= 30:
        return {"status": "sucesso", "texto": str(de.get("texto_tesseract")).strip(), "origem": "ocr_tesseract"}

    # Se há arquivo individual .txt com a seção OCR no disco
    indiv_txt = server_ctx.json_path.parent / "individuais" / f"{md5_str}.txt"
    if indiv_txt.exists():
        try:
            raw_file_text = indiv_txt.read_text(encoding="utf-8", errors="replace")
            marker = "TEXTO INTEGRAL / TRANSCRIÇÃO OCR"
            if marker in raw_file_text:
                parts = raw_file_text.split(marker, 1)
                if len(parts) > 1:
                    clean_extracted = parts[1].strip().lstrip("=").lstrip("-").strip()
                    if sanitize_llm_transcription and not sanitize_llm_transcription(clean_extracted):
                        clean_extracted = ""
                    if len(clean_extracted) >= 30:
                        return {"status": "sucesso", "texto": clean_extracted, "origem": "arquivo_ocr"}
        except Exception:
            pass

    # Executa Tesseract local sob demanda caso seja PDF/imagem sem OCR anterior
    if pdf_file and pdf_file.exists() and pdf_file.suffix.lower() == ".pdf" and extract_tesseract_text_from_pdf:
        try:
            tess_extracted = extract_tesseract_text_from_pdf(pdf_file, max_pages=min(10, 50))
            if tess_extracted and len(tess_extracted.strip()) >= 30:
                if doc:
                    de["texto_tesseract"] = tess_extracted.strip()
                    doc["dados_extras"] = de
                    upsert_document(server_ctx.db_path, doc)
                return {"status": "sucesso", "texto": tess_extracted.strip(), "origem": "ocr_tesseract"}
        except Exception:
            pass

    # -------------------------------------------------------------------------
    # 3ª Prioridade: Transcrição IA (LLM / VLM) Sanitizada Antialucinação
    # -------------------------------------------------------------------------
    if doc:
        raw_llm = de.get("texto_transcrito") or de.get("texto_ocr") or doc.get("texto_transcrito")
        if raw_llm:
            sanitized_llm = sanitize_llm_transcription(str(raw_llm)) if sanitize_llm_transcription else str(raw_llm).strip()
            if sanitized_llm and len(sanitized_llm.strip()) >= 20:
                return {"status": "sucesso", "texto": sanitized_llm.strip(), "origem": "ocr_llm"}

        # -------------------------------------------------------------------------
        # 4ª Prioridade: Transcrição de Conteúdo Manuscrito
        # -------------------------------------------------------------------------
        manuscrito_txt = de.get("conteudo_manuscrito") or doc.get("conteudo_manuscrito")
        if manuscrito_txt and str(manuscrito_txt).strip():
            partes = ["[TRANSCRIÇÃO DE ESCRITA MANUAL / PREENCHIMENTO À MÃO]", "-" * 60]
            if de.get("emitente") or doc.get("emitente"):
                partes.append(f"Emitente / Assinante: {de.get('emitente') or doc.get('emitente')}")
            if de.get("referente_a") or doc.get("referente_a"):
                partes.append(f"Referente a         : {de.get('referente_a') or doc.get('referente_a')}")
            partes.append("-" * 60)
            partes.append(str(manuscrito_txt).strip())
            return {"status": "sucesso", "texto": "\n".join(partes), "origem": "manuscrito_ocr"}

    if not pdf_file or not pdf_file.exists():
        return {"status": "erro", "mensagem": f"Arquivo físico para MD5 {md5_str} não encontrado."}

    # 5. Se não há camada digital legível nem transcrição OCR realizada ainda
    return {
        "status": "aviso",
        "texto": "Documento digitalizado ou imagem sem camada de texto nativa detectada.\n\nUtilize o botão 'Ler e Classificar (OCR)' no rodapé ou no topo do Inspetor para realizar a leitura visual integral e transcrição via IA.",
        "origem": "pendente_ocr"
    }


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

        def _is_authenticated(self) -> bool:
            provided = extract_provided_token(self.headers)
            return token_matches(provided, server_ctx.auth_token)

        def _send_json_body(self, status: int, obj: dict):
            body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _send_unauthorized(self):
            self._send_json_body(401, {"erro": "Não autenticado. Acesse /login e informe o token de acesso."})

        def _serve_login_page(self):
            body = LOGIN_PAGE_HTML.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _handle_login(self, post_body: bytes):
            try:
                payload = json.loads(post_body.decode("utf-8"))
            except Exception:
                payload = {}
            provided = str(payload.get("token", "")).strip()
            if token_matches(provided, server_ctx.auth_token):
                self.send_response(200)
                self.send_header(
                    "Set-Cookie",
                    f"{AUTH_COOKIE_NAME}={provided}; Path=/; HttpOnly; SameSite=Lax; Max-Age=2592000"
                )
                body = json.dumps({"ok": True}).encode("utf-8")
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            else:
                self._send_json_body(401, {"ok": False, "erro": "Token inválido."})

        def do_HEAD(self):
            parsed = urllib.parse.urlparse(self.path)
            path = parsed.path
            if path not in PUBLIC_PATHS and not self._is_authenticated():
                self.send_error(401, "Não autenticado.")
                return
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
                        ".webp": "image/webp",
                        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        ".doc": "application/msword",
                        ".odt": "application/vnd.oasis.opendocument.text",
                        ".rtf": "application/rtf",
                        ".txt": "text/plain; charset=utf-8"
                    }
                    content_type = mime_types.get(ext, "application/octet-stream")
                    file_size = pdf_file.stat().st_size
                    if prefix == "/api/pdf/" and ext in WORD_EXTENSIONS and convert_office_to_pdf:
                        pdf_cached = convert_office_to_pdf(pdf_file)
                        if pdf_cached and pdf_cached.exists():
                            content_type = "application/pdf"
                            file_size = pdf_cached.stat().st_size

                    self.send_response(200)
                    self.send_header("Content-Type", content_type)
                    self.send_header("Content-Length", str(file_size))
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

            if path == "/login":
                self._serve_login_page()
                return

            if not self._is_authenticated():
                if path.startswith("/api/"):
                    self._send_unauthorized()
                else:
                    self.send_response(302)
                    self.send_header("Location", "/login")
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

            # API para obter metadados de um único documento por MD5
            if path.startswith("/api/documento/") or path.startswith("/api/document/"):
                prefix = "/api/documento/" if path.startswith("/api/documento/") else "/api/document/"
                md5_req = path.split(prefix)[-1].strip().lower()
                dados = server_ctx.load_data()
                doc_found = next((item for item in dados if item.get("md5", "").lower() == md5_req), None)
                if not doc_found and server_ctx.db_path and server_ctx.db_path.exists():
                    try:
                        import sqlite3
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
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                    return
                else:
                    self.send_error(404, f"Documento com MD5 {md5_req} não encontrado.")
                    return


            # API de Regras Aprendidas pelo Usuário
            if path == "/api/regras-aprendidas":
                try:
                    regras = obter_regras_aprendidas(server_ctx.db_path)
                except Exception:
                    regras = []
                body = json.dumps(regras, ensure_ascii=False).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return

            # API de Busca Avançada Full-Text (FTS5)
            if path == "/api/busca_fts":
                query = urllib.parse.parse_qs(parsed.query)
                q_termo = query.get("q", [""])[0].strip()
                limit = int(query.get("limit", [50])[0]) if query.get("limit", [""])[0].isdigit() else 50
                try:
                    from joakindex.db import search_fts
                    resultados = search_fts(server_ctx.db_path, q_termo, limit=limit)
                except Exception:
                    resultados = []
                body = json.dumps(resultados, ensure_ascii=False).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return

            # API de Duplicatas Detectadas
            if path == "/api/duplicatas":
                try:
                    from joakindex.deduplication import detect_duplicates
                    dups = detect_duplicates(server_ctx.db_path)
                except Exception:
                    dups = []
                body = json.dumps(dups, ensure_ascii=False).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return

            # API de Comparação Detalhada de Duplicata (Base vs Cópia)
            if path.startswith("/api/duplicatas/comparar"):
                query_params = urllib.parse.parse_qs(parsed.query)
                base_md5 = query_params.get("base", [""])[0].strip().lower()
                copia_md5 = query_params.get("copia", [""])[0].strip().lower()
                try:
                    from joakindex.deduplication import compare_duplicate_pair
                    comp_res = compare_duplicate_pair(server_ctx.db_path, base_md5, copia_md5)
                except Exception as e:
                    comp_res = {"erro": str(e)}
                body = json.dumps(comp_res, ensure_ascii=False).encode("utf-8")
                self.send_response(200 if "erro" not in comp_res else 400)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return

            # API de Dossiês Agrupados
            if path == "/api/dossies":
                try:
                    from joakindex.dossier import get_all_dossiers
                    dossiers = get_all_dossiers(server_ctx.db_path)
                except Exception:
                    dossiers = []
                body = json.dumps(dossiers, ensure_ascii=False).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return

            # API de Estatísticas Gerenciais para o Dashboard
            if path.startswith("/api/estatisticas_gerenciais"):
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
                body = json.dumps(stats, ensure_ascii=False).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return

            # API para Download do Relatório Executivo em PDF
            if path == "/api/relatorio/pdf":
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
                    self.send_response(200)
                    self.send_header("Content-Type", "application/pdf")
                    self.send_header("Content-Disposition", 'attachment; filename="relatorio_auditoria_joakindex.pdf"')
                    self.send_header("Content-Length", str(len(content)))
                    self.end_headers()
                    self.wfile.write(content)
                    return
                except Exception as e:
                    self.send_error(500, f"Erro ao gerar relatório de auditoria: {e}")
                    return

            # API para Inspecionar Assinaturas e Origem de um Documento
            if path.startswith("/api/inspecionar/"):
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
                body = json.dumps(res_insp, ensure_ascii=False).encode("utf-8")
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
                    self.send_response(200)
                    self.send_header("Content-Type", content_type)
                    self.send_header("Content-Disposition", f'{disp_mode}; filename="{disp_name}"')
                    self.send_header("Content-Length", str(size))
                    self.end_headers()
                    with open(file_to_send, "rb") as f:
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
                handle_get_batch_status(self, server_ctx)
                return

            # API para navegar e listar diretórios do sistema
            if path == "/api/browse/dirs":
                handle_get_browse_dirs(self, server_ctx, parsed)
                return

            # Download de lote em ZIP via GET
            if path == "/api/batch/exportar-zip":
                handle_get_batch_exportar_zip(self, server_ctx, parsed)
                return

            super().do_GET()

        def do_POST(self):
            parsed = urllib.parse.urlparse(self.path)
            path = parsed.path
            length = int(self.headers.get("Content-Length", 0))
            post_body = self.rfile.read(length)

            if path == "/api/login":
                self._handle_login(post_body)
                return

            if not self._is_authenticated():
                self._send_unauthorized()
                return

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
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.send_header("Content-Length", str(len(resp)))
                    self.end_headers()
                    self.wfile.write(resp)
                    return

            # Gerenciamento de Regras Aprendidas (Adicionar / Excluir)
            if path == "/api/regras-aprendidas":
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
                handle_post_batch_exportar_zip(self, server_ctx, payload)
                return

            # Aprovação de conferência em lote
            if path == "/api/batch/aprovar":
                handle_post_batch_aprovar(self, server_ctx, payload)
                return

            # Alteração em lote de Tipo, Domínio e Instituição
            if path == "/api/batch/alterar-tipo":
                handle_post_batch_alterar_tipo(self, server_ctx, payload)
                return

            # Smart Dispatcher (Organização Física de Arquivos e Pastas)
            if path == "/api/organizar_arquivos":
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
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return

            # Resolução de Duplicata (Aprovar como duplicado ou Descartar falso positivo)
            if path == "/api/duplicatas/resolver":
                target_md5 = str(payload.get("md5") or "").strip().lower()
                descartar = bool(payload.get("descartar", False))
                try:
                    from joakindex.deduplication import resolve_duplicate
                    ok = resolve_duplicate(server_ctx.db_path, target_md5, descartar=descartar)
                    res_dup = {"status": "sucesso" if ok else "erro"}
                except Exception as e:
                    res_dup = {"status": "erro", "mensagem": str(e)}
                body = json.dumps(res_dup, ensure_ascii=False).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return

            # Geração de Dossiês por Entidades (CPF/CNPJ/Nome)
            if path == "/api/dossies/gerar":
                try:
                    from joakindex.dossier import build_and_save_dossiers
                    dossiers = build_and_save_dossiers(server_ctx.db_path)
                    res_dos = {"status": "sucesso", "total_dossies": len(dossiers), "dossies": dossiers}
                except Exception as e:
                    res_dos = {"status": "erro", "mensagem": str(e)}
                body = json.dumps(res_dos, ensure_ascii=False).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return

            # Exportação de Dossiê Unificado em PDF
            if path == "/api/dossies/exportar":
                dossie_id = str(payload.get("dossie_id") or "").strip()
                out_name = f"{dossie_id}_unificado.pdf"
                out_path = server_ctx.db_path.parent / "dossies_exportados" / out_name
                try:
                    from joakindex.dossier import export_dossier_pdf
                    ok, msg = export_dossier_pdf(server_ctx.db_path, dossie_id, out_path, pdf_base_dir=server_ctx.pdf_dir)
                    res_exp = {"status": "sucesso" if ok else "erro", "mensagem": msg, "caminho": str(out_path)}
                except Exception as e:
                    res_exp = {"status": "erro", "mensagem": str(e)}
                body = json.dumps(res_exp, ensure_ascii=False).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
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
                handle_post_batch_start(self, server_ctx, payload)
                return

            # Interromper processamento em lote
            if path == "/api/batch/stop":
                handle_post_batch_stop(self, server_ctx)
                return

            # Criar nova subpasta
            if path == "/api/browse/mkdir":
                handle_post_browse_mkdir(self, server_ctx, payload)
                return

            # Diálogo nativo do sistema (Zenity / Linux)
            if path == "/api/browse/native":
                handle_post_browse_native(self, server_ctx, payload)
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


def main(argv: Optional[List[str]] = None):
    parser = argparse.ArgumentParser(
        prog="joakindex server",
        description="JoaKinDeX Server - Central Web de Indexação, Governança e Conferência Documental."
    )
    parser.add_argument(
        "-i", "--input", "--docs-dir", "--input-dir", "-p", "--pdf-dir",
        dest="docs_dir",
        type=str,
        default="./pdf",
        help="Diretório contendo os documentos a serem indexados e auditados (PDF, Word, Imagens) (padrão: %(default)s)."
    )
    parser.add_argument(
        "-d", "--data", "--db", "--database", "-o", "--output", "--output-dir", "-j", "--json", "--json-path", "--saida",
        dest="data_path",
        type=str,
        default="./saida/joakindex.json",
        help="Diretório de dados, banco SQLite (joakindex.db) ou arquivo consolidado (.json) (padrão: %(default)s)."
    )
    parser.add_argument(
        "--port", "-P",
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
    parser.add_argument(
        "--hibrido", "--hybrid",
        dest="hybrid",
        action="store_true",
        default=False,
        help="Inicia o servidor com modo híbrido em cascata ativado (padrão: %(default)s)."
    )
    parser.add_argument(
        "--no-hibrido", "--no-hybrid",
        dest="hybrid",
        action="store_false",
        help="Desativa o modo híbrido em cascata no servidor."
    )
    parser.add_argument(
        "--hybrid-cloud-model",
        dest="hybrid_cloud_model",
        type=str,
        default="gpt-4o-mini",
        help="Modelo cloud de fallback para o modo híbrido (padrão: %(default)s)."
    )
    parser.add_argument(
        "--auth-token", "--token",
        dest="auth_token",
        type=str,
        default=None,
        help="Token secreto exigido para acessar o servidor. Recomendado ao expor via túnel/rede pública. "
             "Também pode ser definido pela variável de ambiente JOAKINDEX_AUTH_TOKEN (inclusive via arquivo .env)."
    )

    # Carrega configurações salvas prévias como padrões do parser
    saved_cfg = get_visualizer_config()
    classif_cfg = get_classifier_config()
    saved_key = saved_cfg.get("openai_key") or classif_cfg.get("openai_key") or os.environ.get("OPENAI_API_KEY")
    saved_base_url = saved_cfg.get("openai_base_url") or classif_cfg.get("openai_base_url") or os.environ.get("OPENAI_BASE_URL")

    parser.set_defaults(
        docs_dir=saved_cfg.get("pdf_dir", "./pdf"),
        data_path=saved_cfg.get("json_path", "./saida/joakindex.json"),
        port=saved_cfg.get("port", 8088),
        html=saved_cfg.get("html", "./visualizador.html"),
        provider=saved_cfg.get("provider", "ollama"),
        model=saved_cfg.get("model", None),
        ollama_url=saved_cfg.get("ollama_url", "http://localhost:11434"),
        openai_key=saved_key,
        openai_base_url=saved_base_url,
        hybrid=saved_cfg.get("hybrid", False),
        hybrid_cloud_model=saved_cfg.get("hybrid_cloud_model", "gpt-4o-mini"),
    )

    raw_args = argv if argv is not None else sys.argv[1:]
    args = parser.parse_args(raw_args)

    # Aliases de compatibilidade interna
    args.pdf_dir = args.docs_dir
    args.json_path = args.data_path

    if args.reset_config:
        reset_visualizer_config()
        print("[✓] Configurações do servidor restauradas para os padrões de fábrica neutros com sucesso.")
        other_flags = [a for a in raw_args if a not in ["--reset-config", "--reset", "--factory-reset"]]
        if not other_flags:
            sys.exit(0)
        defaults = get_factory_defaults()["visualizador"]
        for k, v in defaults.items():
            setattr(args, k, v)
        args.pdf_dir = args.docs_dir
        args.json_path = args.data_path

    if getattr(args, "uniformizar_instituicoes", False):
        target_json = resolve_json_path(args.json_path)
        print("\n" + "=" * 70)
        print("🎓 JoaKinDeX - UNIFORMIZAÇÃO INTELIGENTE DE INSTITUIÇÕES")
        print("   Criado por: Joaquim Ferreira Silva Neto <joaquimfsneto@gmail.com>")
        print("=" * 70)
        print(f"\n[✨] Processando arquivo em: {target_json}")
        res = uniformizar_base_dados(target_json, atualizar_individuais=True)
        if res.get("status") == "sucesso":
            print("[✓] Base de dados consolidada com sucesso!")
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

    default_pdf = resolve_pdf_dir(args.docs_dir)
    default_json = resolve_json_path(args.data_path)
    default_port = args.port

    is_interactive = sys.stdin.isatty()
    explicit_cli_args = [
        arg for arg in raw_args
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
            "openai_base_url": args.openai_base_url,
            "hybrid": getattr(args, "hybrid", False),
            "hybrid_cloud_model": getattr(args, "hybrid_cloud_model", "gpt-4o-mini")
        })

    ctx = ConferenciaServer(
        json_path=str(json_path_final),
        pdf_dir=str(pdf_dir_final),
        html_path=args.html,
        provider=args.provider,
        model=args.model,
        ollama_url=args.ollama_url,
        openai_key=args.openai_key,
        openai_base_url=args.openai_base_url,
        hybrid=getattr(args, "hybrid", False),
        hybrid_cloud_model=getattr(args, "hybrid_cloud_model", "gpt-4o-mini"),
        auth_token=args.auth_token
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
    if ctx.auth_token:
        print("🔒 Autenticação por token  : ATIVA (acesse /login e informe o token configurado)")
    else:
        print("⚠️  Autenticação por token  : DESATIVADA")
        print("    Qualquer pessoa com acesso a esta URL pode ver e editar os documentos.")
        print("    Defina JOAKINDEX_AUTH_TOKEN no arquivo .env (ou use --auth-token) antes de expor via túnel/rede.")
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
