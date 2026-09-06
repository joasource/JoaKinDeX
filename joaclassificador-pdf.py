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
import hashlib
import argparse
import warnings
warnings.filterwarnings("ignore", category=UserWarning, module="pypdf")
import base64
import io
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional
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


class OllamaClient(BaseLLMClient):
    """
    Cliente para Ollama, suportando requisições HTTP diretas
    e comunicação via docker exec para containers como open-webui.
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

        try:
            r = requests.get(f"{self.base_url}/api/tags", timeout=2)
            if r.status_code == 200:
                self.use_docker = False
                self._resolve_model_name()
                return
        except Exception:
            pass

        try:
            res = subprocess.run(
                ["docker", "ps", "--format", "{{.Names}}"],
                capture_output=True,
                text=True,
                timeout=5
            )
            containers = res.stdout.strip().splitlines()
            candidates = ["open-webui", "ollama"]
            for c in candidates:
                if c in containers:
                    self.docker_container = c
                    self.use_docker = True
                    break
        except Exception:
            pass

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
            if self.use_docker:
                cmd = ["docker", "exec", "-i", self.docker_container, "curl", "-s", "http://localhost:11434/api/tags"]
                res = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
                data = json.loads(res.stdout)
            else:
                r = requests.get(f"{self.base_url}/api/tags", timeout=5)
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

    def generate_json_with_images(self, prompt: str, images: List[str]) -> Dict[str, Any]:
        content: List[Dict[str, Any]] = [{"type": "text", "text": prompt}]
        for img_b64 in images:
            content.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/jpeg;base64,{img_b64}"
                }
            })

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
    skip_ocr: bool = False
) -> Dict[str, Any]:
    # Metadados do arquivo (MD5, data de criação e modificação)
    meta = get_file_metadata(pdf_path)

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
        # Tenta OCR via LLM uma única vez ("Caso não seja identificado novamente, não insista mais").
        # ---------------------------------------------------------------------
        tipo_atual = (res_dict.get("tipo_documento") or "").strip().lower()
        is_tipo_unidentified = (not tipo_atual) or tipo_atual in [
            "não identificado", "nao identificado", "outro", "não informado", "nao informado"
        ]

        cpf_atual = res_dict.get("cpf")
        is_cpf_flawed = bool(cpf_atual and not is_valid_cpf_syntax(cpf_atual))

        precisa_releitura_ocr = (is_tipo_unidentified or is_cpf_flawed)

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


# ---------------------------------------------------------------------------
# Menu Interativo e Auxiliares de Configuração
# ---------------------------------------------------------------------------
def resolve_default_input_path(specified: Optional[str] = None) -> Path:
    if specified:
        p = Path(specified).expanduser().resolve()
        if p.exists():
            return p
        elif specified not in ["./pdf", "pdf"]:
            return p

    candidates = [
        Path("./pdf"),
        Path("../pdf"),
        Path.home() / "pdf",
    ]
    for c in candidates:
        if c.exists():
            return c.resolve()

    return Path("./pdf").resolve()


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
    # Tentativa 1: HTTP direto
    try:
        r = requests.get(f"{base_url.rstrip('/')}/api/tags", timeout=1.5)
        if r.status_code == 200:
            return [m["name"] for m in r.json().get("models", [])]
    except Exception:
        pass

    # Tentativa 2: Docker
    try:
        candidates = [docker_container] if docker_container else ["open-webui", "ollama"]
        for c in candidates:
            if not c:
                continue
            cmd = ["docker", "exec", "-i", c, "curl", "-s", "http://localhost:11434/api/tags"]
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=2.5)
            if res.returncode == 0 and res.stdout.strip():
                data = json.loads(res.stdout)
                return [m["name"] for m in data.get("models", [])]
    except Exception:
        pass

    return []


def prompt_interactive_menu(args: argparse.Namespace) -> argparse.Namespace:
    print("\n" + "=" * 70)
    print("🎓 JOACLASSIFICADOR-PDF - MENU INTERATIVO DE CLASSIFICAÇÃO")
    print("=" * 70)
    print("Pressione ENTER para aceitar o valor padrão sugerido entre colchetes [ ].\n")

    # 1. Pasta ou arquivo de entrada
    default_input = resolve_default_input_path(args.input)
    while True:
        try:
            resp_input = input(f"📁 Pasta ou arquivo PDF de entrada [{default_input}]: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n[Operação cancelada pelo usuário]")
            sys.exit(0)

        chosen_path = Path(resp_input).expanduser().resolve() if resp_input else default_input
        if not chosen_path.exists():
            print(f"   ⚠️  Aviso: Caminho '{chosen_path}' não foi encontrado.")
            try:
                conf = input("   Deseja manter esse caminho mesmo assim? (s/N): ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                sys.exit(0)
            if conf in ["s", "sim", "y", "yes"]:
                args.input = str(chosen_path)
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
                    args.input = str(chosen_path)
                    break
            else:
                print(f"   ↳ {pdf_count} arquivo(s) PDF localizado(s) para processar.")
                args.input = str(chosen_path)
                break

    # 2. Pasta de saída
    default_out = Path(args.output_dir or "./saida").expanduser().resolve()
    while True:
        try:
            resp_out = input(f"\n📄 Pasta de saída dos relatórios [{default_out}]: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n[Operação cancelada pelo usuário]")
            sys.exit(0)

        chosen_out = Path(resp_out).expanduser().resolve() if resp_out else default_out
        args.output_dir = str(chosen_out)
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
        detected_models = get_available_ollama_models(args.ollama_url, args.docker)
        default_model = args.model or (detected_models[0] if detected_models else "gemma4:e4b")
        if detected_models:
            print(f"   ↳ Modelos detectados no Ollama: {', '.join(detected_models)}")
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

    print("\n" + "=" * 70 + "\n")
    return args


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
        help="Caminho do diretório de PDFs ou de um arquivo PDF específico (padrão: ./pdf)."
    )
    parser.add_argument(
        "-o", "--output-dir",
        type=str,
        default="./saida",
        help="Diretório onde os relatórios JSON e TXT serão salvos (padrão: ./saida)."
    )
    parser.add_argument(
        "-p", "--provider",
        choices=["ollama", "openai"],
        default="ollama",
        help="Provedor de IA a utilizar: 'ollama' ou 'openai' (padrão: ollama)."
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

    args = parser.parse_args()

    # Detecta se foram passados argumentos explícitos via CLI
    explicit_cli_args = [
        arg for arg in sys.argv[1:]
        if arg not in ["--prompt", "--interativo", "-y", "--no-prompt", "--batch"]
    ]
    is_tty = sys.stdin.isatty()
    should_prompt = args.force_prompt or (
        is_tty
        and not args.no_prompt
        and len(explicit_cli_args) == 0
    )

    if should_prompt:
        args = prompt_interactive_menu(args)

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"[ERRO] Caminho de entrada não encontrado: {input_path}")
        sys.exit(1)

    pdf_files = []
    if input_path.is_file():
        if input_path.suffix.lower() == ".pdf":
            pdf_files.append(input_path)
        else:
            print(f"[ERRO] O arquivo indicado não é um PDF: {input_path}")
            sys.exit(1)
    else:
        pdf_files = sorted(list(input_path.glob("*.pdf")) + list(input_path.glob("*.PDF")))

    if not pdf_files:
        print(f"[AVISO] Nenhum arquivo PDF encontrado em: {input_path}")
        sys.exit(0)

    print(f"[*] Total de PDFs identificados: {len(pdf_files)}")

    # Configuração do Cliente LLM
    if args.provider == "ollama":
        model_name = args.model or "gemma4:e4b"
        print(f"[*] Inicializando cliente Ollama (Modelo: {model_name})...")
        client = OllamaClient(
            model=model_name,
            base_url=args.ollama_url,
            docker_container=args.docker
        )
        if client.use_docker:
            print(f"[*] Modo de conexão: Docker exec (container: {client.docker_container})")
        else:
            print(f"[*] Modo de conexão: HTTP direto ({client.base_url})")
    else:
        model_name = args.model or "gpt-4o-mini"
        print(f"[*] Inicializando cliente OpenAI (Modelo: {model_name})...")
        client = OpenAIClient(
            model=model_name,
            api_key=args.openai_key,
            base_url=args.openai_base_url
        )

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    indiv_dir = out_dir / "individuais"
    if not args.no_individual:
        indiv_dir.mkdir(parents=True, exist_ok=True)

    consolidated_json_path = out_dir / "classificacao_diplomas.json"
    existing_by_md5 = {}

    # Carrega processamentos anteriores para modo incremental
    if consolidated_json_path.exists() and not args.force:
        try:
            with open(consolidated_json_path, "r", encoding="utf-8") as f:
                old_data = json.load(f)
                for item in old_data:
                    # Reutiliza documentos que foram processados com sucesso ou conferidos manualmente
                    if "md5" in item:
                        existing_by_md5[item["md5"]] = item
        except Exception as e:
            existing_by_md5 = {}

    # Separa os arquivos entre já processados e novos
    files_to_process = []
    already_done_results = []

    print("[*] Verificando documentos já processados anteriormente...")
    ocr_candidate_count = 0
    for pdf in pdf_files:
        meta = get_file_metadata(pdf)
        h = meta["md5"]
        if h in existing_by_md5 and not args.force:
            item = existing_by_md5[h]
            # Respeita sempre aprovação manual humana
            if item.get("status_conferencia") == "aprovado":
                already_done_results.append(item)
                continue

            tipo_atual = (item.get("tipo_documento") or "").strip().lower()
            tipo_nao_identificado = (not tipo_atual) or tipo_atual in [
                "não identificado", "nao identificado", "outro", "não informado", "nao informado"
            ]
            cpf_item = item.get("cpf")
            cpf_invalido = bool(cpf_item and not is_valid_cpf_syntax(cpf_item))
            teve_tentativa_ocr = item.get("tentativa_ocr_llm", False)
            teve_erro_ocr = (item.get("status") == "erro") and ("OCR" in (item.get("erro") or ""))

            precisa_ocr = (teve_erro_ocr or ((tipo_nao_identificado or cpf_invalido) and not teve_tentativa_ocr))

            if not args.skip_ocr and ((precisa_ocr and not teve_tentativa_ocr) or args.reprocess_ocr):
                files_to_process.append(pdf)
                ocr_candidate_count += 1
            else:
                already_done_results.append(item)
        else:
            files_to_process.append(pdf)

    if ocr_candidate_count > 0:
        print(f"[*] Identificados {ocr_candidate_count} documento(s) elegíveis para OCR via LLM (erros de leitura, tipo não identificado ou CPF com sintaxe errada).")

    print(f"[*] Total de PDFs: {len(pdf_files)} | Já processados: {len(already_done_results)} | A processar: {len(files_to_process)}")

    new_results = []
    if files_to_process:
        print(f"[*] Iniciando classificação de {len(files_to_process)} documento(s) com {args.workers} worker(s)...")

        def handle_file(pdf: Path):
            meta = get_file_metadata(pdf)
            h = meta["md5"]
            old_item = existing_by_md5.get(h)

            res = process_single_pdf(
                pdf,
                client,
                max_pages=args.max_pages,
                skip_ocr=args.skip_ocr
            )

            # Preserva metadados de conferência humana caso já existissem
            if old_item:
                if "status_conferencia" in old_item:
                    res["status_conferencia"] = old_item["status_conferencia"]
                if "observacoes_conferencia" in old_item:
                    res["observacoes_conferencia"] = old_item["observacoes_conferencia"]
                if "conferido_em" in old_item:
                    res["conferido_em"] = old_item["conferido_em"]

            if not args.no_individual:
                file_identifier = res["md5"]
                single_json_path = indiv_dir / f"{file_identifier}.json"
                with open(single_json_path, "w", encoding="utf-8") as f:
                    json.dump(res, f, ensure_ascii=False, indent=2)
                single_txt_path = indiv_dir / f"{file_identifier}.txt"
                with open(single_txt_path, "w", encoding="utf-8") as f:
                    f.write(format_single_txt(res))
            return res

        if args.workers > 1:
            with ThreadPoolExecutor(max_workers=args.workers) as executor:
                future_to_file = {executor.submit(handle_file, f): f for f in files_to_process}
                iterator = as_completed(future_to_file)
                if tqdm:
                    iterator = tqdm(iterator, total=len(files_to_process), desc="Processando Novos PDFs", unit="doc")
                for future in iterator:
                    new_results.append(future.result())
        else:
            iterator = files_to_process
            if tqdm:
                iterator = tqdm(files_to_process, desc="Processando Novos PDFs", unit="doc")
            for f in iterator:
                res = handle_file(f)
                new_results.append(res)
    else:
        print("[*] Todos os documentos já estão atualizados no banco de dados!")

    # Combina existentes + novos (sem duplicatas por MD5)
    all_dict = {item["md5"]: item for item in already_done_results}
    for item in new_results:
        all_dict[item["md5"]] = item

    results = list(all_dict.values())
    results.sort(key=lambda x: x["md5"])

    # 1. Salva arquivo consolidado JSON
    with open(consolidated_json_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    # 2. Salva arquivo consolidado TXT
    consolidated_txt_path = out_dir / "classificacao_diplomas.txt"
    report_text = generate_consolidated_txt(results, args.provider, client.model if hasattr(client, "model") else model_name)
    with open(consolidated_txt_path, "w", encoding="utf-8") as f:
        f.write(report_text)

    # Resumo no terminal
    sucessos = sum(1 for r in results if r.get("status") == "sucesso")
    erros = len(results) - sucessos

    print("\n" + "=" * 60)
    print("PROCESSAMENTO CONCLUÍDO COM SUCESSO!")
    print(f"Total processados : {len(results)}")
    print(f"Classificados OK  : {sucessos}")
    print(f"Erros             : {erros}")
    print("-" * 60)
    print(f"Relatório JSON consolidado : {consolidated_json_path}")
    print(f"Relatório TXT consolidado  : {consolidated_txt_path}")
    if not args.no_individual:
        print(f"Arquivos individuais (MD5) : {indiv_dir}/")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
