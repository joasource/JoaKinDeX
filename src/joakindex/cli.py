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
import random
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
    from PIL import Image, ImageEnhance
except ImportError:
    Image = None
    ImageEnhance = None

IMAGE_EXTENSIONS: Set[str] = {".png", ".jpg", ".jpeg", ".webp"}
WORD_EXTENSIONS: Set[str] = {".docx", ".doc", ".odt", ".rtf"}
TEXT_EXTENSIONS: Set[str] = {".txt"}
DOCUMENT_EXTENSIONS: Set[str] = {".pdf"} | WORD_EXTENSIONS | TEXT_EXTENSIONS
SUPPORTED_EXTENSIONS: Set[str] = DOCUMENT_EXTENSIONS | IMAGE_EXTENSIONS
_OFFICE_CONVERT_LOCK = threading.Lock()
_PDFIUM_LOCK = threading.RLock()

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

try:
    from joakindex.config import (
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
    try:
        from .config import (
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
        get_json_path,
        init_database,
        upsert_document,
        upsert_documents_batch,
        get_all_documents,
        consultar_regra_para_texto,
        resolve_default_db_path
    )
except ImportError:
    try:
        from .db import (
            get_db_path,
            get_json_path,
            init_database,
            upsert_document,
            upsert_documents_batch,
            get_all_documents,
            consultar_regra_para_texto,
            resolve_default_db_path
        )
    except ImportError:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from db_manager import (
            get_db_path,
            get_json_path,
            init_database,
            upsert_document,
            upsert_documents_batch,
            get_all_documents,
            consultar_regra_para_texto,
            resolve_default_db_path
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


def sanitize_llm_transcription(text: Optional[str]) -> Optional[str]:
    """
    Higieniza a transcrição textual retornada pelo LLM.
    Se o LLM tiver entrado em loop de alucinação (repetição infinita da mesma linha
    ou termos repetidos dezenas de vezes), descarta o texto defeituoso e retorna None,
    permitindo que a camada nativa digital ou Tesseract OCR prevaleça como Ground Truth.
    """
    if not text or not isinstance(text, str):
        return None
    cleaned = text.strip()
    if len(cleaned) < 20:
        return None

    lines = [ln.strip() for ln in cleaned.splitlines() if ln.strip()]
    if not lines:
        return None

    # 1. Verifica repetição consecutiva da mesma linha (loop clássico de VLM)
    max_consecutive = 1
    current_consecutive = 1
    for i in range(1, len(lines)):
        if lines[i].lower() == lines[i - 1].lower() and len(lines[i]) > 3:
            current_consecutive += 1
            if current_consecutive > max_consecutive:
                max_consecutive = current_consecutive
        else:
            current_consecutive = 1

    if max_consecutive >= 4:
        return None  # Descarta repetição em loop

    # 2. Verifica dominância excessiva de uma única linha repetida
    from collections import Counter
    counts = Counter(ln.lower() for ln in lines if len(ln) > 4)
    if counts:
        _, freq = counts.most_common(1)[0]
        if freq >= 5 and (freq / len(lines)) > 0.35:
            return None  # Mais de 35% do documento é a mesma linha repetida

    return cleaned


def extract_names_from_document_text(text: str) -> List[str]:
    """
    Extrai múltiplos nomes de pessoas físicas ou jurídicas de tabelas, listagens
    de depósitos, borderôs bancários, relações de pagamentos ou campos explícitos.
    """
    if not text or not isinstance(text, str) or len(text.strip()) < 10:
        return []

    STOPWORDS = {
        'FRACAROLI', 'VALOR', 'TITULAR', 'BANCO', 'AGENCIA', 'CONTA', 'CPF', 'CNPJ',
        'TOTAL', 'LISTAGEM', 'RECEITA', 'MINISTERIO', 'LOTE', 'CORRENTE', 'POUPANCA',
        'AUTENTICACAO', 'MECANICA', 'HISTORICO', 'FAVORECIDO', 'BENEFICIARIO',
        'DESCRICAO', 'DOCUMENTO', 'OPERACAO', 'SALDO', 'EXTRATO', 'DEPOSITO', 'PAGAMENTO'
    }

    def clean_cand_name(n: str) -> str:
        n = re.sub(r'[\~\|\_\\\/\"\'\`\§\*\!\?]', '', n)
        n = re.sub(r'\s+(?:oo|ra|va|A|da|de|do)\s*$', '', n, flags=re.IGNORECASE)
        n = re.sub(r'^\s*(?:oo|ra|va|A)\s+', '', n, flags=re.IGNORECASE)
        n = re.sub(r'[\s\d\W]+$', '', n)
        n = re.sub(r'\s+', ' ', n).strip()
        return n

    detected_names: List[str] = []

    for line in text.splitlines():
        line_str = line.strip()
        if not line_str or len(line_str) < 5:
            continue

        # 1. Linha de tabela com valor monetário inicial (ex: "1150000,00 JOSE MAGNO BUFON 1 5610 ...")
        m_val = re.match(r'^[\*\_\s]?\d+[\.,]\d{2}\s+(.+)$', line_str)
        if m_val:
            rest = m_val.group(1).strip()
            # Procura separador onde começam dados bancários, lotes ou sequências de dígitos
            m_split = re.search(r'[\s~_|\.\'\"\`\-\,\/\§\!\*]+(?:(?:oo|ra|va|A)\s+)?(?:\d{1,4}\s+[\=\.\s]*\d{3,5}|\bAg|\bC\.?Corren|\bTED|\bDEP|\bTES|\bPoup)', rest)
            if m_split:
                name_part = rest[:m_split.start()]
            else:
                m_cpf = re.search(r'\b\d{11}\b|\b\d{14}\b', rest)
                if m_cpf:
                    name_part = rest[:m_cpf.start()].strip()
                    name_part = re.sub(r'[\s\d\=\-\.\,\§\~]+$', '', name_part)
                else:
                    name_part = ""

            cand = clean_cand_name(name_part)
            words = [w for w in cand.split() if len(w) > 1]
            if len(cand) >= 4 and len(words) >= 2:
                if not any(sw in cand.upper() for sw in STOPWORDS):
                    if cand not in detected_names:
                        detected_names.append(cand)
            continue

        # 2. Rótulos explícitos (ex: "Titular: FULANO DE TAL", "Favorecido: BELTRANO")
        m_pref = re.search(r'(?:Titular|Favorecido|Nome|Aluno|Benefici[aá]rio)[\s\:\-]+([A-ZÀ-Úa-zà-ú\s]{4,50})', line_str, re.IGNORECASE)
        if m_pref:
            cand = clean_cand_name(m_pref.group(1))
            words = [w for w in cand.split() if len(w) > 1]
            if len(cand) >= 4 and len(words) >= 2:
                if not any(sw in cand.upper() for sw in STOPWORDS):
                    if cand not in detected_names:
                        detected_names.append(cand)
            continue

        # 3. Nome completo em caixa alta seguido diretamente de CPF ou CNPJ formatado ou puro
        m_cpf_line = re.search(r'([A-ZÀ-Ú]{3,}(?:\s+[A-ZÀ-Ú]{2,}){1,5})\s+(?:\d{3}\.\d{3}\.\d{3}-\d{2}|\d{11}|\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2})', line_str)
        if m_cpf_line:
            cand = clean_cand_name(m_cpf_line.group(1))
            words = [w for w in cand.split() if len(w) > 1]
            if len(cand) >= 4 and len(words) >= 2:
                if not any(sw in cand.upper() for sw in STOPWORDS):
                    if cand not in detected_names:
                        detected_names.append(cand)

    return detected_names


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

    # Nome do arquivo de cache pelo MD5 do conteúdo do arquivo
    try:
        md5_val = hashlib.md5(p.read_bytes()).hexdigest()
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
            subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)

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
    scale: float = 1.6,
    quality: int = 85
) -> List[str]:
    """
    Renderiza páginas do PDF em imagens JPEG codificadas em base64 para leitura visual (OCR) via LLM.
    Utiliza pypdfium2 com fallback para pdfplumber.
    """
    images_b64: List[str] = []

    # Tentativa 1: pypdfium2 (rápido e alta fidelidade com lock thread-safe)
    if pdfium is not None:
        with _PDFIUM_LOCK:
            pdf = None
            try:
                pdf = pdfium.PdfDocument(str(pdf_path))
                num_pages = min(len(pdf), max_pages)
                for i in range(num_pages):
                    page = pdf.get_page(i)
                    try:
                        bitmap = page.render(scale=scale)
                        try:
                            img = bitmap.to_pil()
                            buf = io.BytesIO()
                            img.save(buf, format="JPEG", quality=quality)
                            images_b64.append(base64.b64encode(buf.getvalue()).decode("utf-8"))
                        finally:
                            bitmap.close()
                    finally:
                        page.close()
                if images_b64:
                    return images_b64
            except Exception:
                images_b64 = []
            finally:
                if pdf is not None:
                    try:
                        pdf.close()
                    except Exception:
                        pass

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


def extract_boleto_signals(text: str) -> Tuple[bool, Optional[str], Optional[str], Dict[str, Any]]:
    """
    Identifica de forma universal se o texto contém elementos de Boleto Bancário (FEBRABAN),
    fatura de concessionária com cobrança ou títulos de compensação.
    Retorna: (is_boleto: bool, linha_digitavel: Optional[str], codigo_barras: Optional[str], detalhes: Dict[str, Any])
    """
    if not text or len(text.strip()) < 8:
        return False, None, None, {}

    t_lower = text.lower()
    details: Dict[str, Any] = {}

    # 1. Linha digitável bancária (47 dígitos FEBRABAN)
    m_bancario = re.search(
        r'(?:\d{3}[-\s]\d)?\s*(\d{5}[\.\s]?\d{5}\s+\d{5}[\.\s]?\d{6}\s+\d{5}[\.\s]?\d{6}\s+\d\s+\d{14})\b',
        text
    )
    if not m_bancario:
        m_bancario = re.search(r'\b(\d{47})\b', text)

    # 2. Linha digitável concessionária / convênios (48 dígitos ou 2x24 ou 4x12)
    m_concess = re.search(
        r'\b([89]\d{11}[\s\-]?\d{12}[\s\-]?\d{12}[\s\-]?\d{12})\b|'
        r'\b([89]\d{23}\s+\d{20,24})\b|'
        r'\b[sS]{1,2}(\d{22,23}\s+\d{20,24})\b',
        text
    )
    if not m_concess:
        m_concess = re.search(r'\b([89]\d{47})\b', text)

    # 3. Código de barras numérico contínuo (44 dígitos)
    m_barras = re.search(r'\b(\d{44})\b', text)

    linha_digitavel = None
    if m_bancario:
        linha_digitavel = m_bancario.group(1).strip()
    elif m_concess:
        matched_g = [g for g in m_concess.groups() if g]
        if matched_g:
            raw_concess = matched_g[0].strip()
            if raw_concess.startswith('62') or (len(raw_concess) > 38 and not raw_concess.startswith('8')):
                raw_concess = '88' + raw_concess
            linha_digitavel = raw_concess

    codigo_barras = m_barras.group(1).strip() if m_barras else None

    # 4. Termos estruturais fortes de Boleto Bancário
    termos_fortes = [
        'ficha de compensação', 'ficha de compensacao',
        'recibo do pagador', 'recibo do sacado',
        'nosso número', 'nosso numero',
        'pagável em qualquer banco', 'pagavel em qualquer banco',
        'código de baixa', 'codigo de baixa',
        'agência/código do beneficiário', 'agencia/codigo do beneficiario',
        'agência / código beneficiário', 'agencia / codigo beneficiario',
        'agência/código beneficiário', 'agencia/codigo beneficiario',
        'linha digitável', 'linha digitavel'
    ]
    has_termo_forte = any(t in t_lower for t in termos_fortes)

    # 5. Faturas de concessionárias / contas de energia com cobrança / reaviso
    is_fatura_energia = (
        ('documento auxiliar da nota de energia' in t_lower or 'nota de energia' in t_lower or 'reaviso de debito' in t_lower or 'reaviso de débito' in t_lower)
        and any(k in t_lower for k in ['total a pagar', 'totalapagar', 'codigo de barras', 'código de barras', 'vencimento', 'linha cod. de barra', 'distrib de energia'])
    )

    # 6. Fatura mercantil com duplicata / cobrança bancária
    is_fatura_boleto = ('fatura' in t_lower and any(k in t_lower for k in ['mocal moageira', 'duplicata', 'banco', 'fracaroli']))

    is_boleto = bool(linha_digitavel or codigo_barras or has_termo_forte or is_fatura_energia or is_fatura_boleto)

    # Extração de Nosso Número
    m_nn = re.search(r'(?:nosso\s*n[úu]mero|nosso\s*n[º°])[:\s]+([0-9\-\.\/]+)', text, re.I)
    if m_nn:
        c_nn = m_nn.group(1).strip()
        if len(c_nn) >= 5 and '/' not in c_nn[:4]:
            details['nosso_numero'] = c_nn

    return is_boleto, linha_digitavel, codigo_barras, details


def extract_cheque_signals(text: str) -> Tuple[bool, Optional[str], Optional[str], Dict[str, Any]]:
    """
    Identifica de forma universal se o texto contém elementos característicos de
    Folha de Cheque ou Talão de Cheques (compensação bancária, canhotos, talonários).
    Retorna: (is_cheque: bool, numero_cheque: Optional[str], banco: Optional[str], detalhes: Dict[str, Any])
    """
    if not text or len(text.strip()) < 8:
        return False, None, None, {}

    t_lower = text.lower()
    details: Dict[str, Any] = {}
    score = 0

    # 1. Termos estruturais fortes (linguagem típica e exclusiva de cheques e canhotos)
    termos_fortes = [
        'pague por este cheque', 'pague por este', 'a quantia de', 'à quantia de',
        'ou à sua ordem', 'ou a sua ordem', 'à sua ordem', 'a sua ordem',
        'centavos acima', 'centavos a cima', 'e centavos',
        'saldo anterior', 'saldo atual', 'lançamentos anterior', 'lancamentos anterior',
        'este cheque', 'valor deste cheque',
        'talão de cheque', 'talao de cheque', 'talão de cheques', 'talao de cheques',
        'folha de cheque', 'folhas de cheque', 'talao', 'talão',
        'canhoto', 'compensação bancária', 'compensacao bancaria',
        'ficha de compensação de cheque', 'confecção:', 'confeccao:'
    ]
    for termo in termos_fortes:
        if termo in t_lower:
            score += 4

    # 2. Termos secundários de apoio
    termos_apoio = [
        'cheque', 'cheques', 'emitente', 'c/c', 'conta corrente',
        'cooperativa', 'agência', 'agencia', 'banco', 'série', 'serie',
        'compensação', 'compensacao', 'alínea', 'alinea'
    ]
    for termo in termos_apoio:
        if termo in t_lower:
            score += 1

    # 3. Expressão explícita "Cheque No" ou "Cheque Nº"
    m_cheque_label = re.search(r'\bcheque\s*(?:n[º°o\.]|numero)?\b', text, re.I)
    if m_cheque_label:
        score += 3

    # 4. Detecção de Banco
    banco = None
    bancos_map = [
        (r'sicoob', 'SICOOB'),
        (r'sicredi', 'SICREDI'),
        (r'banco do brasil|\bbb\b', 'Banco do Brasil'),
        (r'bradesco', 'Bradesco'),
        (r'ita[úu]', 'Itaú'),
        (r'santander', 'Santander'),
        (r'caixa\s+econ[ôo]mica|\bcef\b', 'Caixa Econômica Federal'),
        (r'banestes', 'BANESTES'),
        (r'brb\b|banco de bras[íi]lia', 'BRB'),
        (r'safra\b', 'Safra'),
        (r'banco inter|\binter\b', 'Inter'),
        (r'nubank', 'Nubank')
    ]
    for pat, b_name in bancos_map:
        if re.search(pat, t_lower):
            banco = b_name
            details['banco_cheque'] = banco
            score += 2
            break

    # 5. Extração de Números de Cheque (6 dígitos padrão FEBRABAN)
    numeros_encontrados = []
    for m in re.finditer(r'(?:cheque\s*(?:n[º°o\.]|numero)?[\s\:\-\n\r]{1,30}|ch[º°o\.]?[\s\:\-\n\r]{1,30})\b([0-9]{6})\b', text, re.I):
        c_num = m.group(1).strip()
        if c_num not in numeros_encontrados:
            numeros_encontrados.append(c_num)

    if not numeros_encontrados and (score >= 4 or 'cheque' in t_lower):
        for m in re.finditer(r'\b([0-9]{6})\b', text):
            c_num = m.group(1).strip()
            if c_num not in numeros_encontrados and not c_num.startswith('000000'):
                numeros_encontrados.append(c_num)

    # 6. Extração de Série
    m_serie = re.search(r'(?:s[ée]rie|ser)[\s\:\-\n\r]{1,15}\b([0-9]{1,4})\b', text, re.I)
    if not m_serie:
        m_serie = re.search(r'(?:s[ée]rie|ser)[\s\:\-\n\r]{1,15}\b([0-9A-Z]{1,4})\b', text, re.I)
    if m_serie:
        details['serie_cheque'] = m_serie.group(1).strip()

    # 7. Extração de Conta Corrente
    m_conta = re.search(r'(?:c\/c|conta(?:\s*corrente)?|coya)[\s\:\-\n\r]{1,15}\b([0-9]{5,12}(?:[\-\.][0-9Xx])?)\b', text, re.I)
    if not m_conta and '00038' in text:
        m_c = re.search(r'\b(000\d{6,8})\b', text)
        if m_c:
            m_conta = m_c
    if m_conta:
        details['conta_corrente'] = m_conta.group(1).strip()

    # 8. Extração de Agência / Cooperativa
    m_ag = re.search(r'(?:ag[êe]ncia|cooperativa)[\s\:\-\n\r]{1,15}\b([0-9]{3,5}(?:[\-][0-9Xx])?)\b', text, re.I)
    if m_ag:
        details['agencia_cheque'] = m_ag.group(1).strip()

    numero_cheque = numeros_encontrados[0] if numeros_encontrados else None
    if numeros_encontrados:
        details['numeros_cheque'] = numeros_encontrados
        details['numero_cheque'] = numero_cheque

    # Decisão final de is_cheque
    is_cheque = bool(
        score >= 5
        or (score >= 3 and numero_cheque)
        or any(k in t_lower for k in ['pague por este cheque', 'talão de cheque', 'talao de cheque', 'folha de cheque', 'folhas de cheque'])
    )

    if is_cheque and len(numeros_encontrados) > 1:
        details['is_talao'] = True

    return is_cheque, numero_cheque, banco, details


