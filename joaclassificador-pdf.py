#!/usr/bin/env python3
"""
Classificador de PDFs em Massa (Diplomas, Certificados e Documentos Acadêmicos)
Identificação por Hash MD5, Datas de Criação e Modificação do Arquivo,
Extração do CPF do Beneficiário e Natureza/Nível do Curso.
Suporta Ollama (Local / Docker) e OpenAI API.
Gera saídas consolidadas e individuais em JSON e TXT.
"""

import os
import sys
import json
import re
import time
import hashlib
import argparse
import warnings
warnings.filterwarnings("ignore", category=UserWarning, module="pypdf")
import base64
import io
import subprocess
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Union, Callable, Set
from concurrent.futures import ThreadPoolExecutor, as_completed

try:
    import requests
except ImportError:
    requests = None

try:
    from tqdm import tqdm
except ImportError:
    tqdm = None

try:
    import pypdf
except ImportError:
    pypdf = None

try:
    import pdfplumber
except ImportError:
    pdfplumber = None

try:
    import pypdfium2 as pdfium
except ImportError:
    pdfium = None

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

try:
    from config_manager import (
        get_classifier_config,
        save_classifier_config,
        reset_classifier_config,
        has_custom_config,
        get_factory_defaults
    )
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from config_manager import (
        get_classifier_config,
        save_classifier_config,
        reset_classifier_config,
        has_custom_config,
        get_factory_defaults
    )



def load_dotenv_if_present(env_path: Optional[Path] = None):
    """
    Carrega automaticamente variáveis do arquivo .env para os.environ sem dependências externas.
    """
    candidates = [
        env_path,
        Path(".env"),
        Path(__file__).parent / ".env",
        Path.cwd() / ".env"
    ] if env_path else [Path(".env"), Path(__file__).parent / ".env", Path.cwd() / ".env"]

    for p in candidates:
        if p and p.exists() and p.is_file():
            try:
                for line in p.read_text(encoding="utf-8").splitlines():
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    k, v = line.split("=", 1)
                    k = k.strip()
                    v = v.strip().strip("'\"")
                    if k and k not in os.environ:
                        os.environ[k] = v
            except Exception:
                pass
            break

# Carrega .env automaticamente
load_dotenv_if_present()


# ---------------------------------------------------------------------------
# Metadados do Arquivo (MD5, Criação, Modificação)
# ---------------------------------------------------------------------------
def get_file_metadata(file_path: Path) -> Dict[str, str]:
    """
    Calcula o hash MD5 e obtém as datas de criação e modificação do arquivo no sistema.
    """
    hasher = hashlib.md5()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    md5_hash = hasher.hexdigest()

    st = file_path.stat()
    dt_mod = datetime.fromtimestamp(st.st_mtime).strftime("%d/%m/%Y %H:%M:%S")
    c_timestamp = getattr(st, "st_birthtime", st.st_ctime)
    dt_criacao = datetime.fromtimestamp(c_timestamp).strftime("%d/%m/%Y %H:%M:%S")

    return {
        "md5": md5_hash,
        "data_criacao": dt_criacao,
        "data_modificacao": dt_mod
    }


# ---------------------------------------------------------------------------
# Formatação e Validação de CPF
# ---------------------------------------------------------------------------
def format_cpf(raw_cpf: Optional[str]) -> Optional[str]:
    """Formata sequência de 11 dígitos para o padrão 000.000.000-00."""
    if not raw_cpf:
        return None
    digits = re.sub(r"\D", "", str(raw_cpf))
    if len(digits) == 11:
        return f"{digits[:3]}.{digits[3:6]}.{digits[6:9]}-{digits[9:]}"
    return raw_cpf.strip() if raw_cpf else None


def validate_cpf_checksum(cpf: str) -> bool:
    """Valida os dois dígitos verificadores do CPF de acordo com o algoritmo oficial da Receita Federal."""
    digits = [int(d) for d in re.sub(r"\D", "", str(cpf))]
    if len(digits) != 11:
        return False
    if len(set(digits)) == 1:
        return False
    s1 = sum(d * w for d, w in zip(digits[:9], range(10, 1, -1)))
    r1 = (s1 * 10) % 11
    d1 = 0 if r1 == 10 else r1
    if d1 != digits[9]:
        return False
    s2 = sum(d * w for d, w in zip(digits[:10], range(11, 1, -1)))
    r2 = (s2 * 10) % 11
    d2 = 0 if r2 == 10 else r2
    return d2 == digits[10]


def is_valid_cpf_syntax(cpf: Optional[str], check_checksum: bool = True) -> bool:
    """
    Retorna True se o CPF tiver sintaxe correta (11 dígitos, formato 000.000.000-00)
    e opcionalmente se for aprovado no cálculo dos dígitos verificadores.
    """
    if not cpf:
        return False
    digits = re.sub(r"\D", "", str(cpf))
    if len(digits) != 11:
        return False
    if not re.match(r"^\d{3}\.\d{3}\.\d{3}-\d{2}$", str(cpf)):
        return False
    if check_checksum and not validate_cpf_checksum(cpf):
        return False
    return True


def extract_cpf_fallback(text: str) -> Optional[str]:
    """Busca padrão de CPF diretamente no texto do documento como contingência."""
    match = re.search(r"(?:CPF|C\.P\.F)[\s:\.ºn°]*(\d{3}\.?\d{3}\.?\d{3}-?\d{2})", text, re.IGNORECASE)
    if match:
        return format_cpf(match.group(1))
    return None


def extract_rg_fallback(text: str) -> Optional[str]:
    """Busca padrão de Cédula de Identidade / RG diretamente no texto como contingência."""
    if not text:
        return None

    pattern = re.compile(
        r"\b(?:Carteira\s+de\s+Identidade|C[eé]dula\s+de\s+Identidade|Registro\s+Geral|R\.?\s*G\.?|Doc(?:\.|\s+de)?\s+Identidade|Documento\s+de\s+Identidade|Identidade|C\.?I\.?)\b"
        r"(?:\s*(?:n[°ºo\.]*|número|sob\s+o\s+n[°ºo\.]*))?"
        r"\s*[:\s-]*"
        r"([A-Z0-9\.\-\/]+(?:\s*(?:(?:SSP|SPTC|PCMG|DGPC|PC|DETRAN|IFP|PM|POL[IÍ]CIA|MAE|MEX|MD|DPF|SESP|[A-Z]{2,4})\b)?(?:\s*[\/\-]?\s*[A-Z]{2})?)?)",
        re.IGNORECASE
    )

    for match in pattern.finditer(text):
        val = match.group(1).strip()
        val = re.split(r"\s+(?:e\s+)?(?:CPF|C\.P\.F|Data|Nascido|Nasc|Expedi[cç]|Filia[cç])\b", val, flags=re.IGNORECASE)[0].strip()
        val = val.rstrip(".,;:- ")
        digits = re.sub(r"\D", "", val)
        if 5 <= len(digits) <= 14 and len(val) <= 35:
            if len(digits) == 11 and re.match(r"^\d{3}\.\d{3}\.\d{3}-\d{2}$", val):
                continue
            if ("/" in val or "-" in val) and len(digits) == 8 and re.match(r"^\d{2}/\d{2}/\d{4}$|^\d{4}-\d{2}-\d{2}$", val):
                continue
            return val
    return None


# ---------------------------------------------------------------------------
# Extração de texto de PDF
# ---------------------------------------------------------------------------
def extract_pdf_text(pdf_path: str, max_pages: int = 4) -> str:
    """
    Extrai texto do PDF usando pypdf com fallback para pdfplumber.
    Limita ao número máximo de páginas para otimizar velocidade e tokens.
    """
    extracted_text = ""

    # Tentativa 1: pypdf (mais rápido)
    if pypdf is not None:
        try:
            reader = pypdf.PdfReader(pdf_path)
            num_pages = min(len(reader.pages), max_pages)
            pages_text = []
            for i in range(num_pages):
                page_text = reader.pages[i].extract_text() or ""
                if page_text.strip():
                    pages_text.append(page_text.strip())
            extracted_text = "\n\n".join(pages_text)
        except Exception:
            extracted_text = ""

    # Tentativa 2: pdfplumber se pypdf falhar ou extrair pouco texto
    if len(extracted_text.strip()) < 40 and pdfplumber is not None:
        try:
            with pdfplumber.open(pdf_path) as pdf:
                num_pages = min(len(pdf.pages), max_pages)
                pages_text = []
                for i in range(num_pages):
                    page_text = pdf.pages[i].extract_text() or ""
                    if page_text.strip():
                        pages_text.append(page_text.strip())
                extracted_text = "\n\n".join(pages_text)
        except Exception:
            pass

    return extracted_text.strip()


def render_pdf_pages_to_base64(
    pdf_path: str,
    max_pages: int = 2,
    scale: float = 1.5,
    quality: int = 80
) -> List[str]:
    """
    Renderiza páginas do PDF em imagens JPEG codificadas em base64 para leitura visual (OCR) via LLM.
    Utiliza pypdfium2 com fallback para pdfplumber.
    """
    images_b64: List[str] = []

    # Tentativa 1: pypdfium2 (rápido e alta fidelidade)
    if pdfium is not None:
        try:
            pdf = pdfium.PdfDocument(str(pdf_path))
            num_pages = min(len(pdf), max_pages)
            for i in range(num_pages):
                page = pdf[i]
                img = page.render(scale=scale).to_pil()
                buf = io.BytesIO()
                img.save(buf, format="JPEG", quality=quality)
                images_b64.append(base64.b64encode(buf.getvalue()).decode("utf-8"))
            if images_b64:
                return images_b64
        except Exception:
            images_b64 = []

    # Tentativa 2: pdfplumber (fallback)
    if pdfplumber is not None:
        try:
            with pdfplumber.open(str(pdf_path)) as pdf:
                num_pages = min(len(pdf.pages), max_pages)
                for i in range(num_pages):
                    page = pdf.pages[i]
                    pimg = page.to_image(resolution=int(72 * scale))
                    buf = io.BytesIO()
                    pimg.original.save(buf, format="JPEG", quality=quality)
                    images_b64.append(base64.b64encode(buf.getvalue()).decode("utf-8"))
        except Exception:
            pass

    return images_b64


# ---------------------------------------------------------------------------
# Tratamento de JSON retornado pelo LLM
# ---------------------------------------------------------------------------
def clean_and_parse_json(raw_text: str) -> Dict[str, Any]:
    """
    Higieniza e decodifica a resposta JSON do modelo, tratando blocos de código
    markdown e possíveis caracteres extras.
    """
    text = raw_text.strip()

    if "```" in text:
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text)
        text = text.strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"(\{.*\})", text, re.DOTALL)
        if match:
            return json.loads(match.group(1))
        raise ValueError(f"Não foi possível converter a resposta em JSON válido: {raw_text[:200]}")


