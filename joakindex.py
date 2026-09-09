#!/usr/bin/env python3
"""
JoaKinDeX - Central de Indexação & Classificação Documental Multidomínio
Criado por: Joaquim Ferreira Silva Neto <joaquimfsneto@gmail.com>
"""

__project__ = "JoaKinDeX"
__author__ = "Joaquim Ferreira Silva Neto"
__email__ = "joaquimfsneto@gmail.com"
__version__ = "1.0.0"

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
import tempfile
import zipfile
import threading
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Union, Callable, Set, Tuple
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
    from PIL import Image
except ImportError:
    Image = None

IMAGE_EXTENSIONS: Set[str] = {".png", ".jpg", ".jpeg", ".webp"}
WORD_EXTENSIONS: Set[str] = {".docx", ".doc", ".odt", ".rtf"}
TEXT_EXTENSIONS: Set[str] = {".txt"}
DOCUMENT_EXTENSIONS: Set[str] = {".pdf"} | WORD_EXTENSIONS | TEXT_EXTENSIONS
SUPPORTED_EXTENSIONS: Set[str] = DOCUMENT_EXTENSIONS | IMAGE_EXTENSIONS
_OFFICE_CONVERT_LOCK = threading.Lock()

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
        get_factory_defaults,
        clean_path_string,
        resolve_classifier_output_dir,
        resolve_dir_path
    )
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from config_manager import (
        get_classifier_config,
        save_classifier_config,
        reset_classifier_config,
        has_custom_config,
        get_factory_defaults,
        clean_path_string,
        resolve_classifier_output_dir,
        resolve_dir_path
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
        sync_to_json
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
# Metadados do Arquivo (MD5, Modificação, Autor)
# ---------------------------------------------------------------------------
def extract_file_author(file_path: Union[str, Path]) -> Optional[str]:
    """
    Extrai o autor dos metadados internos de arquivos PDF, DOCX, DOC e imagens.
    Retorna a string higienizada do autor ou None se não houver metadados de autoria.
    """
    p = Path(file_path)
    if not p.exists() or not p.is_file():
        return None

    ext = p.suffix.lower()

    # 1. Arquivos PDF (.pdf)
    if ext == ".pdf":
        if pypdf is not None:
            try:
                reader = pypdf.PdfReader(str(p), strict=False)
                meta = reader.metadata
                if meta and meta.author:
                    author = "".join(ch for ch in str(meta.author) if ch.isprintable()).strip()
                    if author and len(author) >= 2:
                        return author
            except Exception:
                pass
        # Fallback via utilitário pdfinfo do sistema
        if shutil.which("pdfinfo"):
            try:
                res = subprocess.run(["pdfinfo", str(p)], capture_output=True, text=True, timeout=3)
                if res.returncode == 0:
                    for line in res.stdout.splitlines():
                        if line.startswith("Author:"):
                            a = line.split("Author:", 1)[1].strip()
                            if a and len(a) >= 2:
                                return a
            except Exception:
                pass

    # 2. Arquivos Word DOCX (.docx)
    elif ext == ".docx":
        try:
            with zipfile.ZipFile(p, "r") as z:
                if "docProps/core.xml" in z.namelist():
                    xml_data = z.read("docProps/core.xml")
                    root = ET.fromstring(xml_data)
                    for elem in root:
                        if elem.tag.endswith("creator") and elem.text and elem.text.strip():
                            return elem.text.strip()
                        if elem.tag.endswith("lastModifiedBy") and elem.text and elem.text.strip():
                            return elem.text.strip()
        except Exception:
            pass

    # 3. Arquivos Word Legado (.doc 97-2003)
    elif ext == ".doc":
        try:
            with open(p, "rb") as f:
                d = f.read()
            m = re.search(rb"\x1e\x00\x00\x00[\x02-\x80]\x00\x00\x00([A-Za-z\xc0-\xff][A-Za-z0-9\xc0-\xff\s\.\-]{1,60})\x00.*?(?:Normal|Microsoft)", d, re.DOTALL)
            if m:
                s = m.group(1).decode("latin1", errors="ignore").strip()
                if s and len(s) >= 2 and s.lower() not in ["normal", "microsoft"]:
                    return s
        except Exception:
            pass

    # 4. Imagens (JPEG/PNG/TIFF/WEBP)
    elif ext in IMAGE_EXTENSIONS or ext in [".tiff", ".tif"]:
        if Image is not None:
            try:
                with Image.open(p) as im:
                    exif = im.getexif()
                    if exif:
                        from PIL.ExifTags import TAGS
                        for tag_id, val in exif.items():
                            tag = TAGS.get(tag_id, tag_id)
                            if tag in ["Artist", "XPAuthor", "Author"]:
                                s = str(val).strip()
                                if s and len(s) >= 2:
                                    return s
            except Exception:
                pass

    return None


def extract_file_dublin_core(file_path: Union[str, Path]) -> Dict[str, Any]:
    """
    Extrai metadados estruturados do padrão Dublin Core (DCMES ISO 15836) e XMP.
    Retorna um dicionário higienizado contendo chaves como:
    title, creator, subject, description, publisher, contributor, date, modified,
    type, format, identifier, source, language, rights, keywords, creator_tool, producer.
    """
    p = Path(file_path)
    if not p.exists() or not p.is_file():
        return {}

    ext = p.suffix.lower()
    res: Dict[str, Any] = {}

    def _clean_str(val: Any) -> Optional[str]:
        if val is None:
            return None
        if isinstance(val, (list, tuple, set)):
            items = [_clean_str(x) for x in val if x is not None]
            items = [x for x in items if x]
            return ", ".join(items) if items else None
        if isinstance(val, dict):
            items = [f"{k}: {_clean_str(v)}" for k, v in val.items() if v is not None]
            return ", ".join(items) if items else None
        s = "".join(ch for ch in str(val) if ch.isprintable() or ch in " \t\n\r").strip()
        return s if len(s) >= 1 else None

    # 1. Arquivos PDF (.pdf)
    if ext == ".pdf":
        if pypdf is not None:
            try:
                reader = pypdf.PdfReader(str(p), strict=False)
                # Dicionário clássico Info
                meta = reader.metadata
                if meta:
                    if meta.title: res["title"] = _clean_str(meta.title)
                    if meta.author: res["creator"] = _clean_str(meta.author)
                    if meta.subject: res["subject"] = _clean_str(meta.subject)
                    if "/Keywords" in meta and meta["/Keywords"]: res["keywords"] = _clean_str(meta["/Keywords"])
                    if meta.creator: res["creator_tool"] = _clean_str(meta.creator)
                    if meta.producer: res["producer"] = _clean_str(meta.producer)
                    if meta.creation_date: res["date"] = _clean_str(meta.creation_date)
                    if meta.modification_date: res["modified"] = _clean_str(meta.modification_date)
                # XMP Metadata estruturado Dublin Core
                xmp = reader.xmp_metadata
                if xmp:
                    dc_attrs = {
                        "dc_title": "title",
                        "dc_creator": "creator",
                        "dc_subject": "subject",
                        "dc_description": "description",
                        "dc_publisher": "publisher",
                        "dc_contributor": "contributor",
                        "dc_date": "date",
                        "dc_type": "type",
                        "dc_format": "format",
                        "dc_identifier": "identifier",
                        "dc_source": "source",
                        "dc_language": "language",
                        "dc_rights": "rights",
                        "dc_coverage": "coverage",
                        "dc_relation": "relation"
                    }
                    for xmp_attr, dc_key in dc_attrs.items():
                        v = getattr(xmp, xmp_attr, None)
                        if v is not None:
                            cleaned = _clean_str(v)
                            if cleaned:
                                res[dc_key] = cleaned
                    if xmp.xmp_creator_tool and not res.get("creator_tool"):
                        res["creator_tool"] = _clean_str(xmp.xmp_creator_tool)
                    if xmp.pdf_producer and not res.get("producer"):
                        res["producer"] = _clean_str(xmp.pdf_producer)
                    if xmp.pdf_keywords and not res.get("keywords"):
                        res["keywords"] = _clean_str(xmp.pdf_keywords)
                    if xmp.xmp_create_date and not res.get("date"):
                        res["date"] = _clean_str(xmp.xmp_create_date)
                    if xmp.xmp_modify_date and not res.get("modified"):
                        res["modified"] = _clean_str(xmp.xmp_modify_date)
            except Exception:
                pass

        # Fallback pdfinfo
        if shutil.which("pdfinfo") and (not res or not res.get("creator")):
            try:
                proc = subprocess.run(["pdfinfo", str(p)], capture_output=True, text=True, timeout=3)
                if proc.returncode == 0:
                    for line in proc.stdout.splitlines():
                        if ":" in line:
                            k, v = line.split(":", 1)
                            k, v = k.strip(), v.strip()
                            if not v: continue
                            if k == "Title" and not res.get("title"): res["title"] = v
                            elif k == "Author" and not res.get("creator"): res["creator"] = v
                            elif k == "Subject" and not res.get("subject"): res["subject"] = v
                            elif k == "Keywords" and not res.get("keywords"): res["keywords"] = v
                            elif k == "Creator" and not res.get("creator_tool"): res["creator_tool"] = v
                            elif k == "Producer" and not res.get("producer"): res["producer"] = v
                            elif k == "CreationDate" and not res.get("date"): res["date"] = v
                            elif k == "ModDate" and not res.get("modified"): res["modified"] = v
            except Exception:
                pass

    # 2. Arquivos Word DOCX (.docx)
    elif ext == ".docx":
        try:
            with zipfile.ZipFile(p, "r") as z:
                if "docProps/core.xml" in z.namelist():
                    xml_data = z.read("docProps/core.xml")
                    root = ET.fromstring(xml_data)
                    for elem in root:
                        tag_name = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
                        val = _clean_str(elem.text)
                        if not val: continue
                        if tag_name == "title": res["title"] = val
                        elif tag_name == "creator": res["creator"] = val
                        elif tag_name == "subject": res["subject"] = val
                        elif tag_name == "description": res["description"] = val
                        elif tag_name == "keywords": res["keywords"] = val
                        elif tag_name == "lastModifiedBy":
                            res["contributor"] = val
                            if not res.get("creator_tool"): res["creator_tool"] = f"Microsoft Word ({val})"
                        elif tag_name == "created": res["date"] = val
                        elif tag_name == "modified": res["modified"] = val
                        elif tag_name == "category": res["type"] = val
                        elif tag_name == "language": res["language"] = val
        except Exception:
            pass

    # 3. Arquivos Word Legado (.doc 97-2003)
    elif ext == ".doc":
        try:
            with open(p, "rb") as f:
                d = f.read()
            # Autor
            m = re.search(rb"\x1e\x00\x00\x00[\x02-\x80]\x00\x00\x00([A-Za-z\xc0-\xff][A-Za-z0-9\xc0-\xff\s\.\-]{1,60})\x00.*?(?:Normal|Microsoft)", d, re.DOTALL)
            if m:
                s = m.group(1).decode("latin1", errors="ignore").strip()
                if s and s.lower() not in ["normal", "microsoft"]:
                    res["creator"] = s
            # Template / Creator Tool
            if b"Microsoft Word" in d:
                res["creator_tool"] = "Microsoft Word (97-2003)"
            elif b"Normal.dot" in d:
                res["creator_tool"] = "Microsoft Word (Normal.dot)"
        except Exception:
            pass

    # 4. Imagens
    elif ext in IMAGE_EXTENSIONS or ext in [".tiff", ".tif"]:
        if Image is not None:
            try:
                with Image.open(p) as im:
                    exif = im.getexif()
                    if exif:
                        from PIL.ExifTags import TAGS
                        for tag_id, val in exif.items():
                            tag = TAGS.get(tag_id, tag_id)
                            cleaned = _clean_str(val)
                            if not cleaned: continue
                            if tag in ["Artist", "XPAuthor", "Author"]: res["creator"] = cleaned
                            elif tag in ["ImageDescription", "XPComment"]: res["description"] = cleaned
                            elif tag in ["XPTitle"]: res["title"] = cleaned
                            elif tag in ["XPSubject"]: res["subject"] = cleaned
                            elif tag in ["XPKeywords"]: res["keywords"] = cleaned
                            elif tag in ["Software"]: res["creator_tool"] = cleaned
                            elif tag in ["DateTime", "DateTimeOriginal"]: res["date"] = cleaned
                            elif tag in ["Copyright"]: res["rights"] = cleaned
            except Exception:
                pass

    # Se creator não foi encontrado e extract_file_author tiver outro detalhe, harmoniza
    if not res.get("creator"):
        aut = extract_file_author(p)
        if aut:
            res["creator"] = aut

    return {k: v for k, v in res.items() if v}


def get_file_metadata(file_path: Path) -> Dict[str, Any]:
    """
    Calcula o hash MD5, data da última alteração e metadados Dublin Core/Autor do arquivo.
    """
    hasher = hashlib.md5()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    md5_hash = hasher.hexdigest()

    st = file_path.stat()
    dt_mod = datetime.fromtimestamp(st.st_mtime).strftime("%d/%m/%Y %H:%M:%S")
    dc_meta = extract_file_dublin_core(file_path)
    autor = dc_meta.get("creator") or extract_file_author(file_path)

    return {
        "md5": md5_hash,
        "data_modificacao": dt_mod,
        "autor": autor,
        "dublin_core": dc_meta,
        "dc_title": dc_meta.get("title"),
        "dc_subject": dc_meta.get("subject"),
        "dc_creator_tool": dc_meta.get("creator_tool")
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
    """Busca padrão de CPF diretamente no texto do documento como contingência com validação de checksum."""
    if not text:
        return None
    # 1. Padrão associado explicitamente a CPF / C.P.F / CIC (inclusive em CNH com '4d CPF')
    match = re.search(r"(?:CPF|C\.P\.F|CIC)[\s:\.ºn°A-Za-z0-9]*?(\d{3}\.?\d{3}\.?\d{3}-?\d{2})\b", text, re.IGNORECASE)
    if match:
        fmt = format_cpf(match.group(1))
        if fmt and validate_cpf_checksum(fmt):
            return fmt
    # 2. Busca qualquer padrão formatado com dígitos verificadores válidos da Receita
    for m in re.finditer(r"\b(\d{3}\.\d{3}\.\d{3}-\d{2})\b", text):
        fmt = format_cpf(m.group(1))
        if fmt and validate_cpf_checksum(fmt):
            return fmt
    # 3. Busca sequência de 11 dígitos contínuos com prefixo CPF
    match3 = re.search(r"(?:CPF|C\.P\.F)[\s:\.ºn°]*(\d{11})\b", text, re.IGNORECASE)
    if match3:
        fmt = format_cpf(match3.group(1))
        if fmt and validate_cpf_checksum(fmt):
            return fmt
    return None


def extract_rg_fallback(text: str) -> Optional[str]:
    """Busca padrão de Cédula de Identidade / RG diretamente no texto como contingência."""
    if not text:
        return None

    pattern = re.compile(
        r"\b(?:Carteira\s+de\s+Identidade|C[eé]dula\s+de\s+Identidade|Registro\s+Geral|R\.?\s*G\.?|Doc(?:\.|\s+de)?\s+Identidade|Documento\s+de\s+Identidade|Identidade|C\.?I\.?)\b"
        r"(?:\s*(?:n[°ºo\.]*|número|sob\s+o\s+n[°ºo\.]*))?"
        r"[\s/A-Z]*\n?"
        r"([A-Z0-9\.\-\/]+(?:\s*(?:(?:SSP|SPTC|PCMG|DGPC|PC|DETRAN|IFP|PM|POL[IÍ]CIA|MAE|MEX|MD|DPF|SESP|[A-Z]{2,4})\b)?(?:\s*[\/\-]?\s*[A-Z]{2})?)?)",
        re.IGNORECASE
    )

    for match in pattern.finditer(text):
        val = match.group(1).strip()
        val = re.split(r"\s+(?:e\s+)?(?:\d*[a-z]?\s*CPF|C\.P\.F|Data|Nascido|Nasc|Expedi[cç]|Filia[cç])\b", val, flags=re.IGNORECASE)[0].strip()
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
# Formatação, Validação e Extração de CNPJ e Dados Cadastrais (Receita Federal)
# ---------------------------------------------------------------------------
def format_cnpj(raw_cnpj: Optional[str]) -> Optional[str]:
    """Formata sequência de 14 dígitos para o padrão 00.000.000/0000-00."""
    if not raw_cnpj:
        return None
    digits = re.sub(r"\D", "", str(raw_cnpj))
    if len(digits) == 14:
        return f"{digits[:2]}.{digits[2:5]}.{digits[5:8]}/{digits[8:12]}-{digits[12:]}"
    return str(raw_cnpj).strip() if raw_cnpj else None


def validate_cnpj_checksum(cnpj: str) -> bool:
    """Valida os dois dígitos verificadores do CNPJ pelo algoritmo oficial da Receita Federal."""
    digits = [int(d) for d in re.sub(r"\D", "", str(cnpj))]
    if len(digits) != 14:
        return False
    if len(set(digits)) == 1:
        return False

    # Primeiro dígito verificador
    weights1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    s1 = sum(d * w for d, w in zip(digits[:12], weights1))
    r1 = s1 % 11
    d1 = 0 if r1 < 2 else 11 - r1
    if d1 != digits[12]:
        return False

    # Segundo dígito verificador
    weights2 = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    s2 = sum(d * w for d, w in zip(digits[:13], weights2))
    r2 = s2 % 11
    d2 = 0 if r2 < 2 else 11 - r2
    return d2 == digits[13]


def is_valid_cnpj_syntax(cnpj: Optional[str], check_checksum: bool = True) -> bool:
    """Retorna True se o CNPJ possuir sintaxe válida (14 dígitos) e checksum aprovado."""
    if not cnpj:
        return False
    digits = re.sub(r"\D", "", str(cnpj))
    if len(digits) != 14:
        return False
    if not re.match(r"^\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}$", str(cnpj)):
        return False
    if check_checksum and not validate_cnpj_checksum(cnpj):
        return False
    return True


def extract_cnpj_fallback(text: str) -> Optional[str]:
    """Busca padrão de CNPJ diretamente no texto do documento com contingência e validação de checksum."""
    if not text:
        return None
    # 1. Padrão associado explicitamente a CNPJ / C.N.P.J / CGC
    match = re.search(r"(?:CNPJ|C\.N\.P\.J|CGC|C\.G\.C)[\s:\.ºn°A-Za-z0-9]*?(\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2})\b", text, re.IGNORECASE)
    if match:
        fmt = format_cnpj(match.group(1))
        if fmt and validate_cnpj_checksum(fmt):
            return fmt
    # 2. Busca qualquer padrão formatado XX.XXX.XXX/XXXX-XX com dígitos verificadores válidos
    for m in re.finditer(r"\b(\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2})\b", text):
        fmt = format_cnpj(m.group(1))
        if fmt and validate_cnpj_checksum(fmt):
            return fmt
    # 3. Busca sequência de 14 dígitos contínuos com prefixo CNPJ
    match3 = re.search(r"(?:CNPJ|C\.N\.P\.J)[\s:\.ºn°]*(\d{14})\b", text, re.IGNORECASE)
    if match3:
        fmt = format_cnpj(match3.group(1))
        if fmt and validate_cnpj_checksum(fmt):
            return fmt
    return None


def extract_cnpj_cadastral_fallback(text: str) -> Dict[str, Any]:
    """
    Extrai informações estruturadas do Comprovante de Inscrição e de Situação Cadastral
    da Receita Federal (CNPJ, Razão Social, Nome Fantasia, Situação, CNAE, Endereço, etc.).
    """
    if not text:
        return {}

    dados = {}
    cnpj = extract_cnpj_fallback(text)
    if cnpj:
        dados["cnpj"] = cnpj

    # 1. Situação Cadastral
    m_sit = re.search(r"SITUA[CÇ][AÃ]O\s+CADASTRAL\s*[\:\-]?\s*(ATIVA|BAIXADA|SUSPENSA|INAPTA|NULA)", text, re.IGNORECASE)
    if m_sit:
        dados["situacao_cadastral"] = m_sit.group(1).upper()

    # 2. Data da Situação Cadastral
    m_dt_sit = re.search(r"DATA\s+DA\s+SITUA[CÇ][AÃ]O\s+CADASTRAL\s*[\:\-]?\s*(\d{2}/\d{2}/\d{4})", text, re.IGNORECASE)
    if m_dt_sit:
        dados["data_situacao"] = m_dt_sit.group(1)

    # 3. Data de Abertura
    m_abertura = re.search(r"DATA\s+DE\s+ABERTURA\s*[\:\-]?\s*(\d{2}/\d{2}/\d{4})", text, re.IGNORECASE)
    if m_abertura:
        dados["data_abertura"] = m_abertura.group(1)

    # 4. Razão Social / Nome Empresarial
    m_razao = re.search(r"NOME\s+EMPRESARIAL\s*[\:\-]?\s*([^\n\r]+)", text, re.IGNORECASE)
    if m_razao:
        razao = m_razao.group(1).strip()
        razao = re.split(r"\s*(?:T[IÍ]TULO|ESTABELECIMENTO|FANTASIA|PORTE|C[OÓ]DIGO)\b", razao, flags=re.IGNORECASE)[0].strip()
        if len(razao) >= 3:
            dados["razao_social"] = razao

    # 5. Título do Estabelecimento / Nome Fantasia
    m_fantasia = re.search(r"(?:T[IÍ]TULO\s+DO\s+ESTABELECIMENTO(?:\s*\([^\)]*\))?|NOME\s+(?:DE\s+)?FANTASIA|\(NOME\s+DE\s+FANTASIA\))\s*[\:\-]?\s*([^\n\r]+)", text, re.IGNORECASE)
    if m_fantasia:
        fantasia = m_fantasia.group(1).strip()
        fantasia = re.sub(r"^\s*\([^\)]*\)\s*[\:\-]?", "", fantasia).strip()
        fantasia = re.split(r"\s*(?:C[OÓ]DIGO|ATIVIDADE|PORTE)\b", fantasia, flags=re.IGNORECASE)[0].strip()
        if fantasia and fantasia.upper() not in ["*****", "NÃO INFORMADO", "NAO INFORMADO", "********"]:
            dados["nome_fantasia"] = fantasia

    # 6. CNAE Principal
    m_cnae = re.search(r"C[OÓ]DIGO\s+E\s+DESCRI[CÇ][AÃ]O\s+DA\s+ATIVIDADE\s+ECON[OÔ]MICA\s+PRINCIPAL\s*[\:\-]?\s*([^\n\r]+)", text, re.IGNORECASE)
    if m_cnae:
        cnae = m_cnae.group(1).strip()
        cnae = re.split(r"\s*(?:C[OÓ]DIGO|ATIVIDADE|SECUND[AÁ]RIA)\b", cnae, flags=re.IGNORECASE)[0].strip()
        if len(cnae) >= 4:
            dados["cnae_principal"] = cnae

    # 7. Natureza Jurídica
    m_nat = re.search(r"C[OÓ]DIGO\s+E\s+DESCRI[CÇ][AÃ]O\s+DA\s+NATUREZA\s+JUR[IÍ]DICA\s*[\:\-]?\s*([^\n\r]+)", text, re.IGNORECASE)
    if m_nat:
        nat = m_nat.group(1).strip()
        nat = re.split(r"\s*(?:LOGRADOURO|ENDERE[CÇ]O|N[UÚ]MERO)\b", nat, flags=re.IGNORECASE)[0].strip()
        if len(nat) >= 4:
            dados["natureza_juridica"] = nat

    # 8. Endereço Eletrônico / E-mail
    m_email = re.search(r"(?:ENDERE[CÇ]O\s+ELETR[OÔ]NICO|E-MAIL|EMAIL)\s*[\:\-]?\s*([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})", text, re.IGNORECASE)
    if m_email:
        dados["email"] = m_email.group(1).lower()

    # 9. Telefone
    m_tel = re.search(r"TELEFONE\s*[\:\-]?\s*([0-9\(\)\s\-\/]{8,25})", text, re.IGNORECASE)
    if m_tel:
        t = m_tel.group(1).strip().rstrip(".,;- ")
        if len(re.sub(r"\D", "", t)) >= 8:
            dados["telefone"] = t

    # 10. Endereço Completo
    m_logr = re.search(r"LOGRADOURO\s*[\:\-]?\s*([^\n\r]+)", text, re.IGNORECASE)
    m_num = re.search(r"\bN[UÚ]MERO\b(?!\s+DE\s+INSCRI[CÇ][AÃ]O)\s*[\:\-]?\s*([^\n\r]+)", text, re.IGNORECASE)
    m_bairro = re.search(r"BAIRRO/DISTRITO\s*[\:\-]?\s*([^\n\r]+)", text, re.IGNORECASE)
    m_mun = re.search(r"MUNIC[IÍ]PIO\s*[\:\-]?\s*([^\n\r]+)", text, re.IGNORECASE)
    m_uf = re.search(r"\bUF\s*[\:\-]?\s*([A-Z]{2})\b", text, re.IGNORECASE)
    m_cep = re.search(r"CEP\s*[\:\-]?\s*(\d{2}\.?\d{3}-?\d{3})", text, re.IGNORECASE)

    partes_end = []
    if m_logr:
        logr = re.split(r"\s*(?:N[UÚ]MERO|COMPLEMENTO)\b", m_logr.group(1).strip(), flags=re.IGNORECASE)[0].strip()
        if m_num:
            num = re.split(r"\s*(?:COMPLEMENTO|BAIRRO|DE\s+INSCRI[CÇ][AÃ]O)\b", m_num.group(1).strip(), flags=re.IGNORECASE)[0].strip()
            partes_end.append(f"{logr}, {num}")
        else:
            partes_end.append(logr)
    if m_bairro:
        bairro = re.split(r"\s*(?:MUNIC[IÍ]PIO|CEP)\b", m_bairro.group(1).strip(), flags=re.IGNORECASE)[0].strip()
        partes_end.append(bairro)
    if m_mun:
        mun = re.split(r"\s*(?:UF|PA[IÍ]S)\b", m_mun.group(1).strip(), flags=re.IGNORECASE)[0].strip()
        uf_val = m_uf.group(1).upper() if m_uf else ""
        mun_str = f"{mun}/{uf_val}" if uf_val else mun
        partes_end.append(mun_str)
        dados["municipio_uf"] = mun_str
    elif m_uf:
        dados["uf"] = m_uf.group(1).upper()
    if m_cep:
        partes_end.append(f"CEP {m_cep.group(1)}")

    if partes_end:
        dados["endereco_completo"] = " - ".join(partes_end)

    return dados


def extract_course_fallback(text: str) -> Optional[str]:
    """Busca nome do curso em frases formais de diploma ou certificado como contingência."""
    if not text:
        return None
    # Padrão 1: conclusão do Curso de [Pedagogia / Direito / Administração] (tolerante a OCR tipo conclusdo / conclusao)
    m = re.search(r"\b(?:conclus[a-z0-9]{1,3}\s+do\s+)?curso\s+de\s+([A-Za-zÀ-ú\s\-]+?)(?:,\s*em|\s+em\s+\d|\s+e\s+a\s+cola|\s+no\s+ano|\s+com\s+dura|\.|\n|$)", text, re.IGNORECASE)
    if m:
        c = m.group(1).strip()
        if 3 <= len(c) <= 60 and not any(k in c.lower() for k in ["faculdade", "universidade", "instituto", "colegio", "escola"]):
            return c
    # Padrão 2: título de Licenciada/Bacharel em [Pedagogia]
    m2 = re.search(r"\b(?:t[ií]tulo|grau)\s+de\s+(?:Licenciad[ao]|Bacharel(?:ado)?|Tecn[oó]log[ao]|Especialista|Mestre|Doutor)\s+(?:em|de|a)?\s+([A-Za-zÀ-ú\s\-]+?)(?:,\s*em|\s+a\s+[A-Z]|\.|\n|$)", text, re.IGNORECASE)
    if m2:
        c2 = m2.group(1).strip()
        if 3 <= len(c2) <= 60 and not any(k in c2.lower() for k in ["faculdade", "universidade", "instituto", "colegio", "escola"]):
            return c2
    return None


# ---------------------------------------------------------------------------
# Extração de Metadados e Fallbacks Especializados (Financeiro / PIX)
# ---------------------------------------------------------------------------
def extract_monetary_value(text: str) -> Optional[str]:
    """Extrai valor monetário em reais (R$) do texto do documento."""
    if not text:
        return None
    # Padrão R$ 1.234,56 ou R$ 1234,56 ou Valor R$ 50,00
    m = re.search(r"(?:R\$\s*|Valor[\s:]*R\$\s*|Valor[\s:]+)([0-9]{1,3}(?:\.[0-9]{3})*,\s*[0-9]{2})\b", text, re.IGNORECASE)
    if m:
        v = m.group(1).replace(" ", "")
        return f"R$ {v}"
    # Padrão simplificado R$ 150.00 ou R$ 150,00
    m2 = re.search(r"R\$\s*([0-9]+(?:[.,][0-9]{2}))\b", text, re.IGNORECASE)
    if m2:
        val = m2.group(1).replace(".", ",")
        return f"R$ {val}"
    return None


def extract_pix_e2e_id(text: str) -> Optional[str]:
    """Busca identificador Fim-a-Fim (End-to-End ID) de transação PIX (iniciado em E seguido de 30-40 caracteres alfanuméricos)."""
    if not text:
        return None
    m = re.search(r"\b(E\d{8}[0-9A-Za-z]{18,32})\b", text)
    if m:
        return m.group(1)
    m2 = re.search(r"(?:ID\s*(?:da\s*)?transa[çc][ãa]o|Identificador|End-to-End|E2E|Fim[\s-]*a[\s-]*Fim)[\s:]*([E0-9A-Za-z\-]{20,45})", text, re.IGNORECASE)
    if m2:
        cand = m2.group(1).strip()
        if len(cand) >= 20:
            return cand
    return None


def extract_pix_chave(text: str) -> Optional[str]:
    """Busca chave PIX identificada no texto."""
    if not text:
        return None
    # 1. Padrão com rótulo: Chave PIX, Chave do recebedor/favorecido/pagador, Chave cadastrada, etc.
    m = re.search(
        r"(?:Chave(?:\s+(?:PIX|do\s+(?:recebedor|favorecido|pagador|cliente)|cadastrada|utilizada|de\s+endere[çc]amento))?)\s*[:\s-]+\s*([a-zA-Z0-9\.\-\@\+\(\)\s]{4,60})",
        text,
        re.IGNORECASE
    )
    if m:
        cand = m.group(1).strip().rstrip(".,;")
        cand = cand.split("\n")[0].strip()
        if len(cand) >= 4 and not re.match(r"^(?:da|do|de|o|a)\b", cand, re.IGNORECASE):
            return cand
    # 2. Busca direta por e-mail no comprovante PIX
    if "pix" in text.lower():
        m_email = re.search(r"\b([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)\b", text)
        if m_email:
            return m_email.group(1).strip()
    return None


def extract_pix_authentication(text: str) -> Optional[str]:
    """Busca código de autenticação bancária / hash de segurança no comprovante."""
    if not text:
        return None
    m = re.search(r"(?:Autentica[çc][ãa]o|C[oó]digo\s*de\s*autentica[çc][ãa]o|Controle)[\s:]*([0-9A-Za-z\.\-\:]{8,45})", text, re.IGNORECASE)
    if m:
        cand = m.group(1).strip().rstrip(".,;")
        if len(cand) >= 8:
            return cand
    return None


def load_image_to_base64(
    image_path: Union[str, Path],
    max_dimension: int = 2048,
    quality: int = 85
) -> List[str]:
    """
    Carrega arquivo de imagem nativo (PNG, JPG, JPEG, WEBP) e converte para base64 JPEG
    otimizado para leitura visual (OCR) multimodal via LLM.
    """
    try:
        from PIL import Image
        with Image.open(str(image_path)) as img:
            if img.mode in ("RGBA", "LA", "P"):
                rgb_img = Image.new("RGB", img.size, (255, 255, 255))
                if img.mode == "RGBA":
                    rgb_img.paste(img, mask=img.split()[3])
                else:
                    rgb_img.paste(img.convert("RGB"))
                img = rgb_img
            elif img.mode != "RGB":
                img = img.convert("RGB")

            w, h = img.size
            if max(w, h) > max_dimension:
                scale_ratio = max_dimension / float(max(w, h))
                new_w = int(w * scale_ratio)
                new_h = int(h * scale_ratio)
                resample_filter = getattr(Image, "Resampling", Image).LANCZOS
                img = img.resize((new_w, new_h), resample_filter)

            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=quality, optimize=True)
            return [base64.b64encode(buf.getvalue()).decode("utf-8")]
    except Exception as e:
        print(f"[Aviso] Falha ao converter imagem {image_path} para base64: {e}")
        return []


def get_document_images_for_vision(
    file_path: Union[str, Path],
    max_pages: int = 2,
    scale: float = 1.5,
    quality: int = 80
) -> List[str]:
    """
    Retorna lista de imagens base64 seja o arquivo um PDF ou imagem nativa (PNG, JPG, JPEG, WEBP).
    """
    p = Path(file_path)
    ext = p.suffix.lower()
    if ext in IMAGE_EXTENSIONS:
        return load_image_to_base64(p, quality=quality)
    elif ext == ".pdf":
        return render_pdf_pages_to_base64(str(p), max_pages=max_pages, scale=scale, quality=quality)
    elif ext in WORD_EXTENSIONS:
        pdf_cached = convert_office_to_pdf(p)
        if pdf_cached and pdf_cached.exists():
            return render_pdf_pages_to_base64(str(pdf_cached), max_pages=max_pages, scale=scale, quality=quality)
    return []


# ---------------------------------------------------------------------------
# Conversão e Extração de Documentos Word e Suíte Office (.docx, .doc, .odt, .rtf, .txt)
# ---------------------------------------------------------------------------
def convert_office_to_pdf(
    office_path: Union[str, Path],
    cache_dir: Optional[Union[str, Path]] = None,
    timeout: int = 45
) -> Optional[Path]:
    """
    Converte documento do Microsoft Word ou OpenOffice (.docx, .doc, .odt, .rtf) para PDF
    utilizando LibreOffice Headless com cache persistente baseado no hash MD5.
    Garante fidelidade 100% de layout, tabelas e tipografia sem conflitos com LibreOffice desktop.
    """
    p = Path(office_path).resolve()
    if not p.exists() or not p.is_file():
        return None

    ext = p.suffix.lower()
    if ext == ".pdf":
        return p

    # Determina pasta de cache
    if cache_dir:
        c_dir = Path(cache_dir).resolve()
    else:
        env_cache = os.environ.get("JOAKINDEX_PDF_CACHE")
        if env_cache:
            c_dir = Path(env_cache).resolve()
        else:
            c_dir = p.parent / ".cache_pdf"

    try:
        c_dir.mkdir(parents=True, exist_ok=True)
    except Exception:
        c_dir = Path(tempfile.gettempdir()) / "joakindex_pdf_cache"
        c_dir.mkdir(parents=True, exist_ok=True)

    # Nome do arquivo de cache pelo MD5
    try:
        md5_val = calculate_md5(p).strip().lower()
    except Exception:
        md5_val = hashlib.md5(p.name.encode("utf-8")).hexdigest()

    target_pdf = c_dir / f"{md5_val}.pdf"

    # Se já existir e for válido, reaproveita instantaneamente
    if target_pdf.exists() and target_pdf.stat().st_size > 500:
        return target_pdf

    # Detecta executável do LibreOffice
    lo_bin = shutil.which("libreoffice") or shutil.which("soffice")
    if not lo_bin:
        print(f"[Aviso Office] LibreOffice não encontrado no sistema para converter {p.name}")
        return None

    with _OFFICE_CONVERT_LOCK:
        # Re-checa após adquirir o lock (evita trabalho redundante)
        if target_pdf.exists() and target_pdf.stat().st_size > 500:
            return target_pdf

        try:
            # Perfil isolado para nunca travar com LibreOffice do usuário
            user_inst = f"file://{tempfile.gettempdir()}/libreoffice_headless_joakindex"
            cmd = [
                lo_bin,
                f"-env:UserInstallation={user_inst}",
                "--headless",
                "--convert-to", "pdf",
                "--outdir", str(c_dir),
                str(p)
            ]
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)

            # O LibreOffice gera o PDF com o mesmo stem do arquivo de origem na pasta outdir
            lo_output = c_dir / f"{p.stem}.pdf"
            if lo_output.exists() and lo_output.stat().st_size > 500:
                if lo_output != target_pdf:
                    shutil.copy2(lo_output, target_pdf)
                return target_pdf
        except Exception as e:
            print(f"[Aviso Office] Falha ao converter {p.name} para PDF via LibreOffice: {e}")

    return None