def extract_irpf_signals(text: str) -> Tuple[bool, Optional[str], Dict[str, Any]]:
    """
    Identifica de forma precisa se o texto pertence a uma Declaração de Ajuste Anual do IRPF
    ou Recibo de Entrega da Declaração emitido pela Secretaria da Receita Federal.
    Retorna: (is_irpf: bool, tipo_documento: Optional[str], metadados: Dict[str, Any])
    """
    if not text or len(text.strip()) < 20:
        return False, None, {}

    t = text.lower()

    # Se tiver título explícito de informe/comprovante de rendimentos financeiros, pertence ao informe e não à declaração
    if re.search(r"(?:informe|comprovante)\s+de\s+rendimentos\s*(?:financeiros)?", t):
        return False, None, {}

    # 1. Marcadores de IRPF / Declaração de Ajuste Anual (tolerante a variações OCR como c, ç, g)
    has_ajuste = bool(
        re.search(r"declara[cçg][aã]o\s+de\s+ajuste\s+anual", t)
        or ("ajuste anual" in t and ("exercício" in t or "exercicio" in t or "ano-calend" in t or "receita federal" in t))
    )
    has_imposto_renda = bool(
        re.search(r"imposto\s+(?:sobre\s+a\s+)?renda", t)
        and ("pessoa f[ií]sica" in t or "pessoa fisica" in t or "irpf" in t or "receita federal" in t)
    )

    # 2. Marcadores de Recibo de Entrega
    has_recibo_entrega = bool(
        re.search(r"recibo\s+de\s+entrega", t)
        or (re.search(r"(?:o\s+)?n[úu]mero\s+do\s+recibo\b", t) and ("declara" in t or "receita federal" in t))
    )

    # 3. Seções típicas de IRPF
    has_sections = any(s in t for s in [
        "declaração de bens e direitos", "declaracao de bens e direitos", "declaragao de bens e direitos",
        "rendimentos tributáveis", "rendimentos tributaveis", "rendimentos isentos", "resumo tributação",
        "resumo tributacao", "resumo tributagao", "demonstrativo de atividade rural", "renda variável",
        "renda variavel", "evolução patrimonial", "evolucao patrimonial", "desconto simplificado",
        "deduções legais", "deducoes legais", "identificação do declarante", "identificacao do declarante",
        "identificação do contribuinte", "identificacao do contribuinte", "imposto a restituir",
        "saldo imposto a pagar"
    ])

    is_irpf = False
    if (has_recibo_entrega and (has_ajuste or has_imposto_renda or "receita federal" in t or "ministério da fazenda" in t or "ministerio da economia" in t)) or \
       (has_ajuste and (has_imposto_renda or has_sections or "exerc" in t)):
        is_irpf = True
    elif has_imposto_renda and has_sections:
        is_irpf = True

    if is_irpf:
        tipo = "Recibo de Entrega da Declaração de Ajuste Anual" if has_recibo_entrega else "Declaração de Imposto de Renda"
        meta = {}
        ex_m = re.search(r"exerc[ií]cio\s*[:\s]*(\d{4})", text, re.IGNORECASE)
        ano_m = re.search(r"ano[- ]calend[aá]rio\s*[:\s]*(?:de\s*)?(\d{4})", text, re.IGNORECASE)
        if ex_m: meta["exercicio"] = ex_m.group(1)
        if ano_m: meta["ano_calendario"] = ano_m.group(1)

        rec_m = re.search(r"(?:n[úu]mero\s+do\s+recibo[^\n]*?|\b)(\d{2}\.\d{2}\.\d{2}\.\d{2}\.\d{2}\s*-\s*\d{2})", text, re.IGNORECASE)
        if rec_m: meta["numero_recibo"] = rec_m.group(1).strip()

        tot_m = re.search(r"total\s+(?:de\s+)?rendimentos\s+tribut[aá]veis\s*[:\s]*([0-9\.\,]+)", text, re.IGNORECASE)
        if tot_m: meta["total_rendimentos_tributaveis"] = tot_m.group(1).strip()

        return True, tipo, meta

    return False, None, {}


def extract_informe_rendimentos_signals(text: str) -> Tuple[bool, Optional[str], Dict[str, Any]]:
    """
    Identifica de forma precisa se o texto pertence a um Informe de Rendimentos Financeiros
    (emitido por instituições financeiras como Caixa, BB, Itaú, Bradesco, etc.)
    ou Comprovante de Rendimentos Pagos e de Retenção de Imposto de Renda na Fonte.
    Retorna: (is_informe: bool, tipo_documento: Optional[str], metadados: Dict[str, Any])
    """
    if not text or len(text.strip()) < 20:
        return False, None, {}

    t = text.lower()

    # Se for comprovadamente o recibo de entrega da declaração da Receita Federal
    if "recibo de entrega da declara" in t:
        return False, None, {}

    has_informe_title = bool(re.search(r"(?:informe|comprovante)\s+de\s+rendimentos\s*(?:financeiros)?", t))
    has_rend_fin = bool("rendimentos financeiros" in t or ("rendimentos" in t and any(b in t for b in ["aplicações financeiras", "aplicacoes financeiras", "tributação exclusiva", "tributacao exclusiva"])))
    has_fonte = bool("fonte pagadora" in t or "beneficiária dos rendimentos" in t or "beneficiaria dos rendimentos" in t or "pessoa física beneficiária" in t or "pessoa fisica beneficiaria" in t)
    has_bank_continuation = bool(
        any(b in t for b in ["sac caixa", "help desk caixa", "ouvidoria caixa", "sac bb", "sac banco"]) and
        any(w in t for w in ["tributação exclusiva", "tributacao exclusiva", "restituição de ir", "restituicao de ir", "contas vinculadas", "contas correntes"])
    )

    if (has_informe_title and (has_rend_fin or has_fonte or "ano-calend" in t)) or has_bank_continuation:
        tipo = "Informe de Rendimentos Financeiros"
        meta = {}
        if "caixa econ" in t or "cef" in t or "sac caixa" in t:
            meta["fonte_pagadora"] = "CAIXA ECONÔMICA FEDERAL"
        elif "banco do brasil" in t:
            meta["fonte_pagadora"] = "BANCO DO BRASIL"
        elif "itau" in t or "itaú" in t:
            meta["fonte_pagadora"] = "ITAÚ UNIBANCO"
        elif "bradesco" in t:
            meta["fonte_pagadora"] = "BANCO BRADESCO"
        elif "santander" in t:
            meta["fonte_pagadora"] = "BANCO SANTANDER"

        ano_m = re.search(r"ano[- ]calend[aá]rio\s*[:\s]*(?:de\s*)?(\d{4})", text, re.IGNORECASE)
        if ano_m: meta["ano_calendario"] = ano_m.group(1)

        cnpj_m = re.search(r"\b\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}\b", text)
        if cnpj_m: meta["cnpj_fonte_pagadora"] = cnpj_m.group(0)

        return True, tipo, meta

    return False, None, {}


def extract_veicular_signals(text: str) -> Tuple[bool, Optional[str], Dict[str, Any]]:
    """
    Identifica de forma universal se o texto pertence ao domínio veicular
    (CRV, CRLV, ATPV, Comunicação de Venda, Laudo de Vistoria, Guia de Remoção,
    Nota de Arrematação, Agendamento DETRAN).
    Retorna: (is_veicular: bool, tipo_documento: Optional[str], metadados: Dict[str, Any])
    """
    if not text or len(text.strip()) < 15:
        return False, None, {}

    t = text.lower()
    meta: Dict[str, Any] = {}

    # Extração universal de entidades veiculares
    placa_m = re.search(r'\b([A-Z]{3}-?[0-9]{4}|[A-Z]{3}[0-9][A-Z][0-9]{2})\b', text)
    if placa_m:
        meta["placa"] = placa_m.group(1).upper()

    renavam_m = re.search(r'\b(?:renavam|c[oó]d(?:igo)?\.?\s*renavam)[:\s\.\-]*([0-9]{9,11})\b', text, re.IGNORECASE)
    if renavam_m:
        meta["renavam"] = renavam_m.group(1).strip()

    chassi_m = re.search(r'\b(?:chassi|chassis|n[ºo°\.\s]*chassi)[:\s\.\-]*([A-HJ-NPR-Z0-9]{17})\b', text, re.IGNORECASE)
    if chassi_m:
        meta["chassi"] = chassi_m.group(1).upper()

    # 1. CRLV - Certificado de Registro e Licenciamento de Veículo (porte/circulação anual)
    # Não diferenciar físico de digital
    is_crlv = (
        "certificado de registro e licenciamento" in t or
        "licenciamento de ve" in t or
        "crlv" in t or
        ("licenciamento" in t and ("veículo" in t or "veiculo" in t or "detran" in t or "senatran" in t)) or
        (re.search(r'\bexerc[ií]cio\s*[:\.\s]*20[0-9]{2}\b', t) and any(w in t for w in ["detran", "senatran", "denatran", "ipva", "dpvat", "porte"]))
    )
    # Proteção: se expressamente for apenas CRV de registro sem licenciamento
    if is_crlv and not ("certificado de registro de ve" in t and "licenciamento" not in t and "crlv" not in t):
        return True, "Certificado de Registro e Licenciamento de Veículo (CRLV)", meta

    # 2. ATPV - Autorização para Transferência de Propriedade de Veículo
    # Não diferenciar física de digital
    is_atpv = (
        "autorização para transferência de propriedade de veículo" in t or
        "autorizacao para transferencia de propriedade de veiculo" in t or
        "autorização para transferência de propriedade" in t or
        "autorizacao para transferencia de propriedade" in t or
        "atpv" in t or
        "declaro que transferi a propriedade deste veículo" in t or
        "declaro que transferi a propriedade" in t or
        ("intenção de venda" in t and any(w in t for w in ["detran", "veículo", "veiculo", "comprador"]))
    )
    if is_atpv:
        return True, "Autorização para Transferência de Propriedade de Veículo (ATPV)", meta

    # 3. CRV - Certificado de Registro de Veículo (propriedade e transferência, antigo DUT)
    # Não diferenciar físico de digital
    is_crv = (
        "certificado de registro de ve" in t or
        "crv" in t or
        "documento único de transferência" in t or
        "documento unico de transferencia" in t or
        ("via anterior" in t and any(w in t for w in ["renavam", "chassi", "placa"])) or
        (any(w in t for w in ["detran", "denatran", "senatran"]) and "renavam" in t and "chassi" in t and not is_crlv)
    )
    if is_crv:
        return True, "Certificado de Registro de Veículo (CRV)", meta

    # 4. Comunicação de Venda ao DETRAN
    if any(k in t for k in ["comunicação de venda", "comunicacao de venda", "certidão de comunicação de venda", "certidao de comunicacao de venda"]):
        return True, "Comunicação de Venda ao DETRAN", meta

    # 5. Agendamento DETRAN (Comprovante / Intenção de Vistoria)
    if any(k in t for k in ["agendamento", "comprovante de agendamento", "fazer agendamento"]) and ("detran" in t or "intenção de venda" in t or "intencao de venda" in t):
        return True, "Comprovante de Agendamento DETRAN", meta

    # 6. Laudo / Documento de Vistoria de Veículo
    if (any(k in t for k in ["vistoria de veículo", "vistoria de veiculo", "vistoria veicular", "inspeção veicular", "inspecao veicular"]) or \
       ("laudo de vistoria" in t and any(w in t for w in ["veículo", "veiculo", "chassi", "motor", "detran"]))) and not any(k in t for k in ["agendamento", "agendar"]):
        return True, "Laudo de Vistoria Veicular", meta

    # 7. Guia de Remoção de Veículo (Pátio / Guincho)
    if any(k in t for k in ["guia de remoção", "guia de remocao", "remoção de veículo", "remocao de veiculo", "termo de recolhimento de veículo", "termo de recolhimento de veiculo"]) or \
       (any(w in t for w in ["pátio", "patio", "guincho"]) and any(w in t for w in ["remoção", "remocao", "apreensão", "apreensao", "guia n"])):
        return True, "Guia de Remoção de Veículo", meta

    # 8. Nota de Arrematação (Leilão)
    if any(k in t for k in ["nota de arrematação", "nota de arrematacao", "arrematação em leilão", "arrematacao em leilao"]) or \
       (any(w in t for w in ["leilão", "leilao", "leiloeiro"]) and any(w in t for w in ["arrematante", "arrematação", "arrematacao", "lote", "chassi"])):
        return True, "Nota de Arrematação (Leilão)", meta

    # 9. Busca e Apreensão / Citação
    if any(k in t for k in ["busca e apreensão", "busca e apreensao"]) and any(w in t for w in ["mandado", "citação", "citacao", "oficial de justiça"]):
        return True, "Citação de Mandado de Busca e Apreensão", meta

    return False, None, {}


def extract_contrato_compra_venda_signals(text: str) -> Tuple[bool, Optional[str], Dict[str, Any]]:
    """
    Identifica se o texto pertence a um Contrato / Compromisso / Promessa de Compra e Venda
    (imóvel, terreno, bens comerciais) ou cláusulas contratuais de compra e venda.
    Retorna: (is_cv: bool, tipo_documento: Optional[str], metadados: Dict[str, Any])
    """
    if not text or len(text.strip()) < 20:
        return False, None, {}

    t = text.lower()

    # Regra estrita: Documentos veiculares oficiais (CRV, CRLV, ATPV, Vistoria, Remoção, DETRAN)
    # NÃO devem ser classificados como Contrato de Compra e Venda
    is_veicular_context = any(k in t for k in [
        "certificado de registro", "crv", "crlv", "atpv",
        "transferência de propriedade de veículo", "transferencia de propriedade de veiculo",
        "comunicação de venda", "comunicacao de venda", "vistoria veicular", "laudo de vistoria",
        "guia de remoção", "guia de remocao", "nota de arrematação", "nota de arrematacao",
        "detran", "senatran", "denatran"
    ]) and not any(k in t for k in [
        "contrato particular de promessa", "instrumento particular de promessa",
        "compromisso de compra e venda de imóvel", "contrato de compra e venda de imóvel"
    ])
    if is_veicular_context:
        return False, None, {}
    
    # Marcadores explícitos de compra e venda
    has_cv_title = any(k in t for k in [
        "compra e venda", "compromisso de compra", "promessa de compra",
        "promitente vendedor", "promitentes-vendedor", "promitentes vendedores",
        "promitente comprador", "promitentes-comprador", "promitentes compradores",
        "promitente compradora", "venda de imóvel", "venda de imovel"
    ])
    
    # Marcadores de cláusulas contratuais de compra e venda ou instrumento contratual
    has_contract_context = any(k in t for k in ["contrato", "instrumento particular", "cláusula", "clausula"])
    has_cv_terms = any(w in t for w in [
        "imóvel", "imovel", "vendedor", "comprador", "evicção", "eviccao",
        "irrevogável", "irrevogavel", "foro da situação", "foro da situacao",
        "sinal e princípio de pagamento", "sinal e principio de pagamento",
        "escritura definitiva"
    ])
    
    if has_cv_title or (has_contract_context and has_cv_terms):
        tipo = "Contrato de Compra e Venda"
        meta = {}
        if "comercial" in t:
            meta["subtipo_contrato"] = "Imóvel Comercial"
        elif "residencial" in t:
            meta["subtipo_contrato"] = "Imóvel Residencial"
        return True, tipo, meta
        
    return False, None, {}