# ---------------------------------------------------------------------------
# Clientes de LLM (Ollama e OpenAI)
# ---------------------------------------------------------------------------
class BaseLLMClient:
    def generate_json(self, prompt: str) -> Dict[str, Any]:
        raise NotImplementedError

    def generate_json_with_images(self, prompt: str, images: List[str]) -> Dict[str, Any]:
        raise NotImplementedError


def detect_ollama_environments(base_url: str = "http://localhost:11434") -> List[Dict[str, Any]]:
    """
    Detecta de forma inteligente e exaustiva todos os ambientes Ollama disponíveis:
    1. Ollama Nativo instalado diretamente no sistema host (sem Docker), rodando em localhost:11434
    2. Binário nativo 'ollama' instalado no host (ativo ou parado)
    3. Container Docker Oficial Puro do Ollama (ex: nome 'ollama' ou imagem 'ollama/ollama')
    4. Container Docker Open-WebUI com Ollama embutido (ex: 'open-webui')
    5. Qualquer outro container Docker executando Ollama

    Retorna uma lista com informações detalhadas e modelos baixados de cada ambiente.
    """
    envs: List[Dict[str, Any]] = []
    clean_url = base_url.rstrip("/")

    # 1. Teste de conexão HTTP direta (Ollama nativo no host ou com porta exposta)
    http_online = False
    http_models: List[str] = []
    http_models_display: List[str] = []
    try:
        r = requests.get(clean_url + "/api/tags", timeout=2)
        if r.status_code == 200:
            http_online = True
            data = r.json()
            for m in data.get("models", []):
                m_name = m.get("name", "")
                if m_name:
                    http_models.append(m_name)
                    sz_bytes = m.get("size", 0)
                    param = m.get("details", {}).get("parameter_size", "")
                    parts = []
                    if sz_bytes:
                        parts.append(f"{sz_bytes / (1024**3):.1f} GB")
                    if param:
                        parts.append(param)
                    desc_extra = f" ({', '.join(parts)})" if parts else ""
                    http_models_display.append(f"{m_name}{desc_extra}")
    except Exception:
        pass

    # Verifica se o executável 'ollama' existe nativamente no host
    native_bin = shutil.which("ollama")

    if http_online:
        desc = "Ollama Nativo / HTTP Direto (localhost:11434 - sem Docker)"
        if native_bin:
            desc = f"Ollama Nativo no Sistema ({native_bin}) via {clean_url}"
        envs.append({
            "type": "native_http",
            "name": "Ollama Nativo (sem Docker)",
            "description": desc,
            "container": None,
            "base_url": base_url,
            "models": http_models,
            "models_display": http_models_display,
            "is_running": True
        })
    elif native_bin:
        envs.append({
            "type": "native_binary_stopped",
            "name": f"Ollama Nativo Instalado ({native_bin})",
            "description": f"Binário 'ollama' instalado no sistema ({native_bin}), mas o serviço HTTP não está ativo (execute: ollama serve)",
            "container": None,
            "base_url": base_url,
            "models": [],
            "models_display": [],
            "is_running": False
        })

    # 2. Inspeção de containers Docker em execução
    try:
        res = subprocess.run(
            ["docker", "ps", "--format", "{{.Names}}\t{{.Image}}\t{{.Status}}"],
            capture_output=True,
            text=True,
            timeout=4
        )
        if res.returncode == 0:
            for line in res.stdout.strip().splitlines():
                if not line.strip():
                    continue
                parts = line.split("\t")
                c_name = parts[0].strip()
                c_image = parts[1].strip() if len(parts) > 1 else ""

                # Classifica o tipo de container Ollama
                is_official_ollama = (
                    "ollama/ollama" in c_image.lower()
                    or c_name.lower() == "ollama"
                    or (c_image.lower() == "ollama:latest")
                )
                is_open_webui = (
                    "open-webui" in c_name.lower()
                    or "open-webui" in c_image.lower()
                )
                is_other_ollama = (
                    not is_official_ollama
                    and not is_open_webui
                    and ("ollama" in c_name.lower() or "ollama" in c_image.lower())
                )

                if is_official_ollama or is_open_webui or is_other_ollama:
                    c_models: List[str] = []
                    c_models_display: List[str] = []

                    # Tentativa 1: curl interno via /api/tags
                    try:
                        cmd_curl = ["docker", "exec", "-i", c_name, "curl", "-s", "http://localhost:11434/api/tags"]
                        r_curl = subprocess.run(cmd_curl, capture_output=True, text=True, timeout=3)
                        if r_curl.returncode == 0 and r_curl.stdout.strip():
                            d_json = json.loads(r_curl.stdout)
                            for m in d_json.get("models", []):
                                m_name = m.get("name", "")
                                if m_name:
                                    c_models.append(m_name)
                                    sz_bytes = m.get("size", 0)
                                    param = m.get("details", {}).get("parameter_size", "")
                                    extra_parts = []
                                    if sz_bytes:
                                        extra_parts.append(f"{sz_bytes / (1024**3):.1f} GB")
                                    if param:
                                        extra_parts.append(param)
                                    extra_str = f" ({', '.join(extra_parts)})" if extra_parts else ""
                                    c_models_display.append(f"{m_name}{extra_str}")
                    except Exception:
                        pass

                    # Tentativa 2: comando ollama list no container
                    if not c_models:
                        try:
                            cmd_list = ["docker", "exec", "-i", c_name, "ollama", "list"]
                            r_list = subprocess.run(cmd_list, capture_output=True, text=True, timeout=3)
                            if r_list.returncode == 0 and r_list.stdout.strip():
                                lines = r_list.stdout.strip().splitlines()
                                if len(lines) > 1:
                                    for l in lines[1:]:
                                        col = l.split()
                                        if col:
                                            m_name = col[0]
                                            c_models.append(m_name)
                                            m_sz = col[2] if len(col) >= 3 else ""
                                            extra = f" ({m_sz})" if m_sz else ""
                                            c_models_display.append(f"{m_name}{extra}")
                        except Exception:
                            pass

                    if is_official_ollama:
                        c_type = "docker_ollama_official"
                        c_name_label = f"Docker Oficial Ollama (container: '{c_name}')"
                        c_desc = f"Container Oficial Ollama Puro (container: '{c_name}', imagem: '{c_image}')"
                    elif is_open_webui:
                        c_type = "docker_open_webui"
                        c_name_label = f"Docker Open-WebUI (container: '{c_name}')"
                        c_desc = f"Container Open-WebUI com Ollama (container: '{c_name}', imagem: '{c_image}')"
                    else:
                        c_type = "docker_ollama_custom"
                        c_name_label = f"Docker Ollama (container: '{c_name}')"
                        c_desc = f"Container Docker Ollama Customizado (container: '{c_name}', imagem: '{c_image}')"

                    envs.append({
                        "type": c_type,
                        "name": c_name_label,
                        "description": c_desc,
                        "container": c_name,
                        "base_url": "http://localhost:11434",
                        "models": c_models,
                        "models_display": c_models_display,
                        "is_running": True
                    })
    except Exception:
        pass

    return envs


class OllamaClient(BaseLLMClient):
    """
    Cliente para Ollama, suportando execução nativa no sistema operacional
    e comunicação via docker exec (Container Oficial Ollama Puro ou Open-WebUI).
    """
    def __init__(
        self,
        model: str = "gemma4:e4b",
        base_url: str = "http://localhost:11434",
        docker_container: Optional[str] = None,
        timeout: int = 180
    ):
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.docker_container = docker_container
        self.timeout = timeout
        self.use_docker = False

        self._detect_connection_mode()

    def _detect_connection_mode(self):
        if self.docker_container:
            self.use_docker = True
            self._resolve_model_name()
            return

        envs = detect_ollama_environments(base_url=self.base_url)
        running = [e for e in envs if e.get("is_running")]

        if running:
            # Prefere ambiente que já possua modelos baixados
            best = next((e for e in running if e.get("models")), running[0])
            if best["type"] == "native_http":
                self.use_docker = False
                self.docker_container = None
            else:
                self.use_docker = True
                self.docker_container = best["container"]
        else:
            self.use_docker = False

        self._resolve_model_name()

    def _resolve_model_name(self):
        models = self._list_models()
        if not models or self.model in models:
            return

        clean_target = self.model.replace(":", "").replace("-", "").lower()
        for m in models:
            clean_m = m.replace(":", "").replace("-", "").lower()
            if clean_target in clean_m or clean_m in clean_target:
                print(f"[Ollama] Ajustando modelo para '{m}' disponível no servidor.")
                self.model = m
                return

    def _list_models(self) -> List[str]:
        try:
            if self.use_docker and self.docker_container:
                cmd = ["docker", "exec", "-i", self.docker_container, "curl", "-s", "http://localhost:11434/api/tags"]
                res = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
                if res.returncode == 0 and res.stdout.strip():
                    data = json.loads(res.stdout)
                    return [m["name"] for m in data.get("models", [])]
                # Fallback para ollama list
                cmd2 = ["docker", "exec", "-i", self.docker_container, "ollama", "list"]
                res2 = subprocess.run(cmd2, capture_output=True, text=True, timeout=5)
                if res2.returncode == 0 and res2.stdout.strip():
                    lines = res2.stdout.strip().splitlines()
                    return [l.split()[0] for l in lines[1:] if l.split()]
            else:
                url = self.base_url.rstrip("/") + "/api/tags"
                r = requests.get(url, timeout=5)
                data = r.json()
                return [m["name"] for m in data.get("models", [])]
        except Exception:
            return []

    def generate_json(self, prompt: str) -> Dict[str, Any]:
        payload = {
            "model": self.model,
            "prompt": prompt,
            "format": "json",
            "stream": False,
            "options": {
                "temperature": 0.0
            }
        }
        payload_str = json.dumps(payload)

        if self.use_docker:
            cmd = [
                "docker", "exec", "-i", self.docker_container,
                "curl", "-s", "-X", "POST", "http://localhost:11434/api/generate",
                "-d", "@-"
            ]
            proc = subprocess.run(
                cmd,
                input=payload_str,
                text=True,
                capture_output=True,
                timeout=self.timeout
            )
            if proc.returncode != 0:
                raise RuntimeError(f"Erro no docker exec: {proc.stderr}")
            response_json = json.loads(proc.stdout)
            raw_response = response_json.get("response", "")
        else:
            url = f"{self.base_url}/api/generate"
            r = requests.post(url, json=payload, timeout=self.timeout)
            r.raise_for_status()
            response_json = r.json()
            raw_response = response_json.get("response", "")

        return clean_and_parse_json(raw_response)

    def generate_json_with_images(self, prompt: str, images: List[str]) -> Dict[str, Any]:
        payload = {
            "model": self.model,
            "prompt": prompt,
            "images": images,
            "format": "json",
            "stream": False,
            "options": {
                "temperature": 0.0
            }
        }
        payload_str = json.dumps(payload)

        if self.use_docker:
            cmd = [
                "docker", "exec", "-i", self.docker_container,
                "curl", "-s", "-X", "POST", "http://localhost:11434/api/generate",
                "-d", "@-"
            ]
            proc = subprocess.run(
                cmd,
                input=payload_str,
                text=True,
                capture_output=True,
                timeout=self.timeout
            )
            if proc.returncode != 0:
                raise RuntimeError(f"Erro no docker exec: {proc.stderr}")
            response_json = json.loads(proc.stdout)
            raw_response = response_json.get("response", "")
        else:
            url = f"{self.base_url}/api/generate"
            r = requests.post(url, json=payload, timeout=self.timeout)
            r.raise_for_status()
            response_json = r.json()
            raw_response = response_json.get("response", "")

        return clean_and_parse_json(raw_response)