def extract_docx_text(docx_path: Union[str, Path]) -> str:
    """
    Extrai texto estruturado de arquivo .docx diretamente do XML interno (word/document.xml)
    em Python puro com zero dependências externas.
    """
    p = Path(docx_path)
    if not p.exists() or not p.is_file():
        return ""
    try:
        with zipfile.ZipFile(p, "r") as zf:
            if "word/document.xml" not in zf.namelist():
                return ""
            xml_content = zf.read("word/document.xml")
            tree = ET.fromstring(xml_content)
            paragraphs = []
            for p_node in tree.iter():
                if p_node.tag.endswith("}p"):
                    texts = [node.text for node in p_node.iter() if node.tag.endswith("}t") and node.text]
                    if texts:
                        paragraphs.append("".join(texts).strip())

            # Coleta também cabeçalhos e rodapés se existirem
            for name in zf.namelist():
                if (name.startswith("word/header") or name.startswith("word/footer")) and name.endswith(".xml"):
                    try:
                        h_tree = ET.fromstring(zf.read(name))
                        for p_node in h_tree.iter():
                            if p_node.tag.endswith("}p"):
                                texts = [node.text for node in p_node.iter() if node.tag.endswith("}t") and node.text]
                                if texts:
                                    paragraphs.append("".join(texts).strip())
                    except Exception:
                        pass

            return "\n\n".join(paragraphs).strip()
    except Exception as e:
        print(f"[Aviso DOCX] Falha ao ler XML de {p.name}: {e}")
        return ""