def extract_nota_promissoria_signals(text: str) -> Tuple[bool, Optional[str], Dict[str, Any]]:
    """
    Identifica de forma universal se o texto pertence a uma Nota Promissória
    (título de crédito comercial, padrão São Domingos, blocos comerciais, etc.).
    Retorna: (is_promissoria: bool, tipo_documento: Optional[str], metadados: Dict[str, Any])
    """
    if not text or len(text.strip()) < 15:
        return False, None, {}

    t = text.lower()
    
    has_title = any(k in t for k in ["nota promissoria", "nota promissória", "promissoria", "promissória"])
    has_classic_phrases = any(k in t for k in [
        "por esta única via", "por esta unica via", "por esta via",
        "pagar por esta", "pagará por esta", "pagarei por esta", "pagaremos por esta",
        "em moeda corrente deste país", "em moeda corrente deste pais",
        "à sua ordem", "a sua ordem", "à nossa ordem", "a nossa ordem", "a quantia de", "à ordem de"
    ])
    has_form_markers = any(k in t for k in ["são domingos", "sao domingos", "cód. 6091", "cod. 6091", "6091"])
    has_credit_parties = ("vencimento" in t or "venc" in t) and any(w in t for w in ["avalista", "avalistas", "emitente", "pagável em", "pagavel em"])
    
    if has_title or (has_classic_phrases and ("vencimento" in t or "avalista" in t or "emitente" in t)) or \
       (has_form_markers and ("vencimento" in t or "emitente" in t or "pagar" in t or has_title)) or \
       has_credit_parties:
        tipo = "Nota Promissória"
        meta = {}
        
        num_m = re.search(r"n[ºo°\.\s]*([0-9]{1,4})\b", text, re.IGNORECASE)
        if num_m:
            meta["numero_nota"] = num_m.group(1).strip()
            
        val_m = re.search(r"r\$\s*([0-9]{1,3}(?:\.[0-9]{3})*,[0-9]{2})", text, re.IGNORECASE)
        if val_m:
            meta["valor"] = val_m.group(1).strip()
            
        venc_m = re.search(r"vencimento\s*[:\.\s]*([0-9]{1,2}\s*(?:de|\/)\s*[a-z0-9A-ZÀ-Ú]+\s*(?:de|\/)\s*[0-9]{2,4})", text, re.IGNORECASE)
        if venc_m:
            meta["vencimento"] = venc_m.group(1).strip()
            
        emit_m = re.search(r"emitente\s*[:\.\s]*([A-ZÀ-Ú\s]{4,35})", text)
        if emit_m:
            meta["emitente"] = emit_m.group(1).strip()
            
        return True, tipo, meta
        
    return False, None, {}


def extract_recibo_signals(text: str) -> Tuple[bool, Optional[str], Dict[str, Any]]:
    """
    Identifica se o texto pertence a um Recibo avulso / Recibo de Pagamento.
    Evita falso positivo quando a palavra recibo é usada apenas em cláusula de quitação de contrato.
    Retorna: (is_recibo: bool, tipo_documento: Optional[str], metadados: Dict[str, Any])
    """
    if not text or len(text.strip()) < 15:
        return False, None, {}

    t = text.lower()
    
    # Se for contrato com cláusulas contratuais extensas, não é recibo avulso
    if any(k in t for k in ["compromisso de compra", "promessa de compra", "promitente vendedor", "promitente comprador", "cláusula sétima", "clausula setima", "foro da situação", "foro da situacao"]):
        return False, None, {}

    # Se for boleto bancário (que contém 'recibo do pagador/sacado'), o documento é Boleto Bancário
    is_bol_chk, _, _, _ = extract_boleto_signals(text)
    if is_bol_chk:
        return False, None, {}
        
    has_recibo_header = bool(re.search(r"\brecibos?\b", t))
    has_recebi = any(k in t for k in [
        "recebi(emos) de", "recebi(emos)", "recebemos de", "recebi de",
        "recebemos do", "recebi do", "recebemos da", "recebi da"
    ])
    has_recibo_terms = any(k in t for k in [
        "a importância de", "a importancia de", "a quantia de",
        "referente a", "referente ao pagamento", "correspondente a",
        "em pagamento de", "como sinal e princípio", "para clareza firmo",
        "para clareza firmamos", "dou plena quitação", "dou plena quitacao"
    ])
    
    if (has_recibo_header and (has_recebi or has_recibo_terms)) or (has_recebi and has_recibo_terms):
        tipo = "Recibo"
        meta = {}
        val_m = re.search(r"r\$\s*([0-9]{1,3}(?:\.[0-9]{3})*,[0-9]{2})", text, re.IGNORECASE)
        if val_m:
            meta["valor"] = val_m.group(1).strip()
        return True, tipo, meta
        
    return False, None, {}


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
        regra = consultar_regra_para_texto(resolve_default_db_path(), text)
        if regra:
            is_bol_test, _, _, _ = extract_boleto_signals(text)
            if not (is_bol_test and regra.get("valor_atribuido") == "Recibo"):
                return regra["valor_atribuido"], regra["dominio"]
    except Exception:
        pass


    # 0.1 Detecção Universal de Boleto Bancário / FEBRABAN
    is_bol, bol_linha, bol_barras, _ = extract_boleto_signals(text)
    if is_bol:
        scores["Boleto Bancário"] = ("financeiro", 11 if (bol_linha or bol_barras) else 10)

    # 0.2 Detecção Universal de Cheque / Talão de Cheques
    is_chk, chk_num, chk_banco, chk_det = extract_cheque_signals(text)
    if is_chk:
        tag_chk = "Talão de Cheques" if chk_det.get("is_talao") else "Folha de Cheque"
        scores[tag_chk] = ("financeiro", 11 if chk_num else 10)

    # 0.3 Detecção Universal de Informe de Rendimentos Financeiros
    is_inf, inf_tipo, inf_det = extract_informe_rendimentos_signals(text)
    if is_inf:
        scores[inf_tipo] = ("financeiro", 12)

    # 0.4 Detecção Universal de IRPF / Recibo de Entrega / Declaração de Ajuste Anual
    is_irpf, irpf_tipo, irpf_det = extract_irpf_signals(text)
    if is_irpf:
        scores[irpf_tipo] = ("financeiro", 13 if "recibo" in irpf_tipo.lower() else 12)

    # 0.45 Detecção Universal Veicular (CRV, CRLV, ATPV, Vistoria, Remoção, Arrematação, DETRAN)
    is_veic, veic_tipo, veic_det = extract_veicular_signals(text)
    if is_veic:
        v_dom = "juridico" if "citação" in (veic_tipo or "").lower() else "veicular"
        scores[veic_tipo] = (v_dom, 13)

    # 0.5 Detecção Universal de Contrato de Compra e Venda
    is_cv, cv_tipo, cv_det = extract_contrato_compra_venda_signals(text)
    if is_cv and not is_veic:
        scores[cv_tipo] = ("juridico", 11)

    # 0.6 Detecção Universal de Nota Promissória
    is_np, np_tipo, np_det = extract_nota_promissoria_signals(text)
    if is_np:
        scores[np_tipo] = ("financeiro", 11)

    # 0.7 Detecção Universal de Recibo
    is_rec, rec_tipo, rec_det = extract_recibo_signals(text)
    if is_rec and not is_cv and not is_veic:
        scores[rec_tipo] = ("financeiro", 10)

    # 1. Domínio: Identificação
    # Protege contra qualificação de partes em contratos ou declarações
    is_contract_context = is_cv or any(k in t for k in [
        "instrumento particular", "contrato", "cláusula", "clausula", "promitente",
        "outorgante", "outorgado", "promitentes-vendedor", "promitentes vendedores"
    ])

    if any(k in t for k in ["carteira nacional de habilita", "driver license", "permiso de conduccion", "senatran", "denatran", "1° habilita", "1ª habilita"]) or ("cnh" in t and "categoria" in t):
        scores["CNH"] = ("identificacao", 10)
    elif not is_contract_context and any(k in t for k in ["cédula de identidade", "cedula de identidade", "registro geral", "instituto de identificação", "instituto de identificacao", "secretaria de segurança", "ssp/", "ssp-", "polícia civil"]):
        scores["RG"] = ("identificacao", 9)
    elif any(k in t for k in ["certidão de nascimento", "certidao de nascimento", "nascimento sob o termo", "registro civil das pessoas naturais"]):
        scores["Certidão de Nascimento"] = ("identificacao", 9)
    elif any(k in t for k in ["certidão de casamento", "certidao de casamento", "casamento sob o termo"]):
        scores["Certidão de Casamento"] = ("identificacao", 9)
    elif not is_irpf and not is_inf and not is_contract_context and (any(k in t for k in ["comprovante de inscrição no cpf", "comprovante de inscricao no cpf", "cartão de identificação do contribuinte", "cartao de identificacao do contribuinte", "cadastro de pessoas físicas", "cadastro de pessoas fisicas"]) or ("cpf" in t and "receita federal" in t and not any(w in t for w in ["ajuste anual", "imposto sobre a renda", "informe de rendimentos"]))):
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
    elif (re.search(r'\bementas?\b', t) and any(w in t for w in ["curso", "disciplina", "grade", "curricular", "plano de ensino", "conteúdo programático", "conteudo programatico", "bibliografia", "acadêmico", "academico"])) or any(k in t for k in ["conteúdo programático", "conteudo programatico", "plano de ensino"]):
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
    elif is_np:
        scores["Nota Promissória"] = ("financeiro", 11)
    elif any(k in t for k in ["talão de cheque", "talao de cheque", "talão de cheques", "talao de cheques"]):
        scores["Talão de Cheques"] = ("financeiro", 10)
    elif any(k in t for k in ["folha de cheque", "folhas de cheque", "pague por este cheque"]):
        scores["Folha de Cheque"] = ("financeiro", 10)
    elif any(k in t for k in ["boleto bancário", "boleto bancario", "recibo do pagador", "linha digitável", "código de barras", "ficha de compensação"]):
        scores["Boleto Bancário"] = ("financeiro", 10)
    elif any(k in t for k in ["comprovante de pagamento", "comprovante de transferência", "comprovante de transferencia", "autenticação bancária", "autenticação mecânica", "ted", "doc"]) and not is_contract_context:
        scores["Comprovante de Pagamento"] = ("financeiro", 8)
    elif any(k in t for k in ["informe de rendimentos", "informe de rendimento", "comprovante de rendimentos"]):
        scores["Informe de Rendimentos Financeiros"] = ("financeiro", 10)
    elif any(k in t for k in ["declaração de ajuste anual", "declaracao de ajuste anual", "imposto sobre a renda", "irpf"]):
        scores["Declaração de Imposto de Renda"] = ("financeiro", 10)
    elif is_rec and not is_cv:
        scores["Recibo"] = ("financeiro", 10)
    elif any(k in t for k in ["recibo de pagamento", "recebemos de"]) and not is_contract_context:
        scores["Recibo"] = ("financeiro", 7)

    # 5. Domínio: Jurídico / Outros
    if is_cv and not is_veic:
        scores["Contrato de Compra e Venda"] = ("juridico", 11)
    elif any(k in t for k in ["procuração", "procuracao", "outorgante", "outorgado"]):
        scores["Procuração"] = ("juridico", 8)
    elif any(k in t for k in ["termo de posse", "posse no cargo"]):
        scores["Termo de Posse"] = ("juridico", 8)
    elif not is_veic and any(k in t for k in ["contrato de compra e venda", "compromisso de compra", "promessa de compra"]):
        scores["Contrato de Compra e Venda"] = ("juridico", 11)
    elif any(k in t for k in ["contrato de prestação", "contrato de locação", "contrato particular", "instrumento particular", "contrato de"]):
        scores["Contrato"] = ("juridico", 9)

    # 6. Domínio: Veicular / Trânsito
    if is_veic:
        v_dom = "juridico" if "citação" in (veic_tipo or "").lower() else "veicular"
        scores[veic_tipo] = (v_dom, 13)

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

    def _exec_tess(p: str, extra_args: Optional[List[str]] = None) -> str:
        for lang in ["por+eng", "eng"]:
            try:
                cmd = ["tesseract", p, "stdout", "-l", lang]
                if extra_args:
                    cmd.extend(extra_args)
                proc = subprocess.run(
                    cmd,
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

    # Se o texto for curto ou vazio (típico de notas promissórias em papel moeda/fundo padronizado ou recibos com baixo contraste)
    if len(text.strip()) < 80 and ImageEnhance is not None:
        try:
            enh_img = ImageEnhance.Contrast(img.convert("L")).enhance(2.5)
            enh_img.save(tmp_path)
            for psm in ["6", "3"]:
                t_enh = _exec_tess(tmp_path, ["--psm", psm])
                if len(t_enh.strip()) > len(text.strip()):
                    text = t_enh
                    if len(text.strip()) >= 80:
                        break
        except Exception:
            pass

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
        with _PDFIUM_LOCK:
            pdf = None
            try:
                pdf = pdfium.PdfDocument(str(pdf_path))
                num_pages = min(len(pdf), max_pages)
                for i in range(num_pages):
                    page = pdf.get_page(i)
                    try:
                        for obj in page.get_objects():
                            if obj.type == pdfium.raw.FPDF_PAGEOBJ_IMAGE:
                                bm = None
                                try:
                                    bm = obj.get_bitmap()
                                    pil_img = bm.to_pil()
                                    if pil_img.width >= 200 and pil_img.height >= 200:
                                        t = run_tesseract_ocr_on_image(pil_img, try_rotation=True)
                                        if t and len(t) >= 15:
                                            extracted_parts.append(t)
                                finally:
                                    if bm is not None:
                                        bm.close()
                    finally:
                        page.close()
            except Exception:
                pass
            finally:
                if pdf is not None:
                    try:
                        pdf.close()
                    except Exception:
                        pass

    # 2. Se nenhuma imagem embutida foi encontrada ou se ainda não achou CPF, renderiza as páginas
    combined = "\n\n".join(extracted_parts)
    if not re.search(r"\d{3}\.?\d{3}\.?\d{3}-?\d{2}", combined):
        if pdfium is not None:
            with _PDFIUM_LOCK:
                pdf = None
                try:
                    pdf = pdfium.PdfDocument(str(pdf_path))
                    num_pages = min(len(pdf), max_pages)
                    for i in range(num_pages):
                        page = pdf.get_page(i)
                        try:
                            bitmap = page.render(scale=2.0)
                            try:
                                p_img = bitmap.to_pil()
                                t = run_tesseract_ocr_on_image(p_img, try_rotation=True)
                                if t and len(t) >= 15:
                                    extracted_parts.append(t)
                            finally:
                                bitmap.close()
                        finally:
                            page.close()
                except Exception:
                    pass
                finally:
                    if pdf is not None:
                        try:
                            pdf.close()
                        except Exception:
                            pass

    return "\n\n".join(extracted_parts).strip()





def analyze_pdf_dossier(
    pdf_path: Union[str, Path],
    max_ocr_pages: int = 25
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
        "dominio_principal": None,
        "numero_cheque": None,
        "numeros_cheque": [],
        "banco_cheque": None,
        "conta_corrente": None,
        "serie_cheque": None,
        "agencia_cheque": None,
        "numero_recibo": None,
        "exercicio_irpf": None,
        "ano_calendario": None,
        "fonte_pagadora": None,
        "cnpj_fonte_pagadora": None
    }

    if not p.exists() or pdfium is None:
        return result

    pages_info = []
    seen_tipos = []
    seen_dominios = []
    all_cheque_numbers = []
    banco_cheque = None
    conta_corrente = None
    serie_cheque = None
    agencia_cheque = None
    numero_recibo = None
    exercicio_irpf = None
    ano_calendario = None
    fonte_pagadora = None
    cnpj_fonte_pagadora = None

    with _PDFIUM_LOCK:
        pdf = None
        try:
            pdf = pdfium.PdfDocument(str(p))
            total_pages = len(pdf)
            last_tipo = None

            for i in range(total_pages):
                page = None
                p_text = ""
                embedded_texts = []
                ocr_rendered_text = ""
                page_num = i + 1

                try:
                    page = pdf.get_page(i)

                    # 1. Leitura de texto digital da página
                    try:
                        textpage = page.get_textpage()
                        try:
                            p_text = textpage.get_text_range().strip()
                        finally:
                            textpage.close()
                    except Exception:
                        p_text = ""

                    # 2. Se a página for escaneada / imagem pura sem texto digital, renderiza a página completa (respeita /Rotate e orientação)
                    if len(p_text) < 40 and i < max_ocr_pages:
                        try:
                            bitmap = page.render(scale=2.0)
                            try:
                                p_img = bitmap.to_pil()
                                ocr_rendered_text = run_tesseract_ocr_on_image(p_img, try_rotation=True)
                            finally:
                                bitmap.close()
                        except Exception:
                            pass
                    elif len(p_text) >= 40:
                        # Se já tem texto digital, mas pode conter recortes de imagem (ex: CDT/SENATRAN)
                        try:
                            for obj in page.get_objects():
                                if obj.type == pdfium.raw.FPDF_PAGEOBJ_IMAGE:
                                    bm = None
                                    try:
                                        bm = obj.get_bitmap()
                                        pil_img = bm.to_pil()
                                        if pil_img.width >= 200 and pil_img.height >= 200 and (pil_img.width < 1000 or pil_img.height < 1000):
                                            t = run_tesseract_ocr_on_image(pil_img, try_rotation=True)
                                            if t and len(t) >= 15:
                                                embedded_texts.append(t)
                                    finally:
                                        if bm is not None:
                                            bm.close()
                        except Exception:
                            pass
                finally:
                    if page is not None:
                        page.close()

                combined_page_text = "\n".join(
                    x for x in [p_text, "\n".join(embedded_texts), ocr_rendered_text] if x.strip()
                ).strip()

                if not combined_page_text:
                    continue

                is_chk_p, chk_num_p, chk_bco_p, chk_det_p = extract_cheque_signals(combined_page_text)
                is_irpf_p, irpf_tipo_p, irpf_meta_p = extract_irpf_signals(combined_page_text)
                is_inf_p, inf_tipo_p, inf_meta_p = extract_informe_rendimentos_signals(combined_page_text)
                is_veic_p, veic_tipo_p, veic_det_p = extract_veicular_signals(combined_page_text)
                is_cv_p, cv_tipo_p, cv_det_p = extract_contrato_compra_venda_signals(combined_page_text)
                is_np_p, np_tipo_p, np_det_p = extract_nota_promissoria_signals(combined_page_text)
                is_rec_p, rec_tipo_p, rec_det_p = extract_recibo_signals(combined_page_text)

                # 0. Prioridade Máxima: Regras Aprendidas pelo Usuário a partir de Páginas Conferidas
                regra_pg = None
                try:
                    regra_pg = consultar_regra_para_texto(resolve_default_db_path(), combined_page_text)
                    is_bol_p, _, _, _ = extract_boleto_signals(combined_page_text)
                    if regra_pg and is_bol_p and regra_pg.get("valor_atribuido") == "Recibo":
                        regra_pg = None
                except Exception:
                    pass

                if regra_pg and regra_pg.get("valor_atribuido"):
                    tipo = regra_pg["valor_atribuido"]
                    dom = regra_pg.get("dominio") or "academico"

                elif is_veic_p:
                    tipo = veic_tipo_p
                    dom = "juridico" if "citação" in (veic_tipo_p or "").lower() else "veicular"
                elif is_cv_p:
                    tipo = cv_tipo_p
                    dom = "juridico"
                elif is_np_p:
                    tipo = np_tipo_p
                    dom = "financeiro"
                elif is_rec_p:
                    tipo = rec_tipo_p
                    dom = "financeiro"
                elif is_chk_p:
                    tipo = "Talão de Cheques" if chk_det_p.get("is_talao") else "Folha de Cheque"
                    dom = "financeiro"
                elif is_inf_p:
                    tipo = inf_tipo_p
                    dom = "financeiro"
                elif is_irpf_p:
                    if last_tipo == "Recibo de Entrega da Declaração de Ajuste Anual":
                        tipo = "Recibo de Entrega da Declaração de Ajuste Anual"
                    else:
                        tipo = irpf_tipo_p
                    dom = "financeiro"
                else:
                    tipo, dom = classify_text_signatures(combined_page_text)


                # Continuidade de Contrato: se a página anterior era Contrato e a atual tem termos contratuais sem novo cabeçalho
                if not tipo or tipo == "Documento Diverso":
                    if last_tipo in ["Contrato de Compra e Venda", "Contrato Particular de Compra e Venda de Imóvel", "Contrato"] and \
                       any(k in combined_page_text.lower() for k in ["clausula", "cláusula", "foro", "testemunha", "cartorio", "cartório", "vendedor", "comprador", "instrumento", "eviccao", "evicção", "irrevogavel", "irrevogável"]):
                        tipo = last_tipo
                        dom = "juridico"

                if tipo and tipo != "Documento Diverso":
                    last_tipo = tipo

                if is_chk_p or (tipo and "cheque" in tipo.lower()):
                    for n in chk_det_p.get("numeros_cheque", ([chk_num_p] if chk_num_p else [])):
                        if n and n not in all_cheque_numbers:
                            all_cheque_numbers.append(n)
                    if chk_bco_p and not banco_cheque:
                        banco_cheque = chk_bco_p
                    if chk_det_p.get("conta_corrente") and not conta_corrente:
                        conta_corrente = chk_det_p["conta_corrente"]
                    if chk_det_p.get("serie_cheque") and not serie_cheque:
                        serie_cheque = chk_det_p["serie_cheque"]
                    if chk_det_p.get("agencia_cheque") and not agencia_cheque:
                        agencia_cheque = chk_det_p["agencia_cheque"]

                if is_irpf_p or irpf_meta_p:
                    if irpf_meta_p.get("numero_recibo") and not numero_recibo:
                        numero_recibo = irpf_meta_p["numero_recibo"]
                    if irpf_meta_p.get("exercicio") and not exercicio_irpf:
                        exercicio_irpf = irpf_meta_p["exercicio"]
                    if irpf_meta_p.get("ano_calendario") and not ano_calendario:
                        ano_calendario = irpf_meta_p["ano_calendario"]

                if is_inf_p or inf_meta_p:
                    if inf_meta_p.get("fonte_pagadora") and not fonte_pagadora:
                        fonte_pagadora = inf_meta_p["fonte_pagadora"]
                    if inf_meta_p.get("cnpj_fonte_pagadora") and not cnpj_fonte_pagadora:
                        cnpj_fonte_pagadora = inf_meta_p["cnpj_fonte_pagadora"]
                    if inf_meta_p.get("ano_calendario") and not ano_calendario:
                        ano_calendario = inf_meta_p["ano_calendario"]

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
        except Exception:
            return result
        finally:
            if pdf is not None:
                try:
                    pdf.close()
                except Exception:
                    pass


    # Consolidação de pacotes de IRPF: se houver páginas de Recibo de Entrega da Declaração de Ajuste Anual
    # e páginas de Declaração de Imposto de Renda contíguas, unifica como Recibo de Entrega da Declaração de Ajuste Anual
    has_recibo_irpf = any(p.get("tipo") == "Recibo de Entrega da Declaração de Ajuste Anual" for p in pages_info)
    if has_recibo_irpf:
        for p_info in pages_info:
            if p_info.get("tipo") == "Declaração de Imposto de Renda":
                p_info["tipo"] = "Recibo de Entrega da Declaração de Ajuste Anual"
        seen_tipos = [t for t in seen_tipos if t != "Declaração de Imposto de Renda"]
        if "Recibo de Entrega da Declaração de Ajuste Anual" not in seen_tipos:
            seen_tipos.insert(0, "Recibo de Entrega da Declaração de Ajuste Anual")

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
        "Dossiê Veicular",
        "Certificado de Registro de Veículo (CRV)", "Certificado de Registro e Licenciamento de Veículo (CRLV)",
        "Autorização para Transferência de Propriedade de Veículo (ATPV)",
        "Comunicação de Venda ao DETRAN", "Laudo de Vistoria Veicular", "Guia de Remoção de Veículo",
        "Nota de Arrematação (Leilão)", "Comprovante de Agendamento DETRAN",
        "CNH", "RG", "CPF", "Certidão de Nascimento", "Certidão de Casamento", "Passaporte",
        "Contrato de Compra e Venda", "Contrato Particular de Compra e Venda de Imóvel", "Contrato", "Procuração", "Termo de Posse",
        "Recibo de Entrega da Declaração de Ajuste Anual", "Declaração de Imposto de Renda", "Informe de Rendimentos Financeiros",
        "Talão de Cheques", "Folha de Cheque",
        "Comprovante PIX", "Comprovante de Pagamento", "Boleto", "Boleto Bancário", "Nota Promissória", "Recibo"
    ]

    cheque_pages = [p for p in pages_info if p.get("tipo") in ("Folha de Cheque", "Talão de Cheques")]
    veic_pages = [p for p in pages_info if p.get("dominio") == "veicular"]
    has_academic_prime = any(p["tipo"] in priority_order[:7] for p in pages_info)
    has_id_prime = any(p["tipo"] in ["CNH", "RG", "CPF", "Certidão de Nascimento", "Certidão de Casamento", "Passaporte"] for p in pages_info)

    if (len(cheque_pages) >= 2 or len(all_cheque_numbers) >= 2 or (len(cheque_pages) >= 1 and total_pages > 1 and len(cheque_pages) / max(1, len(pages_info)) >= 0.5)) and not has_academic_prime:
        tipo_principal = "Talão de Cheques"
        dominio_principal = "financeiro"
    elif len(cheque_pages) == 1 and not has_academic_prime and not has_id_prime:
        tipo_principal = "Folha de Cheque"
        dominio_principal = "financeiro"
    elif len(veic_pages) >= 2 and len(set(p.get("tipo") for p in veic_pages)) >= 2 and not has_academic_prime:
        tipo_principal = "Dossiê Veicular"
        dominio_principal = "veicular"
    elif len(veic_pages) >= 1 and not has_academic_prime and not has_id_prime:
        tipo_principal = veic_pages[0]["tipo"]
        dominio_principal = "veicular"
    else:
        for p_tipo in priority_order:
            if p_tipo in seen_tipos:
                tipo_principal = p_tipo
                break
        if not tipo_principal and seen_tipos:
            tipo_principal = seen_tipos[0]

        if tipo_principal:
            for p_info in pages_info:
                if p_info.get("tipo") == tipo_principal:
                    dominio_principal = p_info.get("dominio", dominio_principal)
                    break

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
    result["numero_cheque"] = all_cheque_numbers[0] if all_cheque_numbers else None
    result["numeros_cheque"] = all_cheque_numbers
    result["banco_cheque"] = banco_cheque
    result["conta_corrente"] = conta_corrente
    result["serie_cheque"] = serie_cheque
    result["agencia_cheque"] = agencia_cheque
    result["numero_recibo"] = numero_recibo
    result["exercicio_irpf"] = exercicio_irpf
    result["ano_calendario"] = ano_calendario
    result["fonte_pagadora"] = fonte_pagadora
    result["cnpj_fonte_pagadora"] = cnpj_fonte_pagadora

    return result


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
    * "veicular" (para Certificado de Registro de Veículo - CRV, Certificado de Registro e Licenciamento de Veículo - CRLV, Autorização para Transferência de Propriedade - ATPV, laudos de vistoria veicular, guias de remoção/pátio, comunicação de venda ao DETRAN, notas de arrematação de veículos)
    * "juridico" (para contratos, procurações, termos de posse, certidões judiciais, mandados de busca e apreensão, escrituras, petições)
    * "outro" (para quaisquer outros documentos não contemplados acima)