class OpenAIClient(BaseLLMClient):
    """
    Cliente para OpenAI API (ou endpoints compatíveis como Groq, vLLM, etc).
    """
    def __init__(
        self,
        model: str = "gpt-4o-mini",
        api_key: Optional[str] = None,
        base_url: Optional[str] = None
    ):
        if OpenAI is None:
            raise ImportError("O pacote 'openai' não está instalado. Execute: pip install openai")

        resolved_key = api_key or os.environ.get("OPENAI_API_KEY")
        if not resolved_key:
            raise ValueError(
                "\n[ERRO] Chave de API da OpenAI não encontrada!\n"
                "Você pode informá-la de 4 formas simples:\n"
                "  1. No menu interativo ao selecionar OpenAI\n"
                "  2. Via linha de comando: ./joaclassificador-pdf -p openai -k sk-proj-...\n"
                "  3. No arquivo .env: OPENAI_API_KEY=sk-proj-...\n"
                "  4. No terminal: export OPENAI_API_KEY=sk-proj-...\n"
            )

        self.model = model
        self.client = OpenAI(
            api_key=resolved_key,
            base_url=base_url or os.environ.get("OPENAI_BASE_URL")
        )

    def generate_json(self, prompt: str) -> Dict[str, Any]:
        max_retries = 5
        for attempt in range(max_retries):
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {
                            "role": "system",
                            "content": (
                                "Você é um assistente especialista em analisar e extrair dados "
                                "estruturados de documentos acadêmicos e diplomas. "
                                "Responda estritamente em formato JSON válido."
                            )
                        },
                        {"role": "user", "content": prompt}
                    ],
                    response_format={"type": "json_object"},
                    temperature=0.0
                )
                raw_response = response.choices[0].message.content or "{}"
                return clean_and_parse_json(raw_response)
            except Exception as e:
                err_msg = str(e).lower()
                is_rate_limit = "429" in err_msg or "rate limit" in err_msg or "tokens per min" in err_msg
                if is_rate_limit and attempt < max_retries - 1:
                    sleep_s = (attempt + 1) * 3
                    time.sleep(sleep_s)
                    continue
                raise e

    def generate_json_with_images(self, prompt: str, images: List[str]) -> Dict[str, Any]:
        content: List[Dict[str, Any]] = [{"type": "text", "text": prompt}]
        for img_b64 in images:
            content.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/jpeg;base64,{img_b64}"
                }
            })

        max_retries = 5
        for attempt in range(max_retries):
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {
                            "role": "system",
                            "content": (
                                "Você é um assistente especialista em analisar visualmente e extrair dados "
                                "estruturados de documentos acadêmicos e diplomas via OCR. "
                                "Responda estritamente em formato JSON válido."
                            )
                        },
                        {"role": "user", "content": content}
                    ],
                    response_format={"type": "json_object"},
                    temperature=0.0
                )
                raw_response = response.choices[0].message.content or "{}"
                return clean_and_parse_json(raw_response)
            except Exception as e:
                err_msg = str(e).lower()
                is_rate_limit = "429" in err_msg or "rate limit" in err_msg or "tokens per min" in err_msg
                if is_rate_limit and attempt < max_retries - 1:
                    sleep_s = (attempt + 1) * 4
                    time.sleep(sleep_s)
                    continue
                raise e


# ---------------------------------------------------------------------------
# Prompts de Extração (Texto e Visão / OCR)
# ---------------------------------------------------------------------------
def build_vision_prompt(extra_context: str = "") -> str:
    ctx_note = ""
    if extra_context:
        ctx_note = f"""
OBSERVAÇÃO DA LEITURA TEXTUAL PRÉVIA:
\"\"\"
{extra_context[:1200]}
\"\"\"
Atenção: Na leitura da camada de texto digital, o 'tipo_documento' NÃO pôde ser determinado com precisão ou ficou não identificado. Analise os elementos visuais das páginas do documento (título principal, cabeçalho, carimbos, assinaturas, selos, brasões e formatação) para classificar o tipo_documento corretamente (ex: Diploma, Certificado, Histórico Escolar, Declaração, etc.).
"""

    return f"""Analise visualmente as imagens deste documento acadêmico e extraia as informações com a máxima precisão via OCR.
{ctx_note}
Extraia as seguintes informações e retorne ESTRITAMENTE um objeto JSON com as chaves exatas abaixo:
- "data": Data principal do documento (data de emissão do diploma, conclusão do curso ou colação de grau, ex: "18 de dezembro de 2023" ou "18/12/2023"). Se não encontrar, retorne null.
- "beneficiario": Nome completo do aluno / diplomado / titular do documento. Se não encontrar, retorne null.
- "cpf": CPF do beneficiário / titular identificado no documento (ex: "000.000.000-00" ou apenas números). Se não houver menção ao CPF, retorne null.
- "rg": Número da Cédula de Identidade / RG / Registro Geral do titular (incluindo órgão emissor e UF se constar, ex: "12.345.678-9 SSP/SP" ou "MG-12.345.678"). Se não houver menção ao RG, retorne null.
- "curso": Nome completo e oficial do curso concluído (ex: "Pós-graduação Lato Sensu em Gestão Escolar", "Licenciatura em Pedagogia", "Bacharelado em Administração"). Se não encontrar, retorne null.
- "natureza_curso": Nível ou natureza acadêmica do curso identificado no documento. Classifique em uma das opções:
    * "Graduação / Curso Superior" (para Bacharelado, Licenciatura, Tecnólogo)
    * "Pós-Graduação Lato Sensu (Especialização/MBA)"
    * "Pós-Graduação Stricto Sensu (Mestrado/Doutorado)"
    * "Curso Técnico / Profissionalizante"
    * "Curso de Extensão / Aperfeiçoamento"
    * "Educação Básica" (Fundamental / Médio)
    * Ou null se não for possível determinar ou não for curso.
- "carga_horaria": Carga horária total do curso (ex: "750 h/aulas", "360 horas", "750h"). Se não encontrar, retorne null.
- "faculdade": Nome completo da faculdade, universidade ou instituição de ensino emissora. Se não encontrar, retorne null.
- "tipo_documento": Classificação do documento (ex: "Diploma", "Certificado", "Histórico Escolar", "Declaração", "Currículo", "Outro"). Se mesmo após análise visual não for possível classificar, informe "Não identificado".

REGRAS:
1. Responda APENAS o JSON válido. Sem explicações, sem comentários e sem formatação fora do JSON.
2. Não invente nenhuma informação. Se não estiver visível na imagem, preencha o valor como null.
"""


def build_prompt(document_text: str) -> str:
    return f"""Analise o seguinte texto extraído de um documento acadêmico (diploma, certificado, histórico escolar, declaração, currículo, etc.) e extraia as informações com a máxima precisão.

Texto extraído do documento:
\"\"\"
{document_text}
\"\"\"

Extraia as seguintes informações e retorne ESTRITAMENTE um objeto JSON com as chaves exatas abaixo:
- "data": Data principal do documento (data de emissão do diploma, conclusão do curso ou colação de grau, ex: "18 de dezembro de 2023" ou "18/12/2023"). Se não encontrar, retorne null.
- "beneficiario": Nome completo do aluno / diplomado / titular do certificado. Se não encontrar, retorne null.
- "cpf": CPF do beneficiário / titular identificado no texto (ex: "000.000.000-00" ou números). Se não houver menção ao CPF, retorne null.
- "rg": Número da Cédula de Identidade / RG / Registro Geral do titular (incluindo órgão emissor e UF se constar, ex: "12.345.678-9 SSP/SP" ou "MG-12.345.678"). Se não houver menção ao RG, retorne null.
- "curso": Nome completo e oficial do curso concluído (ex: "Pós-graduação Lato Sensu em Gestão Escolar", "Bacharelado em Administração"). Se não encontrar, retorne null.
- "natureza_curso": Nível ou natureza acadêmica do curso identificado no documento. Classifique em uma das opções:
    * "Graduação / Curso Superior" (para Bacharelado, Licenciatura, Tecnólogo)
    * "Pós-Graduação Lato Sensu (Especialização/MBA)"
    * "Pós-Graduação Stricto Sensu (Mestrado/Doutorado)"
    * "Curso Técnico / Profissionalizante"
    * "Curso de Extensão / Aperfeiçoamento"
    * "Educação Básica" (Fundamental / Médio)
    * Ou null se não for possível determinar ou não for curso.
- "carga_horaria": Carga horária total do curso (ex: "750 h/aulas", "360 horas", "750h"). Se não encontrar, retorne null.
- "faculdade": Nome completo da faculdade, universidade ou instituição de ensino emissora (ex: "Faculdades Integradas Vale do Rio Verde - FIVAR"). Se não encontrar, retorne null.
- "tipo_documento": Classificação do documento (ex: "Diploma", "Certificado", "Currículo", "Histórico Escolar", "Declaração", "Outro").

REGRAS:
1. Responda APENAS o JSON válido. Sem explicações, sem comentários e sem formatação fora do JSON.
2. Não invente nenhuma informação. Se não estiver explícito no texto, preencha o valor como null.
"""