def extract_odt_text(odt_path: Union[str, Path]) -> str:
    """Extrai texto estruturado de arquivo .odt diretamente do content.xml interno."""
    p = Path(odt_path)
    if not p.exists() or not p.is_file():
        return ""
    try:
        with zipfile.ZipFile(p, "r") as zf:
            if "content.xml" not in zf.namelist():
                return ""
            xml_content = zf.read("content.xml")
            tree = ET.fromstring(xml_content)
            paragraphs = []
            for node in tree.iter():
                if node.tag.endswith("}p") or node.tag.endswith("}h"):
                    t = "".join(node.itertext()).strip()
                    if t:
                        paragraphs.append(t)
            return "\n\n".join(paragraphs).strip()
    except Exception as e:
        print(f"[Aviso ODT] Falha ao ler content.xml de {p.name}: {e}")
        return ""


def extract_txt_text(txt_path: Union[str, Path]) -> str:
    """Extrai texto de arquivo .txt com detecção inteligente de encodings (UTF-8, CP1252, Latin-1)."""
    p = Path(txt_path)
    if not p.exists() or not p.is_file():
        return ""
    for enc in ["utf-8-sig", "utf-8", "cp1252", "latin-1"]:
        try:
            return p.read_text(encoding=enc).strip()
        except Exception:
            continue
    return ""


def extract_document_text(file_path: Union[str, Path], max_pages: int = 4) -> str:
    """
    Roteia a extração de texto para o leitor especializado de acordo com a extensão do documento:
    PDF, DOCX, DOC, ODT, RTF ou TXT.
    """
    p = Path(file_path)
    ext = p.suffix.lower()

    if ext == ".pdf":
        return extract_pdf_text(str(p), max_pages=max_pages)

    if ext == ".docx":
        t = extract_docx_text(p)
        if len(t) >= 20:
            return t
        pdf_c = convert_office_to_pdf(p)
        if pdf_c and pdf_c.exists():
            return extract_pdf_text(str(pdf_c), max_pages=max_pages)
        return t

    if ext == ".odt":
        t = extract_odt_text(p)
        if len(t) >= 20:
            return t
        pdf_c = convert_office_to_pdf(p)
        if pdf_c and pdf_c.exists():
            return extract_pdf_text(str(pdf_c), max_pages=max_pages)
        return t

    if ext == ".txt":
        return extract_txt_text(p)

    if ext in [".doc", ".rtf"]:
        pdf_c = convert_office_to_pdf(p)
        if pdf_c and pdf_c.exists():
            return extract_pdf_text(str(pdf_c), max_pages=max_pages)
        return ""

    return ""


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
    max_pages: int = 4,
    scale: float = 2.0,
    quality: int = 85
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