- "tipo_documento": Nome específico do documento. Exemplos com critérios estritos:
    * "Certificado de Registro de Veículo (CRV)" (ATENÇÃO: documento de propriedade e transferência de veículo, antigo DUT, frente e verso físico ou versão digital unificada. NUNCA confunda com CRLV e NUNCA classifique como Contrato de Compra e Venda)
    * "Certificado de Registro e Licenciamento de Veículo (CRLV)" (ATENÇÃO: documento anual de porte obrigatório para circulação do veículo, com exercício/ano e QR Code, físico ou digital unificado. NUNCA confunda com CRV e NUNCA classifique como Contrato de Compra e Venda)
    * "Autorização para Transferência de Propriedade de Veículo (ATPV)" (ATENÇÃO: autorização de transferência de veículo física ou digital/ATPV-e com comprador, vendedor e valor da venda. NUNCA classifique como Contrato de Compra e Venda)
    * "Comunicação de Venda ao DETRAN", "Laudo de Vistoria Veicular", "Guia de Remoção de Veículo", "Nota de Arrematação (Leilão)", "Comprovante de Agendamento DETRAN"
    * "Recibo de Entrega da Declaração de Ajuste Anual" / "Declaração de Imposto de Renda" (ATENÇÃO: classifique no domínio financeiro se o documento for declaração de IRPF ou recibo de entrega da Receita Federal, contendo expressões como "Imposto sobre a Renda - Pessoa Física", "Declaração de Ajuste Anual", "Recibo de Entrega", número do recibo, exercício/ano-calendário)
    * "Informe de Rendimentos Financeiros" (ATENÇÃO: classifique no domínio financeiro se o documento for um informe de rendimentos financeiros emitido por banco/instituição financeira ou comprovante de rendimentos para fins de IRPF)
    * "Talão de Cheques" / "Folha de Cheque" (ATENÇÃO: classifique como Folha de Cheque ou Talão de Cheques se o documento for uma folha ou talonário de cheque bancário, contendo expressões como "Pague por este cheque", "a quantia de", "à sua ordem", "centavos acima", número do cheque com 6 dígitos, série, agência, conta corrente ou canhotos de talão)
    * "Boleto Bancário" (ATENÇÃO: classifique categoricamente como Boleto Bancário se o documento contiver linha digitável com 47 ou 48 dígitos, código de barras FEBRABAN com 44 dígitos, termos como "ficha de compensação", "recibo do pagador/sacado", "nosso número", "pagável em qualquer banco", ou se for conta/fatura de concessionária de energia/água/serviços públicos com código de cobrança)
    * "Listagem de Pagamentos / Depósitos" (para borderôs, listagens de depósitos bancários, relações de pagamentos com tabelas ou múltiplos favorecidos)
    * "Comprovante PIX" (ATENÇÃO: classifique como PIX ESTRITAMENTE se o documento contiver expressamente o termo "PIX" ou identificador E2E padrão BACEN iniciado por 'E')
    * "Comprovante de Transferência Bancária (TED/DOC)" (para transferências bancárias entre contas sem indicação de PIX)
    * "DARF / Guia de Arrecadação Federal" (para guias de receitas federais / tributos)
    * "Contrato de Compra e Venda" (ATENÇÃO: classifique no domínio jurídico apenas se o documento for contrato particular ou escritura de compromisso/promessa de compra e venda. NUNCA classifique CRV, CRLV ou ATPV como Contrato de Compra e Venda, mesmo que contenham vendedor, comprador e valor da venda)
    * "Nota Promissória" (ATENÇÃO: classifique no domínio financeiro se o documento for nota promissória / título de crédito comercial, contendo expressões como "Nota Promissória", "por esta única via", "pagarei/pagará por esta", "vencimento", "avalista", "emitente", padrão São Domingos cód. 6091)
    * "Recibo" / "Recibo de Pagamento" (ATENÇÃO: classifique no domínio financeiro para recibos de quitação ou comprovantes de recebimento de valores)
    * "Citação de Mandado de Busca e Apreensão" (para mandados judiciais e citações)
    * "Extrato Bancário", "Cartão CNPJ / Situação Cadastral", "Diploma", "Certificado", "Histórico Escolar", "RG / Identidade", "CNH", "Contrato de Prestação de Serviços", "Declaração", "Outro". Se não puder identificar, retorne "Não identificado".

2. CAMPOS UNIVERSAIS:
- "data": Data principal do documento ou data/hora da transação (ex: "18/12/2023", "08/09/2026 14:30:00" ou "18 de dezembro de 2023"). Se não encontrar, retorne null.
- "beneficiario": Nome do titular principal, favorecido, empresa ou emitente. Se não encontrar, retorne null.
- "cpf": CPF do titular ou recebedor identificado (ex: "000.000.000-00" ou apenas números). Se não houver menção, retorne null.
- "rg": Número da Cédula de Identidade / RG do titular incluindo órgão emissor/UF (ex: "12.345.678-9 SSP/SP"). Se não houver, retorne null.
- "cnpj": CNPJ da empresa, órgão ou pagador/recebedor formatado (ex: "00.000.000/0000-00") ou apenas números. Se não houver, retorne null.
- "valor_monetario": Se for comprovante financeiro, cheque ou PIX, informe o valor monetário com 'R$' (ex: "R$ 150,00" ou "R$ 1.250,50"). Para outros documentos, retorne null.

