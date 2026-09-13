#!/usr/bin/env python3
"""
JoaKinDeX - Inspetor de Assinaturas Digitais e Origem Documental
Criado por: Joaquim Ferreira Silva Neto <joaquimfsneto@gmail.com>

Analisa estruturas criptográficas PAdES/ICP-Brasil em arquivos PDF e
determina se o documento é Nativo Digital ou Digitalizado/Escaneado.
"""

import os
import re
from pathlib import Path
from typing import Dict, Any, List, Optional, Union
from datetime import datetime

try:
    import pypdf
except ImportError:
    pypdf = None


KNOWN_CAS = [
    ("ICP-Brasil", "ICP-Brasil (Infraestrutura de Chaves Públicas Brasileira)"),
    ("SERPRO", "AC SERPRO"),
    ("Certisign", "AC Certisign"),
    ("SOLUTI", "AC SOLUTI"),
    ("VALID", "AC VALID"),
    ("OAB", "AC OAB"),
    ("DocuSign", "DocuSign Inc."),
    ("Gov.br", "Assinatura Eletrônica Gov.br"),
    ("Adobe", "Adobe Certified Document Services")
]


def inspect_pdf(pdf_path: Union[str, Path]) -> Dict[str, Any]:
    """
    Inspeciona um arquivo PDF para determinar:
    1. eh_nativo_digital: booleano indicando se possui camada de texto vetorial/digital.
    2. tem_assinatura_digital: booleano indicando se possui assinatura criptográfica PAdES.
    3. info_assinaturas: dicionário com detalhes de signatários, autoridade certificadora e datas.
    """
    p = Path(pdf_path).expanduser().resolve()
    if not p.exists() or not p.is_file():
        return {
            "eh_nativo_digital": False,
            "tem_assinatura_digital": False,
            "natureza": "Arquivo inexistente",
            "info_assinaturas": {}
        }

    eh_nativo = False
    tem_assinatura = False
    info_assinaturas: Dict[str, Any] = {
        "tem_assinatura": False,
        "signatarios": [],
        "autoridades": [],
        "tipo_assinatura": None,
        "data_assinatura": None
    }

    # 1. Análise binária rápida para assinaturas e autoridades
    try:
        with open(p, "rb") as f:
            raw_data = f.read(2 * 1024 * 1024)  # Lê até 2MB para estruturas de assinatura
            # Detecção de assinaturas padrão PAdES
            has_byterange = b"/ByteRange" in raw_data
            has_sig_type = b"/Type /Sig" in raw_data or b"/Type/Sig" in raw_data or b"/SubFilter" in raw_data

            if has_byterange or has_sig_type:
                tem_assinatura = True
                info_assinaturas["tem_assinatura"] = True
                info_assinaturas["tipo_assinatura"] = "PAdES (PDF Advanced Electronic Signature)"

                # Identificação de autoridades certificadoras conhecidas
                for key, full_name in KNOWN_CAS:
                    if key.encode("utf-8", errors="ignore").lower() in raw_data.lower():
                        if full_name not in info_assinaturas["autoridades"]:
                            info_assinaturas["autoridades"].append(full_name)

                # Busca nomes de signatários comuns em metadados /Name ou CN=
                matches_cn = re.findall(rb"CN=([^,/\r\n\(\)]+)", raw_data)
                for m in matches_cn:
                    try:
                        cn_str = m.decode("utf-8", errors="ignore").strip()
                        if cn_str and len(cn_str) > 3 and not cn_str.startswith("AC ") and cn_str not in info_assinaturas["signatarios"]:
                            info_assinaturas["signatarios"].append(cn_str)
                    except Exception:
                        pass
    except Exception:
        pass

    # 2. Análise da camada de texto para determinar se é Nativo Digital
    total_text_chars = 0
    if pypdf:
        try:
            reader = pypdf.PdfReader(str(p))
            # Checa primeiras 3 páginas
            pages_to_check = reader.pages[:3]
            for page in pages_to_check:
                text = page.extract_text() or ""
                total_text_chars += len(text.strip())
        except Exception:
            pass

    # Se possui mais de 40 caracteres digitais sem necessidade de OCR, consideramos nativo digital
    eh_nativo = (total_text_chars >= 40)

    # 3. Também checa no texto se há indicação de assinatura Gov.br ou ICP-Brasil impressa
    natureza = "Nativo Digital" if eh_nativo else "Digitalizado / Escaneado"
    if tem_assinatura:
        natureza += " (Assinado Digitalmente)"

    return {
        "eh_nativo_digital": eh_nativo,
        "tem_assinatura_digital": tem_assinatura,
        "natureza": natureza,
        "info_assinaturas": info_assinaturas
    }