def classify_text_signatures(text: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Identifica o tipo de documento e seu domínio a partir de assinaturas textuais e palavras-chave.
    Retorna (tipo_documento, dominio) ou (None, None).
    """
    if not text or len(text.strip()) < 10:
        return None, None

    t = text.lower()
    scores = {}

    # 0. Consulta dinâmica de Regras Aprendidas pelo Usuário
    try:
        from db_manager import consultar_regra_para_texto, DEFAULT_DB_PATH
        regra = consultar_regra_para_texto(DEFAULT_DB_PATH, text)
        if regra:
            return regra["valor_atribuido"], regra["dominio"]
    except Exception:
        pass

    # 1. Domínio: Identificação
    if any(k in t for k in ["carteira nacional de habilita", "driver license", "permiso de conduccion", "senatran", "denatran", "1° habilita", "1ª habilita"]) or ("cnh" in t and "categoria" in t):
        scores["CNH"] = ("identificacao", 10)
    elif any(k in t for k in ["cédula de identidade", "cedula de identidade", "registro geral", "instituto de identificação", "instituto de identificacao", "secretaria de segurança", "ssp/", "ssp-", "polícia civil"]):
        scores["RG"] = ("identificacao", 9)
    elif any(k in t for k in ["certidão de nascimento", "certidao de nascimento", "nascimento sob o termo", "registro civil das pessoas naturais"]):
        scores["Certidão de Nascimento"] = ("identificacao", 9)
    elif any(k in t for k in ["certidão de casamento", "certidao de casamento", "casamento sob o termo"]):
        scores["Certidão de Casamento"] = ("identificacao", 9)
    elif any(k in t for k in ["cadastro de pessoas físicas", "cadastro de pessoas fisicas", "receita federal do brasil", "comprovante de inscrição no cpf", "cartão de identificação do contribuinte"]) or ("cpf" in t and "receita federal" in t):
        scores["CPF"] = ("identificacao", 8)
    elif any(k in t for k in ["passaporte", "passport", "república federativa do brasil passaporte"]):
        scores["Passaporte"] = ("identificacao", 9)
    elif any(k in t for k in ["título de eleitor", "titulo de eleitor", "justiça eleitoral"]):
        scores["Título de Eleitor"] = ("identificacao", 8)
    elif any(k in t for k in ["carteira de trabalho", "ctps", "previdência social"]):
        scores["Carteira de Trabalho"] = ("identificacao", 8)

    # 2. Domínio: Acadêmico
    if any(k in t for k in ["diploma", "conferiu o grau", "confere o grau", "colação de grau", "conclusão do curso de", "conclusdo do curso de", "licenciada a", "licenciado a", "bacharel em", "conferiu o título"]):
        scores["Diploma"] = ("academico", 10)
    elif any(k in t for k in ["histórico escolar", "historico escolar", "rendimento escolar", "componente curricular", "disciplinas cursadas", "coeficiente de rendimento"]):
        scores["Histórico Escolar"] = ("academico", 9)
    elif any(k in t for k in ["certificamos que", "concluiu com êxito", "concluiu com exito", "conferimos o presente certificado", "concluiu o curso de"]) or (
        ("certificado" in t or "pós-graduação" in t or "pos-graduacao" in t or "especialização" in t or "especializacao" in t)
        and not any(cnae in t for cnae in ["código e descrição", "codigo e descricao", "atividade econômica", "atividade economica", "cnae", "cadastro nacional da pessoa jurídica", "cadastro nacional da pessoa juridica", "situação cadastral", "situacao cadastral"])
        and any(w in t for w in ["curso", "conclusão", "conclusao", "titulação", "titulacao", "certificamos", "outorgado", "aprovação", "aprovacao", "carga horária", "carga horaria"])
    ):
        scores["Certificado"] = ("academico", 8)
    elif any(k in t for k in ["declaração de matrícula", "atestado de matrícula", "declaração de conclusão", "declaramos para os devidos fins"]):
        scores["Declaração"] = ("academico", 7)
    elif any(k in t for k in ["ementa", "conteúdo programático", "plano de ensino"]):
        scores["Ementa"] = ("academico", 7)
    elif any(k in t for k in ["dissertação de mestrado", "dissertacao de mestrado", "tese de doutorado", "trabalho de conclusão de curso"]):
        scores["Dissertação"] = ("academico", 8)
    elif any(k in t for k in ["ficha catalográfica", "ficha catalografica"]) or ("isbn" in t and "editora" in t):
        scores["Livro/Publicação"] = ("academico", 8)

    # 3. Domínio: Profissional / Carreira / Cadastral
    has_academic_signatures = any(k in t for k in [
        "diploma", "certificamos que", "concluiu com êxito", "concluiu com exito",
        "conferimos o presente certificado", "concluiu o curso", "conferiu o grau",
        "histórico escolar", "historico escolar", "componente curricular", "colação de grau"
    ])
    if (any(k in t for k in ["comprovante de inscrição e de situação cadastral", "comprovante de inscricao e de situacao cadastral", "cadastro nacional da pessoa jurídica", "cadastro nacional da pessoa juridica", "cartão cnpj", "cartao cnpj", "cartão do cnpj", "cartao do cnpj"]) or ("situação cadastral" in t and "cnpj" in t) or ("situacao cadastral" in t and "cnpj" in t) or (("receita federal" in t or "ministério da fazenda" in t) and "cnpj" in t and not has_academic_signatures)):
        scores["Cartão CNPJ / Situação Cadastral"] = ("profissional", 10)
    elif any(k in t for k in ["curriculum vitae", "currículo vitae", "curriculo lattes", "currículo lattes", "experiência profissional", "experiencia profissional", "resumo profissional", "histórico profissional", "historico profissional", "trajetória profissional", "trajetoria profissional", "dados profissionais", "formação acadêmica e profissional"]):
        scores["Currículo"] = ("profissional", 9)
    elif any(k in t for k in ["declaração de experiência", "declaracao de experiencia", "atestado de capacidade técnica", "atestado de capacidade tecnica"]):
        scores["Declaração de Experiência Profissional"] = ("profissional", 8)

    # 4. Domínio: Financeiro
    if any(k in t for k in ["comprovante pix", "transferência pix", "transferencia pix", "pagamento pix", "chave pix", "fim-a-fim", "end-to-end", "e2eid"]):
        scores["Comprovante PIX"] = ("financeiro", 10)
    elif any(k in t for k in ["comprovante de pagamento", "comprovante de transferência", "comprovante de transferencia", "autenticação bancária", "autenticação mecânica", "ted", "doc"]):
        scores["Comprovante de Pagamento"] = ("financeiro", 8)
    elif any(k in t for k in ["boleto bancário", "boleto bancario", "recibo do pagador", "linha digitável", "código de barras"]):
        scores["Boleto"] = ("financeiro", 8)
    elif any(k in t for k in ["recibo de pagamento", "recebemos de"]):
        scores["Recibo"] = ("financeiro", 7)

    # 5. Domínio: Jurídico / Outros
    if any(k in t for k in ["procuração", "procuracao", "outorgante", "outorgado"]):
        scores["Procuração"] = ("juridico", 8)
    elif any(k in t for k in ["termo de posse", "posse no cargo"]):
        scores["Termo de Posse"] = ("juridico", 8)
    elif any(k in t for k in ["contrato de prestação", "instrumento particular"]):
        scores["Contrato"] = ("juridico", 7)

    if not scores:
        return None, None

    best_tipo = max(scores.keys(), key=lambda k: scores[k][1])
    return best_tipo, scores[best_tipo][0]


# ---------------------------------------------------------------------------
# OCR Local Rápido de Contingência (Tesseract)
# ---------------------------------------------------------------------------
def run_tesseract_ocr_on_image(img: Any, try_rotation: bool = True) -> str:
    """
    Executa OCR local rápido via Tesseract em uma imagem PIL ou array.
    Testa automaticamente rotação em 180° se a primeira passada não encontrar CPF ou texto suficiente.
    """
    if not shutil.which("tesseract"):
        return ""

    if Image is not None and not isinstance(img, Image.Image):
        try:
            img = Image.fromarray(img)
        except Exception:
            return ""

    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        tmp_path = f.name
        img.save(tmp_path)

    def _exec_tess(p: str) -> str:
        for lang in ["por+eng", "eng"]:
            try:
                proc = subprocess.run(
                    ["tesseract", p, "stdout", "-l", lang],
                    capture_output=True,
                    text=True,
                    timeout=12
                )
                if proc.returncode == 0 and proc.stdout.strip():
                    return proc.stdout.strip()
            except Exception:
                pass
        return ""

    text = _exec_tess(tmp_path)

    # Se não encontrou CPF ou assinatura conhecida, tenta rotação de 180 graus (documentos de cabeça para baixo)
    if try_rotation:
        has_cpf = bool(re.search(r"\d{3}\.?\d{3}\.?\d{3}-?\d{2}", text))
        has_sig = bool(classify_text_signatures(text)[0])
        # Só testa rotação 180° se não houver CPF E (não houver assinatura conhecida OU o texto for muito curto)
        if not has_cpf and (not has_sig or len(text) < 60):
            try:
                img_180 = img.rotate(180, expand=True)
                img_180.save(tmp_path)
                text_180 = _exec_tess(tmp_path)
                has_cpf_180 = bool(re.search(r"\d{3}\.?\d{3}\.?\d{3}-?\d{2}", text_180))
                has_sig_180 = bool(classify_text_signatures(text_180)[0])
                if has_cpf_180 or (not has_sig and has_sig_180):
                    text = text_180
            except Exception:
                pass
        elif not has_cpf:
            # Já tem assinatura de documento (ex: certidão), mas se 180° encontrar um CPF válido, pode ser anexo invertido
            try:
                img_180 = img.rotate(180, expand=True)
                img_180.save(tmp_path)
                text_180 = _exec_tess(tmp_path)
                if re.search(r"\d{3}\.?\d{3}\.?\d{3}-?\d{2}", text_180):
                    text = text_180
            except Exception:
                pass

    if os.path.exists(tmp_path):
        try:
            os.remove(tmp_path)
        except Exception:
            pass

    return text.strip()


def extract_tesseract_text_from_pdf(
    pdf_path: Union[str, Path],
    max_pages: int = 4
) -> str:
    """
    Extrai texto complementar via Tesseract local das imagens embutidas e das páginas do PDF.
    Captura CPFs, RGs e dados pessoais em alta resolução (ex: recortes do app CDT/SENATRAN).
    """
    if not shutil.which("tesseract"):
        return ""

    extracted_parts: List[str] = []

    # 1. Analisa imagens embutidas em alta resolução (fotos de CNH, RG, CPF inseridas no PDF)
    if pdfium is not None:
        try:
            pdf = pdfium.PdfDocument(str(pdf_path))
            num_pages = min(len(pdf), max_pages)
            for i in range(num_pages):
                page = pdf[i]
                for obj in page.get_objects():
                    if obj.type == pdfium.raw.FPDF_PAGEOBJ_IMAGE:
                        bm = obj.get_bitmap()
                        pil_img = bm.to_pil()
                        if pil_img.width >= 200 and pil_img.height >= 200:
                            t = run_tesseract_ocr_on_image(pil_img, try_rotation=True)
                            if t and len(t) >= 15:
                                extracted_parts.append(t)
        except Exception:
            pass

    # 2. Se nenhuma imagem embutida foi encontrada ou se ainda não achou CPF, renderiza as páginas
    combined = "\n\n".join(extracted_parts)
    if not re.search(r"\d{3}\.?\d{3}\.?\d{3}-?\d{2}", combined):
        if pdfium is not None:
            try:
                pdf = pdfium.PdfDocument(str(pdf_path))
                num_pages = min(len(pdf), max_pages)
                for i in range(num_pages):
                    page = pdf[i]
                    p_img = page.render(scale=2.0).to_pil()
                    t = run_tesseract_ocr_on_image(p_img, try_rotation=True)
                    if t and len(t) >= 15:
                        extracted_parts.append(t)
            except Exception:
                pass

    return "\n\n".join(extracted_parts).strip()





def analyze_pdf_dossier(
    pdf_path: Union[str, Path],
    max_ocr_pages: int = 10
) -> Dict[str, Any]:
    """
    Realiza a varredura completa de todas as páginas do PDF para identificar múltiplos documentos.
    Utiliza leitura digital em 100% das páginas e OCR Tesseract pontual em páginas de imagem.
    Aplica regras de hierarquia e anti-contaminação para consolidar dados do titular.
    """
    p = Path(pdf_path)
    if p.suffix.lower() in WORD_EXTENSIONS:
        cached_pdf = convert_office_to_pdf(p)
        if cached_pdf and cached_pdf.exists():
            p = cached_pdf

    result = {
        "paginas": [],
        "todos_tipos": [],
        "todos_dominios": [],
        "dossie_paginas": [],
        "cpf_titular": None,
        "rg_titular": None,
        "curso_titular": None,
        "faculdade_titular": None,
        "tipo_documento_principal": None,
        "dominio_principal": None
    }

    if not p.exists() or pdfium is None:
        return result

    try:
        pdf = pdfium.PdfDocument(str(p))
        total_pages = len(pdf)
    except Exception:
        return result

    pages_info = []
    seen_tipos = []
    seen_dominios = []

    for i in range(total_pages):
        page = pdf[i]
        page_num = i + 1

        # 1. Leitura de texto digital da página
        try:
            p_text = page.get_textpage().get_text_range().strip()
        except Exception:
            p_text = ""

        embedded_texts = []
        # 2. Se houver imagens embutidas em alta resolução (ex: recortes CDT/SENATRAN)
        try:
            for obj in page.get_objects():
                if obj.type == pdfium.raw.FPDF_PAGEOBJ_IMAGE:
                    bm = obj.get_bitmap()
                    pil_img = bm.to_pil()
                    if pil_img.width >= 200 and pil_img.height >= 200:
                        t = run_tesseract_ocr_on_image(pil_img, try_rotation=True)
                        if t and len(t) >= 15:
                            embedded_texts.append(t)
        except Exception:
            pass

        # 3. Se a página for imagem pura sem texto digital e não achou imagens embutidas, roda OCR se dentro do limite
        ocr_rendered_text = ""
        if len(p_text) < 40 and not embedded_texts and i < max_ocr_pages:
            try:
                p_img = page.render(scale=1.5).to_pil()
                ocr_rendered_text = run_tesseract_ocr_on_image(p_img, try_rotation=True)
            except Exception:
                pass

        combined_page_text = "\n".join(
            x for x in [p_text, "\n".join(embedded_texts), ocr_rendered_text] if x.strip()
        ).strip()

        if not combined_page_text:
            continue

        tipo, dom = classify_text_signatures(combined_page_text)
        p_cpf = extract_cpf_fallback(combined_page_text)
        p_rg = extract_rg_fallback(combined_page_text)
        p_cnpj = extract_cnpj_fallback(combined_page_text)
        p_curso = extract_course_fallback(combined_page_text)

        p_entry = {
            "pagina": page_num,
            "dominio": dom or "outros",
            "tipo": tipo or "Documento Diverso",
            "cpf": p_cpf,
            "rg": p_rg,
            "cnpj": p_cnpj,
            "curso": p_curso
        }
        pages_info.append(p_entry)

        if tipo and tipo not in seen_tipos:
            seen_tipos.append(tipo)
        if dom and dom not in seen_dominios:
            seen_dominios.append(dom)

    # Hierarquia e Anti-Contaminação
    # CPF: Prioridade 1 = Identificação, 2 = Acadêmico, 3 = Financeiro
    cpf_titular = None
    for target_dom in ["identificacao", "academico", "financeiro", "outros"]:
        for p_info in pages_info:
            if p_info["dominio"] == target_dom and p_info.get("cpf"):
                cpf_titular = p_info["cpf"]
                break
        if cpf_titular:
            break

    # RG: Prioridade 1 = Identificação, 2 = Acadêmico
    rg_titular = None
    for target_dom in ["identificacao", "academico", "outros"]:
        for p_info in pages_info:
            if p_info["dominio"] == target_dom and p_info.get("rg"):
                rg_titular = p_info["rg"]
                break
        if rg_titular:
            break

    # CNPJ: Prioridade 1 = Profissional / Cadastral, 2 = Outros
    cnpj_titular = None
    for target_dom in ["profissional", "identificacao", "financeiro", "outros"]:
        for p_info in pages_info:
            if p_info["dominio"] == target_dom and p_info.get("cnpj"):
                cnpj_titular = p_info["cnpj"]
                break
        if cnpj_titular:
            break

    # Curso: Estritamente de páginas acadêmicas
    curso_titular = None
    for p_info in pages_info:
        if p_info["dominio"] == "academico" and p_info.get("curso"):
            curso_titular = p_info["curso"]
            break

    # Determinação do Tipo e Domínio Principal
    # Se houver Diploma ou documento acadêmico, o dossiê tem primazia acadêmica
    dominio_principal = "academico" if "academico" in seen_dominios else (seen_dominios[0] if seen_dominios else "academico")
    tipo_principal = None
    priority_order = [
        "Diploma", "Certificado", "Histórico Escolar", "Declaração", "Ementa", "Dissertação", "Livro/Publicação",
        "Cartão CNPJ / Situação Cadastral", "Comprovante de Inscrição e de Situação Cadastral", "Currículo", "Declaração de Experiência Profissional",
        "CNH", "RG", "CPF", "Certidão de Nascimento", "Certidão de Casamento", "Passaporte",
        "Comprovante PIX", "Comprovante de Pagamento", "Boleto", "Recibo"
    ]
    for p_tipo in priority_order:
        if p_tipo in seen_tipos:
            tipo_principal = p_tipo
            break
    if not tipo_principal and seen_tipos:
        tipo_principal = seen_tipos[0]

    result["paginas"] = pages_info
    result["todos_tipos"] = seen_tipos
    result["todos_dominios"] = seen_dominios
    result["dossie_paginas"] = [{"pagina": p["pagina"], "tipo": p["tipo"], "dominio": p["dominio"]} for p in pages_info]
    result["cpf_titular"] = cpf_titular
    result["rg_titular"] = rg_titular
    result["cnpj_titular"] = cnpj_titular
    result["curso_titular"] = curso_titular
    result["tipo_documento_principal"] = tipo_principal
    result["dominio_principal"] = dominio_principal

    return result


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
                "  2. Via linha de comando: ./joakindex -p openai -k sk-proj-...\n"
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
# Prompts Universais de Extração (Texto e Visão / OCR Multimodal)
# ---------------------------------------------------------------------------
def build_universal_vision_prompt(extra_context: str = "") -> str:
    ctx_note = ""
    if extra_context:
        ctx_note = f"""
OBSERVAÇÃO DA LEITURA TEXTUAL PRÉVIA:
\"\"\"
{extra_context[:1200]}
\"\"\"
Atenção: Analise com precisão os elementos visuais das páginas (títulos, logotipos de faculdades ou bancos, cabeçalhos, comprovantes PIX, tabelas, selos, carimbos, assinaturas e formatação) para classificar o domínio e tipo de documento.
"""

    return f"""Você é um especialista em OCR multimodal e classificação de documentos oficiais brasileiros.
Analise visualmente as imagens deste documento (que pode ser acadêmico, comprovante financeiro/PIX, identificação civil, jurídico ou outro) e extraia todas as entidades estruturadas.
{ctx_note}
Extraia as seguintes informações e retorne ESTRITAMENTE um objeto JSON com as chaves exatas abaixo:

1. DOMÍNIO E CLASSIFICAÇÃO:
- "dominio": Classifique em uma das seguintes opções estritas:
    * "academico" (para diplomas, certificados de cursos, históricos escolares, declarações de matrícula/conclusão, carteiras de estudante)
    * "financeiro" (para comprovantes PIX, recibos de pagamento, transferências bancárias, boletos, extratos, notas fiscais)
    * "identificacao" (para RG, CNH, CPF, Título de Eleitor, Certidão de Nascimento/Casamento, Passaporte, Registro Profissional)
    * "profissional" (para Cartão CNPJ, Comprovante de Inscrição e Situação Cadastral, currículos, carteira de trabalho, atestados de capacidade)
    * "juridico" (para contratos, procurações, termos de posse, certidões judiciais, escrituras, petições)
    * "outro" (para quaisquer outros documentos não contemplados acima)
- "tipo_documento": Nome específico do documento (ex: "Cartão CNPJ / Situação Cadastral", "Comprovante PIX", "Recibo de Pagamento", "Diploma", "Certificado", "Histórico Escolar", "RG / Identidade", "CNH", "Contrato de Prestação de Serviços", "Declaração", "Outro"). Se não puder identificar, retorne "Não identificado".

2. CAMPOS UNIVERSAIS:
- "data": Data principal do documento ou data/hora da transação (ex: "18/12/2023", "08/09/2026 14:30:00" ou "18 de dezembro de 2023"). Se não encontrar, retorne null.
- "beneficiario": Nome do titular, aluno, favorecido do pagamento ou Razão Social da empresa. Se não encontrar, retorne null.
- "cpf": CPF do titular ou recebedor identificado (ex: "000.000.000-00" ou apenas números). Se não houver menção, retorne null.
- "rg": Número da Cédula de Identidade / RG do titular incluindo órgão emissor/UF (ex: "12.345.678-9 SSP/SP"). Se não houver, retorne null.
- "cnpj": CNPJ da empresa, órgão ou pagador/recebedor formatado (ex: "00.000.000/0000-00") ou apenas números. Se não houver, retorne null.
- "valor_monetario": Se for comprovante financeiro ou PIX, informe o valor monetário com 'R$' (ex: "R$ 150,00" ou "R$ 1.250,50"). Para outros documentos, retorne null.

3. CAMPOS ACADÊMICOS (se aplicável):
- "curso": Nome oficial do curso concluído (ex: "Pós-graduação Lato Sensu em Gestão Escolar", "Bacharelado em Administração"). Se não for curso, retorne null.
- "natureza_curso": Nível acadêmico: "Graduação / Curso Superior", "Pós-Graduação Lato Sensu (Especialização/MBA)", "Pós-Graduação Stricto Sensu (Mestrado/Doutorado)", "Curso Técnico / Profissionalizante", "Curso de Extensão / Aperfeiçoamento", "Educação Básica" ou null.
- "carga_horaria": Carga horária total (ex: "750 h/aulas", "360 horas", "750h"). Se não houver, retorne null.
- "faculdade": Nome padronizado da faculdade, universidade ou instituição de ensino no formato "Nome Completo por Extenso (SIGLA)" (ex: "Universidade de São Paulo (USP)"). Se for comprovante bancário ou PIX, informe o nome da Instituição Financeira / Banco / PSP (ex: "Nu Pagamentos S.A. (NUBANK)", "Banco do Brasil (BB)", "Caixa Econômica Federal (CEF)"). Se for Cartão CNPJ, informe "Receita Federal do Brasil (RFB)". Se não houver, retorne null.

4. CAMPOS ESPECÍFICOS DE PIX / FINANCEIRO (preencha se for documento financeiro/PIX, senão retorne null):
- "pix_pagador_nome": Nome completo do pagador da transferência.
- "pix_pagador_cpf_cnpj": CPF ou CNPJ mascarado ou completo do pagador (ex: "***.123.456-**").
- "pix_pagador_banco": Banco / PSP de origem do pagador.
- "pix_recebedor_banco": Banco / PSP de destino do recebedor.
- "pix_chave": Chave PIX utilizada (e-mail, CPF/CNPJ, telefone ou chave EVP aleatória).
- "pix_e2e_id": Identificador fim-a-fim da transação (ID E2E com 32 a 40 caracteres iniciado por 'E', ex: "E00416968202609081430s0123456789").
- "pix_autenticacao": Código de autenticação bancária ou hash de controle de segurança.

5. CAMPOS CADASTRAIS / PESSOA JURÍDICA (preencha se for Cartão CNPJ / Comprovante de Situação Cadastral ou documento de empresa, senão retorne null):
- "razao_social": Nome empresarial oficial da entidade/empresa.
- "nome_fantasia": Título do estabelecimento / nome fantasia.
- "situacao_cadastral": Situação cadastral oficial (ex: "ATIVA", "BAIXADA", "SUSPENSA", "INAPTA", "NULA").
- "data_situacao": Data da situação cadastral (ex: "10/05/2021").
- "data_abertura": Data de fundação / início de atividade da empresa.
- "cnae_principal": Código e descrição da atividade econômica principal (CNAE).
- "natureza_juridica": Código e descrição da natureza jurídica.
- "endereco_completo": Endereço cadastral completo (logradouro, número, complemento, bairro, município, UF e CEP).
- "telefone": Telefone oficial informado no cadastro.
- "email": Endereço eletrônico / e-mail informado na Receita.

REGRAS:
1. Responda APENAS o JSON válido. Sem explicações, sem comentários e sem formatação markdown fora do JSON.
2. Não invente nenhuma informação. Se não estiver visível na imagem, preencha o valor como null.
"""


def build_universal_prompt(document_text: str) -> str:
    return f"""Você é um especialista em classificação de documentos oficiais brasileiros e extração estruturada de dados.
Analise o texto extraído deste documento (que pode ser acadêmico, comprovante financeiro/PIX, identificação, profissional/CNPJ, jurídico ou outro) e extraia todas as entidades estruturadas.

Texto extraído do documento:
\"\"\"
{document_text}
\"\"\"

Extraia as seguintes informações e retorne ESTRITAMENTE um objeto JSON com as chaves exatas abaixo:

1. DOMÍNIO E CLASSIFICAÇÃO:
- "dominio": Classifique em uma das seguintes opções estritas:
    * "academico" (para diplomas, certificados de cursos, históricos escolares, declarações de matrícula/conclusão, carteiras de estudante)
    * "financeiro" (para comprovantes PIX, recibos de pagamento, transferências bancárias, boletos, extratos, notas fiscais)
    * "identificacao" (para RG, CNH, CPF, Título de Eleitor, Certidão de Nascimento/Casamento, Passaporte, Registro Profissional)
    * "profissional" (para Cartão CNPJ, Comprovante de Inscrição e Situação Cadastral, currículos, carteira de trabalho, atestados de capacidade)
    * "juridico" (para contratos, procurações, termos de posse, certidões judiciais, escrituras, petições)
    * "outro" (para quaisquer outros documentos não contemplados acima)
- "tipo_documento": Nome específico do documento (ex: "Cartão CNPJ / Situação Cadastral", "Comprovante PIX", "Recibo de Pagamento", "Diploma", "Certificado", "Histórico Escolar", "RG / Identidade", "CNH", "Contrato de Prestação de Serviços", "Declaração", "Outro"). Se não puder identificar, retorne "Não identificado".

2. CAMPOS UNIVERSAIS:
- "data": Data principal do documento ou data/hora da transação (ex: "18/12/2023", "08/09/2026 14:30:00" ou "18 de dezembro de 2023"). Se não encontrar, retorne null.
- "beneficiario": Nome do titular, aluno, favorecido do pagamento ou Razão Social da empresa. Se não encontrar, retorne null.
- "cpf": CPF do titular ou recebedor identificado (ex: "000.000.000-00" ou apenas números). Se não houver menção, retorne null.
- "rg": Número da Cédula de Identidade / RG do titular incluindo órgão emissor/UF (ex: "12.345.678-9 SSP/SP"). Se não houver, retorne null.
- "cnpj": CNPJ da empresa, órgão ou pagador/recebedor formatado (ex: "00.000.000/0000-00") ou apenas números. Se não houver, retorne null.
- "valor_monetario": Se for comprovante financeiro ou PIX, informe o valor monetário com 'R$' (ex: "R$ 150,00" ou "R$ 1.250,50"). Para outros documentos, retorne null.

3. CAMPOS ACADÊMICOS (se aplicável):
- "curso": Nome oficial do curso concluído (ex: "Pós-graduação Lato Sensu em Gestão Escolar", "Bacharelado em Administração"). Se não for curso, retorne null.
- "natureza_curso": Nível acadêmico: "Graduação / Curso Superior", "Pós-Graduação Lato Sensu (Especialização/MBA)", "Pós-Graduação Stricto Sensu (Mestrado/Doutorado)", "Curso Técnico / Profissionalizante", "Curso de Extensão / Aperfeiçoamento", "Educação Básica" ou null.
- "carga_horaria": Carga horária total (ex: "750 h/aulas", "360 horas", "750h"). Se não houver, retorne null.
- "faculdade": Nome padronizado da faculdade, universidade ou instituição de ensino no formato "Nome Completo por Extenso (SIGLA)" (ex: "Universidade de São Paulo (USP)"). Se for comprovante bancário ou PIX, informe o nome da Instituição Financeira / Banco / PSP (ex: "Nu Pagamentos S.A. (NUBANK)", "Banco do Brasil (BB)", "Caixa Econômica Federal (CEF)"). Se for Cartão CNPJ, informe "Receita Federal do Brasil (RFB)". Se não houver, retorne null.

4. CAMPOS ESPECÍFICOS DE PIX / FINANCEIRO (preencha se for documento financeiro/PIX, senão retorne null):
- "pix_pagador_nome": Nome completo do pagador da transferência.
- "pix_pagador_cpf_cnpj": CPF ou CNPJ mascarado ou completo do pagador (ex: "***.123.456-**").
- "pix_pagador_banco": Banco / PSP de origem do pagador.
- "pix_recebedor_banco": Banco / PSP de destino do recebedor.
- "pix_chave": Chave PIX utilizada (e-mail, CPF/CNPJ, telefone ou chave EVP aleatória).
- "pix_e2e_id": Identificador fim-a-fim da transação (ID E2E com 32 a 40 caracteres iniciado por 'E', ex: "E00416968202609081430s0123456789").
- "pix_autenticacao": Código de autenticação bancária ou hash de controle de segurança.

5. CAMPOS CADASTRAIS / PESSOA JURÍDICA (preencha se for Cartão CNPJ / Comprovante de Situação Cadastral ou documento de empresa, senão retorne null):
- "razao_social": Nome empresarial oficial da entidade/empresa.
- "nome_fantasia": Título do estabelecimento / nome fantasia.
- "situacao_cadastral": Situação cadastral oficial (ex: "ATIVA", "BAIXADA", "SUSPENSA", "INAPTA", "NULA").
- "data_situacao": Data da situação cadastral (ex: "10/05/2021").
- "data_abertura": Data de fundação / início de atividade da empresa.
- "cnae_principal": Código e descrição da atividade econômica principal (CNAE).
- "natureza_juridica": Código e descrição da natureza jurídica.
- "endereco_completo": Endereço cadastral completo (logradouro, número, complemento, bairro, município, UF e CEP).
- "telefone": Telefone oficial informado no cadastro.
- "email": Endereço eletrônico / e-mail informado na Receita.

REGRAS:
1. Responda APENAS o JSON válido. Sem explicações, sem comentários e sem formatação markdown fora do JSON.
2. Não invente nenhuma informação. Se não estiver explícito no texto, preencha como null.
"""

# Aliases para retrocompatibilidade
build_vision_prompt = build_universal_vision_prompt
build_prompt = build_universal_prompt


# ---------------------------------------------------------------------------
# Processamento Universal de Documentos (PDF e Imagens PNG/JPG/JPEG/WEBP)
# ---------------------------------------------------------------------------
def process_single_pdf(
    pdf_path: Path,
    client: BaseLLMClient,
    max_pages: int = 4,
    force_ocr: bool = False,
    skip_ocr: bool = False,
    metadata: Optional[Dict[str, str]] = None
) -> Dict[str, Any]:
    pdf_path = Path(pdf_path)
    # Metadados do arquivo (MD5, data da última alteração, extensão)
    meta = metadata or get_file_metadata(pdf_path)
    ext = meta.get("extensao") or pdf_path.suffix.lower()
    is_image = ext in IMAGE_EXTENSIONS

    res_dict = {
        "md5": meta["md5"],
        "nome_arquivo": pdf_path.name,
        "caminho_relativo": meta.get("caminho_relativo") or pdf_path.name,
        "extensao": ext,
        "dominio": "academico",
        "data_modificacao": meta.get("data_modificacao"),
        "autor": meta.get("autor"),
        "dublin_core": meta.get("dublin_core"),
        "dc_title": meta.get("dc_title"),
        "dc_subject": meta.get("dc_subject"),
        "dc_creator_tool": meta.get("dc_creator_tool"),
        "data": None,
        "beneficiario": None,
        "cpf": None,
        "rg": None,
        "cnpj": None,
        "curso": None,
        "natureza_curso": None,
        "carga_horaria": None,
        "faculdade": None,
        "tipo_documento": None,
        "valor_monetario": None,
        "todos_dominios": [],
        "todos_tipos": [],
        "dossie_paginas": [],
        "status": "pendente",
        "erro": None,
        "metodo_leitura": "imagem_ocr_llm" if is_image else "texto_digital",
        "tentativa_ocr_llm": is_image,
        "processado_em": datetime.now().isoformat()
    }

    try:
        # Helper para sanitização de strings e listas
        def _clean_str(v):
            if isinstance(v, list):
                return ", ".join(str(x) for x in v if x).strip() or None
            if isinstance(v, str):
                return v.strip() or None
            return v

        text = ""
        has_text = False
        extracted_data = {}

        # ---------------------------------------------------------------------
        # RAMO A: ARQUIVO DE IMAGEM NATIVA (PNG, JPG, JPEG, WEBP)
        # ---------------------------------------------------------------------
        if is_image:
            if skip_ocr:
                res_dict["status"] = "erro"
                res_dict["erro"] = "Arquivo de imagem requer visão computacional (OCR), mas --skip-ocr está ativo."
                return res_dict

            images = load_image_to_base64(pdf_path)
            if not images:
                res_dict["status"] = "erro"
                res_dict["erro"] = f"Falha ao carregar e converter imagem '{pdf_path.name}' para processamento visual."
                return res_dict

            # OCR local preliminar rápido via Tesseract na imagem
            tess_text = ""
            if Image is not None:
                try:
                    pil_im = Image.open(pdf_path)
                    tess_text = run_tesseract_ocr_on_image(pil_im, try_rotation=True)
                except Exception:
                    pass

            try:
                vision_prompt = build_universal_vision_prompt(extra_context=tess_text if tess_text else "")
                extracted_data = client.generate_json_with_images(vision_prompt, images)
                res_dict["metodo_leitura"] = "imagem_ocr_llm"
                res_dict["tentativa_ocr_llm"] = True
            except Exception as e:
                if tess_text:
                    try:
                        prompt = build_universal_prompt(tess_text)
                        extracted_data = client.generate_json(prompt)
                        res_dict["metodo_leitura"] = "imagem_tesseract_llm"
                        res_dict["tentativa_ocr_llm"] = True
                    except Exception as e2:
                        res_dict["status"] = "erro"
                        res_dict["erro"] = f"Falha no processamento visual da imagem ({e}) e no OCR textual ({e2})"
                        res_dict["tentativa_ocr_llm"] = True
                        return res_dict
                else:
                    res_dict["status"] = "erro"
                    res_dict["erro"] = f"Falha no processamento visual da imagem via LLM: {e}"
                    res_dict["tentativa_ocr_llm"] = True
                    return res_dict

        # ---------------------------------------------------------------------
        # RAMO B: DOCUMENTOS (PDF, Word DOCX/DOC, ODT, RTF, TXT)
        # ---------------------------------------------------------------------
        else:
            is_word = ext in WORD_EXTENSIONS
            is_txt = ext in TEXT_EXTENSIONS
            text = extract_document_text(pdf_path, max_pages=max_pages)
            has_text = bool(text and len(text.strip()) >= 15)
            tess_text = ""

            if not has_text or force_ocr:
                if skip_ocr:
                    res_dict["status"] = "erro"
                    res_dict["erro"] = "Documento sem texto legível digitalmente (requer OCR, mas --skip-ocr está ativo)."
                    return res_dict

                # 1. OCR complementar rápido (Tesseract em imagens embutidas e páginas)
                # Para Word, converte para PDF espelho primeiro
                target_pdf_path = convert_office_to_pdf(pdf_path) if is_word else pdf_path

                if target_pdf_path and target_pdf_path.exists():
                    tess_text = extract_tesseract_text_from_pdf(target_pdf_path, max_pages=max_pages)
                    images = render_pdf_pages_to_base64(str(target_pdf_path), max_pages=min(max_pages, 4))
                else:
                    images = []

                combined_text = f"{text}\n\n{tess_text}".strip() if (text and tess_text) else (tess_text or text)

                if not images and not combined_text:
                    res_dict["status"] = "erro"
                    res_dict["erro"] = "Documento sem texto legível digitalmente e falha ao renderizar páginas para OCR."
                    return res_dict

                try:
                    extra_ctx = combined_text if combined_text else None
                    vision_prompt = build_universal_vision_prompt(extra_context=extra_ctx)
                    if images:
                        extracted_data = client.generate_json_with_images(vision_prompt, images)
                    else:
                        prompt = build_universal_prompt(combined_text)
                        extracted_data = client.generate_json(prompt)
                    res_dict["metodo_leitura"] = "ocr_llm" if not has_text else ("office_ocr_llm" if is_word else "hibrido_texto_e_ocr_llm")
                    res_dict["tentativa_ocr_llm"] = True
                except Exception as e:
                    if combined_text:
                        try:
                            print(f"[*] Chamada de visão falhou ({e}). Fazendo fallback para texto OCR Tesseract...")
                            prompt = build_universal_prompt(combined_text)
                            extracted_data = client.generate_json(prompt)
                            res_dict["metodo_leitura"] = "ocr_tesseract_llm"
                            res_dict["tentativa_ocr_llm"] = True
                        except Exception as e2:
                            res_dict["status"] = "erro"
                            res_dict["erro"] = f"Falha no OCR via LLM ({e}) e na leitura textual ({e2})"
                            res_dict["tentativa_ocr_llm"] = True
                            extracted_data = {}
                    else:
                        res_dict["status"] = "erro"
                        res_dict["erro"] = f"Falha no OCR via LLM: {e}"
                        res_dict["tentativa_ocr_llm"] = True
                        return res_dict
            else:
                # Leitura normal da camada de texto digital via LLM
                prompt = build_universal_prompt(text)
                try:
                    extracted_data = client.generate_json(prompt)
                except Exception as e_llm:
                    print(f"[*] Chamada LLM falhou ({e_llm}). Prosseguindo com extração por regras e heurísticas...")
                    extracted_data = {}
                res_dict["metodo_leitura"] = "texto_office" if is_word else ("texto_puro" if is_txt else "texto_digital")

        # Preenchimento e sanitização dos campos gerais
        res_dict["data"] = _clean_str(extracted_data.get("data"))
        res_dict["beneficiario"] = _clean_str(extracted_data.get("beneficiario"))
        dominio_raw = _clean_str(extracted_data.get("dominio"))
        tipo_doc_raw = _clean_str(extracted_data.get("tipo_documento"))
        valor_raw = _clean_str(extracted_data.get("valor_monetario"))
        tipo_lower = str(tipo_doc_raw or "").lower()

        is_academic_doc = any(k in tipo_lower for k in [
            "diploma", "certificado", "histórico", "historico", "declaração", "declaracao",
            "ementa", "dissertação", "dissertacao", "tese", "graduação", "graduacao",
            "pós-graduação", "pos-graduacao", "especialização", "especializacao"
        ]) or (dominio_raw == "academico")

        is_actual_cadastral_doc = any(k in tipo_lower for k in [
            "situação cadastral", "situacao cadastral", "cartão cnpj", "cartao cnpj", "cartão do cnpj", "cartao do cnpj",
            "cadastro nacional da pessoa"
        ]) or (dominio_raw == "profissional" and ("cnpj" in tipo_lower or "cadastral" in tipo_lower))

        # Tratamento e fallback para CPF
        cpf_val = extracted_data.get("cpf")
        formatted_cpf = format_cpf(cpf_val)
        if not formatted_cpf or not is_valid_cpf_syntax(formatted_cpf):
            if has_text:
                formatted_cpf = extract_cpf_fallback(text)
            if (not formatted_cpf or not is_valid_cpf_syntax(formatted_cpf)):
                if not tess_text and not is_image:
                    try:
                        tess_text = extract_tesseract_text_from_pdf(pdf_path, max_pages=max_pages)
                    except Exception:
                        pass
                if tess_text:
                    formatted_cpf = extract_cpf_fallback(tess_text)
        res_dict["cpf"] = formatted_cpf

        # Tratamento e fallback para RG / Identidade
        rg_val = _clean_str(extracted_data.get("rg"))
        if not rg_val:
            if has_text:
                rg_val = extract_rg_fallback(text)
            if not rg_val:
                if not tess_text and not is_image:
                    try:
                        tess_text = extract_tesseract_text_from_pdf(pdf_path, max_pages=max_pages)
                    except Exception:
                        pass
                if tess_text:
                    rg_val = extract_rg_fallback(tess_text)
        res_dict["rg"] = rg_val

        # Tratamento e fallback para CNPJ
        cnpj_val = extracted_data.get("cnpj") or (extracted_data.get("pix_pagador_cpf_cnpj") if (extracted_data.get("pix_pagador_cpf_cnpj") and "/" in str(extracted_data.get("pix_pagador_cpf_cnpj"))) else None)
        formatted_cnpj = format_cnpj(cnpj_val)
        if not formatted_cnpj or not is_valid_cnpj_syntax(formatted_cnpj):
            if has_text:
                formatted_cnpj = extract_cnpj_fallback(text)
            if not formatted_cnpj or not is_valid_cnpj_syntax(formatted_cnpj):
                if not tess_text and not is_image:
                    try:
                        tess_text = extract_tesseract_text_from_pdf(pdf_path, max_pages=max_pages)
                    except Exception:
                        pass
                if tess_text:
                    formatted_cnpj = extract_cnpj_fallback(tess_text)
        res_dict["cnpj"] = formatted_cnpj
        if formatted_cnpj and not res_dict.get("cpf") and is_actual_cadastral_doc:
            res_dict["cpf"] = formatted_cnpj

        # Extração de campos cadastrais (Cartão CNPJ / Receita Federal)
        cadastral_fallback = {}
        if has_text:
            cadastral_fallback = extract_cnpj_cadastral_fallback(text)
        elif tess_text:
            cadastral_fallback = extract_cnpj_cadastral_fallback(tess_text)

        cnpj_fields = {
            "razao_social": _clean_str(extracted_data.get("razao_social")) or cadastral_fallback.get("razao_social"),
            "nome_fantasia": _clean_str(extracted_data.get("nome_fantasia")) or cadastral_fallback.get("nome_fantasia"),
            "situacao_cadastral": _clean_str(extracted_data.get("situacao_cadastral")) or cadastral_fallback.get("situacao_cadastral"),
            "data_situacao": _clean_str(extracted_data.get("data_situacao")) or cadastral_fallback.get("data_situacao"),
            "data_abertura": _clean_str(extracted_data.get("data_abertura")) or cadastral_fallback.get("data_abertura"),
            "cnae_principal": _clean_str(extracted_data.get("cnae_principal")) or cadastral_fallback.get("cnae_principal"),
            "natureza_juridica": _clean_str(extracted_data.get("natureza_juridica")) or cadastral_fallback.get("natureza_juridica"),
            "endereco_completo": _clean_str(extracted_data.get("endereco_completo")) or cadastral_fallback.get("endereco_completo"),
            "telefone": _clean_str(extracted_data.get("telefone")) or cadastral_fallback.get("telefone"),
            "email": _clean_str(extracted_data.get("email")) or cadastral_fallback.get("email"),
        }

        # Se houver dados de CNPJ ou dados cadastrais/endereço, consolida em dados_extras
        if formatted_cnpj or any(cnpj_fields.values()):
            if "dados_extras" not in res_dict or not isinstance(res_dict["dados_extras"], dict):
                res_dict["dados_extras"] = {}
            if formatted_cnpj:
                res_dict["dados_extras"]["cnpj"] = formatted_cnpj
                if is_academic_doc:
                    res_dict["dados_extras"]["cnpj_instituicao"] = formatted_cnpj
            for k_field, v_field in cnpj_fields.items():
                if v_field:
                    res_dict["dados_extras"][k_field] = v_field
                    res_dict[k_field] = v_field

            # Preenchimento inteligente de beneficiário com razão social se vazio (apenas para documentos empresariais/cadastrais)
            if not res_dict.get("beneficiario") and not is_academic_doc:
                if cnpj_fields.get("razao_social"):
                    res_dict["beneficiario"] = cnpj_fields["razao_social"]
                elif cnpj_fields.get("nome_fantasia"):
                    res_dict["beneficiario"] = cnpj_fields["nome_fantasia"]

            # Emissor Receita Federal se não informado (estritamente se for documento cadastral da RFB)
            if not res_dict.get("faculdade") and is_actual_cadastral_doc:
                res_dict["faculdade"] = "Receita Federal do Brasil (RFB)"

            # Data da situação cadastral ou abertura se data vazia
            if not res_dict.get("data") and is_actual_cadastral_doc:
                if cnpj_fields.get("data_situacao"):
                    res_dict["data"] = cnpj_fields["data_situacao"]
                elif cnpj_fields.get("data_abertura"):
                    res_dict["data"] = cnpj_fields["data_abertura"]

        # Campos acadêmicos
        raw_curso = _clean_str(extracted_data.get("curso"))
        if not raw_curso or any(k in raw_curso.lower() for k in ["faculdade", "universidade", "instituto", "colegio", "escola"]):
            c_fallback = (extract_course_fallback(text) if has_text else None) or (extract_course_fallback(tess_text) if tess_text else None)
            if not c_fallback and not tess_text and not is_image:
                try:
                    tess_text = extract_tesseract_text_from_pdf(pdf_path, max_pages=max_pages)
                except Exception:
                    pass
                if tess_text:
                    c_fallback = extract_course_fallback(tess_text)
            if c_fallback:
                raw_curso = c_fallback
            elif any(k in str(raw_curso).lower() for k in ["faculdade", "universidade", "instituto", "colegio", "escola"]):
                raw_curso = None
        res_dict["curso"] = raw_curso
        res_dict["natureza_curso"] = _clean_str(extracted_data.get("natureza_curso"))
        res_dict["carga_horaria"] = _clean_str(extracted_data.get("carga_horaria"))
        res_dict["faculdade"] = normalizar_instituicao(_clean_str(extracted_data.get("faculdade")))

        # Classificação e campos financeiros / PIX
        dominio_raw = _clean_str(extracted_data.get("dominio"))
        tipo_doc_raw = _clean_str(extracted_data.get("tipo_documento"))
        valor_raw = _clean_str(extracted_data.get("valor_monetario"))

        pix_pagador_nome = _clean_str(extracted_data.get("pix_pagador_nome"))
        pix_pagador_cpf_cnpj = _clean_str(extracted_data.get("pix_pagador_cpf_cnpj"))
        pix_pagador_banco = _clean_str(extracted_data.get("pix_pagador_banco"))
        pix_recebedor_banco = _clean_str(extracted_data.get("pix_recebedor_banco"))
        pix_chave = _clean_str(extracted_data.get("pix_chave"))
        pix_e2e_id = _clean_str(extracted_data.get("pix_e2e_id"))
        pix_autenticacao = _clean_str(extracted_data.get("pix_autenticacao"))

        # Fallbacks regex para comprovantes quando houver texto disponível
        if has_text:
            if not valor_raw:
                valor_raw = extract_monetary_value(text)
            if not pix_e2e_id:
                pix_e2e_id = extract_pix_e2e_id(text)
            if not pix_chave:
                pix_chave = extract_pix_chave(text)
            if not pix_autenticacao:
                pix_autenticacao = extract_pix_authentication(text)

        # Heurística inteligente para consolidação do domínio
        tipo_lower = str(tipo_doc_raw or "").lower()
        is_non_financial_comprovante = any(k in tipo_lower for k in [
            "inscrição", "inscricao", "situação cadastral", "situacao cadastral", "cnpj",
            "residência", "residencia", "matrícula", "matricula", "rendimentos", "votação", "votacao"
        ])

        has_explicit_financial = bool(
            "pix" in tipo_lower or
            "comprovante de pagamento" in tipo_lower or
            "comprovante de transferência" in tipo_lower or
            "comprovante de transferencia" in tipo_lower or
            "comprovante bancário" in tipo_lower or
            "comprovante bancario" in tipo_lower or
            "recibo de pagamento" in tipo_lower or
            "boleto" in tipo_lower or
            ("recibo" in tipo_lower and not is_non_financial_comprovante)
        )

        has_pix_signal = bool(
            (pix_e2e_id or pix_chave or (pix_pagador_nome and pix_pagador_banco) or has_explicit_financial)
            and not is_non_financial_comprovante
        )

        if not is_non_financial_comprovante and (has_pix_signal or valor_raw or dominio_raw == "financeiro"):
            dominio = "financeiro"
            if not tipo_doc_raw or tipo_lower in ["não identificado", "nao identificado", "outro", "não informado", "nao informado"]:
                tipo_doc_raw = "Comprovante PIX" if ("pix" in tipo_lower or pix_e2e_id or pix_chave) else "Recibo de Pagamento"
            if not res_dict.get("faculdade") and pix_pagador_banco:
                res_dict["faculdade"] = pix_pagador_banco
        elif is_academic_doc:
            dominio = "academico"
        elif is_actual_cadastral_doc or any(k in tipo_lower for k in ["currículo", "curriculo", "experiência profissional", "experiencia profissional", "lattes", "ctps", "carteira de trabalho"]):
            dominio = "profissional"
            if not tipo_doc_raw or tipo_lower in ["não identificado", "nao identificado", "outro", "não informado", "nao informado"]:
                tipo_doc_raw = "Cartão CNPJ / Situação Cadastral"
        elif any(k in tipo_lower for k in ["rg", "cnh", "identidade", "cpf", "certidão", "certidao", "eleitor", "passaporte"]):
            dominio = "identificacao"
        elif any(k in tipo_lower for k in ["contrato", "procuração", "procuracao", "posse", "juridico", "petição", "peticao"]):
            dominio = "juridico"
        elif dominio_raw in ["academico", "financeiro", "identificacao", "juridico", "profissional", "outro"]:
            dominio = dominio_raw
        else:
            dominio = "academico"

        res_dict["dominio"] = dominio
        res_dict["tipo_documento"] = tipo_doc_raw
        res_dict["valor_monetario"] = valor_raw

        # Atribuição de campos específicos de PIX
        if pix_pagador_nome: res_dict["pix_pagador_nome"] = pix_pagador_nome
        if pix_pagador_cpf_cnpj: res_dict["pix_pagador_cpf_cnpj"] = pix_pagador_cpf_cnpj
        if pix_pagador_banco: res_dict["pix_pagador_banco"] = pix_pagador_banco
        if pix_recebedor_banco: res_dict["pix_recebedor_banco"] = pix_recebedor_banco
        if pix_chave: res_dict["pix_chave"] = pix_chave
        if pix_e2e_id: res_dict["pix_e2e_id"] = pix_e2e_id
        if pix_autenticacao: res_dict["pix_autenticacao"] = pix_autenticacao

        # ---------------------------------------------------------------------
        # CASO 2 (Somente PDF com texto digital): Se dados essenciais falharam,
        # faz tentativa de OCR local rápido (Tesseract) e/ou multimodal via LLM
        # ---------------------------------------------------------------------
        if not is_image and has_text and dominio != "financeiro" and not res_dict.get("tentativa_ocr_llm") and not skip_ocr:
            tipo_atual = (res_dict.get("tipo_documento") or "").strip().lower()
            is_tipo_unidentified = (not tipo_atual) or tipo_atual in [
                "não identificado", "nao identificado", "outro", "não informado", "nao informado"
            ]
            cpf_atual = res_dict.get("cpf")
            is_cpf_flawed = bool(not cpf_atual or not is_valid_cpf_syntax(cpf_atual))
            is_dados_principais_missing = (not res_dict.get("beneficiario")) and (not res_dict.get("curso"))

            if is_tipo_unidentified or is_cpf_flawed or is_dados_principais_missing:
                # 1. Tenta resgatar dados críticos via Tesseract local rápido
                if not tess_text:
                    tess_text = extract_tesseract_text_from_pdf(pdf_path, max_pages=max_pages)

                if tess_text:
                    if is_cpf_flawed:
                        cand_cpf = extract_cpf_fallback(tess_text)
                        if cand_cpf and is_valid_cpf_syntax(cand_cpf):
                            res_dict["cpf"] = cand_cpf
                            is_cpf_flawed = False
                    if not res_dict.get("rg"):
                        cand_rg = extract_rg_fallback(tess_text)
                        if cand_rg:
                            res_dict["rg"] = cand_rg

                # 2. Se o documento ainda estiver sem tipo ou sem dados principais, escala para OCR Multimodal
                if is_tipo_unidentified or is_dados_principais_missing:
                    res_dict["tentativa_ocr_llm"] = True
                    try:
                        images = render_pdf_pages_to_base64(str(pdf_path), max_pages=min(max_pages, 4))
                        if images:
                            context_msg = f"{text}\n\nTexto OCR complementar:\n{tess_text}\n\nAtenção: O tipo de documento ou titular não puderam ser plenamente identificados no texto. Verifique visualmente."
                            vision_prompt = build_universal_vision_prompt(extra_context=context_msg)
                            ocr_data = client.generate_json_with_images(vision_prompt, images)

                            if is_tipo_unidentified:
                                new_tipo = _clean_str(ocr_data.get("tipo_documento"))
                                if new_tipo and new_tipo.lower() not in ["não identificado", "nao identificado", "outro"]:
                                    res_dict["tipo_documento"] = new_tipo
                                    res_dict["metodo_leitura"] = "hibrido_texto_e_ocr_llm"

                            new_cpf_raw = ocr_data.get("cpf")
                            if new_cpf_raw:
                                formatted_new_cpf = format_cpf(new_cpf_raw)
                                if formatted_new_cpf and is_valid_cpf_syntax(formatted_new_cpf):
                                    res_dict["cpf"] = formatted_new_cpf
                                    res_dict["metodo_leitura"] = "hibrido_texto_e_ocr_llm"

                            if not res_dict["beneficiario"] and ocr_data.get("beneficiario"):
                                res_dict["beneficiario"] = _clean_str(ocr_data.get("beneficiario"))
                            if not res_dict["rg"] and ocr_data.get("rg"):
                                res_dict["rg"] = _clean_str(ocr_data.get("rg"))
                            if not res_dict["curso"] or any(k in str(res_dict["curso"]).lower() for k in ["faculdade", "universidade", "instituto", "colegio"]):
                                if ocr_data.get("curso") and not any(k in str(ocr_data.get("curso")).lower() for k in ["faculdade", "universidade", "instituto", "colegio"]):
                                    res_dict["curso"] = _clean_str(ocr_data.get("curso"))
                                else:
                                    cf = (extract_course_fallback(text) if has_text else None) or (extract_course_fallback(tess_text) if tess_text else None)
                                    if cf:
                                        res_dict["curso"] = cf
                            if not res_dict["natureza_curso"] and ocr_data.get("natureza_curso"):
                                res_dict["natureza_curso"] = _clean_str(ocr_data.get("natureza_curso"))
                            if not res_dict["carga_horaria"] and ocr_data.get("carga_horaria"):
                                res_dict["carga_horaria"] = _clean_str(ocr_data.get("carga_horaria"))
                            if not res_dict["faculdade"] and ocr_data.get("faculdade"):
                                res_dict["faculdade"] = normalizar_instituicao(_clean_str(ocr_data.get("faculdade")))
                            if not res_dict["data"] and ocr_data.get("data"):
                                res_dict["data"] = _clean_str(ocr_data.get("data"))
                    except Exception:
                        pass

        # 3. Rede de segurança final para CPF, RG e Curso caso ainda estejam vazios e haja texto do Tesseract
        if (not res_dict.get("cpf") or not is_valid_cpf_syntax(res_dict.get("cpf"))) and tess_text:
            cand_cpf = extract_cpf_fallback(tess_text)
            if cand_cpf and is_valid_cpf_syntax(cand_cpf):
                res_dict["cpf"] = cand_cpf
        if not res_dict.get("rg") and tess_text:
            cand_rg = extract_rg_fallback(tess_text)
            if cand_rg:
                res_dict["rg"] = cand_rg
        if not res_dict.get("curso") or any(k in str(res_dict.get("curso")).lower() for k in ["faculdade", "universidade", "instituto", "colegio"]):
            cf = (extract_course_fallback(text) if has_text else None) or (extract_course_fallback(tess_text) if tess_text else None)
            if cf:
                res_dict["curso"] = cf

        # 4. Integração do Dossiê Multi-Páginas e Hierarquia Anti-Contaminação
        if not is_image:
            try:
                dossier = analyze_pdf_dossier(pdf_path, max_ocr_pages=min(max_pages, 10))
                todos_tipos = list(dossier.get("todos_tipos", []))
                todos_dominios = list(dossier.get("todos_dominios", []))

                prim_tipo = res_dict.get("tipo_documento")
                prim_dom = res_dict.get("dominio")

                # Se o classificador ou LLM definiu um tipo primário, assegura presença em todos_tipos
                if prim_tipo and prim_tipo not in todos_tipos:
                    todos_tipos.insert(0, prim_tipo)
                if prim_dom and prim_dom not in todos_dominios:
                    todos_dominios.insert(0, prim_dom)

                # Se o LLM não identificou o tipo principal, assume a primazia do dossiê
                if (not res_dict.get("tipo_documento") or res_dict.get("tipo_documento") in ["Outro", "não identificado", "nao identificado"]) and dossier.get("tipo_documento_principal"):
                    res_dict["tipo_documento"] = dossier["tipo_documento_principal"]
                    if not res_dict.get("dominio") or res_dict.get("dominio") == "outros":
                        res_dict["dominio"] = dossier.get("dominio_principal", "academico")

                # Resgate prioritário de CPF do titular (CNH / CPF / RG têm prioridade máxima sobre comprovantes PIX)
                if (not res_dict.get("cpf") or not is_valid_cpf_syntax(res_dict.get("cpf"))) and dossier.get("cpf_titular"):
                    res_dict["cpf"] = dossier["cpf_titular"]

                # Resgate de RG do titular
                if not res_dict.get("rg") and dossier.get("rg_titular"):
                    res_dict["rg"] = dossier["rg_titular"]

                # Resgate de CNPJ do titular
                if not res_dict.get("cnpj") and dossier.get("cnpj_titular"):
                    res_dict["cnpj"] = dossier["cnpj_titular"]

                # Resgate do curso (estritamente de páginas acadêmicas)
                if (not res_dict.get("curso") or any(k in str(res_dict.get("curso")).lower() for k in ["faculdade", "universidade", "instituto", "colegio"])) and dossier.get("curso_titular"):
                    res_dict["curso"] = dossier["curso_titular"]

                res_dict["todos_tipos"] = todos_tipos if todos_tipos else ([prim_tipo] if prim_tipo else [])
                res_dict["todos_dominios"] = todos_dominios if todos_dominios else ([prim_dom] if prim_dom else [])
                res_dict["dossie_paginas"] = dossier.get("dossie_paginas", [])
            except Exception:
                prim_tipo = res_dict.get("tipo_documento")
                prim_dom = res_dict.get("dominio")
                res_dict["todos_tipos"] = [prim_tipo] if prim_tipo else []
                res_dict["todos_dominios"] = [prim_dom] if prim_dom else []
                res_dict["dossie_paginas"] = []
        else:
            prim_tipo = res_dict.get("tipo_documento")
            prim_dom = res_dict.get("dominio")
            res_dict["todos_tipos"] = [prim_tipo] if prim_tipo else []
            res_dict["todos_dominios"] = [prim_dom] if prim_dom else []
            res_dict["dossie_paginas"] = [{"pagina": 1, "tipo": prim_tipo or "Documento", "dominio": prim_dom or "outros"}]

        # Validação de sucesso adaptativa para múltiplos domínios
        campos_uteis = [
            res_dict.get("beneficiario"),
            res_dict.get("curso"),
            res_dict.get("cpf"),
            res_dict.get("rg"),
            res_dict.get("cnpj"),
            res_dict.get("faculdade"),
            res_dict.get("tipo_documento"),
            res_dict.get("valor_monetario"),
            res_dict.get("pix_pagador_nome"),
            res_dict.get("pix_e2e_id")
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


process_single_document = process_single_pdf



# ---------------------------------------------------------------------------
# Formatação de Saídas (JSON e TXT)
# ---------------------------------------------------------------------------
def format_single_txt(item: Dict[str, Any]) -> str:
    metodo = item.get("metodo_leitura", "texto_digital")
    if item.get("tentativa_ocr_llm") and "ocr" not in metodo.lower():
        metodo += " (OCR LLM acionado)"

    dom = item.get("dominio") or "academico"
    ext = item.get("extensao") or ""
    todos_tipos = item.get("todos_tipos") or []
    dossie_line = f"\nDocumentos no Arquivo  : {', '.join(str(t) for t in todos_tipos)}" if (isinstance(todos_tipos, list) and len(todos_tipos) > 1) else ""
    de = item.get("dados_extras") if isinstance(item.get("dados_extras"), dict) else {}

    dc_extra = ""
    if item.get('dc_title'):
        dc_extra += f"dc:title                : {item.get('dc_title')}\n"
    if item.get('dc_creator_tool'):
        dc_extra += f"dc:tool                 : {item.get('dc_creator_tool')}\n"

    txt = f"""--------------------------------------------------------------------------------
MD5                     : {item.get('md5')}
Status                  : {item.get('status', '').upper()}
Domínio                 : {dom.upper()}
Tipo Documento          : {item.get('tipo_documento') or 'Não identificado'}{dossie_line}
Extensão                : {ext.upper() if ext else 'N/A'}
Método de Leitura       : {metodo}
Data da Última Alteração: {item.get('data_modificacao')}
dc:creator              : {item.get('autor') or 'Não informado'}
{dc_extra}Beneficiário / Titular  : {item.get('beneficiario') or 'Não informado'}
CPF                     : {item.get('cpf') or 'Não informado'}
RG / Identidade         : {item.get('rg') or 'Não informado'}
CNPJ                    : {item.get('cnpj') or 'Não informado'}
"""
    if dom == "financeiro" or item.get("valor_monetario") or item.get("pix_pagador_nome"):
        txt += f"""Valor Monetário         : {item.get('valor_monetario') or 'Não informado'}
Data da Transação       : {item.get('data') or 'Não informada'}
Instituição / Banco     : {item.get('faculdade') or 'Não informada'}
Pagador                 : {item.get('pix_pagador_nome') or 'Não informado'}
CPF/CNPJ do Pagador     : {item.get('pix_pagador_cpf_cnpj') or 'Não informado'}
Banco Origem (Pagador)  : {item.get('pix_pagador_banco') or 'Não informado'}
Banco Destino (Receb.)  : {item.get('pix_recebedor_banco') or 'Não informado'}
Chave PIX               : {item.get('pix_chave') or 'Não informada'}
ID Fim-a-Fim (E2E)      : {item.get('pix_e2e_id') or 'Não informado'}
Autenticação Bancária   : {item.get('pix_autenticacao') or 'Não informada'}
"""
    elif dom == "profissional" or item.get("cnpj") or de.get("situacao_cadastral"):
        txt += f"""Razão Social            : {item.get('beneficiario') or de.get('razao_social') or 'Não informada'}
Nome Fantasia           : {de.get('nome_fantasia') or 'Não informado'}
CNPJ                    : {item.get('cnpj') or 'Não informado'}
Situação Cadastral      : {de.get('situacao_cadastral') or 'Não informada'}
Data da Situação        : {de.get('data_situacao') or 'Não informada'}
Data de Abertura        : {de.get('data_abertura') or 'Não informada'}
CNAE Principal          : {de.get('cnae_principal') or 'Não informado'}
Natureza Jurídica       : {de.get('natureza_juridica') or 'Não informada'}
Endereço Completo       : {de.get('endereco_completo') or 'Não informado'}
Telefone                : {de.get('telefone') or 'Não informado'}
E-mail                  : {de.get('email') or 'Não informado'}
Instituição Emissora    : {item.get('faculdade') or 'Receita Federal do Brasil (RFB)'}
Data do Documento       : {item.get('data') or 'Não informada'}
"""
    else:
        txt += f"""Curso                   : {item.get('curso') or 'Não informado'}
Natureza do Curso       : {item.get('natureza_curso') or 'Não identificada'}
Carga Horária           : {item.get('carga_horaria') or 'Não informada'}
Faculdade / Instituição : {item.get('faculdade') or 'Não informada'}
Data do Documento       : {item.get('data') or 'Não informada'}
"""

    txt += f"""Processado em           : {item.get('processado_em')}
{f"Erro                    : {item.get('erro')}" if item.get('erro') else ""}--------------------------------------------------------------------------------
"""
    return txt


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
        "JOAKINDEX - RELATÓRIO CONSOLIDADO DE CLASSIFICAÇÃO",
        "Criado por: Joaquim Ferreira Silva Neto <joaquimfsneto@gmail.com>",
        f"Data/Hora de Geração : {now_str}",
        f"Provedor LLM         : {provider_name.upper()} (Modelo: {model_name})",
        f"Total de Documentos  : {total}",
        f"Classificados com OK : {sucesso}",
        f"Falhas / Erros       : {erros}",
        "=" * 80,
        ""
    ]

    for idx, item in enumerate(results, 1):
        dom = item.get("dominio") or "academico"
        lines.append(f"[{idx}/{total}] MD5: {item.get('md5')}")
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
        if item.get("erro"):
            lines.append(f"  • Detalhe do Erro         : {item.get('erro')}")
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
    Salva os relatórios consolidado SQLite, JSON e TXT de forma atômica para evitar perda ou
    corrupção de dados em caso de parada forçada (Ctrl+C, kill ou reinicialização).
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    consolidated_json_path = out_dir / "joakindex.json"
    consolidated_txt_path = out_dir / "joakindex.txt"
    consolidated_db_path = get_db_path(out_dir)
    results = sorted(list(items_dict.values()), key=lambda x: str(x.get("md5", "")))
    for r in results:
        if isinstance(r, dict):
            r.pop("data_criacao", None)

    # 1. Banco SQLite relacional (WAL mode e ACID)
    try:
        init_database(consolidated_db_path)
        upsert_documents_batch(consolidated_db_path, results)
    except Exception as e:
        print(f"[Aviso] Falha ao gravar SQLite {consolidated_db_path.name}: {e}")

    # 2. JSON consolidado atômico
    tmp_json = out_dir / f".tmp_{consolidated_json_path.name}"
    try:
        with open(tmp_json, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        tmp_json.replace(consolidated_json_path)
    except Exception as e:
        print(f"[Aviso] Falha ao gravar {consolidated_json_path.name}: {e}")

    # 3. TXT consolidado atômico
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
    if not specified:
        return "./pdf"
    clean = clean_path_string(specified)
    if clean in ["./pdf", "pdf", ""]:
        return "./pdf"
    p = Path(clean).expanduser()
    return str(p.resolve())


def count_pdfs_in_path(p: Path) -> int:
    if not p.exists():
        return 0
    if p.is_file():
        return 1 if p.suffix.lower() in SUPPORTED_EXTENSIONS else 0
    cnt = 0
    for ext in SUPPORTED_EXTENSIONS:
        cnt += len(list(p.glob(f"*{ext}"))) + len(list(p.glob(f"*{ext.upper()}")))
    return cnt


count_documents_in_path = count_pdfs_in_path


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
    print("🎓 JoaKinDeX - MENU INTERATIVO DE CLASSIFICAÇÃO")
    print("   Criado por: Joaquim Ferreira Silva Neto <joaquimfsneto@gmail.com>")
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

        clean_input = clean_path_string(resp_input)
        if clean_input.lower() in ["reset", "resetar", "padrao", "fábrica", "fabrica"]:
            reset_classifier_config()
            factory = get_factory_defaults()["classificador"]
            for k, v in factory.items():
                setattr(args, k, v)
            default_input = resolve_default_input_path(args.input)
            print("   [✓] Configurações restauradas para os padrões de fábrica neutros!")
            continue

        raw_chosen = clean_input if clean_input else default_input
        chosen_path = Path(raw_chosen).expanduser().resolve()
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
    default_out = resolve_classifier_output_dir(args.output_dir or "./saida")
    while True:
        try:
            resp_out = input(f"\n📄 Pasta de saída dos relatórios [{default_out}]: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n[Operação cancelada pelo usuário]")
            sys.exit(0)

        clean_out = clean_path_string(resp_out)
        if clean_out.lower() in ["reset", "resetar", "padrao", "fábrica", "fabrica"]:
            factory = get_factory_defaults()["classificador"]
            default_out = resolve_classifier_output_dir(factory.get("output_dir", "./saida"))
            print("   [✓] Pasta de saída restaurada para o padrão de fábrica neutro!")
            continue

        raw_out = clean_out if clean_out else default_out
        args.output_dir = resolve_classifier_output_dir(raw_out)
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

    in_clean = clean_path_string(input_path) if input_path else "./pdf"
    in_p = Path(in_clean).expanduser().resolve()
    if not in_p.exists():
        err_msg = f"Caminho de entrada não encontrado: {in_p}"
        print(f"[ERRO] {err_msg}")
        notify({"event": "error", "error": err_msg})
        return {"status": "erro", "mensagem": err_msg, "total": 0, "results": []}

    pdf_files = []
    if in_p.is_file():
        if in_p.suffix.lower() in SUPPORTED_EXTENSIONS:
            pdf_files.append(in_p)
        else:
            err_msg = f"O arquivo indicado não possui formato suportado (PDF, PNG, JPG, JPEG, WEBP): {in_p}"
            print(f"[ERRO] {err_msg}")
            notify({"event": "error", "error": err_msg})
            return {"status": "erro", "mensagem": err_msg, "total": 0, "results": []}
    else:
        found_set = set()
        for ext in SUPPORTED_EXTENSIONS:
            found_set |= set(in_p.glob(f"*{ext}")) | set(in_p.glob(f"*{ext.upper()}"))
        if not found_set:
            for ext in SUPPORTED_EXTENSIONS:
                found_set |= set(in_p.rglob(f"*{ext}")) | set(in_p.rglob(f"*{ext.upper()}"))
        pdf_files = sorted(list(found_set))

    if not pdf_files:
        msg = f"Nenhum documento suportado (PDF/Imagem) encontrado em: {in_p}"
        print(f"[AVISO] {msg}")
        notify({"event": "warning", "message": msg})
        return {"status": "aviso", "mensagem": msg, "total": 0, "results": []}

    print(f"[*] Total de documentos identificados: {len(pdf_files)}")
    notify({"event": "init", "total_files": len(pdf_files), "message": f"{len(pdf_files)} documentos identificados."})

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

    out_dir = Path(resolve_classifier_output_dir(output_dir)).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    indiv_dir = out_dir / "individuais"
    if not no_individual:
        indiv_dir.mkdir(parents=True, exist_ok=True)

    consolidated_json_path = get_json_path(out_dir)
    consolidated_txt_path = out_dir / "joakindex.txt"
    if not consolidated_txt_path.exists() and (out_dir / "classificacao_diplomas.txt").exists():
        consolidated_txt_path = out_dir / "classificacao_diplomas.txt"
    consolidated_db_path = get_db_path(out_dir)
    existing_by_md5 = {}

    # Inicializa banco SQLite (auto-migra do JSON consolidado caso o banco esteja vazio)
    init_database(consolidated_db_path, initial_json_path=consolidated_json_path)

    # 1. Carrega processamentos anteriores prioritariamente do SQLite
    count_from_db = 0
    count_from_consolidated = 0
    if not force:
        try:
            db_docs = get_all_documents(consolidated_db_path)
            if db_docs:
                for item in db_docs:
                    if isinstance(item, dict) and "md5" in item:
                        item.pop("data_criacao", None)
                        existing_by_md5[item["md5"]] = item
                        count_from_db += 1
            elif consolidated_json_path.exists():
                with open(consolidated_json_path, "r", encoding="utf-8") as f:
                    old_data = json.load(f)
                    if isinstance(old_data, list):
                        for item in old_data:
                            if isinstance(item, dict) and "md5" in item:
                                item.pop("data_criacao", None)
                                existing_by_md5[item["md5"]] = item
                                count_from_consolidated += 1
                        if old_data:
                            upsert_documents_batch(consolidated_db_path, old_data)
        except Exception as e:
            print(f"[Aviso] Não foi possível ler histórico do banco de dados: {e}")

    # 2. Carrega / reconcilia arquivos da pasta 'individuais'
    count_from_indiv = 0
    indiv_recovered = []
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
                                    item.pop("data_criacao", None)
                                    existing_by_md5[item["md5"]] = item
                                    indiv_recovered.append(item)
                                    count_from_indiv += 1
                        except Exception:
                            continue
        except Exception as e:
            print(f"[Aviso] Erro ao ler pasta de arquivos individuais: {e}")

        if indiv_recovered:
            try:
                upsert_documents_batch(consolidated_db_path, indiv_recovered)
            except Exception:
                pass

    effective_model_name = getattr(client, "model", model_name)

    if existing_by_md5:
        details = []
        if count_from_db > 0:
            details.append(f"{count_from_db} do banco SQLite")
        elif count_from_consolidated > 0:
            details.append(f"{count_from_consolidated} do JSON consolidado")
        if count_from_indiv > 0:
            details.append(f"{count_from_indiv} recuperados da pasta individuais/")
        det_str = f" ({', '.join(details)})" if details else ""
        print(f"[*] Histórico carregado: {len(existing_by_md5)} documento(s) já classificados{det_str}.")

        if count_from_indiv > 0:
            save_consolidated_reports(existing_by_md5, out_dir, provider, effective_model_name)
            print(f"[*] Relatórios sincronizados com sucesso ({len(existing_by_md5)} documentos salvos).")

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
                    pdf_meta_map[p] = {"md5": "", "data_modificacao": "", "autor": None}
                if idx_i % 25 == 0:
                    notify({"event": "indexing_progress", "indexed": idx_i, "total": len(pdf_files)})
    else:
        for p in pdf_files:
            try:
                pdf_meta_map[p] = get_file_metadata(p)
            except Exception:
                pdf_meta_map[p] = {"md5": "", "data_modificacao": "", "autor": None}

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

            res.pop("data_criacao", None)
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

            # Persiste imediatamente no SQLite para garantia ACID e tolerância a falhas
            try:
                upsert_document(consolidated_db_path, res)
            except Exception as e_up:
                print(f"[Aviso] Falha ao persistir no SQLite ({res.get('md5')}): {e_up}")

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
            "db_path": str(consolidated_db_path),
            "txt_path": str(consolidated_txt_path),
            "mensagem": "Processamento interrompido pelo usuário."
        }

    print("\n" + "=" * 60)
    print("PROCESSAMENTO CONCLUÍDO COM SUCESSO!")
    print(f"Total processados : {len(results)}")
    print(f"Classificados OK  : {sucessos_totais}")
    print(f"Erros             : {erros_totais}")
    print("-" * 60)
    print(f"Banco SQLite consolidado   : {consolidated_db_path}")
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
        "db_path": str(consolidated_db_path),
        "txt_path": str(consolidated_txt_path),
        "mensagem": "Processamento concluído com sucesso!"
    }


# ---------------------------------------------------------------------------
# Execução Principal (CLI)
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="JoaKinDeX - Central de Indexação e Classificação Documental Multidomínio (Acadêmico, Civil e Financeiro)."
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
    parser.add_argument(
        "--uniformizar-instituicoes", "--normalizar-instituicoes",
        dest="uniformizar_instituicoes",
        action="store_true",
        help="Executa a uniformização e consolidação inteligente de nomes de instituições na base de dados sem reprocessar PDFs."
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

    if getattr(args, "uniformizar_instituicoes", False):
        print("\n" + "=" * 70)
        print("🎓 JoaKinDeX - UNIFORMIZAÇÃO INTELIGENTE DE INSTITUIÇÕES")
        print("   Criado por: Joaquim Ferreira Silva Neto <joaquimfsneto@gmail.com>")
        print("=" * 70)
        out_target = args.output_dir or "./saida"
        print(f"\n[✨] Processando arquivo e fichas em: {out_target}")
        res = uniformizar_base_dados(out_target, atualizar_individuais=not args.no_individual)
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

    # Detecta se foram passados argumentos explícitos via CLI
    explicit_cli_args = [
        arg for arg in sys.argv[1:]
        if arg not in ["--prompt", "--interativo", "-y", "--no-prompt", "--batch", "--reset-config", "--reset", "--factory-reset", "--uniformizar-instituicoes", "--normalizar-instituicoes"]
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
        print("\n" + "=" * 70)
        print("🎓 JoaKinDeX - CLASSIFICAÇÃO DE DOCUMENTOS EM MASSA")
        print("   Criado por: Joaquim Ferreira Silva Neto <joaquimfsneto@gmail.com>")
        print("=" * 70)
        args.input = resolve_dir_path(args.input, default="./pdf") if (args.input and not (Path(clean_path_string(args.input)).is_file() and Path(clean_path_string(args.input)).suffix.lower() == ".pdf")) else (str(Path(clean_path_string(args.input)).expanduser().resolve()) if args.input else "./pdf")
        args.output_dir = resolve_classifier_output_dir(args.output_dir)
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