3. CAMPOS VEICULARES (se for documento do domínio veicular, senão retorne null):
- "placa": Placa do veículo identificada no documento (ex: "MQB-4382" ou "MQB4382").
- "renavam": Código Renavam do veículo com 9 a 11 dígitos (ex: "00833434136").
- "chassi": Número de Identificação do Veículo / Chassi VIN com 17 dígitos (ex: "9C2JC30104R079694").
- "marca_modelo": Marca, modelo e versão do veículo (ex: "HONDA/CG 125 TITAN KS").
- "ano_veiculo": Ano de fabricação e modelo (ex: "2003/2004").
- "orgao_transito": Órgão executivo de trânsito emissor (ex: "DETRAN-ES", "DETRAN-SP", "SENATRAN").
- "valor_venda": Valor da venda expresso na ATPV ou nota de arrematação se houver.

4. CAMPOS ACADÊMICOS (se aplicável):
- "curso": Nome oficial do curso concluído (ex: "Pós-graduação Lato Sensu em Gestão Escolar", "Bacharelado em Administração"). Se não for curso, retorne null.
- "natureza_curso": Nível acadêmico: "Graduação / Curso Superior", "Pós-Graduação Lato Sensu (Especialização/MBA)", "Pós-Graduação Stricto Sensu (Mestrado/Doutorado)", "Curso Técnico / Profissionalizante", "Curso de Extensão / Aperfeiçoamento", "Educação Básica" ou null.
- "carga_horaria": Carga horária total (ex: "750 h/aulas", "360 horas", "750h"). Se não houver, retorne null.
- "faculdade": Nome padronizado da faculdade, universidade ou instituição de ensino no formato "Nome Completo por Extenso (SIGLA)" (ex: "Universidade de São Paulo (USP)"). Se for comprovante bancário, cheque ou PIX, informe o nome da Instituição Financeira / Banco / PSP (ex: "SICOOB", "Banco do Brasil (BB)", "Caixa Econômica Federal (CEF)"). Se for Cartão CNPJ, informe "Receita Federal do Brasil (RFB)". Se não houver, retorne null.

4. CAMPOS ESPECÍFICOS DE BOLETO / CHEQUE / PIX / FINANCEIRO (preencha se for comprovante financeiro/boleto/cheque, senão retorne null):
- "numero_cheque": Número de 6 dígitos da folha de cheque (ex: "002366") se for cheque.
- "banco_cheque": Nome do banco emissor do cheque (ex: "SICOOB", "Banco do Brasil").
- "conta_corrente": Conta corrente bancária do emitente.
- "serie_cheque": Série da folha de cheque (ex: "001").
- "linha_digitavel": Linha digitável completa do boleto bancário (ex: "00190.00009 03183.378003 00078.500170 6 12780001804302" ou "836000000099 121500513001 180131922639 000227593344"). Se não houver, retorne null.
- "codigo_barras": Código de barras numérico contínuo do boleto (44 dígitos). Se não houver, retorne null.
- "nosso_numero": Nosso Número do boleto bancário (se presente).
- "pix_pagador_nome": Nome completo do pagador da transferência.
- "pix_pagador_cpf_cnpj": CPF ou CNPJ mascarado ou completo do pagador (ex: "***.123.456-**").
- "pix_pagador_banco": Banco / PSP de origem do pagador.
- "pix_recebedor_banco": Banco / PSP de destino do recebedor.
- "pix_chave": Chave PIX utilizada (e-mail, CPF/CNPJ, telefone ou chave EVP aleatória). Não confunda com número de conta ou agência!
- "pix_e2e_id": Identificador fim-a-fim da transação (ID E2E com 32 a 40 caracteres iniciado por 'E', ex: "E00416968202609081430s0123456789"). Não confunda com CPF ou conta!
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

6. ESCRITA MANUAL / PREENCHIMENTO À MÃO (ATENÇÃO ESPECIAL):
- "manuscrito": true ou false. Defina OBRIGATORIAMENTE como true se o documento contiver escrita cursiva, manual ou se for um formulário/recibo preenchido com caneta/lápis (ex: recibos manuais de papelaria preenchidos à mão, notas promissórias, declarações de próprio punho, fichas com preenchimento manual). Caso contrário, retorne false.
- "emitente": Se for documento/recibo preenchido à mão, nome do emitente, pagador ou responsável que preencheu/assinou. Se não houver, retorne null.
- "referente_a": Finalidade, histórico ou justificativa manuscrita da operação (ex: "Serviços prestados de reforma", "Aluguel referente ao mês de janeiro"). Se não houver, retorne null.
- "conteudo_manuscrito": Transcrição fiel do conteúdo escrito à mão relevante (especialmente para declarações de próprio punho ou observações manuais). Se não houver, retorne null.

7. LEITURA E TRANSCRIÇÃO INTEGRAL (OCR COMPLETO):
- "texto_transcrito": Transcrição textual contínua e integral de TODO o conteúdo legível no documento (OCR completo de todas as páginas/imagens, incluindo parágrafos digitados, cabeçalhos, carimbos, tabelas e escrita manual). Transcreva com máxima fidelidade. Se o documento for ilegível ou sem texto visível, retorne null.

8. MÚLTIPLOS NOMES / TITULARES (LISTAGENS E RELAÇÕES):
- "nomes_detectados": Se o documento contiver uma relação, listagem, tabela de depósitos/pagamentos ou múltiplos titulares, favorecidos, alunos, clientes ou signatários, retorne um array de strings contendo TODOS os nomes completos identificados (ex: ["NOME 1", "NOME 2", ...]). Se houver apenas uma pessoa no documento, retorne [nome]. Se não houver nomes, retorne [].

REGRAS:
1. Responda APENAS o JSON válido. Sem explicações, sem comentários e sem formatação markdown fora do JSON.
2. ATENÇÃO A DOCUMENTOS PREENCHIDOS À MÃO: Leia atentamente caligrafia e números manuscritos com caneta, transcrevendo com máxima fidelidade valores, nomes, CPFs, datas e emitentes para os respectivos campos.
3. ATENÇÃO A LISTAGENS: Se for listagem ou tabela com vários nomes, extraia a lista completa em "nomes_detectados".
4. REGRA DO PIX: Não classifique como Comprovante PIX a menos que a palavra "PIX" esteja claramente presente.
5. REGRA DO BOLETO: Se o documento contiver linha digitável (47 ou 48 dígitos), código de barras (44 dígitos), ficha de compensação, recibo do sacado/pagador ou for fatura de energia/água com cobrança, classifique categoricamente como "Boleto Bancário" (domínio "financeiro") e NUNCA como PIX.
6. Não invente nenhuma informação. Se não estiver visível na imagem, preencha o valor como null.
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
    * "financeiro" (para comprovantes PIX, recibos de pagamento, transferências bancárias, boletos, extratos, notas fiscais, listagens de depósito)
    * "identificacao" (para RG, CNH, CPF, Título de Eleitor, Certidão de Nascimento/Casamento, Passaporte, Registro Profissional)
    * "profissional" (para Cartão CNPJ, Comprovante de Inscrição e Situação Cadastral, currículos, carteira de trabalho, atestados de capacidade)
    * "veicular" (para Certificado de Registro de Veículo - CRV, Certificado de Registro e Licenciamento de Veículo - CRLV, Autorização para Transferência de Propriedade - ATPV, laudos de vistoria veicular, guias de remoção/pátio, comunicação de venda ao DETRAN, notas de arrematação de veículos)
    * "juridico" (para contratos, procurações, termos de posse, certidões judiciais, mandados de busca e apreensão, escrituras, petições)
    * "outro" (para quaisquer outros documentos não contemplados acima)
- "tipo_documento": Nome específico do documento. Exemplos com critérios estritos:
    * "Certificado de Registro de Veículo (CRV)" (ATENÇÃO: documento de propriedade e transferência de veículo, antigo DUT, frente e verso físico ou versão digital unificada. NUNCA confunda com CRLV e NUNCA classifique como Contrato de Compra e Venda)
    * "Certificado de Registro e Licenciamento de Veículo (CRLV)" (ATENÇÃO: documento anual de porte obrigatório para circulação do veículo, com exercício/ano e QR Code, físico ou digital unificado. NUNCA confunda com CRV e NUNCA classifique como Contrato de Compra e Venda)
    * "Autorização para Transferência de Propriedade de Veículo (ATPV)" (ATENÇÃO: autorização de transferência de veículo física ou digital/ATPV-e com comprador, vendedor e valor da venda. NUNCA classifique como Contrato de Compra e Venda)
    * "Comunicação de Venda ao DETRAN", "Laudo de Vistoria Veicular", "Guia de Remoção de Veículo", "Nota de Arrematação (Leilão)", "Comprovante de Agendamento DETRAN"
    * "Recibo de Entrega da Declaração de Ajuste Anual" / "Declaração de Imposto de Renda" (ATENÇÃO: classifique no domínio financeiro se o documento for declaração de IRPF ou recibo de entrega da Receita Federal, contendo expressões como "Imposto sobre a Renda - Pessoa Física", "Declaração de Ajuste Anual", "Recibo de Entrega", número do recibo, exercício/ano-calendário)
    * "Informe de Rendimentos Financeiros" (ATENÇÃO: classifique no domínio financeiro se o documento for um informe de rendimentos financeiros emitido por banco/instituição financeira ou comprovante de rendimentos para fins de IRPF)
    * "Talão de Cheques" / "Folha de Cheque" (ATENÇÃO: classifique como Folha de Cheque ou Talão de Cheques se o documento for uma folha ou talonário de cheque bancário, contendo expressões como "Pague por este cheque", "a quantia de", "à sua ordem", "centavos acima", número do cheque com 6 dígitos, série, agência, conta corrente ou canhotos de talão)
    * "Boleto Bancário" (ATENÇÃO: classifique categoricamente como Boleto Bancário se o documento contiver linha digitável com 47 ou 48 dígitos, código de barras FEBRABAN com 44 dígitos, termos como "ficha de compensação", "recibo do pagador/sacado", "nosso número", "pagável em qualquer banco", ou se for conta/fatura de concessionária de energia/água/serviços públicos com código de cobrança)
    * "Listagem de Pagamentos / Depósitos" (para borderôs, listagens de depósitos bancários, relações de pagamentos com tabelas ou múltiplos favorecidos)
    * "Comprovante PIX" (ATENÇÃO: classifique como PIX ESTRITAMENTE se o documento contiver expressamente o termo "PIX" ou identificador E2E padrão BACEN iniciado por 'E')
    * "Comprovante de Transferência Bancária (TED/DOC)" (para transferências bancárias entre contas sem indicação de PIX)
    * "DARF / Guia de Arrecadação Federal" (para guias DARF, arrecadação federal, impostos federais)
    * "Contrato de Compra e Venda" (ATENÇÃO: classifique no domínio jurídico apenas se o documento for contrato particular ou escritura de compromisso/promessa de compra e venda. NUNCA classifique CRV, CRLV ou ATPV como Contrato de Compra e Venda, mesmo que contenham vendedor, comprador e valor da venda)
    * "Nota Promissória" (ATENÇÃO: classifique no domínio financeiro se o documento for nota promissória / título de crédito comercial, contendo expressões como "Nota Promissória", "por esta única via", "pagarei/pagará por esta", "vencimento", "avalista", "emitente", padrão São Domingos cód. 6091)
    * "Recibo" / "Recibo de Pagamento" (ATENÇÃO: classifique no domínio financeiro para recibos de quitação ou comprovantes de recebimento de valores)
    * "Citação de Mandado de Busca e Apreensão" (para mandados judiciais e citações)
    * "Extrato Bancário", "Cartão CNPJ / Situação Cadastral", "Diploma", "Certificado", "Histórico Escolar", "RG / Identidade", "CNH", "Contrato de Prestação de Serviços", "Declaração", "Outro". Se não puder identificar, retorne "Não identificado".

2. CAMPOS UNIVERSAIS:
- "data": Data principal do documento ou data/hora da transação (ex: "18/12/2023", "08/09/2026 14:30:00" ou "18 de dezembro de 2023"). Se não encontrar, retorne null.
- "beneficiario": Nome do titular, aluno, favorecido do pagamento ou Razão Social da empresa. Se não encontrar, retorne null.
- "cpf": CPF do titular ou recebedor identificado (ex: "000.000.000-00" ou apenas números). Se não houver menção, retorne null.
- "rg": Número da Cédula de Identidade / RG do titular incluindo órgão emissor/UF (ex: "12.345.678-9 SSP/SP"). Se não houver, retorne null.
- "cnpj": CNPJ da empresa, órgão ou pagador/recebedor formatado (ex: "00.000.000/0000-00") ou apenas números. Se não houver, retorne null.
- "valor_monetario": Se for comprovante financeiro, cheque ou PIX, informe o valor monetário com 'R$' (ex: "R$ 150,00" ou "R$ 1.250,50"). Para outros documentos, retorne null.

3. CAMPOS VEICULARES (se for documento do domínio veicular, senão retorne null):
- "placa": Placa do veículo identificada no documento (ex: "MQB-4382" ou "MQB4382").
- "renavam": Código Renavam do veículo com 9 a 11 dígitos (ex: "00833434136").
- "chassi": Número de Identificação do Veículo / Chassi VIN com 17 dígitos (ex: "9C2JC30104R079694").
- "marca_modelo": Marca, modelo e versão do veículo (ex: "HONDA/CG 125 TITAN KS").
- "ano_veiculo": Ano de fabricação e modelo (ex: "2003/2004").
- "orgao_transito": Órgão executivo de trânsito emissor (ex: "DETRAN-ES", "DETRAN-SP", "SENATRAN").
- "valor_venda": Valor da venda expresso na ATPV ou nota de arrematação se houver.

4. CAMPOS ACADÊMICOS (se aplicável):
- "curso": Nome oficial do curso concluído (ex: "Pós-graduação Lato Sensu em Gestão Escolar", "Bacharelado em Administração"). Se não for curso, retorne null.
- "natureza_curso": Nível acadêmico: "Graduação / Curso Superior", "Pós-Graduação Lato Sensu (Especialização/MBA)", "Pós-Graduação Stricto Sensu (Mestrado/Doutorado)", "Curso Técnico / Profissionalizante", "Curso de Extensão / Aperfeiçoamento", "Educação Básica" ou null.
- "carga_horaria": Carga horária total (ex: "750 h/aulas", "360 horas", "750h"). Se não houver, retorne null.
- "faculdade": Nome padronizado da faculdade, universidade ou instituição de ensino no formato "Nome Completo por Extenso (SIGLA)" (ex: "Universidade de São Paulo (USP)"). Se for comprovante bancário, cheque ou PIX, informe o nome da Instituição Financeira / Banco / PSP (ex: "SICOOB", "Banco do Brasil (BB)", "Caixa Econômica Federal (CEF)"). Se for Cartão CNPJ, informe "Receita Federal do Brasil (RFB)". Se não houver, retorne null.

4. CAMPOS ESPECÍFICOS DE BOLETO / CHEQUE / PIX / FINANCEIRO (preencha se for documento financeiro/PIX/boleto/cheque, senão retorne null):
- "numero_cheque": Número de 6 dígitos da folha de cheque (ex: "002366") se for cheque.
- "banco_cheque": Nome do banco emissor do cheque (ex: "SICOOB", "Banco do Brasil").
- "conta_corrente": Conta corrente bancária do emitente.
- "serie_cheque": Série da folha de cheque (ex: "001").
- "linha_digitavel": Linha digitável completa do boleto bancário (ex: "00190.00009 03183.378003 00078.500170 6 12780001804302" ou "836000000099 121500513001 180131922639 000227593344"). Se não houver, retorne null.
- "codigo_barras": Código de barras numérico contínuo do boleto (44 dígitos). Se não houver, retorne null.
- "nosso_numero": Nosso Número do boleto bancário (se presente).
- "pix_pagador_nome": Nome completo do pagador da transferência.
- "pix_pagador_cpf_cnpj": CPF ou CNPJ mascarado ou completo do pagador (ex: "***.123.456-**").
- "pix_pagador_banco": Banco / PSP de origem do pagador.
- "pix_recebedor_banco": Banco / PSP de destino do recebedor.
- "pix_chave": Chave PIX utilizada (e-mail, CPF/CNPJ, telefone ou chave EVP aleatória). Não confunda com conta bancária!
- "pix_e2e_id": Identificador fim-a-fim da transação (ID E2E com 32 a 40 caracteres iniciado por 'E', ex: "E00416968202609081430s0123456789"). Não confunda com CPF ou conta!
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

6. ESCRITA MANUAL / PREENCHIMENTO À MÃO:
- "manuscrito": true ou false. Defina como true se o texto indicar documento escrito ou preenchido à mão (ex: recibos preenchidos com caneta, notas promissórias, declarações de próprio punho). Caso contrário, retorne false.
- "emitente": Se for documento/recibo manual, nome do emitente ou pagador. Se não houver, retorne null.
- "referente_a": Finalidade ou justificativa da operação manuscrita. Se não houver, retorne null.
- "conteudo_manuscrito": Transcrição de trecho escrito à mão se identificado. Se não houver, retorne null.

