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
from typing import Any, Dict, List, Optional, Tuple

from joakindex.extractors_texto import validate_cnpj_checksum, validate_cpf_checksum

# Campos de passthrough do LLM (sem coluna dedicada) que identificam uma pessoa
# física por um papel específico num documento — lidos defensivamente via .get(),
# podem ou não existir dependendo do tipo de documento.
_CAMPOS_PAPEL_PF_SIMPLES = (
    ("emitente", "emitente"),
    ("vendedor", "vendedor"),
    ("comprador", "comprador"),
    ("proprietario_anterior", "proprietario_anterior"),
)


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
    # O hash do nome é incluído no id para que duas pessoas diferentes e sem
    # identificação no MESMO documento (ex.: comprador e vendedor sem CPF) não colidam.
    md5 = str(doc.get("md5") or "")
    digest = hashlib.sha1(nome_norm.encode("utf-8")).hexdigest()[:8]
    entidade_id = f"PF_PROV_{md5[:16]}_{digest}"
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


def _vinculo_pf_por_nome(md5: str, nome: Optional[str], papel: str) -> Optional[Dict[str, Any]]:
    """Resolve um nome solto (sem CPF/RG dedicados) para um vínculo de pessoa física."""
    if not nome or not str(nome).strip():
        return None
    entidade_id, _, _ = resolve_pessoa_fisica_id({"md5": md5, "beneficiario": nome})
    if not entidade_id:
        return None
    return {"documento_md5": md5, "entidade_id": entidade_id, "tipo_entidade": "PF", "papel": papel}


def build_vinculos_for_doc(doc: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Extrai TODAS as partes (papéis) de um documento como linhas de vínculo,
    a partir dos campos populados (não do `tipo_documento`, que é texto livre
    gerado pelo LLM e não um enum confiável). Um documento pode gerar 0, 1 ou
    várias linhas dependendo de quantos papéis distintos ele tiver.
    """
    md5 = str(doc.get("md5") or "")
    vinculos: List[Dict[str, Any]] = []

    # 1. Titular: beneficiario (PF) tem prioridade; cai para razao_social/cnpj (PJ)
    #    quando não há beneficiário (ex.: Cartão CNPJ / Situação Cadastral).
    beneficiario = doc.get("beneficiario")
    if beneficiario and str(beneficiario).strip():
        pf_id, _, _ = resolve_pessoa_fisica_id(doc)
        if pf_id:
            vinculos.append({"documento_md5": md5, "entidade_id": pf_id, "tipo_entidade": "PF", "papel": "titular"})
    else:
        razao_social = doc.get("razao_social")
        if razao_social and str(razao_social).strip():
            pj_id, _, _ = resolve_pessoa_juridica_id(razao_social, doc.get("cnpj"), md5)
            vinculos.append({"documento_md5": md5, "entidade_id": pj_id, "tipo_entidade": "PJ", "papel": "titular"})

    # 2. Fonte pagadora: PJ se tiver CNPJ válido, senão trata como nome de PF solto.
    fonte_pagadora = doc.get("fonte_pagadora")
    if fonte_pagadora and str(fonte_pagadora).strip():
        cnpj_fp_digits = _only_digits(doc.get("cnpj_fonte_pagadora"))
        if cnpj_fp_digits and validate_cnpj_checksum(cnpj_fp_digits):
            pj_id, _, _ = resolve_pessoa_juridica_id(fonte_pagadora, cnpj_fp_digits, md5)
            vinculos.append({"documento_md5": md5, "entidade_id": pj_id, "tipo_entidade": "PJ", "papel": "fonte_pagadora"})
        else:
            v = _vinculo_pf_por_nome(md5, fonte_pagadora, "fonte_pagadora")
            if v:
                vinculos.append(v)

    # 3. Papéis simples de PF via passthrough do LLM (emitente, vendedor, comprador, proprietario_anterior).
    for campo, papel in _CAMPOS_PAPEL_PF_SIMPLES:
        v = _vinculo_pf_por_nome(md5, doc.get(campo), papel)
        if v:
            vinculos.append(v)

    # 4. Listagens com múltiplos nomes (borderôs, relações de pagamento) -> um vínculo
    #    "listado" por nome. Quando o documento tem só uma pessoa, o prompt de extração
    #    instrui o LLM a retornar `nomes_detectados: [mesmo nome do beneficiário]` — nesse
    #    caso o nome já virou vínculo "titular" acima, então é pulado aqui para não duplicar.
    nomes_detectados = doc.get("nomes_detectados")
    nome_titular_norm = _normalize_nome(beneficiario) if beneficiario else ""
    if isinstance(nomes_detectados, list):
        for nome in nomes_detectados:
            if nome and _normalize_nome(nome) == nome_titular_norm and nome_titular_norm:
                continue
            v = _vinculo_pf_por_nome(md5, nome, "listado")
            if v:
                vinculos.append(v)

    return vinculos