# ---------------------------------------------------------------------------
# Processamento de um único PDF
# ---------------------------------------------------------------------------
def process_single_pdf(
    pdf_path: Path,
    client: BaseLLMClient,
    max_pages: int = 4,
    force_ocr: bool = False,
    skip_ocr: bool = False,
    metadata: Optional[Dict[str, str]] = None
) -> Dict[str, Any]:
    # Metadados do arquivo (MD5, data de criação e modificação)
    meta = metadata or get_file_metadata(pdf_path)

    res_dict = {
        "md5": meta["md5"],
        "data_criacao": meta["data_criacao"],
        "data_modificacao": meta["data_modificacao"],
        "data": None,
        "beneficiario": None,
        "cpf": None,
        "rg": None,
        "curso": None,
        "natureza_curso": None,
        "carga_horaria": None,
        "faculdade": None,
        "tipo_documento": None,
        "status": "pendente",
        "erro": None,
        "metodo_leitura": "texto_digital",
        "tentativa_ocr_llm": False,
        "processado_em": datetime.now().isoformat()
    }

    try:
        # Extração de texto da camada digital nativa
        text = extract_pdf_text(str(pdf_path), max_pages=max_pages)
        has_text = bool(text and len(text.strip()) >= 15)

        # Helper para sanitização de strings e listas
        def _clean_str(v):
            if isinstance(v, list):
                return ", ".join(str(x) for x in v if x).strip() or None
            if isinstance(v, str):
                return v.strip() or None
            return v

        # ---------------------------------------------------------------------
        # CASO 1: Arquivo sem texto legível digitalmente OU force_ocr -> OCR usando a LLM
        # ---------------------------------------------------------------------
        if not has_text or force_ocr:
            if skip_ocr:
                res_dict["status"] = "erro"
                res_dict["erro"] = "Documento sem texto legível digitalmente (requer OCR, mas --skip-ocr está ativo)."
                return res_dict

            images = render_pdf_pages_to_base64(str(pdf_path), max_pages=min(max_pages, 2))
            if not images:
                res_dict["status"] = "erro"
                res_dict["erro"] = "Documento sem texto legível digitalmente e falha ao renderizar páginas para OCR."
                return res_dict

            try:
                extra_ctx = text if (force_ocr and has_text) else None
                vision_prompt = build_vision_prompt(extra_context=extra_ctx)
                extracted_data = client.generate_json_with_images(vision_prompt, images)
                res_dict["metodo_leitura"] = "ocr_llm" if not has_text else "hibrido_texto_e_ocr_llm"
                res_dict["tentativa_ocr_llm"] = True
            except Exception as e:
                # Fallback gracioso: se a chamada com imagens falhar (ex: modelo sem suporte a visão)
                # mas o documento possuir camada de texto digital, aproveita a leitura do texto:
                if has_text:
                    try:
                        print(f"[*] Chamada de visão falhou ({e}). Fazendo fallback para texto digital...")
                        prompt = build_prompt(text)
                        extracted_data = client.generate_json(prompt)
                        res_dict["metodo_leitura"] = "texto_digital"
                        res_dict["tentativa_ocr_llm"] = True
                    except Exception as e2:
                        res_dict["status"] = "erro"
                        res_dict["erro"] = f"Falha no OCR via LLM ({e}) e na leitura textual ({e2})"
                        res_dict["tentativa_ocr_llm"] = True
                        return res_dict
                else:
                    res_dict["status"] = "erro"
                    res_dict["erro"] = f"Falha no OCR via LLM: {e}"
                    res_dict["tentativa_ocr_llm"] = True
                    return res_dict
        else:
            # Leitura normal da camada de texto digital via LLM
            prompt = build_prompt(text)
            extracted_data = client.generate_json(prompt)
            res_dict["metodo_leitura"] = "texto_digital"

        # Preenchimento e sanitização dos campos extraídos
        res_dict["data"] = _clean_str(extracted_data.get("data"))
        res_dict["beneficiario"] = _clean_str(extracted_data.get("beneficiario"))

        # Tratamento e fallback para CPF
        cpf_val = extracted_data.get("cpf")
        formatted_cpf = format_cpf(cpf_val)
        if not formatted_cpf and has_text:
            formatted_cpf = extract_cpf_fallback(text)
        res_dict["cpf"] = formatted_cpf

        # Tratamento e fallback para RG / Identidade
        rg_val = _clean_str(extracted_data.get("rg"))
        if not rg_val and has_text:
            rg_val = extract_rg_fallback(text)
        res_dict["rg"] = rg_val

        res_dict["curso"] = _clean_str(extracted_data.get("curso"))
        res_dict["natureza_curso"] = _clean_str(extracted_data.get("natureza_curso"))
        res_dict["carga_horaria"] = _clean_str(extracted_data.get("carga_horaria"))
        res_dict["faculdade"] = _clean_str(extracted_data.get("faculdade"))
        res_dict["tipo_documento"] = _clean_str(extracted_data.get("tipo_documento"))

        # ---------------------------------------------------------------------
        # CASO 2: Tinha camada de leitura, mas:
        # A) O tipo_documento ficou "Não identificado" / "Outro" / None
        # OU
        # B) Foi detectado um CPF, mas com sintaxe errada (tamanho != 11, formatação incorreta ou dígitos inválidos)
        # OU
        # C) Nem beneficiário (aluno) nem curso foram identificados (ex: texto ilegível/fonte sem mapa)
        # Tenta OCR via LLM uma única vez ("Caso não seja identificado novamente, não insista mais").
        # ---------------------------------------------------------------------
        tipo_atual = (res_dict.get("tipo_documento") or "").strip().lower()
        is_tipo_unidentified = (not tipo_atual) or tipo_atual in [
            "não identificado", "nao identificado", "outro", "não informado", "nao informado"
        ]

        cpf_atual = res_dict.get("cpf")
        is_cpf_flawed = bool(cpf_atual and not is_valid_cpf_syntax(cpf_atual))

        is_dados_principais_missing = (not res_dict.get("beneficiario")) and (not res_dict.get("curso"))

        precisa_releitura_ocr = (is_tipo_unidentified or is_cpf_flawed or is_dados_principais_missing)

        if has_text and precisa_releitura_ocr and not res_dict.get("tentativa_ocr_llm") and not skip_ocr:
            res_dict["tentativa_ocr_llm"] = True
            try:
                images = render_pdf_pages_to_base64(str(pdf_path), max_pages=min(max_pages, 2))
                if images:
                    extra_notes = []
                    if is_tipo_unidentified:
                        extra_notes.append("O 'tipo_documento' não pôde ser determinado com precisão na leitura textual.")
                    if is_cpf_flawed:
                        extra_notes.append(f"O CPF extraído da camada de texto ({cpf_atual}) está com sintaxe ou dígitos incorretos. Verifique visualmente com atenção o CPF impresso no documento.")
                    if is_dados_principais_missing:
                        extra_notes.append("O nome do aluno (beneficiário) e/ou curso não foram encontrados no texto digital. Verifique atentamente o documento visualmente.")

                    context_msg = f"{text}\n\n" + "\n".join(extra_notes)
                    vision_prompt = build_vision_prompt(extra_context=context_msg)
                    ocr_data = client.generate_json_with_images(vision_prompt, images)

                    # 1. Atualiza tipo de documento se OCR classificou
                    if is_tipo_unidentified:
                        new_tipo = _clean_str(ocr_data.get("tipo_documento"))
                        if new_tipo and new_tipo.lower() not in [
                            "não identificado", "nao identificado", "outro", "não informado", "nao informado"
                        ]:
                            res_dict["tipo_documento"] = new_tipo
                            res_dict["metodo_leitura"] = "hibrido_texto_e_ocr_llm"

                    # 2. Atualiza CPF se OCR encontrou CPF com sintaxe correta
                    new_cpf_raw = ocr_data.get("cpf")
                    if new_cpf_raw:
                        formatted_new_cpf = format_cpf(new_cpf_raw)
                        if formatted_new_cpf and is_valid_cpf_syntax(formatted_new_cpf):
                            res_dict["cpf"] = formatted_new_cpf
                            res_dict["metodo_leitura"] = "hibrido_texto_e_ocr_llm"

                    # 3. Aproveita outros dados que o OCR possa ter localizado e que estavam vazios
                    if not res_dict["beneficiario"] and ocr_data.get("beneficiario"):
                        res_dict["beneficiario"] = _clean_str(ocr_data.get("beneficiario"))
                    if not res_dict["rg"] and ocr_data.get("rg"):
                        res_dict["rg"] = _clean_str(ocr_data.get("rg"))
                    if not res_dict["curso"] and ocr_data.get("curso"):
                        res_dict["curso"] = _clean_str(ocr_data.get("curso"))
                    if not res_dict["natureza_curso"] and ocr_data.get("natureza_curso"):
                        res_dict["natureza_curso"] = _clean_str(ocr_data.get("natureza_curso"))
                    if not res_dict["carga_horaria"] and ocr_data.get("carga_horaria"):
                        res_dict["carga_horaria"] = _clean_str(ocr_data.get("carga_horaria"))
                    if not res_dict["faculdade"] and ocr_data.get("faculdade"):
                        res_dict["faculdade"] = _clean_str(ocr_data.get("faculdade"))
                    if not res_dict["data"] and ocr_data.get("data"):
                        res_dict["data"] = _clean_str(ocr_data.get("data"))
            except Exception:
                # Se falhar a tentativa de OCR ou continuar não identificado, não insiste mais
                pass

        # Validação de sucesso: pelo menos algum campo relevante identificado
        campos_uteis = [
            res_dict["beneficiario"],
            res_dict["curso"],
            res_dict["cpf"],
            res_dict["rg"],
            res_dict["faculdade"],
            res_dict["tipo_documento"]
        ]
        if any(campos_uteis):
            res_dict["status"] = "sucesso"
            res_dict["erro"] = None
        else:
            res_dict["status"] = "erro"
            res_dict["erro"] = "Documento sem informações identificáveis após análise."

    except Exception as e:
        res_dict["status"] = "erro"
        res_dict["erro"] = str(e)

    return res_dict


# ---------------------------------------------------------------------------
# Formatação de Saídas (JSON e TXT)
# ---------------------------------------------------------------------------
def format_single_txt(item: Dict[str, Any]) -> str:
    metodo = item.get("metodo_leitura", "texto_digital")
    if item.get("tentativa_ocr_llm"):
        metodo += " (OCR LLM acionado)"
    return f"""--------------------------------------------------------------------------------
MD5                 : {item.get('md5')}
Status              : {item.get('status', '').upper()}
Método de Leitura   : {metodo}
Data de Criação     : {item.get('data_criacao')}
Data de Modificação : {item.get('data_modificacao')}
Tipo Documento      : {item.get('tipo_documento') or 'Não identificado'}
Beneficiário        : {item.get('beneficiario') or 'Não informado'}
CPF                 : {item.get('cpf') or 'Não informado'}
RG / Identidade     : {item.get('rg') or 'Não informado'}
Curso               : {item.get('curso') or 'Não informado'}
Natureza do Curso   : {item.get('natureza_curso') or 'Não identificada'}
Carga Horária       : {item.get('carga_horaria') or 'Não informada'}
Faculdade           : {item.get('faculdade') or 'Não informada'}
Data do Documento   : {item.get('data') or 'Não informada'}
Processado em       : {item.get('processado_em')}
{f"Erro                : {item.get('erro')}" if item.get('erro') else ""}
--------------------------------------------------------------------------------
"""


