#!/usr/bin/env python3
"""
JoaKinDeX - Extração Fallback de CPF/CNPJ/RG, Curso, Valores e PIX via Regex
Criado por: Joaquim Ferreira Silva Neto <joaquimfsneto@gmail.com>

Funções puras (sem I/O) de formatação, validação (checksum oficial da Receita
Federal) e extração por regex de CPF, RG, CNPJ e dados cadastrais, curso,
valor monetário, identificadores PIX, nomes de pessoas em listagens/tabelas
e sanitização de transcrições de LLM contra loops de alucinação. Usadas como
contingência quando o LLM multimodal não retorna (ou retorna incorretamente)
esses campos a partir do texto nativo/OCR do documento.
"""

__project__ = "JoaKinDeX"
__author__ = "Joaquim Ferreira Silva Neto"
__email__ = "joaquimfsneto@gmail.com"
__version__ = "1.0.0"

import re
from typing import Any, Dict, List, Optional


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
