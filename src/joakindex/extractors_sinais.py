#!/usr/bin/env python3
"""
JoaKinDeX - Classificação de Documentos por Assinaturas Textuais (Boleto, Cheque, IRPF, Veicular, etc.)
Criado por: Joaquim Ferreira Silva Neto <joaquimfsneto@gmail.com>

Detectores por regex/palavra-chave de tipos de documento financeiro, jurídico
e veicular (Boleto Bancário, Cheque, Declaração/Recibo de IRPF, Informe de
Rendimentos, CRV/CRLV/ATPV veicular, Contrato de Compra e Venda, Nota
Promissória, Recibo) e o dispatcher `classify_text_signatures`, que primeiro
consulta as Regras Aprendidas do usuário no banco e, na ausência de regra,
pontua e escolhe o tipo/domínio mais provável entre esses detectores.
"""

__project__ = "JoaKinDeX"
__author__ = "Joaquim Ferreira Silva Neto"
__email__ = "joaquimfsneto@gmail.com"
__version__ = "1.0.0"

import re
from typing import Any, Dict, Optional, Tuple

try:
    from joakindex.db import consultar_regra_para_texto, resolve_default_db_path
except ImportError:
    from .db import consultar_regra_para_texto, resolve_default_db_path


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