7. LEITURA E TRANSCRIÇÃO INTEGRAL:
- "texto_transcrito": Se o documento necessitar de transcrição ou consolidação textual completa, retorne-a na íntegra. Caso contrário, retorne null.

8. MÚLTIPLOS NOMES / TITULARES (LISTAGENS E RELAÇÕES):
- "nomes_detectados": Se o documento contiver uma relação, listagem, tabela de depósitos/pagamentos ou múltiplos titulares, favorecidos, alunos, clientes ou signatários, retorne um array de strings contendo TODOS os nomes completos identificados (ex: ["NOME 1", "NOME 2", ...]). Se houver apenas uma pessoa no documento, retorne [nome]. Se não houver nomes, retorne [].

REGRAS:
1. Responda APENAS o JSON válido. Sem explicações, sem comentários e sem formatação markdown fora do JSON.
2. ATENÇÃO A DOCUMENTOS PREENCHIDOS À MÃO: Se o texto contiver dados preenchidos manualmente com caneta, transcreva com fidelidade valores, nomes e datas.
3. ATENÇÃO A LISTAGENS: Se for listagem ou tabela com vários nomes, extraia a lista completa em "nomes_detectados".
4. REGRA DO PIX: Não classifique como Comprovante PIX a menos que a palavra "PIX" esteja claramente presente.
5. REGRA DO BOLETO: Se o documento contiver linha digitável (47 ou 48 dígitos), código de barras (44 dígitos), ficha de compensação, recibo do sacado/pagador ou for fatura de energia/água com cobrança, classifique categoricamente como "Boleto Bancário" (domínio "financeiro") e NUNCA como PIX.
6. Não invente nenhuma informação. Se não estiver explícito no texto, preencha como null.
"""

# Aliases para retrocompatibilidade
build_vision_prompt = build_universal_vision_prompt
build_prompt = build_universal_prompt


def should_trigger_hybrid_fallback(doc: Dict[str, Any], text_length: int = 0) -> Tuple[bool, str]:
    """
    Avalia se um documento classificado localmente deve ser promovido para
    reclassificação na nuvem (OpenAI) no modo cascata híbrido.
    Retorna (deve_promover: bool, motivo: str).
    """
    if not doc:
        return True, "resultado_nulo"

    status = str(doc.get("status") or "").lower()
    if status == "erro":
        err_det = doc.get("motivo") or doc.get("erro") or "erro_leitura"
        return True, f"falha_leitura_local ({err_det})"

    tipo = str(doc.get("tipo_documento") or "").strip().upper()
    if not tipo or tipo in ["NÃO IDENTIFICADO", "NAO IDENTIFICADO", "OUTRO", "DESCONHECIDO", "DOCUMENTO NÃO IDENTIFICADO"]:
        return True, "tipo_documento_inconclusivo"

    dominio = str(doc.get("dominio") or "").strip().lower()

    # 1. Detecção de documento manuscrito / preenchido à mão com leitura local incompleta
    is_manuscrito = bool(
        doc.get("manuscrito")
        or any("manuscrito" in str(t).lower() or "mão" in str(t).lower() or "mao" in str(t).lower() for t in (doc.get("todos_tipos") or []))
        or "manuscrito" in tipo.lower() or "manual" in tipo.lower()
    )
    if is_manuscrito:
        tem_beneficiario = bool(str(doc.get("beneficiario") or "").strip())
        tem_valor = bool(str(doc.get("valor_monetario") or "").strip())
        tem_curso = bool(str(doc.get("curso") or "").strip())
        tem_emitente = bool(str(doc.get("emitente") or "").strip())
        if not tem_beneficiario and not tem_valor and not tem_curso and not tem_emitente:
            return True, "manuscrito_incompleto (caligrafia requer visão multimodal em nuvem)"

    if dominio == "academico" or any(k in tipo.lower() for k in ["diploma", "certificado", "histórico", "historico", "declaração", "declaracao"]):
        tem_beneficiario = bool(str(doc.get("beneficiario") or "").strip())
        tem_curso = bool(str(doc.get("curso") or "").strip())
        tem_faculdade = bool(str(doc.get("faculdade") or "").strip())
        if not tem_beneficiario:
            return True, "beneficiario_ausente (aluno/titular não identificado)"
        if not tem_curso and not tem_faculdade:
            return True, "dados_academicos_essenciais_ausentes (sem curso nem instituição)"

    elif dominio == "financeiro" or any(k in tipo.lower() for k in ["comprovante", "pagamento", "recibo", "nota fiscal", "extrato"]):
        tem_valor = bool(str(doc.get("valor_monetario") or "").strip())
        tem_beneficiario = bool(str(doc.get("beneficiario") or "").strip())
        if not tem_valor and not tem_beneficiario:
            return True, "dados_financeiros_essenciais_ausentes (sem valor nem beneficiário)"

    if text_length > 0 and text_length < 100:
        if dominio == "academico" and (not doc.get("beneficiario") or not doc.get("curso")):
            return True, "camada_textual_insuficiente"
        elif not doc.get("beneficiario") and not doc.get("valor_monetario"):
            return True, "camada_textual_insuficiente"

    return False, ""


# ---------------------------------------------------------------------------
# Processamento Universal de Documentos (PDF e Imagens PNG/JPG/JPEG/WEBP)
# ---------------------------------------------------------------------------
def process_single_pdf(
    pdf_path: Path,
    client: BaseLLMClient,
    max_pages: int = 4,
    force_ocr: bool = False,
    skip_ocr: bool = False,
    metadata: Optional[Dict[str, str]] = None,
    hybrid: bool = False,
    hybrid_cloud_client: Optional[BaseLLMClient] = None
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

        # Validação Estrita Anti-Falso Positivo de PIX (Pilar 1)
        full_text_corpus = f"{text or ''} {tess_text or ''}".lower()
        has_explicit_pix_term = bool(re.search(r'\bpix\b', full_text_corpus) or re.search(r'\bpix\b', tipo_lower))

        # Valida se pix_e2e_id é realmente um identificador E2E BACEN (iniciado por E e alfanumérico longo)
        is_genuine_e2e = bool(pix_e2e_id and re.match(r'^E\d{8}[0-9A-Za-z]{15,35}$', pix_e2e_id))
        if not is_genuine_e2e and pix_e2e_id:
            # Se for CPF ou número de conta ou lote, descarta de pix_e2e_id
            if re.match(r'^\d{11}$', pix_e2e_id) or len(pix_e2e_id) < 20:
                pix_e2e_id = None

        # Valida se pix_chave é realmente uma chave PIX legítima (não confunde com conta bancária ou agência)
        if pix_chave:
            if re.search(r'-\w$', pix_chave) or (len(pix_chave) < 9 and "@" not in pix_chave and not pix_chave.startswith("+")):
                pix_chave = None

        is_legitimate_pix = bool(has_explicit_pix_term or is_genuine_e2e)

        # 0. Consulta dinâmica de Regras Aprendidas pelo Usuário
        regra_aprendida = None
        try:
            full_doc_raw = f"{text or ''}\n{tess_text or ''}".strip()
            regra_aprendida = consultar_regra_para_texto(resolve_default_db_path(), full_doc_raw)
        except Exception:
            pass

        # 0.1 Detecção Universal e Extração de Sinais de Boleto Bancário (FEBRABAN)
        boleto_corpus = f"{text or ''}\n{tess_text or ''}".strip()
        is_boleto, boleto_linha, boleto_barras, boleto_detalhes = extract_boleto_signals(boleto_corpus)

        # 0.2 Detecção Universal e Extração de Sinais de Cheque / Talão de Cheques
        cheque_corpus = f"{text or ''}\n{tess_text or ''}".strip()
        is_cheque, cheque_num, cheque_banco, cheque_detalhes = extract_cheque_signals(cheque_corpus)

        # 0.3 Detecção Universal e Extração de Sinais de IRPF e Informe de Rendimentos
        doc_corpus = f"{text or ''}\n{tess_text or ''}".strip()
        is_irpf, irpf_tipo, irpf_det = extract_irpf_signals(doc_corpus)
        is_informe, informe_tipo, informe_det = extract_informe_rendimentos_signals(doc_corpus)
        is_cv, cv_tipo, cv_det = extract_contrato_compra_venda_signals(doc_corpus)
        is_np, np_tipo, np_det = extract_nota_promissoria_signals(doc_corpus)
        is_rec, rec_tipo, rec_det = extract_recibo_signals(doc_corpus)

        # Se a LLM já extraiu linha_digitavel ou codigo_barras no JSON, consolida
        if not boleto_linha and extracted_data.get("linha_digitavel"):
            boleto_linha = _clean_str(extracted_data.get("linha_digitavel"))
        if not boleto_barras and extracted_data.get("codigo_barras"):
            boleto_barras = _clean_str(extracted_data.get("codigo_barras"))
        if not boleto_detalhes.get("nosso_numero") and extracted_data.get("nosso_numero"):
            boleto_detalhes["nosso_numero"] = _clean_str(extracted_data.get("nosso_numero"))

        if (
            is_boleto
            or boleto_linha
            or boleto_barras
            or "boleto" in tipo_lower
            or (regra_aprendida and "boleto" in str(regra_aprendida.get("valor_atribuido") or "").lower())
        ):
            is_boleto = True
            dominio_raw = "financeiro"
            tipo_doc_raw = "Boleto Bancário"
            tipo_lower = "boleto bancário"
            is_legitimate_pix = False
            has_explicit_pix_term = False
            pix_chave = None
            pix_e2e_id = None
            pix_autenticacao = None
        elif (
            is_cheque
            or "cheque" in tipo_lower
            or "talao" in tipo_lower
            or "talão" in tipo_lower
            or (regra_aprendida and any(k in str(regra_aprendida.get("valor_atribuido") or "").lower() for k in ["cheque", "talao", "talão"]))
        ):
            is_cheque = True
            dominio_raw = "financeiro"
            is_talao_sig = cheque_detalhes.get("is_talao", False) or "talao" in tipo_lower or "talão" in tipo_lower
            tipo_doc_raw = "Talão de Cheques" if is_talao_sig else "Folha de Cheque"
            tipo_lower = tipo_doc_raw.lower()
            is_legitimate_pix = False
            has_explicit_pix_term = False
            pix_chave = None
            pix_e2e_id = None
            pix_autenticacao = None
        elif is_irpf:
            dominio_raw = "financeiro"
            tipo_doc_raw = irpf_tipo
            tipo_lower = tipo_doc_raw.lower()
            is_legitimate_pix = False
            has_explicit_pix_term = False
            pix_chave = None
            pix_e2e_id = None
            pix_autenticacao = None
        elif is_informe:
            dominio_raw = "financeiro"
            tipo_doc_raw = informe_tipo
            tipo_lower = tipo_doc_raw.lower()
            is_legitimate_pix = False
            has_explicit_pix_term = False
            pix_chave = None
            pix_e2e_id = None
            pix_autenticacao = None
        elif is_cv:
            dominio_raw = "juridico"
            tipo_doc_raw = cv_tipo or "Contrato de Compra e Venda"
            tipo_lower = tipo_doc_raw.lower()
            is_legitimate_pix = False
            has_explicit_pix_term = False
            pix_chave = None
            pix_e2e_id = None
            pix_autenticacao = None
        elif is_np:
            dominio_raw = "financeiro"
            tipo_doc_raw = np_tipo or "Nota Promissória"
            tipo_lower = tipo_doc_raw.lower()
            is_legitimate_pix = False
            has_explicit_pix_term = False
            pix_chave = None
            pix_e2e_id = None
            pix_autenticacao = None
        elif is_rec:
            dominio_raw = "financeiro"
            tipo_doc_raw = rec_tipo or "Recibo"
            tipo_lower = tipo_doc_raw.lower()
            is_legitimate_pix = False
            has_explicit_pix_term = False
            pix_chave = None
            pix_e2e_id = None
            pix_autenticacao = None
        elif regra_aprendida:
            tipo_doc_raw = regra_aprendida.get("valor_atribuido") or tipo_doc_raw
            tipo_lower = str(tipo_doc_raw).lower()
            dominio_raw = regra_aprendida.get("dominio") or dominio_raw
            if regra_aprendida.get("remover_pix"):
                is_legitimate_pix = False
                has_explicit_pix_term = False
                pix_chave = None
                pix_e2e_id = None
                pix_autenticacao = None

        # Detecção de outros tipos específicos de documentos financeiros
        is_listagem = bool(
            any(k in full_text_corpus for k in ["listagem", "depósito", "deposito", "relação", "relacao", "borderô", "bordero", "relação de depósitos", "relacao de depositos"])
            or ("titular" in full_text_corpus and "banco" in full_text_corpus and "agência" in full_text_corpus)
            or ("titular" in full_text_corpus and "banco" in full_text_corpus and "agencia" in full_text_corpus)
        )
        is_darf = bool(any(k in full_text_corpus for k in ["darf", "arrecadação", "arrecadacao", "receita federal", "ministerio da fazenda", "ministério da fazenda", "cofins", "pis/pasep"]))
        is_ted = bool(any(k in full_text_corpus for k in ["\bted\b", "\bdoc\b", "transferência bancária", "transferencia bancaria", "transferência entre contas", "transferencia entre contas"]))

        # Se foi sugerido como PIX sem conter termo 'PIX' ou E2E ID oficial, corrige a classificação
        if "pix" in tipo_lower and not is_legitimate_pix and not is_boleto and not is_cheque:
            if is_listagem:
                tipo_doc_raw = "Listagem de Pagamentos / Depósitos"
            elif is_darf:
                tipo_doc_raw = "DARF / Guia de Arrecadação Federal"
            elif is_ted:
                tipo_doc_raw = "Comprovante de Transferência Bancária (TED/DOC)"
            else:
                tipo_doc_raw = "Comprovante de Pagamento Bancário"
            tipo_lower = tipo_doc_raw.lower()
            pix_chave = None
            pix_e2e_id = None

        # Heurística inteligente para consolidação do domínio
        is_non_financial_comprovante = (
            any(k in tipo_lower for k in [
                "inscrição", "inscricao", "situação cadastral", "situacao cadastral", "cnpj",
                "residência", "residencia", "matrícula", "matricula", "votação", "votacao"
            ]) and not any(f in tipo_lower for f in ["informe de rendimentos", "rendimentos financeiros"])
        )

        has_explicit_financial = bool(
            is_boleto or
            is_cheque or
            is_irpf or
            is_informe or
            is_np or
            is_rec or
            is_legitimate_pix or
            is_listagem or
            is_darf or
            is_ted or
            "nota promissória" in tipo_lower or
            "nota promissoria" in tipo_lower or
            "recibo" in tipo_lower or
            "comprovante de pagamento" in tipo_lower or
            "comprovante de transferência" in tipo_lower or
            "comprovante de transferencia" in tipo_lower or
            "comprovante bancário" in tipo_lower or
            "comprovante bancario" in tipo_lower or
            "recibo de pagamento" in tipo_lower or
            "boleto" in tipo_lower or
            "cheque" in tipo_lower or
            "talao" in tipo_lower or
            "talão" in tipo_lower or
            "informe de rendimentos" in tipo_lower or
            "imposto de renda" in tipo_lower or
            "ajuste anual" in tipo_lower or
            ("recibo" in tipo_lower and not is_non_financial_comprovante)
        )

        has_pix_signal = bool(is_legitimate_pix and (pix_e2e_id or pix_chave or has_explicit_pix_term))

        if is_boleto:
            dominio = "financeiro"
            tipo_doc_raw = "Boleto Bancário"
        elif is_cheque:
            dominio = "financeiro"
            is_talao_sig = cheque_detalhes.get("is_talao", False) or "talao" in tipo_lower or "talão" in tipo_lower
            tipo_doc_raw = "Talão de Cheques" if is_talao_sig else "Folha de Cheque"
        elif is_irpf:
            dominio = "financeiro"
            tipo_doc_raw = irpf_tipo
        elif is_informe:
            dominio = "financeiro"
            tipo_doc_raw = informe_tipo
        elif not is_non_financial_comprovante and (has_pix_signal or has_explicit_financial or valor_raw or dominio_raw == "financeiro"):
            dominio = "financeiro"
            if not tipo_doc_raw or tipo_lower in ["não identificado", "nao identificado", "outro", "não informado", "nao informado"]:
                if has_pix_signal:
                    tipo_doc_raw = "Comprovante PIX"
                elif is_listagem:
                    tipo_doc_raw = "Listagem de Pagamentos / Depósitos"
                elif is_darf:
                    tipo_doc_raw = "DARF / Guia de Arrecadação Federal"
                elif is_ted:
                    tipo_doc_raw = "Comprovante de Transferência Bancária (TED/DOC)"
                else:
                    tipo_doc_raw = "Recibo de Pagamento"
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

        # Detecção de escrita manual / preenchimento à mão (caneta/lápis)
        is_manuscrito = bool(
            extracted_data.get("manuscrito") is True
            or str(extracted_data.get("manuscrito") or "").strip().lower() in ["true", "1", "sim", "yes"]
            or any(k in tipo_lower for k in ["manuscrito", "preenchido a mão", "preenchido à mão", "proprio punho", "próprio punho", "recibo manual", "nota promissória manual", "declaracao de proprio punho", "declaração de próprio punho"])
            or (has_text and any(k in text.lower() for k in ["preenchido a mão", "preenchido à mão", "de próprio punho", "de proprio punho"]))
            or (tess_text and any(k in tess_text.lower() for k in ["preenchido a mão", "preenchido à mão", "de próprio punho", "de proprio punho"]))
        )

        if "dados_extras" not in res_dict or not isinstance(res_dict["dados_extras"], dict):
            res_dict["dados_extras"] = {}

        # Atribuição e consolidação dos campos de Boleto Bancário
        if is_boleto:
            if boleto_linha:
                res_dict["linha_digitavel"] = boleto_linha
                res_dict["dados_extras"]["linha_digitavel"] = boleto_linha
            if boleto_barras:
                res_dict["codigo_barras"] = boleto_barras
                res_dict["dados_extras"]["codigo_barras"] = boleto_barras
            if boleto_detalhes.get("nosso_numero"):
                res_dict["nosso_numero"] = boleto_detalhes["nosso_numero"]
                res_dict["dados_extras"]["nosso_numero"] = boleto_detalhes["nosso_numero"]

        # Atribuição e consolidação dos campos de Cheque / Talão de Cheques
        if is_cheque or cheque_num or cheque_banco:
            if cheque_num:
                res_dict["dados_extras"]["numero_cheque"] = cheque_num
            if cheque_detalhes.get("numeros_cheque"):
                res_dict["dados_extras"]["numeros_cheque"] = cheque_detalhes["numeros_cheque"]
            if cheque_banco or cheque_detalhes.get("banco_cheque"):
                b_chk = cheque_banco or cheque_detalhes.get("banco_cheque")
                res_dict["dados_extras"]["banco_cheque"] = b_chk
                if not res_dict.get("faculdade"):
                    res_dict["faculdade"] = b_chk
            if cheque_detalhes.get("serie_cheque"):
                res_dict["dados_extras"]["serie_cheque"] = cheque_detalhes["serie_cheque"]
            if cheque_detalhes.get("agencia_cheque"):
                res_dict["dados_extras"]["agencia_cheque"] = cheque_detalhes["agencia_cheque"]
            if cheque_detalhes.get("conta_corrente"):
                res_dict["dados_extras"]["conta_corrente"] = cheque_detalhes["conta_corrente"]

        # Atribuição e consolidação dos campos de IRPF e Informe de Rendimentos
        if is_irpf or irpf_det:
            if irpf_det.get("numero_recibo"):
                res_dict["dados_extras"]["numero_recibo"] = irpf_det["numero_recibo"]
            if irpf_det.get("exercicio"):
                res_dict["dados_extras"]["exercicio"] = irpf_det["exercicio"]
                res_dict["dados_extras"]["exercicio_irpf"] = irpf_det["exercicio"]
            if irpf_det.get("ano_calendario"):
                res_dict["dados_extras"]["ano_calendario"] = irpf_det["ano_calendario"]
            if irpf_det.get("total_rendimentos_tributaveis"):
                res_dict["dados_extras"]["total_rendimentos_tributaveis"] = irpf_det["total_rendimentos_tributaveis"]
            if not res_dict.get("faculdade"):
                res_dict["faculdade"] = "Secretaria da Receita Federal do Brasil (RFB)"

        if is_informe or informe_det:
            if informe_det.get("fonte_pagadora"):
                res_dict["dados_extras"]["fonte_pagadora"] = informe_det["fonte_pagadora"]
                if not res_dict.get("faculdade"):
                    res_dict["faculdade"] = informe_det["fonte_pagadora"]
            if informe_det.get("cnpj_fonte_pagadora"):
                res_dict["dados_extras"]["cnpj_fonte_pagadora"] = informe_det["cnpj_fonte_pagadora"]
            if informe_det.get("ano_calendario") and not res_dict["dados_extras"].get("ano_calendario"):
                res_dict["dados_extras"]["ano_calendario"] = informe_det["ano_calendario"]

        if is_manuscrito:
            res_dict["manuscrito"] = True
            res_dict["dados_extras"]["manuscrito"] = True

        emitente_val = _clean_str(extracted_data.get("emitente"))
        if emitente_val:
            res_dict["emitente"] = emitente_val
            res_dict["dados_extras"]["emitente"] = emitente_val

        referente_val = _clean_str(extracted_data.get("referente_a"))
        if referente_val:
            res_dict["referente_a"] = referente_val
            res_dict["dados_extras"]["referente_a"] = referente_val

        conteudo_manuscrito_val = _clean_str(extracted_data.get("conteudo_manuscrito"))
        if conteudo_manuscrito_val:
            res_dict["conteudo_manuscrito"] = conteudo_manuscrito_val
            res_dict["dados_extras"]["conteudo_manuscrito"] = conteudo_manuscrito_val

        # Captura e higienização da transcrição textual integral (OCR / Leitura Completa)
        raw_transcrito = _clean_str(
            extracted_data.get("texto_transcrito")
            or extracted_data.get("texto_ocr")
            or extracted_data.get("transcricao_completa")
        )
        sanitized_transcrito = sanitize_llm_transcription(raw_transcrito) if raw_transcrito else None
        if sanitized_transcrito:
            res_dict["texto_transcrito"] = sanitized_transcrito
            res_dict["dados_extras"]["texto_transcrito"] = sanitized_transcrito

        if text and text.strip():
            res_dict["dados_extras"]["texto_digital"] = text.strip()
        if tess_text and tess_text.strip():
            res_dict["dados_extras"]["texto_tesseract"] = tess_text.strip()

        # Extração e Consolidação de Múltiplos Nomes / Titulares (Pilar 3)
        detected_names_list: List[str] = []
        raw_llm_names = extracted_data.get("nomes_detectados")
        if isinstance(raw_llm_names, list):
            for nm in raw_llm_names:
                if isinstance(nm, str) and len(nm.strip()) >= 3:
                    c_nm = re.sub(r'\s+', ' ', nm).strip()
                    if c_nm not in detected_names_list:
                        detected_names_list.append(c_nm)
        elif isinstance(raw_llm_names, str) and len(raw_llm_names.strip()) >= 3:
            detected_names_list.append(raw_llm_names.strip())

        heur_names = []
        if has_text:
            heur_names.extend(extract_names_from_document_text(text))
        if tess_text:
            heur_names.extend(extract_names_from_document_text(tess_text))

        for hn in heur_names:
            if hn not in detected_names_list:
                detected_names_list.append(hn)

        benef_curr = res_dict.get("beneficiario")
        if benef_curr and benef_curr not in detected_names_list and len(benef_curr.split()) >= 2:
            detected_names_list.insert(0, benef_curr)
        elif not benef_curr and detected_names_list:
            res_dict["beneficiario"] = detected_names_list[0]

        if detected_names_list:
            res_dict["nomes_detectados"] = detected_names_list
            res_dict["dados_extras"]["nomes_detectados"] = detected_names_list

        # Consolidação de quaisquer atributos adicionais da LLM em dados_extras
        known_top_level = {
            "dominio", "tipo_documento", "data", "beneficiario", "cpf", "rg", "cnpj",
            "valor_monetario", "curso", "natureza_curso", "carga_horaria", "faculdade",
            "pix_pagador_nome", "pix_pagador_cpf_cnpj", "pix_pagador_banco", "pix_recebedor_banco",
            "pix_chave", "pix_e2e_id", "pix_autenticacao", "razao_social", "nome_fantasia",
            "situacao_cadastral", "data_situacao", "data_abertura", "cnae_principal",
            "natureza_juridica", "endereco_completo", "telefone", "email", "manuscrito",
            "emitente", "referente_a", "conteudo_manuscrito", "texto_transcrito", "texto_ocr",
            "transcricao_completa", "nomes_detectados", "dados_extras"
        }
        for k_dyn, v_dyn in extracted_data.items():
            if k_dyn not in known_top_level and v_dyn is not None:
                v_clean = _clean_str(v_dyn) if isinstance(v_dyn, str) else v_dyn
                if v_clean not in [None, "", "null", "N/A", "none"]:
                    res_dict["dados_extras"][k_dyn] = v_clean
                    res_dict[k_dyn] = v_clean

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
                            if ocr_data.get("manuscrito"):
                                res_dict["manuscrito"] = True
                                if "dados_extras" in res_dict and isinstance(res_dict["dados_extras"], dict):
                                    res_dict["dados_extras"]["manuscrito"] = True
                            if not res_dict.get("emitente") and ocr_data.get("emitente"):
                                res_dict["emitente"] = _clean_str(ocr_data.get("emitente"))
                                res_dict["dados_extras"]["emitente"] = res_dict["emitente"]
                            if not res_dict.get("referente_a") and ocr_data.get("referente_a"):
                                res_dict["referente_a"] = _clean_str(ocr_data.get("referente_a"))
                                res_dict["dados_extras"]["referente_a"] = res_dict["referente_a"]
                            if not res_dict.get("conteudo_manuscrito") and ocr_data.get("conteudo_manuscrito"):
                                res_dict["conteudo_manuscrito"] = _clean_str(ocr_data.get("conteudo_manuscrito"))
                                res_dict["dados_extras"]["conteudo_manuscrito"] = res_dict["conteudo_manuscrito"]
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
                dossier = analyze_pdf_dossier(pdf_path, max_ocr_pages=max(max_pages, 25))
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

                if is_boleto:
                    res_dict["tipo_documento"] = "Boleto Bancário"
                    res_dict["dominio"] = "financeiro"
                    if "Boleto Bancário" not in todos_tipos:
                        todos_tipos.insert(0, "Boleto Bancário")
                    else:
                        todos_tipos.remove("Boleto Bancário")
                        todos_tipos.insert(0, "Boleto Bancário")
                    if "financeiro" not in todos_dominios:
                        todos_dominios.insert(0, "financeiro")
                elif dossier.get("tipo_documento_principal") in ("Talão de Cheques", "Folha de Cheque") or is_cheque:
                    tag_chk = dossier.get("tipo_documento_principal") or ("Talão de Cheques" if cheque_detalhes.get("is_talao") else "Folha de Cheque")
                    res_dict["tipo_documento"] = tag_chk
                    res_dict["dominio"] = "financeiro"
                    if tag_chk not in todos_tipos:
                        todos_tipos.insert(0, tag_chk)
                    else:
                        todos_tipos.remove(tag_chk)
                        todos_tipos.insert(0, tag_chk)
                    if "financeiro" not in todos_dominios:
                        todos_dominios.insert(0, "financeiro")
                    # Remove false PIX remnants
                    res_dict["pix_chave"] = None
                    res_dict["pix_e2e_id"] = None
                    res_dict["pix_autenticacao"] = None
                    for k_pix in ["pix_chave", "pix_e2e_id", "pix_autenticacao", "pix_pagador_nome", "pix_pagador_cpf_cnpj", "pix_pagador_banco", "pix_recebedor_banco", "pix_recebedor_nome", "pix_recebedor_cpf_cnpj"]:
                        res_dict.pop(k_pix, None)
                        if "dados_extras" in res_dict and isinstance(res_dict["dados_extras"], dict):
                            res_dict["dados_extras"].pop(k_pix, None)
                elif is_irpf or is_informe or (dossier.get("tipo_documento_principal") and ("imposto de renda" in dossier.get("tipo_documento_principal").lower() or "recibo de entrega" in dossier.get("tipo_documento_principal").lower() or "informe de rendimentos" in dossier.get("tipo_documento_principal").lower())):
                    tag_ir = (irpf_tipo if is_irpf else (informe_tipo if is_informe else None)) or dossier.get("tipo_documento_principal") or "Declaração de Imposto de Renda"
                    res_dict["tipo_documento"] = tag_ir
                    res_dict["dominio"] = "financeiro"
                    if tag_ir not in todos_tipos:
                        todos_tipos.insert(0, tag_ir)
                    if "financeiro" not in todos_dominios:
                        todos_dominios.insert(0, "financeiro")
                    # Remove false PIX remnants
                    res_dict["pix_chave"] = None
                    res_dict["pix_e2e_id"] = None
                    res_dict["pix_autenticacao"] = None
                    for k_pix in ["pix_chave", "pix_e2e_id", "pix_autenticacao", "pix_pagador_nome", "pix_pagador_cpf_cnpj", "pix_pagador_banco", "pix_recebedor_banco", "pix_recebedor_nome", "pix_recebedor_cpf_cnpj"]:
                        res_dict.pop(k_pix, None)
                        if "dados_extras" in res_dict and isinstance(res_dict["dados_extras"], dict):
                            res_dict["dados_extras"].pop(k_pix, None)
                elif is_cv or (dossier.get("tipo_documento_principal") and ("compra e venda" in dossier.get("tipo_documento_principal").lower() or "contrato" in dossier.get("tipo_documento_principal").lower())):
                    tag_cv = (cv_tipo if is_cv else None) or dossier.get("tipo_documento_principal") or "Contrato de Compra e Venda"
                    res_dict["tipo_documento"] = tag_cv
                    res_dict["dominio"] = "juridico"
                    if tag_cv not in todos_tipos:
                        todos_tipos.insert(0, tag_cv)
                    if "juridico" not in todos_dominios:
                        todos_dominios.insert(0, "juridico")
                elif is_np or (dossier.get("tipo_documento_principal") and "promissória" in dossier.get("tipo_documento_principal").lower()):
                    tag_np = (np_tipo if is_np else None) or dossier.get("tipo_documento_principal") or "Nota Promissória"
                    res_dict["tipo_documento"] = tag_np
                    res_dict["dominio"] = "financeiro"
                    if tag_np not in todos_tipos:
                        todos_tipos.insert(0, tag_np)
                    if "financeiro" not in todos_dominios:
                        todos_dominios.insert(0, "financeiro")
                elif is_rec or (dossier.get("tipo_documento_principal") and "recibo" in dossier.get("tipo_documento_principal").lower()):
                    tag_rec = (rec_tipo if is_rec else None) or dossier.get("tipo_documento_principal") or "Recibo"
                    res_dict["tipo_documento"] = tag_rec
                    res_dict["dominio"] = "financeiro"
                    if tag_rec not in todos_tipos:
                        todos_tipos.insert(0, tag_rec)
                    if "financeiro" not in todos_dominios:
                        todos_dominios.insert(0, "financeiro")

                # Consolida campos de cheque vindos do dossier
                if dossier.get("numero_cheque") and "numero_cheque" not in res_dict.get("dados_extras", {}):
                    res_dict.setdefault("dados_extras", {})["numero_cheque"] = dossier["numero_cheque"]
                if dossier.get("numeros_cheque"):
                    res_dict.setdefault("dados_extras", {})["numeros_cheque"] = dossier["numeros_cheque"]
                if dossier.get("banco_cheque"):
                    res_dict.setdefault("dados_extras", {})["banco_cheque"] = dossier["banco_cheque"]
                    if not res_dict.get("faculdade"):
                        res_dict["faculdade"] = dossier["banco_cheque"]
                if dossier.get("conta_corrente") and "conta_corrente" not in res_dict.get("dados_extras", {}):
                    res_dict.setdefault("dados_extras", {})["conta_corrente"] = dossier["conta_corrente"]
                if dossier.get("serie_cheque") and "serie_cheque" not in res_dict.get("dados_extras", {}):
                    res_dict.setdefault("dados_extras", {})["serie_cheque"] = dossier["serie_cheque"]
                if dossier.get("agencia_cheque") and "agencia_cheque" not in res_dict.get("dados_extras", {}):
                    res_dict.setdefault("dados_extras", {})["agencia_cheque"] = dossier["agencia_cheque"]

                # Consolida campos de IRPF e Informe vindos do dossier
                if dossier.get("numero_recibo") and "numero_recibo" not in res_dict.get("dados_extras", {}):
                    res_dict.setdefault("dados_extras", {})["numero_recibo"] = dossier["numero_recibo"]
                if dossier.get("exercicio_irpf") and "exercicio" not in res_dict.get("dados_extras", {}):
                    res_dict.setdefault("dados_extras", {})["exercicio"] = dossier["exercicio_irpf"]
                    res_dict.setdefault("dados_extras", {})["exercicio_irpf"] = dossier["exercicio_irpf"]
                if dossier.get("ano_calendario") and "ano_calendario" not in res_dict.get("dados_extras", {}):
                    res_dict.setdefault("dados_extras", {})["ano_calendario"] = dossier["ano_calendario"]
                if dossier.get("fonte_pagadora") and "fonte_pagadora" not in res_dict.get("dados_extras", {}):
                    res_dict.setdefault("dados_extras", {})["fonte_pagadora"] = dossier["fonte_pagadora"]
                    if not res_dict.get("faculdade"):
                        is_doc_irpf = is_irpf or any(k in (res_dict.get("tipo_documento") or "").lower() for k in ["ajuste anual", "imposto de renda"])
                        if not is_doc_irpf:
                            res_dict["faculdade"] = dossier["fonte_pagadora"]
                        else:
                            res_dict["faculdade"] = "Secretaria da Receita Federal do Brasil (RFB)"
                if dossier.get("cnpj_fonte_pagadora") and "cnpj_fonte_pagadora" not in res_dict.get("dados_extras", {}):
                    res_dict.setdefault("dados_extras", {})["cnpj_fonte_pagadora"] = dossier["cnpj_fonte_pagadora"]

                res_dict["todos_tipos"] = todos_tipos if todos_tipos else ([prim_tipo] if prim_tipo else [])
                res_dict["todos_dominios"] = todos_dominios if todos_dominios else ([prim_dom] if prim_dom else [])
                res_dict["dossie_paginas"] = dossier.get("dossie_paginas", [])
            except Exception:
                prim_tipo = res_dict.get("tipo_documento")
                prim_dom = res_dict.get("dominio")
                if is_boleto:
                    prim_tipo = "Boleto Bancário"
                    prim_dom = "financeiro"
                elif is_cheque:
                    prim_tipo = "Talão de Cheques" if cheque_detalhes.get("is_talao") else "Folha de Cheque"
                    prim_dom = "financeiro"
                elif is_irpf:
                    prim_tipo = irpf_tipo
                    prim_dom = "financeiro"
                elif is_informe:
                    prim_tipo = informe_tipo
                    prim_dom = "financeiro"
                res_dict["todos_tipos"] = [prim_tipo] if prim_tipo else []
                res_dict["todos_dominios"] = [prim_dom] if prim_dom else []
                res_dict["dossie_paginas"] = []
        else:
            prim_tipo = res_dict.get("tipo_documento")
            prim_dom = res_dict.get("dominio")
            if is_boleto:
                prim_tipo = "Boleto Bancário"
                prim_dom = "financeiro"
            elif is_cheque:
                prim_tipo = "Talão de Cheques" if cheque_detalhes.get("is_talao") else "Folha de Cheque"
                prim_dom = "financeiro"
            elif is_irpf:
                prim_tipo = irpf_tipo
                prim_dom = "financeiro"
            elif is_informe:
                prim_tipo = informe_tipo
                prim_dom = "financeiro"
            res_dict["todos_tipos"] = [prim_tipo] if prim_tipo else []
            res_dict["todos_dominios"] = [prim_dom] if prim_dom else []
            res_dict["dossie_paginas"] = [{"pagina": 1, "tipo": prim_tipo or "Documento", "dominio": prim_dom or "outros"}]

        # Se for identificado como manuscrito ou preenchido à mão, adiciona a tag "Manuscrito"
        if res_dict.get("manuscrito"):
            tem_tag_man = any("manuscrito" in str(t).lower() or "mão" in str(t).lower() or "mao" in str(t).lower() for t in res_dict.get("todos_tipos", []))
            if not tem_tag_man:
                res_dict["todos_tipos"].append("Manuscrito")

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
            res_dict.get("linha_digitavel"),
            res_dict.get("codigo_barras"),
            res_dict.get("nosso_numero"),
            res_dict.get("pix_pagador_nome"),
            res_dict.get("pix_e2e_id"),
            res_dict.get("emitente"),
            res_dict.get("referente_a"),
            res_dict.get("conteudo_manuscrito")
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

    # -------------------------------------------------------------------------
    # MODO HÍBRIDO EM CASCATA: Fallback para Modelo de Nuvem (Item 4)
    # -------------------------------------------------------------------------
    if hybrid and hybrid_cloud_client is not None:
        raw_text_len = len(text.strip()) if ('text' in locals() and text and isinstance(text, str)) else 0
        if raw_text_len == 0 and 'tess_text' in locals() and tess_text and isinstance(tess_text, str):
            raw_text_len = len(tess_text.strip())

        should_fallback, reason = should_trigger_hybrid_fallback(res_dict, text_length=raw_text_len)
        if should_fallback:
            try:
                cloud_doc = process_single_pdf(
                    pdf_path=pdf_path,
                    client=hybrid_cloud_client,
                    max_pages=max_pages,
                    force_ocr=True,
                    skip_ocr=False,
                    metadata=meta,
                    hybrid=False,  # Evita recursão infinita
                    hybrid_cloud_client=None
                )
                cloud_doc["metodo_leitura"] = "hibrido_fallback_openai"
                cloud_doc["provedor_primario"] = getattr(client, "provider", "ollama")
                cloud_doc["provedor_final"] = "openai"
                cloud_doc["motivo_fallback"] = reason
                return cloud_doc
            except Exception as ex_cloud:
                res_dict["erro_fallback_nuvem"] = str(ex_cloud)

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
    if isinstance(de, str):
        try:
            de = json.loads(de)
        except Exception:
            de = {}

    lines = [
        "-" * 80,
        f"MD5                     : {item.get('md5')}",
        f"Status                  : {str(item.get('status', '')).upper()}",
        f"Domínio                 : {dom.upper()}",
        f"Tipo Documento          : {item.get('tipo_documento') or 'Não identificado'}{dossie_line}",
        f"Extensão                : {ext.upper() if ext else 'N/A'}",
        f"Método de Leitura       : {metodo}",
        f"Data da Última Alteração: {item.get('data_modificacao') or 'N/A'}",
    ]

    # REGRA ZERO NOISE: Somente inclui campos que realmente possuem valor substantivo
    def _add_if_val(label: str, val: Any):
        if val is None:
            return
        s_val = str(val).strip()
        if not s_val or s_val.lower() in [
            "não informado", "não identificada", "não identificado",
            "nao informado", "nao identificada", "nao identificado",
            "none", "null", "n/a", "-", "--"
        ]:
            return
        lines.append(f"{label:<24}: {s_val}")

    _add_if_val("dc:creator", item.get("autor"))
    _add_if_val("dc:title", item.get("dc_title"))
    _add_if_val("dc:tool", item.get("dc_creator_tool"))
    _add_if_val("Beneficiário / Titular", item.get("beneficiario"))
    _add_if_val("CPF", item.get("cpf"))
    _add_if_val("RG / Identidade", item.get("rg"))
    _add_if_val("CNPJ", item.get("cnpj") or de.get("cnpj"))
    _add_if_val("Valor Monetário", item.get("valor_monetario"))
    _add_if_val("Data do Documento", item.get("data"))
    _add_if_val("Instituição / Faculdade", item.get("faculdade"))

    if dom == "academico":
        _add_if_val("Curso", item.get("curso"))
        _add_if_val("Natureza do Curso", item.get("natureza_curso"))
        _add_if_val("Carga Horária", item.get("carga_horaria"))
    elif dom == "financeiro":
        _add_if_val("Número do Cheque", de.get("numero_cheque"))
        if de.get("numeros_cheque") and len(de.get("numeros_cheque")) > 1:
            amostra_chk = ", ".join(str(n) for n in de["numeros_cheque"][:8])
            if len(de["numeros_cheque"]) > 8:
                amostra_chk += f" ... (+{len(de['numeros_cheque']) - 8} cheques)"
            _add_if_val("Cheques no Talão", f"{amostra_chk} (Total: {len(de['numeros_cheque'])})")
        _add_if_val("Banco do Cheque", de.get("banco_cheque"))
        _add_if_val("Série do Cheque", de.get("serie_cheque"))
        _add_if_val("Agência", de.get("agencia_cheque"))
        _add_if_val("Conta Corrente", de.get("conta_corrente"))
        _add_if_val("Pagador", item.get("pix_pagador_nome"))
        _add_if_val("CPF/CNPJ do Pagador", item.get("pix_pagador_cpf_cnpj"))
        _add_if_val("Banco Origem (Pagador)", item.get("pix_pagador_banco"))
        _add_if_val("Banco Destino (Receb.)", item.get("pix_recebedor_banco"))
        _add_if_val("Chave PIX", item.get("pix_chave"))
        _add_if_val("ID Fim-a-Fim (E2E)", item.get("pix_e2e_id"))
        _add_if_val("Autenticação Bancária", item.get("pix_autenticacao"))
    elif dom == "profissional":
        _add_if_val("Razão Social", de.get("razao_social") or item.get("beneficiario"))
        _add_if_val("Nome Fantasia", de.get("nome_fantasia"))
        _add_if_val("Situação Cadastral", de.get("situacao_cadastral"))
        _add_if_val("Data da Situação", de.get("data_situacao"))
        _add_if_val("Data de Abertura", de.get("data_abertura"))
        _add_if_val("CNAE Principal", de.get("cnae_principal"))
        _add_if_val("Natureza Jurídica", de.get("natureza_juridica"))
        _add_if_val("Endereço Completo", de.get("endereco_completo"))
        _add_if_val("Telefone", de.get("telefone"))
        _add_if_val("E-mail", de.get("email"))
    elif dom == "veicular":
        _add_if_val("Placa", de.get("placa"))
        _add_if_val("Renavam", de.get("renavam"))
        _add_if_val("Chassi", de.get("chassi"))
        _add_if_val("Marca / Modelo", de.get("marca_modelo"))
        _add_if_val("Ano Fab / Modelo", de.get("ano_fabricacao_modelo") or de.get("ano_veiculo"))
        _add_if_val("Órgão de Trânsito", de.get("orgao_transito") or item.get("faculdade"))
        _add_if_val("Proprietário / Vendedor", de.get("vendedor") or de.get("proprietario_anterior") or item.get("beneficiario"))
        _add_if_val("Comprador", de.get("comprador"))

    # Dados de manuscrito
    if de.get("manuscrito") or item.get("manuscrito"):
        _add_if_val("Preenchimento Manual", "Sim (Documento manuscrito)")
        _add_if_val("Emitente / Assinante", de.get("emitente") or item.get("emitente"))
        _add_if_val("Referente a", de.get("referente_a") or item.get("referente_a"))
        _add_if_val("Conteúdo Manuscrito", de.get("conteudo_manuscrito") or item.get("conteudo_manuscrito"))

    # Múltiplos Nomes Detectados (Listagens e Relações)
    nomes_det = item.get("nomes_detectados") or de.get("nomes_detectados")
    if isinstance(nomes_det, list) and len(nomes_det) > 1:
        amostra = ", ".join(str(n) for n in nomes_det[:6])
        if len(nomes_det) > 6:
            amostra += f" ... (+{len(nomes_det) - 6} nomes)"
        _add_if_val("Titulares / Nomes Det.", f"{amostra} (Total: {len(nomes_det)})")

    # Outros campos dinâmicos em dados_extras
    ignore_keys = {
        "razao_social", "nome_fantasia", "situacao_cadastral", "data_situacao",
        "data_abertura", "cnae_principal", "natureza_juridica", "endereco_completo",
        "telefone", "email", "manuscrito", "emitente", "referente_a", "conteudo_manuscrito",
        "texto_transcrito", "texto_ocr", "texto_digital", "texto_tesseract", "transcricao_completa",
        "nomes_detectados", "dossie_paginas", "todos_dominios", "todos_tipos", "data_criacao",
        "numero_cheque", "numeros_cheque", "banco_cheque", "serie_cheque", "agencia_cheque", "conta_corrente",
        "placa", "renavam", "chassi", "marca_modelo", "ano_fabricacao_modelo", "ano_veiculo",
        "orgao_transito", "vendedor", "proprietario_anterior", "comprador", "cnpj"
    }
    for k, v in de.items():
        if k not in ignore_keys:
            label = k.replace("_", " ").title()
            _add_if_val(label, v)

    _add_if_val("Processado em", item.get("processado_em"))
    if item.get("erro"):
        lines.append(f"Erro                    : {item.get('erro')}")

    lines.append("-" * 80)

    # Hierarquia de Verdade Textual (Ground Truth First):
    # 1. Camada Digital Nativa -> 2. Tesseract OCR -> 3. Transcrição IA Sanitizada
    texto_puro = None
    if de.get("texto_digital") and len(str(de.get("texto_digital")).strip()) >= 30:
        texto_puro = str(de.get("texto_digital")).strip()
    elif de.get("texto_tesseract") and len(str(de.get("texto_tesseract")).strip()) >= 30:
        texto_puro = str(de.get("texto_tesseract")).strip()
    else:
        raw_t = de.get("texto_transcrito") or de.get("texto_ocr") or item.get("texto_transcrito")
        clean_t = sanitize_llm_transcription(str(raw_t)) if raw_t else None
        if clean_t:
            texto_puro = clean_t
        elif de.get("texto_digital") and str(de.get("texto_digital")).strip():
            texto_puro = str(de.get("texto_digital")).strip()
        elif de.get("texto_tesseract") and str(de.get("texto_tesseract")).strip():
            texto_puro = str(de.get("texto_tesseract")).strip()

    if texto_puro:
        lines.append("\n" + "=" * 80)
        lines.append("TEXTO INTEGRAL / TRANSCRIÇÃO OCR")
        lines.append("=" * 80)
        lines.append(texto_puro)
        lines.append("\n" + "-" * 80)

    return "\n".join(lines) + "\n"


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
            resp_prov = input("Escolha o provedor (1 ou 2) [1]: ").strip()
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
    client: Optional[Any] = None,
    hybrid: bool = False,
    hybrid_cloud_model: str = "gpt-4o-mini",
    hybrid_openai_key: Optional[str] = None,
    hybrid_openai_base_url: Optional[str] = None
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

    # Inicialização do Cliente Cloud para Modo Híbrido se ativo
    hybrid_cloud_client = None
    if hybrid:
        cloud_key = hybrid_openai_key or openai_key or os.environ.get("OPENAI_API_KEY")
        if not cloud_key:
            print("[*] [Aviso Híbrido] Modo híbrido ativado, mas nenhuma chave da OpenAI foi configurada. Modo híbrido desativado.")
            hybrid = False
        else:
            cloud_mod = hybrid_cloud_model or "gpt-4o-mini"
            cloud_base = hybrid_openai_base_url or openai_base_url or os.environ.get("OPENAI_BASE_URL")
            print(f"[*] [Modo Híbrido Ativado] Fallback configurado para OpenAI ({cloud_mod}).")
            try:
                hybrid_cloud_client = OpenAIClient(
                    model=cloud_mod,
                    api_key=cloud_key,
                    base_url=cloud_base
                )
            except Exception as ex_init_h:
                print(f"[*] [Aviso Híbrido] Falha ao inicializar cliente de fallback OpenAI ({ex_init_h}). Modo híbrido desativado.")
                hybrid = False

    if provider == "ollama" and workers > 2:
        print(f"[*] [Dica de Performance] Executando Ollama local com {workers} workers. Em GPUs domésticas (12GB VRAM), recomenda-se 1 ou 2 workers para evitar fila de inferência.")

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
                metadata=meta,
                hybrid=hybrid,
                hybrid_cloud_client=hybrid_cloud_client
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
    # Subcomando 'server' ou 'web' para iniciar a interface gráfica
    if len(sys.argv) > 1 and sys.argv[1].lower() in ["server", "web", "servidor"]:
        server_args = sys.argv[2:]
        try:
            from joakindex.server import main as server_main
        except ImportError:
            try:
                from .server import main as server_main
            except ImportError:
                sys.path.insert(0, str(Path(__file__).resolve().parent))
                import joakindex_server
                server_main = joakindex_server.main
        sys.exit(server_main(server_args))

    parser = argparse.ArgumentParser(
        prog="joakindex",
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
    parser.add_argument(
        "--hibrido", "--hybrid",
        dest="hybrid",
        action="store_true",
        default=False,
        help="Ativa o modo cascata híbrido: tenta primeiro modelo local e faz fallback para OpenAI se inconclusivo (padrão: %(default)s)."
    )
    parser.add_argument(
        "--no-hibrido", "--no-hybrid",
        dest="hybrid",
        action="store_false",
        help="Desativa forçadamente o modo cascata híbrido."
    )
    parser.add_argument(
        "--hybrid-cloud-model",
        dest="hybrid_cloud_model",
        type=str,
        default="gpt-4o-mini",
        help="Modelo OpenAI para fallback no modo híbrido (padrão: %(default)s)."
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
        hybrid=saved_cfg.get("hybrid", False),
        hybrid_cloud_model=saved_cfg.get("hybrid_cloud_model", "gpt-4o-mini"),
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
            "no_individual": args.no_individual,
            "hybrid": getattr(args, "hybrid", False),
            "hybrid_cloud_model": getattr(args, "hybrid_cloud_model", "gpt-4o-mini")
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
            use_tqdm=True,
            hybrid=getattr(args, "hybrid", False),
            hybrid_cloud_model=getattr(args, "hybrid_cloud_model", "gpt-4o-mini")
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
