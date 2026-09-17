#!/usr/bin/env python3
"""
JoaKinDeX - Exportação Relacional Estruturada (Multi-CSV)
Criado por: Joaquim Ferreira Silva Neto <joaquimfsneto@gmail.com>

Agrega o banco SQLite inteiro em um conjunto de tabelas CSV relacionadas
(pessoas físicas, pessoas jurídicas, endereços, documentos e vínculos),
com política de deduplicação conservadora: funde entidades apenas por CPF/CNPJ
com checksum válido, ou por nome normalizado + RG quando não há CPF/CNPJ.
Nunca funde por nome isolado (homônimos são comuns e uma fusão indevida numa
ferramenta de auditoria é pior do que deixar uma linha duplicada). Não depende
de dossier.py nem toca a tabela `dossies` — é um agregador paralelo, somente
leitura, específico para este export.
"""

__project__ = "JoaKinDeX"
__author__ = "Joaquim Ferreira Silva Neto"
__email__ = "joaquimfsneto@gmail.com"
__version__ = "1.0.0"

import hashlib
import re
from typing import Any, Dict, Optional, Tuple

from joakindex.extractors_texto import validate_cnpj_checksum, validate_cpf_checksum


def _only_digits(val: Optional[str]) -> str:
    """Normaliza um valor para dígitos apenas (mesmo padrão inline usado em todo o projeto)."""
    return re.sub(r"\D", "", str(val)) if val else ""


def _normalize_nome(val: Optional[str]) -> str:
    """Uppercase + colapso de espaços — mesmo padrão de normalização usado em dossier.py."""
    return re.sub(r"\s+", " ", str(val or "").strip().upper())


def resolve_pessoa_fisica_id(doc: Dict[str, Any]) -> Tuple[Optional[str], bool, Dict[str, Any]]:
    """
    Resolve o entidade_id de uma pessoa física titular de um documento.

    Retorna (entidade_id | None, identificacao_incompleta, campos_para_linha).
    Retorna (None, False, {}) se o documento não tiver nenhum indício de pessoa
    física titular (ex.: documento cujo titular é só PJ, como um Cartão CNPJ puro).

    Política de resolução, em ordem:
    1. CPF com checksum válido -> chave forte, funde automaticamente entre documentos.
    2. Sem CPF válido, mas com RG -> funde por nome normalizado + RG.
    3. Sem CPF válido e sem RG -> entidade provisória 1:1 com o documento (nunca
       funde por nome isolado).
    """
    cpf_raw = doc.get("cpf")
    rg_raw = doc.get("rg")
    nome_raw = doc.get("beneficiario")
    cpf_digits = _only_digits(cpf_raw)
    nome_norm = _normalize_nome(nome_raw)

    if not (cpf_digits or (rg_raw and str(rg_raw).strip()) or (nome_raw and str(nome_raw).strip())):
        return None, False, {}

    if cpf_digits and validate_cpf_checksum(cpf_digits):
        entidade_id = f"PF_{cpf_digits}"
        return entidade_id, False, {
            "entidade_id": entidade_id,
            "nome_normalizado": nome_norm,
            "cpf": cpf_digits,
            "rg": (str(rg_raw).strip() if rg_raw else ""),
            "identificacao_incompleta": False,
        }

    if rg_raw and str(rg_raw).strip():
        rg_norm = _only_digits(rg_raw) or str(rg_raw).strip().upper()
        chave = f"{nome_norm}|{rg_norm}"
        digest = hashlib.sha1(chave.encode("utf-8")).hexdigest()[:16]
        entidade_id = f"PF_RGNM_{digest}"
        return entidade_id, False, {
            "entidade_id": entidade_id,
            "nome_normalizado": nome_norm,
            "cpf": "",
            "rg": rg_norm,
            "identificacao_incompleta": False,
        }

    # Provisório: sem CPF válido e sem RG -> não mescla por nome. 1:1 com o documento.
    md5 = str(doc.get("md5") or "")
    entidade_id = f"PF_PROV_{md5[:16]}"
    return entidade_id, True, {
        "entidade_id": entidade_id,
        "nome_normalizado": nome_norm,
        "cpf": "",
        "rg": (str(rg_raw).strip() if rg_raw else ""),
        "identificacao_incompleta": True,
    }


def resolve_pessoa_juridica_id(
    nome_razao: Optional[str], cnpj_raw: Optional[str], md5: str
) -> Tuple[str, bool, Dict[str, Any]]:
    """
    Resolve o entidade_id de uma pessoa jurídica dado (razão social, cnpj) já
    extraídos de um slot específico (titular, fonte_pagadora, comprador, etc).
    Sempre retorna um entidade_id (nunca None) — chamar apenas quando já se
    sabe que o slot em questão é uma pessoa jurídica.
    """
    cnpj_digits = _only_digits(cnpj_raw)
    nome_norm = _normalize_nome(nome_razao)
    if cnpj_digits and validate_cnpj_checksum(cnpj_digits):
        entidade_id = f"PJ_{cnpj_digits}"
        return entidade_id, False, {
            "entidade_id": entidade_id,
            "razao_social_normalizada": nome_norm,
            "cnpj": cnpj_digits,
            "identificacao_incompleta": False,
        }
    digest = hashlib.sha1(nome_norm.encode("utf-8")).hexdigest()[:8]
    entidade_id = f"PJ_PROV_{md5[:16]}_{digest}"
    return entidade_id, True, {
        "entidade_id": entidade_id,
        "razao_social_normalizada": nome_norm,
        "cnpj": "",
        "identificacao_incompleta": True,
    }