def generate_consolidated_txt(
    results: List[Dict[str, Any]],
    provider_name: str,
    model_name: str
) -> str:
    total = len(results)
    sucesso = sum(1 for r in results if r.get("status") == "sucesso")
    erros = total - sucesso
    now_str = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

    lines = [
        "=" * 80,
        "RELATÓRIO CONSOLIDADO DE CLASSIFICAÇÃO DE DIPLOMAS E CERTIFICADOS",
        f"Data/Hora de Geração : {now_str}",
        f"Provedor LLM         : {provider_name.upper()} (Modelo: {model_name})",
        f"Total de Documentos  : {total}",
        f"Classificados com OK : {sucesso}",
        f"Falhas / Erros       : {erros}",
        "=" * 80,
        ""
    ]

    for idx, item in enumerate(results, 1):
        lines.append(f"[{idx}/{total}] MD5: {item.get('md5')}")
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
        if item.get("erro"):
            lines.append(f"  • Detalhe do Erro    : {item.get('erro')}")
        lines.append("-" * 80)

    lines.append("")
    lines.append("=" * 80)
    lines.append("FIM DO RELATÓRIO")
    lines.append("=" * 80)

    return "\n".join(lines)


def save_consolidated_reports(
    items_dict: Dict[str, Any],
    out_dir: Path,
    provider_name: str,
    model_name: str
) -> None:
    """
    Salva os relatórios consolidado JSON e TXT de forma atômica para evitar perda ou
    corrupção de dados em caso de parada forçada (Ctrl+C, kill ou reinicialização).
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    consolidated_json_path = out_dir / "classificacao_diplomas.json"
    consolidated_txt_path = out_dir / "classificacao_diplomas.txt"
    results = sorted(list(items_dict.values()), key=lambda x: str(x.get("md5", "")))

    # 1. JSON consolidado atômico
    tmp_json = out_dir / f".tmp_{consolidated_json_path.name}"
    try:
        with open(tmp_json, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        tmp_json.replace(consolidated_json_path)
    except Exception as e:
        print(f"[Aviso] Falha ao gravar {consolidated_json_path.name}: {e}")

    # 2. TXT consolidado atômico
    try:
        report_text = generate_consolidated_txt(results, provider_name, model_name)
        tmp_txt = out_dir / f".tmp_{consolidated_txt_path.name}"
        with open(tmp_txt, "w", encoding="utf-8") as f:
            f.write(report_text)
        tmp_txt.replace(consolidated_txt_path)
    except Exception as e:
        print(f"[Aviso] Falha ao gravar {consolidated_txt_path.name}: {e}")


# ---------------------------------------------------------------------------
# Menu Interativo e Auxiliares de Configuração
# ---------------------------------------------------------------------------
def resolve_default_input_path(specified: Optional[str] = None) -> str:
    if specified and specified not in ["./pdf", "pdf"]:
        return str(specified)
    return "./pdf"


def count_pdfs_in_path(p: Path) -> int:
    if not p.exists():
        return 0
    if p.is_file():
        return 1 if p.suffix.lower() == ".pdf" else 0
    return len(list(p.glob("*.pdf")) + list(p.glob("*.PDF")))


def get_available_ollama_models(
    base_url: str = "http://localhost:11434",
    docker_container: Optional[str] = None
) -> List[str]:
    envs = detect_ollama_environments(base_url=base_url)
    if docker_container:
        for e in envs:
            if e.get("container") == docker_container:
                return e.get("models", [])
    for e in envs:
        if e.get("is_running") and e.get("models"):
            return e.get("models", [])
    return []


def prompt_interactive_menu(args: argparse.Namespace) -> argparse.Namespace:
    print("\n" + "=" * 70)
    print("🎓 JOACLASSIFICADOR-PDF - MENU INTERATIVO DE CLASSIFICAÇÃO")
    print("=" * 70)
    print("Pressione ENTER para aceitar o valor padrão sugerido entre colchetes [ ].")

    # Opção inicial se houver configurações personalizadas salvas
    if has_custom_config("classificador"):
        print("\n⚙️  Configurações salvas da execução anterior detectadas:")
        print("   1) Continuar e personalizar configurações salvas [Padrão]")
        print("   2) Restaurar todos os padrões de fábrica (limpar configurações salvas)")
        try:
            init_choice = input("Escolha a opção (1 ou 2) [1]: ").strip()
            if init_choice == "2":
                reset_classifier_config()
                factory = get_factory_defaults()["classificador"]
                for k, v in factory.items():
                    setattr(args, k, v)
                print("   [✓] Configurações restauradas com sucesso para os padrões de fábrica neutros!\n")
        except (EOFError, KeyboardInterrupt):
            print("\n[Operação cancelada pelo usuário]")
            sys.exit(0)

    # 1. Pasta ou arquivo de entrada
    default_input = resolve_default_input_path(args.input)
    while True:
        try:
            resp_input = input(f"\n📁 Pasta ou arquivo PDF de entrada [{default_input}]: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n[Operação cancelada pelo usuário]")
            sys.exit(0)

        if resp_input.lower() in ["reset", "resetar", "padrao", "fábrica", "fabrica"]:
            reset_classifier_config()
            factory = get_factory_defaults()["classificador"]
            for k, v in factory.items():
                setattr(args, k, v)
            default_input = resolve_default_input_path(args.input)
            print("   [✓] Configurações restauradas para os padrões de fábrica neutros!")
            continue

        raw_chosen = resp_input if resp_input else default_input
        chosen_path = Path(raw_chosen).expanduser().resolve()
        if not chosen_path.exists():
            print(f"   ⚠️  Aviso: Caminho '{chosen_path}' não foi encontrado.")
            try:
                conf = input("   Deseja manter esse caminho mesmo assim? (s/N): ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                sys.exit(0)
            if conf in ["s", "sim", "y", "yes"]:
                args.input = raw_chosen
                break
        else:
            pdf_count = count_pdfs_in_path(chosen_path)
            if pdf_count == 0:
                print(f"   ⚠️  Aviso: Nenhum arquivo PDF encontrado em '{chosen_path}'.")
                try:
                    conf = input("   Deseja manter esse caminho mesmo assim? (s/N): ").strip().lower()
                except (EOFError, KeyboardInterrupt):
                    sys.exit(0)
                if conf in ["s", "sim", "y", "yes"]:
                    args.input = raw_chosen
                    break
            else:
                print(f"   ↳ {pdf_count} arquivo(s) PDF localizado(s) para processar.")
                args.input = raw_chosen
                break

    # 2. Pasta de saída
    default_out = args.output_dir or "./saida"
    while True:
        try:
            resp_out = input(f"\n📄 Pasta de saída dos relatórios [{default_out}]: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n[Operação cancelada pelo usuário]")
            sys.exit(0)

        chosen_out = resp_out if resp_out else default_out
        args.output_dir = chosen_out
        break

    # 3. Provedor de IA
    print("\n🤖 Provedor de Inteligência Artificial:")
    print("   1) Ollama (Modelos locais ou Docker open-webui) [Padrão]")
    print("   2) OpenAI (Modelos em nuvem via API)")
    while True:
        try:
            resp_prov = input(f"Escolha o provedor (1 ou 2) [1]: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n[Operação cancelada pelo usuário]")
            sys.exit(0)

        if resp_prov in ["", "1", "ollama"]:
            args.provider = "ollama"
            break
        elif resp_prov in ["2", "openai"]:
            args.provider = "openai"
            break
        else:
            print("   ⚠️  Opção inválida. Digite 1 ou 2.")

    # 4. Modelo de IA
    if args.provider == "ollama":
        print("\n🔍 Detectando ambientes Ollama (Nativo no sistema, Docker oficial puro, Open-WebUI)...")
        detected_envs = detect_ollama_environments(base_url=args.ollama_url)
        running_envs = [e for e in detected_envs if e.get("is_running")]

        chosen_env = None
        if len(running_envs) == 1:
            chosen_env = running_envs[0]
            print(f"   [✓] {chosen_env['description']}")
            if chosen_env["container"]:
                args.docker = chosen_env["container"]
        elif len(running_envs) > 1:
            print(f"   [✓] Foram identificados {len(running_envs)} ambientes Ollama ativos:")
            for idx, env_opt in enumerate(running_envs, 1):
                m_prev = f" (Modelos: {', '.join(env_opt['models'][:3])})" if env_opt.get("models") else " (Sem modelos baixados)"
                print(f"      {idx}) {env_opt['description']}{m_prev}")
            try:
                resp_env = input(f"   Selecione o ambiente Ollama desejado (1-{len(running_envs)}) [1]: ").strip()
                sel_idx = int(resp_env) - 1 if (resp_env.isdigit() and 1 <= int(resp_env) <= len(running_envs)) else 0
                chosen_env = running_envs[sel_idx]
                if chosen_env["container"]:
                    args.docker = chosen_env["container"]
                else:
                    args.docker = None
            except (EOFError, KeyboardInterrupt):
                print("\n[Operação cancelada pelo usuário]")
                sys.exit(0)
        else:
            stopped_native = next((e for e in detected_envs if e.get("type") == "native_binary_stopped"), None)
            if stopped_native:
                print(f"   ⚠️  {stopped_native['description']}")
            else:
                print("   ⚠️  Nenhum servidor Ollama detectado (nem nativo em localhost:11434, nem em containers Docker).")

        available_models = chosen_env["models"] if chosen_env else []
        models_display = chosen_env.get("models_display", []) if chosen_env else []

        if available_models:
            print(f"   ↳ Modelos baixados encontrados: {', '.join(models_display or available_models)}")
            default_model = args.model or available_models[0]
        else:
            default_model = args.model or "gemma4:e4b"

        while True:
            try:
                resp_mod = input(f"\n🧠 Modelo Ollama [{default_model}]: ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\n[Operação cancelada pelo usuário]")
                sys.exit(0)
            args.model = resp_mod if resp_mod else default_model
            break
    else:
        default_model = args.model or "gpt-4o-mini"
        while True:
            try:
                resp_mod = input(f"\n🧠 Modelo OpenAI [{default_model}]: ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\n[Operação cancelada pelo usuário]")
                sys.exit(0)
            args.model = resp_mod if resp_mod else default_model
            break

        # Chave da OpenAI
        current_key = args.openai_key or os.environ.get("OPENAI_API_KEY", "")
        if current_key:
            masked = (current_key[:7] + "..." + current_key[-4:]) if len(current_key) > 12 else "********"
            prompt_key_str = f"🔑 Chave de API OpenAI [{masked} - ENTER para manter]: "
        else:
            prompt_key_str = "🔑 Chave de API OpenAI (sk-...): "

        while True:
            try:
                resp_key = input(prompt_key_str).strip()
            except (EOFError, KeyboardInterrupt):
                print("\n[Operação cancelada pelo usuário]")
                sys.exit(0)

            if resp_key:
                args.openai_key = resp_key
                break
            elif current_key:
                args.openai_key = current_key
                break
            else:
                print("   ⚠️  Aviso: O uso da OpenAI requer uma chave de API válida.")
                try:
                    conf_no_key = input("   Deseja continuar sem informar a chave agora? (s/N): ").strip().lower()
                except (EOFError, KeyboardInterrupt):
                    sys.exit(0)
                if conf_no_key in ["s", "sim", "y", "yes"]:
                    break

        # Base URL opcional (para compatibilidade com Groq, OpenRouter, vLLM, etc.)
        current_base_url = args.openai_base_url or os.environ.get("OPENAI_BASE_URL", "")
        default_url_desc = current_base_url if current_base_url else "padrão oficial OpenAI"
        try:
            resp_base = input(f"🌐 OpenAI Base URL (opcional para Groq/OpenRouter) [{default_url_desc}]: ").strip()
            if resp_base:
                args.openai_base_url = resp_base
            elif current_base_url:
                args.openai_base_url = current_base_url
        except (EOFError, KeyboardInterrupt):
            print("\n[Operação cancelada pelo usuário]")
            sys.exit(0)

    # 5. Threads de processamento (Workers)
    default_workers = args.workers if (args.workers and args.workers > 1) else (4 if args.provider == "openai" else 1)
    while True:
        try:
            resp_w = input(f"\n⚡ Concorrência / Threads simultâneas [{default_workers}]: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n[Operação cancelada pelo usuário]")
            sys.exit(0)

        if not resp_w:
            args.workers = default_workers
            break
        try:
            w_val = int(resp_w)
            if w_val >= 1:
                args.workers = w_val
                break
            else:
                print("   ⚠️  O número de workers deve ser pelo menos 1.")
        except ValueError:
            print("   ⚠️  Digite um número inteiro válido.")

    # 6. OCR Multimodal via LLM
    print("\n🔍 OCR Multimodal via LLM (para PDFs digitalizados e correções de CPF/Tipo):")
    default_ocr_str = "N" if args.skip_ocr else "S"
    try:
        resp_ocr = input(f"Deseja manter o OCR multimodal ativado? (S/n) [{default_ocr_str}]: ").strip().lower()
        if resp_ocr in ["n", "nao", "não", "no"]:
            args.skip_ocr = True
        elif resp_ocr in ["s", "sim", "y", "yes", ""]:
            args.skip_ocr = False
    except (EOFError, KeyboardInterrupt):
        print("\n[Operação cancelada pelo usuário]")
        sys.exit(0)

    # 7. Estratégia de Processamento
    print("\n⚙️  Estratégia de Processamento:")
    print("   1) Incremental: Processar novos e pendentes (ignora já concluídos com sucesso) [Padrão]")
    print("   2) Reprocessar documentos que necessitam de OCR (erros ou não identificados)")
    print("   3) Forçar reprocessamento de TODOS os documentos do zero")
    while True:
        try:
            resp_mode = input("Escolha o modo de execução (1, 2 ou 3) [1]: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n[Operação cancelada pelo usuário]")
            sys.exit(0)

        if resp_mode in ["", "1"]:
            args.force = False
            args.reprocess_ocr = False
            break
        elif resp_mode == "2":
            args.force = False
            args.reprocess_ocr = True
            break
        elif resp_mode == "3":
            args.force = True
            args.reprocess_ocr = False
            break
        else:
            print("   ⚠️  Opção inválida. Digite 1, 2 ou 3.")

    # Resumo
    in_p = Path(args.input)
    pdf_qtd = count_pdfs_in_path(in_p)
    mode_desc = (
        "Reprocessar TUDO do zero (--force)" if args.force
        else ("Reprocessar pendentes de OCR (--reprocess-ocr)" if args.reprocess_ocr
        else "Incremental (apenas novos e pendentes)")
    )
    ocr_desc = "Desativado (--skip-ocr)" if args.skip_ocr else "Ativado (Automático para escaneados e erros de CPF/Tipo)"

    print("\n" + "=" * 70)
    print("📋 RESUMO DA CONFIGURAÇÃO DO CLASSIFICADOR")
    print("=" * 70)
    print(f"• Entrada      : {args.input} ({pdf_qtd} arquivo(s) PDF)")
    print(f"• Saída        : {args.output_dir}")
    if args.provider == "openai":
        k_val = args.openai_key or os.environ.get("OPENAI_API_KEY", "")
        masked_k = (k_val[:7] + "..." + k_val[-4:]) if (k_val and len(k_val) > 12) else ("Configurada" if k_val else "Não informada")
        print(f"• Provedor     : OPENAI (Modelo: {args.model} | Chave: {masked_k})")
        if args.openai_base_url:
            print(f"• Base URL     : {args.openai_base_url}")
    else:
        print(f"• Provedor     : OLLAMA (Modelo: {args.model})")
    print(f"• Concorrência : {args.workers} thread(s)")
    print(f"• OCR com LLM  : {ocr_desc}")
    print(f"• Execução     : {mode_desc}")
    print("=" * 70)

    try:
        conf_start = input("Deseja iniciar a classificação agora? (S/n) [S]: ").strip().lower()
        if conf_start in ["n", "nao", "não", "no"]:
            print("\n[Operação cancelada pelo usuário]")
            sys.exit(0)
    except (EOFError, KeyboardInterrupt):
        print("\n[Operação cancelada pelo usuário]")
        sys.exit(0)

    # Salva opções configuradas pelo usuário para persistência
    save_classifier_config({
        "input": str(args.input),
        "output_dir": str(args.output_dir),
        "provider": args.provider,
        "model": args.model,
        "docker": args.docker,
        "ollama_url": args.ollama_url,
        "openai_key": args.openai_key,
        "openai_base_url": args.openai_base_url,
        "workers": args.workers,
        "max_pages": args.max_pages,
        "skip_ocr": args.skip_ocr,
        "no_individual": args.no_individual
    })

    print("\n" + "=" * 70 + "\n")
    return args

# ---------------------------------------------------------------------------
# Pipeline de Processamento em Lote (Compartilhado entre CLI e Web)
# ---------------------------------------------------------------------------
def run_batch_classification(
    input_path: Union[str, Path],
    output_dir: Union[str, Path],
    provider: str = "ollama",
    model: Optional[str] = None,
    ollama_url: str = "http://localhost:11434",
    docker: Optional[str] = None,
    openai_key: Optional[str] = None,
    openai_base_url: Optional[str] = None,
    workers: int = 1,
    max_pages: int = 4,
    skip_ocr: bool = False,
    reprocess_ocr: bool = False,
    force: bool = False,
    no_individual: bool = False,
    progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
    stop_checker: Optional[Callable[[], bool]] = None,
    use_tqdm: bool = True,
    client: Optional[Any] = None
) -> Dict[str, Any]:
    """
    Executa a classificação em lote de documentos PDF com suporte a:
    - Execução concorrente (workers)
    - Modo incremental inteligente (recuperação contínua de individuais/ e JSON consolidado)
    - Preservação estrita de aprovações de conferência humana prévia
    - Callbacks de progresso em tempo real (compatível com visualizador web e CLI)
    - Cancelamento seguro e gracioso via stop_checker()
    """
    def notify(event: Dict[str, Any]):
        if progress_callback:
            try:
                progress_callback(event)
            except Exception as ex_cb:
                print(f"[Aviso Callback] Erro ao notificar: {ex_cb}")

    in_p = Path(input_path).expanduser().resolve()
    if not in_p.exists():
        err_msg = f"Caminho de entrada não encontrado: {in_p}"
        print(f"[ERRO] {err_msg}")
        notify({"event": "error", "error": err_msg})
        return {"status": "erro", "mensagem": err_msg, "total": 0, "results": []}

    pdf_files = []
    if in_p.is_file():
        if in_p.suffix.lower() == ".pdf":
            pdf_files.append(in_p)
        else:
            err_msg = f"O arquivo indicado não é um PDF: {in_p}"
            print(f"[ERRO] {err_msg}")
            notify({"event": "error", "error": err_msg})
            return {"status": "erro", "mensagem": err_msg, "total": 0, "results": []}
    else:
        pdf_set = set(in_p.glob("*.pdf")) | set(in_p.glob("*.PDF"))
        if not pdf_set:
            pdf_set = set(in_p.rglob("*.pdf")) | set(in_p.rglob("*.PDF"))
        pdf_files = sorted(list(pdf_set))

    if not pdf_files:
        msg = f"Nenhum arquivo PDF encontrado em: {in_p}"
        print(f"[AVISO] {msg}")
        notify({"event": "warning", "message": msg})
        return {"status": "aviso", "mensagem": msg, "total": 0, "results": []}

    print(f"[*] Total de PDFs identificados: {len(pdf_files)}")
    notify({"event": "init", "total_files": len(pdf_files), "message": f"{len(pdf_files)} PDFs identificados."})

    # Inicialização do Cliente LLM
    if client is None:
        if provider == "ollama":
            model_name = model or "gemma4:e4b"
            print(f"[*] Inicializando cliente Ollama (Modelo: {model_name})...")
            client = OllamaClient(
                model=model_name,
                base_url=ollama_url or "http://localhost:11434",
                docker_container=docker
            )
            if client.use_docker:
                c_name_lower = client.docker_container.lower()
                c_label = "Open-WebUI" if "open-webui" in c_name_lower else ("Oficial Puro" if "ollama" in c_name_lower else "Docker")
                print(f"[*] Modo de conexão: Docker exec [{c_label}] (container: '{client.docker_container}')")
            else:
                print(f"[*] Modo de conexão: Ollama Nativo / HTTP direto ({client.base_url})")
        else:
            model_name = model or "gpt-4o-mini"
            print(f"[*] Inicializando cliente OpenAI (Modelo: {model_name})...")
            client = OpenAIClient(
                model=model_name,
                api_key=openai_key,
                base_url=openai_base_url
            )
    else:
        model_name = getattr(client, "model", model or "llm")

    out_dir = Path(output_dir).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    indiv_dir = out_dir / "individuais"
    if not no_individual:
        indiv_dir.mkdir(parents=True, exist_ok=True)

    consolidated_json_path = out_dir / "classificacao_diplomas.json"
    consolidated_txt_path = out_dir / "classificacao_diplomas.txt"
    existing_by_md5 = {}

    # 1. Carrega processamentos anteriores do JSON consolidado (se existir e não for --force)
    count_from_consolidated = 0
    if consolidated_json_path.exists() and not force:
        try:
            with open(consolidated_json_path, "r", encoding="utf-8") as f:
                old_data = json.load(f)
                if isinstance(old_data, list):
                    for item in old_data:
                        if isinstance(item, dict) and "md5" in item:
                            existing_by_md5[item["md5"]] = item
                            count_from_consolidated += 1
        except Exception as e:
            print(f"[Aviso] Não foi possível ler {consolidated_json_path.name}: {e}")

    # 2. Carrega / reconcilia arquivos da pasta 'individuais'
    count_from_indiv = 0
    if indiv_dir.exists() and not force:
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
                                    count_from_indiv += 1
                        except Exception:
                            continue
        except Exception as e:
            print(f"[Aviso] Erro ao ler pasta de arquivos individuais: {e}")

    effective_model_name = getattr(client, "model", model_name)

    if existing_by_md5:
        details = []
        if count_from_consolidated > 0:
            details.append(f"{count_from_consolidated} do JSON consolidado")
        if count_from_indiv > 0:
            details.append(f"{count_from_indiv} recuperados da pasta individuais/")
        det_str = f" ({', '.join(details)})" if details else ""
        print(f"[*] Histórico carregado: {len(existing_by_md5)} documento(s) já classificados{det_str}.")

        if count_from_indiv > 0:
            save_consolidated_reports(existing_by_md5, out_dir, provider, effective_model_name)
            print(f"[*] Relatório consolidado sincronizado com sucesso ({len(existing_by_md5)} documentos salvos).")

    # 3. Indexa hashes MD5 dos PDFs de entrada
    if stop_checker and stop_checker():
        return {
            "status": "interrompido",
            "total": len(pdf_files),
            "processed": 0,
            "already_done": len(existing_by_md5),
            "new_processed": 0,
            "sucessos": sum(1 for r in existing_by_md5.values() if r.get("status") == "sucesso"),
            "erros": sum(1 for r in existing_by_md5.values() if r.get("status") != "sucesso"),
            "results": list(existing_by_md5.values()),
            "json_path": str(consolidated_json_path),
            "txt_path": str(consolidated_txt_path),
            "mensagem": "Interrompido antes da indexação."
        }

    print(f"[*] Indexando e verificando integridade de {len(pdf_files)} PDF(s)...")
    notify({"event": "indexing", "total_files": len(pdf_files), "message": f"Indexando integridade de {len(pdf_files)} PDFs..."})

    pdf_meta_map = {}
    if len(pdf_files) > 20:
        workers_idx = min(16, (os.cpu_count() or 4) * 2)
        with ThreadPoolExecutor(max_workers=workers_idx) as executor:
            future_to_pdf = {executor.submit(get_file_metadata, p): p for p in pdf_files}
            iterator = as_completed(future_to_pdf)
            if use_tqdm and tqdm:
                iterator = tqdm(iterator, total=len(pdf_files), desc="Indexando PDFs (MD5)", unit="doc")
            for idx_i, fut in enumerate(iterator, 1):
                if stop_checker and stop_checker():
                    executor.shutdown(wait=False, cancel_futures=True)
                    return {
                        "status": "interrompido",
                        "total": len(pdf_files),
                        "processed": 0,
                        "already_done": len(existing_by_md5),
                        "new_processed": 0,
                        "sucessos": sum(1 for r in existing_by_md5.values() if r.get("status") == "sucesso"),
                        "erros": sum(1 for r in existing_by_md5.values() if r.get("status") != "sucesso"),
                        "results": list(existing_by_md5.values()),
                        "json_path": str(consolidated_json_path),
                        "txt_path": str(consolidated_txt_path),
                        "mensagem": "Interrompido durante a indexação."
                    }
                p = future_to_pdf[fut]
                try:
                    pdf_meta_map[p] = fut.result()
                except Exception:
                    pdf_meta_map[p] = {"md5": "", "data_criacao": "", "data_modificacao": ""}
                if idx_i % 25 == 0:
                    notify({"event": "indexing_progress", "indexed": idx_i, "total": len(pdf_files)})
    else:
        for p in pdf_files:
            try:
                pdf_meta_map[p] = get_file_metadata(p)
            except Exception:
                pdf_meta_map[p] = {"md5": "", "data_criacao": "", "data_modificacao": ""}

    # 4. Separa os arquivos entre já processados e novos/pendentes
    files_to_process = []
    already_done_results = []
    ocr_candidate_count = 0
    seen_md5_to_process = set()

    for pdf in pdf_files:
        meta = pdf_meta_map.get(pdf) or get_file_metadata(pdf)
        h = meta.get("md5", "")
        if not h:
            files_to_process.append(pdf)
            continue

        if h in existing_by_md5 and not force:
            item = existing_by_md5[h]
            # Respeita sempre aprovação manual humana
            if item.get("status_conferencia") == "aprovado":
                already_done_results.append(item)
                continue

            # Se o usuário solicitou reprocessamento de OCR (--reprocess-ocr / Opção 2)
            if reprocess_ocr:
                tipo_atual = (item.get("tipo_documento") or "").strip().lower()
                tipo_nao_identificado = (not tipo_atual) or tipo_atual in [
                    "não identificado", "nao identificado", "outro", "não informado", "nao informado"
                ]
                cpf_item = item.get("cpf")
                cpf_invalido = bool(cpf_item and not is_valid_cpf_syntax(cpf_item))
                teve_tentativa_ocr = item.get("tentativa_ocr_llm", False)
                teve_erro_ocr = (item.get("status") == "erro") and ("OCR" in (item.get("erro") or ""))

                precisa_ocr = (teve_erro_ocr or ((tipo_nao_identificado or cpf_invalido) and not teve_tentativa_ocr))

                if not skip_ocr and precisa_ocr:
                    if h not in seen_md5_to_process:
                        files_to_process.append(pdf)
                        seen_md5_to_process.add(h)
                    ocr_candidate_count += 1
                else:
                    already_done_results.append(item)
            else:
                # Modo Incremental padrão
                if item.get("status") == "sucesso":
                    already_done_results.append(item)
                else:
                    if h not in seen_md5_to_process:
                        files_to_process.append(pdf)
                        seen_md5_to_process.add(h)
        else:
            if h not in seen_md5_to_process:
                files_to_process.append(pdf)
                seen_md5_to_process.add(h)

    if ocr_candidate_count > 0:
        print(f"[*] Identificados {ocr_candidate_count} documento(s) elegíveis para OCR via LLM (erros de leitura, tipo não identificado ou CPF com sintaxe errada).")

    print(f"[*] Total de PDFs: {len(pdf_files)} | Já concluídos: {len(already_done_results)} | A processar: {len(files_to_process)}")
    notify({
        "event": "ready",
        "total_files": len(pdf_files),
        "already_done": len(already_done_results),
        "to_process": len(files_to_process),
        "ocr_candidates": ocr_candidate_count,
        "message": f"Pronto. {len(files_to_process)} a processar, {len(already_done_results)} já concluídos."
    })

    # Mantém um dicionário global unificado com todo o histórico acumulado
    active_results = dict(existing_by_md5)
    new_results = []
    processed_count = 0
    success_count = 0
    error_count = 0
    save_interval = 10
    was_stopped = False

    if files_to_process:
        print(f"[*] Iniciando classificação de {len(files_to_process)} documento(s) com {workers} worker(s)...")
        notify({"event": "start_batch", "to_process": len(files_to_process), "workers": workers})

        def handle_file(pdf: Path):
            meta = pdf_meta_map.get(pdf) or get_file_metadata(pdf)
            h = meta.get("md5")
            old_item = existing_by_md5.get(h)

            res = process_single_pdf(
                pdf,
                client,
                max_pages=max_pages,
                skip_ocr=skip_ocr,
                metadata=meta
            )

            # Preserva metadados de conferência humana caso já existissem
            if old_item:
                if "status_conferencia" in old_item:
                    res["status_conferencia"] = old_item["status_conferencia"]
                if "observacoes_conferencia" in old_item:
                    res["observacoes_conferencia"] = old_item["observacoes_conferencia"]
                if "conferido_em" in old_item:
                    res["conferido_em"] = old_item["conferido_em"]

            if not no_individual:
                file_identifier = res["md5"]
                single_json_path = indiv_dir / f"{file_identifier}.json"
                tmp_single_json = indiv_dir / f".{file_identifier}.json.tmp"
                try:
                    with open(tmp_single_json, "w", encoding="utf-8") as f:
                        json.dump(res, f, ensure_ascii=False, indent=2)
                    tmp_single_json.replace(single_json_path)
                except Exception as e:
                    print(f"[Aviso] Falha ao gravar {single_json_path.name}: {e}")

                single_txt_path = indiv_dir / f"{file_identifier}.txt"
                tmp_single_txt = indiv_dir / f".{file_identifier}.txt.tmp"
                try:
                    with open(tmp_single_txt, "w", encoding="utf-8") as f:
                        f.write(format_single_txt(res))
                    tmp_single_txt.replace(single_txt_path)
                except Exception as e:
                    print(f"[Aviso] Falha ao gravar {single_txt_path.name}: {e}")

            return res

        if workers > 1:
            executor = ThreadPoolExecutor(max_workers=workers)
            try:
                future_to_file = {executor.submit(handle_file, f): f for f in files_to_process}
                iterator = as_completed(future_to_file)
                if use_tqdm and tqdm:
                    iterator = tqdm(iterator, total=len(files_to_process), desc="Processando Novos PDFs", unit="doc")
                for future in iterator:
                    if stop_checker and stop_checker():
                        print("\n[!] Interrupção solicitada pelo usuário. Encerrando lote...")
                        was_stopped = True
                        executor.shutdown(wait=False, cancel_futures=True)
                        break

                    try:
                        res = future.result()
                        new_results.append(res)
                        active_results[res["md5"]] = res
                        processed_count += 1
                        if res.get("status") == "sucesso":
                            success_count += 1
                        else:
                            error_count += 1

                        cur_file = future_to_file[future].name
                        notify({
                            "event": "file_done",
                            "current_file": cur_file,
                            "processed_count": processed_count,
                            "to_process_count": len(files_to_process),
                            "total_files": len(pdf_files),
                            "success_count": success_count,
                            "error_count": error_count,
                            "item": res
                        })

                        if processed_count % save_interval == 0:
                            save_consolidated_reports(active_results, out_dir, provider, effective_model_name)
                            notify({"event": "periodic_save", "total_saved": len(active_results)})
                    except Exception as e:
                        error_count += 1
                        print(f"[Erro no processamento de arquivo] {e}")
            except KeyboardInterrupt:
                print("\n\n[!] Interrupção solicitada pelo usuário (Ctrl+C). Cancelando fila e salvando dados...")
                executor.shutdown(wait=False, cancel_futures=True)
                was_stopped = True
            finally:
                executor.shutdown(wait=False)
        else:
            iterator = files_to_process
            if use_tqdm and tqdm:
                iterator = tqdm(files_to_process, desc="Processando Novos PDFs", unit="doc")
            try:
                for f in iterator:
                    if stop_checker and stop_checker():
                        print("\n[!] Interrupção solicitada pelo usuário. Encerrando lote...")
                        was_stopped = True
                        break

                    try:
                        notify({"event": "file_start", "current_file": f.name})
                        res = handle_file(f)
                        new_results.append(res)
                        active_results[res["md5"]] = res
                        processed_count += 1
                        if res.get("status") == "sucesso":
                            success_count += 1
                        else:
                            error_count += 1

                        notify({
                            "event": "file_done",
                            "current_file": f.name,
                            "processed_count": processed_count,
                            "to_process_count": len(files_to_process),
                            "total_files": len(pdf_files),
                            "success_count": success_count,
                            "error_count": error_count,
                            "item": res
                        })

                        if processed_count % save_interval == 0:
                            save_consolidated_reports(active_results, out_dir, provider, effective_model_name)
                            notify({"event": "periodic_save", "total_saved": len(active_results)})
                    except Exception as e:
                        error_count += 1
                        print(f"[Erro no processamento do arquivo {f.name}] {e}")
            except KeyboardInterrupt:
                print("\n\n[!] Interrupção solicitada pelo usuário (Ctrl+C). Salvando dados...")
                was_stopped = True
    else:
        print("[*] Todos os documentos já estão atualizados no banco de dados!")
        notify({"event": "up_to_date", "message": "Todos os documentos já estão atualizados."})

    # Gravação final consolidada
    save_consolidated_reports(active_results, out_dir, provider, effective_model_name)
    results = sorted(list(active_results.values()), key=lambda x: str(x.get("md5", "")))
    sucessos_totais = sum(1 for r in results if r.get("status") == "sucesso")
    erros_totais = len(results) - sucessos_totais

    if was_stopped:
        print(f"[✓] Progresso salvo com sucesso! ({len(active_results)} documentos totais no consolidado e individuais)")
        print("[*] Você pode retomar a qualquer momento escolhendo a Opção 1 (Incremental).")
        notify({
            "event": "stopped",
            "message": f"Processamento interrompido. {processed_count} novos processados. Total consolidado: {len(active_results)}.",
            "processed_count": processed_count,
            "total_files": len(pdf_files),
            "sucessos": sucessos_totais,
            "erros": erros_totais
        })
        return {
            "status": "interrompido",
            "total": len(pdf_files),
            "processed": processed_count,
            "already_done": len(already_done_results),
            "new_processed": len(new_results),
            "sucessos": sucessos_totais,
            "erros": erros_totais,
            "results": results,
            "json_path": str(consolidated_json_path),
            "txt_path": str(consolidated_txt_path),
            "mensagem": "Processamento interrompido pelo usuário."
        }

    print("\n" + "=" * 60)
    print("PROCESSAMENTO CONCLUÍDO COM SUCESSO!")
    print(f"Total processados : {len(results)}")
    print(f"Classificados OK  : {sucessos_totais}")
    print(f"Erros             : {erros_totais}")
    print("-" * 60)
    print(f"Relatório JSON consolidado : {consolidated_json_path}")
    print(f"Relatório TXT consolidado  : {consolidated_txt_path}")
    if not no_individual:
        print(f"Arquivos individuais (MD5) : {indiv_dir}/")
    print("=" * 60 + "\n")

    notify({
        "event": "completed",
        "message": f"Processamento concluído com sucesso! {len(results)} documentos consolidados.",
        "total_files": len(pdf_files),
        "processed_count": processed_count,
        "sucessos": sucessos_totais,
        "erros": erros_totais
    })

    return {
        "status": "sucesso",
        "total": len(pdf_files),
        "processed": processed_count,
        "already_done": len(already_done_results),
        "new_processed": len(new_results),
        "sucessos": sucessos_totais,
        "erros": erros_totais,
        "results": results,
        "json_path": str(consolidated_json_path),
        "txt_path": str(consolidated_txt_path),
        "mensagem": "Processamento concluído com sucesso!"
    }


# ---------------------------------------------------------------------------
# Execução Principal (CLI)
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="Classificador e Extrator de Diplomas/Certificados em PDFs em Massa (Identificação por MD5, CPF e Natureza do Curso)."
    )
    parser.add_argument(
        "-i", "--input",
        type=str,
        default="./pdf",
        help="Caminho do diretório de PDFs ou de um arquivo PDF específico (padrão: %(default)s)."
    )
    parser.add_argument(
        "-o", "--output-dir",
        type=str,
        default="./saida",
        help="Diretório onde os relatórios JSON e TXT serão salvos (padrão: %(default)s)."
    )
    parser.add_argument(
        "-p", "--provider",
        choices=["ollama", "openai"],
        default="ollama",
        help="Provedor de IA a utilizar: 'ollama' ou 'openai' (padrão: %(default)s)."
    )
    parser.add_argument(
        "-m", "--model",
        type=str,
        default=None,
        help="Nome do modelo. Padrão: 'gemma4:e4b' para Ollama ou 'gpt-4o-mini' para OpenAI."
    )
    parser.add_argument(
        "--docker",
        type=str,
        default=None,
        help="Nome do container Docker do Ollama (padrão: auto-detecta 'open-webui')."
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
        help="Chave de API da OpenAI (se omitido, lê de OPENAI_API_KEY ou do arquivo .env)."
    )
    parser.add_argument(
        "--openai-base-url", "--base-url",
        dest="openai_base_url",
        type=str,
        default=None,
        help="URL base personalizada para OpenAI ou endpoints compatíveis (Groq, OpenRouter, vLLM)."
    )
    parser.add_argument(
        "-w", "--workers",
        type=int,
        default=1,
        help="Número de threads simultâneas para processamento (padrão: 1 para Ollama local)."
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=4,
        help="Máximo de páginas a ler por PDF (padrão: 4)."
    )
    parser.add_argument(
        "-f", "--force",
        action="store_true",
        help="Força o reprocessamento de todos os PDFs, ignorando os já processados com sucesso."
    )
    parser.add_argument(
        "--skip-ocr",
        action="store_true",
        help="Desativa tentativas de OCR via LLM para documentos escaneados ou não identificados."
    )
    parser.add_argument(
        "--reprocess-ocr",
        action="store_true",
        help="Força o reprocessamento de documentos que necessitam de OCR (erros de leitura e tipos não identificados)."
    )
    parser.add_argument(
        "--no-individual",
        action="store_true",
        help="Desativa a criação de arquivos JSON e TXT individuais por PDF (nomeados por MD5)."
    )
    parser.add_argument(
        "--prompt", "--interativo",
        dest="force_prompt",
        action="store_true",
        help="Abre o menu interativo no console para configurar as opções antes de iniciar."
    )
    parser.add_argument(
        "-y", "--no-prompt", "--batch",
        dest="no_prompt",
        action="store_true",
        help="Executa diretamente sem perguntas interativas no console."
    )
    parser.add_argument(
        "--reset-config", "--reset", "--factory-reset",
        dest="reset_config",
        action="store_true",
        help="Restaura todas as configurações salvas para os padrões de fábrica neutros."
    )

    # Carrega configurações salvas prévias como padrões do parser
    saved_cfg = get_classifier_config()
    parser.set_defaults(
        input=saved_cfg.get("input", "./pdf"),
        output_dir=saved_cfg.get("output_dir", "./saida"),
        provider=saved_cfg.get("provider", "ollama"),
        model=saved_cfg.get("model", None),
        docker=saved_cfg.get("docker", None),
        ollama_url=saved_cfg.get("ollama_url", "http://localhost:11434"),
        openai_key=saved_cfg.get("openai_key", None),
        openai_base_url=saved_cfg.get("openai_base_url", None),
        workers=saved_cfg.get("workers", 1),
        max_pages=saved_cfg.get("max_pages", 4),
        skip_ocr=saved_cfg.get("skip_ocr", False),
        no_individual=saved_cfg.get("no_individual", False),
    )

    args = parser.parse_args()

    if args.reset_config:
        reset_classifier_config()
        print("[✓] Configurações do classificador restauradas para os padrões de fábrica neutros com sucesso.")
        other_flags = [a for a in sys.argv[1:] if a not in ["--reset-config", "--reset", "--factory-reset"]]
        if not other_flags:
            sys.exit(0)
        defaults = get_factory_defaults()["classificador"]
        for k, v in defaults.items():
            setattr(args, k, v)

    # Detecta se foram passados argumentos explícitos via CLI
    explicit_cli_args = [
        arg for arg in sys.argv[1:]
        if arg not in ["--prompt", "--interativo", "-y", "--no-prompt", "--batch", "--reset-config", "--reset", "--factory-reset"]
    ]
    is_tty = sys.stdin.isatty()
    should_prompt = args.force_prompt or (
        is_tty
        and not args.no_prompt
        and len(explicit_cli_args) == 0
    )

    if should_prompt:
        args = prompt_interactive_menu(args)
    else:
        # Salva opções configuradas via CLI para persistência
        save_classifier_config({
            "input": str(args.input),
            "output_dir": str(args.output_dir),
            "provider": args.provider,
            "model": args.model,
            "docker": args.docker,
            "ollama_url": args.ollama_url,
            "openai_key": args.openai_key,
            "openai_base_url": args.openai_base_url,
            "workers": args.workers,
            "max_pages": args.max_pages,
            "skip_ocr": args.skip_ocr,
            "no_individual": args.no_individual
        })

    try:
        summary = run_batch_classification(
            input_path=args.input,
            output_dir=args.output_dir,
            provider=args.provider,
            model=args.model,
            ollama_url=args.ollama_url,
            docker=args.docker,
            openai_key=args.openai_key,
            openai_base_url=args.openai_base_url,
            workers=args.workers,
            max_pages=args.max_pages,
            skip_ocr=args.skip_ocr,
            reprocess_ocr=args.reprocess_ocr,
            force=args.force,
            no_individual=args.no_individual,
            use_tqdm=True
        )
        if summary.get("status") == "erro":
            sys.exit(1)
        elif summary.get("status") == "interrompido":
            sys.exit(130)
    except KeyboardInterrupt:
        print("\n\n[!] Execução encerrada pelo usuário.")
        sys.exit(130)



if __name__ == "__main__":
    main()
