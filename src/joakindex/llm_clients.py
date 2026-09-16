#!/usr/bin/env python3
"""
JoaKinDeX - Clientes de LLM (Ollama e OpenAI)
Criado por: Joaquim Ferreira Silva Neto <joaquimfsneto@gmail.com>

Camada de transporte para os provedores de LLM usados na classificação/OCR:
detecção de ambientes Ollama (nativo ou via Docker), os clientes Ollama/OpenAI
propriamente ditos, e a higienização/auto-reparo do JSON retornado pelo modelo.
"""

__project__ = "JoaKinDeX"
__author__ = "Joaquim Ferreira Silva Neto"
__email__ = "joaquimfsneto@gmail.com"
__version__ = "1.0.0"

import os
import json
import re
import time
import random
import subprocess
import shutil
from typing import Dict, Any, List, Optional

try:
    import requests
except ImportError:
    requests = None

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None


# ---------------------------------------------------------------------------
# Tratamento e Auto-Reparo de JSON retornado pelo LLM
# ---------------------------------------------------------------------------
def clean_and_parse_json(raw_text: str) -> Dict[str, Any]:
    """
    Higieniza e decodifica a resposta JSON do modelo, tratando blocos de código
    markdown, caracteres extras e truncamento acidental de tokens (auto-reparo).
    """
    text = (raw_text or "").strip()
    if not text:
        return {}

    # 1. Limpeza de blocos de código markdown (```json ... ```)
    if "```" in text:
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text)
        text = text.strip()

    # 2. Tentativa direta com json.loads
    try:
        return json.loads(text)
    except Exception:
        pass

    # 3. Busca por bloco JSON completo delimitado por chaves { ... }
    match = re.search(r"(\{.*\})", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except Exception:
            pass

    # 4. Auto-reparo de JSON truncado ou cortado pelo LLM
    try:
        start_idx = text.find("{")
        if start_idx != -1:
            s = text[start_idx:]

            # Conta aspas não escapadas para detectar strings abertas
            def _count_unescaped_quotes(st: str) -> int:
                count = 0
                escaped = False
                for ch in st:
                    if ch == "\\" and not escaped:
                        escaped = True
                        continue
                    if ch == '"' and not escaped:
                        count += 1
                    escaped = False
                return count

            if _count_unescaped_quotes(s) % 2 != 0:
                last_quote_idx = s.rfind('"')
                before_quote = s[:last_quote_idx].rstrip()
                after_quote = s[last_quote_idx + 1:]
                # Se for chave pendente como: , " ou , "campo
                if ":" not in after_quote and (before_quote.endswith(",") or before_quote.endswith("{")):
                    s = before_quote.rstrip(",")
                else:
                    # Se for valor de string interrompido: "campo": "texto_incompleto
                    s = s + '"'

            # Remove vírgulas finais soltas antes do fechamento
            s = re.sub(r",\s*$", "", s)

            # Empilha e fecha delimitadores não balanceados ({ e [)
            stack = []
            in_string = False
            escaped = False
            for ch in s:
                if ch == "\\" and not escaped:
                    escaped = True
                    continue
                if ch == '"':
                    in_string = not in_string
                elif not in_string:
                    if ch in ("{", "["):
                        stack.append(ch)
                    elif ch == "}" and stack and stack[-1] == "{":
                        stack.pop()
                    elif ch == "]" and stack and stack[-1] == "[":
                        stack.pop()
                escaped = False

            while stack:
                opener = stack.pop()
                s = s.rstrip().rstrip(",")
                s += "}" if opener == "{" else "]"

            repaired = json.loads(s)
            if isinstance(repaired, dict):
                return repaired
    except Exception:
        pass

    # 5. Fallback Resiliente: Extração de pares chave-valor via Regex
    extracted: Dict[str, Any] = {}
    pattern = r'"([a-zA-Z0-9_]+)"\s*:\s*(null|true|false|-?\d+(?:\.\d+)?|"(?:[^"\\]|\\.)*")'
    for m in re.finditer(pattern, text):
        k = m.group(1)
        v_raw = m.group(2)
        try:
            extracted[k] = json.loads(v_raw)
        except Exception:
            extracted[k] = v_raw.strip('"')

    if extracted:
        return extracted

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
        self.session = requests.Session() if requests else None

        self._detect_connection_mode()

    def _detect_connection_mode(self):
        if self.docker_container:
            self.use_docker = True
            self._resolve_model_name()
            return

        # 1. Prioridade Máxima: Tenta comunicação HTTP nativa direta com a URL base
        # Se a porta 11434 estiver aberta no host (ou container exposto), utiliza conexão direta ultra-rápida
        if requests:
            try:
                r = requests.get(f"{self.base_url}/api/tags", timeout=1.5)
                if r.status_code == 200:
                    data = r.json()
                    models = [m.get("name") for m in data.get("models", []) if m.get("name")]
                    if models:
                        self.use_docker = False
                        self.docker_container = None
                        self._resolve_model_name()
                        return
            except Exception:
                pass

        # 2. Fallback: Se não respondeu nativo na porta, busca containers Docker em execução
        envs = detect_ollama_environments(base_url=self.base_url)
        running = [e for e in envs if e.get("is_running")]

        if running:
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
                if self.session:
                    r = self.session.get(url, timeout=5)
                else:
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
                "temperature": 0.0,
                "num_predict": 2048,
                "num_ctx": 8192
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
            if self.session:
                r = self.session.post(url, json=payload, timeout=self.timeout)
            else:
                r = requests.post(url, json=payload, timeout=self.timeout)
            if not r.ok:
                err_msg = r.text
                try:
                    err_json = r.json()
                    if "error" in err_json:
                        err_msg = err_json["error"]
                except Exception:
                    pass
                raise RuntimeError(f"Ollama API Error ({r.status_code}): {err_msg}")
            response_json = r.json()
            raw_response = response_json.get("response", "")

        return clean_and_parse_json(raw_response)

    def generate_json_with_images(self, prompt: str, images: List[str]) -> Dict[str, Any]:
        # Para modelos de visão VLM (Qwen2.5-VL, Llama-3.2-Vision), cada página em imagem consome
        # tokens de visão adicionais. Expandimos o num_ctx para 16384 (ou 32768 se mais de 2 páginas).
        ctx_size = 16384 if len(images) <= 2 else 32768
        payload = {
            "model": self.model,
            "prompt": prompt,
            "images": images,
            "format": "json",
            "stream": False,
            "options": {
                "temperature": 0.0,
                "num_predict": 2048,
                "num_ctx": ctx_size
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
            if self.session:
                r = self.session.post(url, json=payload, timeout=self.timeout)
            else:
                r = requests.post(url, json=payload, timeout=self.timeout)
            if not r.ok:
                err_msg = r.text
                try:
                    err_json = r.json()
                    if "error" in err_json:
                        err_msg = err_json["error"]
                except Exception:
                    pass
                raise RuntimeError(f"Ollama API Error ({r.status_code}): {err_msg}")
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
                "  2. Via linha de comando: ./joakindex -p openai -k sk-proj-...\n"
                "  3. No arquivo .env: OPENAI_API_KEY=sk-proj-...\n"
                "  4. No terminal: export OPENAI_API_KEY=sk-proj-...\n"
            )

        self.model = model
        self.client = OpenAI(
            api_key=resolved_key,
            base_url=base_url or os.environ.get("OPENAI_BASE_URL")
        )

    @staticmethod
    def _calculate_retry_delay(err_msg: str, attempt: int, default_step: float = 4.0) -> float:
        """Calcula tempo de espera adaptativo para 429 / Rate Limit (TPM)."""
        # 1. Tenta extrair tempo sugerido no corpo do erro da OpenAI
        m_ms = re.search(r"try again in (\d+(?:\.\d+)?)\s*ms", err_msg, re.IGNORECASE)
        if m_ms:
            try:
                ms_val = float(m_ms.group(1))
                return max(0.8, (ms_val / 1000.0) + random.uniform(0.3, 1.2))
            except Exception:
                pass

        m_s = re.search(r"try again in (\d+(?:\.\d+)?)\s*s", err_msg, re.IGNORECASE)
        if m_s:
            try:
                s_val = float(m_s.group(1))
                return max(1.0, s_val + random.uniform(0.5, 2.0))
            except Exception:
                pass

        # 2. Backoff exponencial adaptativo com jitter para evitar efeito manada (thundering herd)
        delays = [4.0, 8.0, 16.0, 30.0, 45.0, 60.0]
        idx = min(attempt, len(delays) - 1)
        return delays[idx] + random.uniform(0.5, 2.0)

    def generate_json(self, prompt: str) -> Dict[str, Any]:
        max_retries = 6
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
                    sleep_s = self._calculate_retry_delay(err_msg, attempt, default_step=3.0)
                    print(f"[*] [OpenAI] Limite de taxa atingido (429/TPM). Aguardando {sleep_s:.1f}s antes da tentativa {attempt + 2}/{max_retries}...")
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

        max_retries = 6
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
                    sleep_s = self._calculate_retry_delay(err_msg, attempt, default_step=4.0)
                    print(f"[*] [OpenAI] Limite de taxa atingido (429/TPM). Aguardando {sleep_s:.1f}s antes da tentativa {attempt + 2}/{max_retries}...")
                    time.sleep(sleep_s)
                    continue
                raise e
