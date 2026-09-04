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
    from openai import OpenAI
except ImportError:
    OpenAI = None


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


def extract_cpf_fallback(text: str) -> Optional[str]:
    """Busca padrão de CPF diretamente no texto do documento como contingência."""
    match = re.search(r"(?:CPF|C\.P\.F)[\s:\.ºn°]*(\d{3}\.?\d{3}\.?\d{3}-?\d{2})", text, re.IGNORECASE)
    if match:
        return format_cpf(match.group(1))
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

        self.model = model
        self.client = OpenAI(
            api_key=api_key or os.environ.get("OPENAI_API_KEY"),
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


# ---------------------------------------------------------------------------
# Prompt de Extração (Incluindo Natureza do Curso e CPF)
# ---------------------------------------------------------------------------
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
    max_pages: int = 4
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
        "curso": None,
        "natureza_curso": None,
        "carga_horaria": None,
        "faculdade": None,
        "tipo_documento": None,
        "status": "pendente",
        "erro": None,
        "processado_em": datetime.now().isoformat()
    }

    try:
        # Extração de texto
        text = extract_pdf_text(str(pdf_path), max_pages=max_pages)
        if not text or len(text.strip()) < 15:
            res_dict["status"] = "erro"
            res_dict["erro"] = "Documento sem texto legível digitalmente (provavelmente imagem digitalizada/requer OCR)."
            return res_dict

        # Chamada ao LLM
        prompt = build_prompt(text)
        extracted_data = client.generate_json(prompt)

        # Atualiza os campos com o retorno do LLM
        res_dict["data"] = extracted_data.get("data")
        res_dict["beneficiario"] = extracted_data.get("beneficiario")

        # Tratamento e fallback para CPF
        cpf_val = extracted_data.get("cpf")
        formatted_cpf = format_cpf(cpf_val)
        if not formatted_cpf:
            formatted_cpf = extract_cpf_fallback(text)
        res_dict["cpf"] = formatted_cpf

        res_dict["curso"] = extracted_data.get("curso")
        res_dict["natureza_curso"] = extracted_data.get("natureza_curso")
        res_dict["carga_horaria"] = extracted_data.get("carga_horaria")
        res_dict["faculdade"] = extracted_data.get("faculdade")
        res_dict["tipo_documento"] = extracted_data.get("tipo_documento")
        res_dict["status"] = "sucesso"

    except Exception as e:
        res_dict["status"] = "erro"
        res_dict["erro"] = str(e)

    return res_dict


# ---------------------------------------------------------------------------
# Formatação de Saídas (JSON e TXT)
# ---------------------------------------------------------------------------
def format_single_txt(item: Dict[str, Any]) -> str:
    return f"""--------------------------------------------------------------------------------
MD5                 : {item.get('md5')}
Status              : {item.get('status', '').upper()}
Data de Criação     : {item.get('data_criacao')}
Data de Modificação : {item.get('data_modificacao')}
Tipo Documento      : {item.get('tipo_documento') or 'Não identificado'}
Beneficiário        : {item.get('beneficiario') or 'Não informado'}
CPF                 : {item.get('cpf') or 'Não informado'}
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
        "--openai-key",
        type=str,
        default=None,
        help="Chave de API da OpenAI (se omitido, lê de OPENAI_API_KEY)."
    )
    parser.add_argument(
        "--openai-base-url",
        type=str,
        default=None,
        help="URL base personalizada para OpenAI ou endpoints compatíveis."
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
        "--no-individual",
        action="store_true",
        help="Desativa a criação de arquivos JSON e TXT individuais por PDF (nomeados por MD5)."
    )

    args = parser.parse_args()

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

    results: List[Dict[str, Any]] = []

    print(f"[*] Iniciando classificação em massa com {args.workers} worker(s)...")

    def handle_file(pdf: Path):
        res = process_single_pdf(pdf, client, max_pages=args.max_pages)
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
            future_to_file = {executor.submit(handle_file, f): f for f in pdf_files}
            iterator = as_completed(future_to_file)
            if tqdm:
                iterator = tqdm(iterator, total=len(pdf_files), desc="Processando PDFs", unit="doc")
            for future in iterator:
                results.append(future.result())
    else:
        iterator = pdf_files
        if tqdm:
            iterator = tqdm(pdf_files, desc="Processando PDFs", unit="doc")
        for f in iterator:
            res = handle_file(f)
            results.append(res)

    results.sort(key=lambda x: x["md5"])

    # 1. Salva arquivo consolidado JSON
    consolidated_json_path = out_dir / "classificacao_diplomas.json"
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
