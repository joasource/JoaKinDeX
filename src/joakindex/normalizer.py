#!/usr/bin/env python3
"""
JoaKinDeX - Normalizador Inteligente de Instituições de Ensino
Criado por: Joaquim Ferreira Silva Neto <joaquimfsneto@gmail.com>

Módulo responsável por uniformizar e consolidar nomes de instituições de ensino,
eliminando discrepâncias causadas por inversão de ordem (ex: 'SIGLA - Nome' vs
'Nome - SIGLA' vs 'Nome (SIGLA)'), variações de maiúsculas/minúsculas, acentuação,
sufixos empresariais (LTDA, S/A) e artefatos de OCR.

Garante acurácia estatística no painel de BI, relatórios e contagens agregadas.
"""

__project__ = "JoaKinDeX"
__author__ = "Joaquim Ferreira Silva Neto"
__email__ = "joaquimfsneto@gmail.com"
__version__ = "1.0.0"

import json
import os
import re
import sys
import unicodedata
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple

try:
    from joakindex.db import get_db_path, upsert_documents_batch
except ImportError:
    try:
        from .db import get_db_path, upsert_documents_batch
    except ImportError:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from db_manager import get_db_path, upsert_documents_batch

# Conectivos que devem permanecer em minúsculas no padrão brasileiro de títulos
CONNECTIVES = {
    "de", "da", "do", "das", "dos",
    "e", "em", "para", "com", "no", "na", "nos", "nas", "a", "o", "as", "os"
}

# Siglas comuns conhecidas no contexto de instituições de ensino
KNOWN_ACRONYMS = {
    "FIVAR", "FAB", "CETEC", "CTEC", "CEITEC", "CEIC", "CEIT", "CEEC",
    "FACI", "FAD", "FAP", "UESC", "IASES", "UGF", "SENAC", "UNIFTB",
    "UNIFENAS", "UNIFIL", "FABRANI", "FABAVI", "NEJA", "DETRAN", "CEUFTB",
    "UNIP", "USP", "UFRJ", "UFBA", "UFMG", "UNIFESP", "PUC", "UNIDERP",
    "UNICIAN", "IFES", "IFSP", "MEC", "INEP"
}


def remover_acentos(texto: str) -> str:
    """Remove diacríticos e acentos de uma string."""
    if not texto:
        return ""
    return "".join(
        c for c in unicodedata.normalize("NFD", texto)
        if unicodedata.category(c) != "Mn"
    )


def formatar_titulo_pt(texto: str) -> str:
    """
    Aplica Title Case inteligente em português, mantendo conectivos em minúsculas
    e siglas conhecidas em maiúsculas.
    """
    if not texto:
        return ""

    m_par = re.search(r'\s*\(([A-Za-z0-9\s\-]+)\)$', texto)
    paren_sigla = ""
    corpo = texto
    if m_par:
        paren_sigla = f" ({m_par.group(1).strip().upper()})"
        corpo = texto[:m_par.start()].strip()

    palavras = corpo.split()
    res = []
    for i, p in enumerate(palavras):
        plow = p.lower()
        pup = p.upper()
        if pup in KNOWN_ACRONYMS:
            res.append(pup)
        elif i > 0 and plow in CONNECTIVES:
            res.append(plow)
        elif plow.startswith("(") and plow.endswith(")"):
            res.append(p.upper())
        elif len(p) <= 5 and p.isupper() and p.isalpha() and plow not in CONNECTIVES:
            res.append(pup)
        else:
            res.append(p.capitalize())

    return " ".join(res) + paren_sigla


def normalizar_instituicao(nome: Optional[str]) -> Optional[str]:
    """
    Uniformiza o nome da instituição para o formato canônico:
    'Nome por Extenso da Instituição (SIGLA)' ou 'Nome por Extenso'.

    Resolve variações como:
    - 'SIGLA - Nome' -> 'Nome (SIGLA)'
    - 'Nome - SIGLA' -> 'Nome (SIGLA)'
    - 'Nome (SIGLA)' -> 'Nome (SIGLA)'
    - 'SIGLA (Nome)' -> 'Nome (SIGLA)'
    - 'NOME EM CAIXA ALTA' -> 'Nome em Caixa Alta'
    - 'FIVAR - Faculdades Integradas Vale do Rio Verde' -> 'Faculdades Integradas Vale do Rio Verde (FIVAR)'
    - 'Faculdade Alffa do Brasil-FAB' -> 'Faculdade Alfa do Brasil (FAB)'
    """
    if not nome or not isinstance(nome, str):
        return None

    raw = nome.strip()
    if not raw:
        return None

    # Valores nulos / vazios comuns
    if raw.lower() in [
        "null", "none", "nao informada", "nao informado", "não informada",
        "não informado", "n/a", "desconhecida", "desconhecido", "sem instituicao",
        "universidade", "faculdade", "instituicao", "instituição"
    ]:
        return None

    # 1. Limpeza de caracteres especiais, hífens tipográficos e aspas
    cleaned = re.sub(r"[\u2010\u2011\u2012\u2013\u2014\u2015\u2212]", "-", raw)
    cleaned = re.sub(r"[\"\'\`´]", "", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()

    # 2. Remover sufixos empresariais/jurídicos não acadêmicos
    cleaned = re.sub(r"\b(LTDA|S/?A|EIRELI|ME|EPP)\b\.?", "", cleaned, flags=re.IGNORECASE).strip()
    cleaned = re.sub(r"\s*-\s*$", "", cleaned).strip()

    sem_acento = remover_acentos(cleaned).lower()
    sem_acento_compact = re.sub(r"[^a-z0-9]", "", sem_acento)

    # 3. Reconhecimento Canônico de Alta Frequência (Entidades Centrais do Domínio)

    # FIVAR / Faculdades Integradas Vale do Rio Verde
    if "vale do rio" in sem_acento or "fivar" in sem_acento or "fivar" in sem_acento_compact:
        if "itarare" in sem_acento and "vale do rio" not in sem_acento:
            return "Faculdades Integradas de Itararé"
        return "Faculdades Integradas Vale do Rio Verde (FIVAR)"

    # UNIFTB / Tobias Barreto
    if "uniftb" in sem_acento or "tobias barreto" in sem_acento or "ceuftb" in sem_acento:
        return "Faculdade UNIFTB"

    # FAB / Faculdade Alffa do Brasil
    if (
        ("alfa" in sem_acento or "alffa" in sem_acento or "afpa" in sem_acento or "fauldaffe" in sem_acento or "fauldae" in sem_acento)
        and ("brasil" in sem_acento or "fab" in sem_acento)
    ) or sem_acento_compact in ["fab", "faculdadefab"]:
        return "Faculdade Alffa do Brasil (FAB)"

    # CETEC / CTEC / CEITEC / Centro Técnico de Capacitação
    if any(k in sem_acento for k in ["cetec", "ctec", "ceitec", "ceic", "ceit", "ceec"]) and "capacitacao" in sem_acento:
        return "Centro Técnico de Capacitação (CETEC)"
    if "centro tecnico de capacitacao" in sem_acento:
        return "Centro Técnico de Capacitação (CETEC)"

    # FACI / Faculdades Impactos Brasil
    if "impacto" in sem_acento or "impracto" in sem_acento or ("faci" in sem_acento and ("faculdade" in sem_acento or "faculdades" in sem_acento)):
        return "Faculdades Impactos Brasil (FACI)"

    # Faculdade Dominius / FAD
    if "domini" in sem_acento or "dominus" in sem_acento:
        return "Faculdade Dominius (FAD)"

    # Faculdade Paraná / FAP
    if ("parana" in sem_acento or "jarani" in sem_acento) and ("faculdade" in sem_acento or "fap" in sem_acento):
        return "Faculdade Paraná (FAP)"

    # Faculdades Integradas de Itararé
    if "itarare" in sem_acento or "itarae" in sem_acento:
        return "Faculdades Integradas de Itararé"

    # Faculdade Famart
    if "famart" in sem_acento:
        return "Faculdade Famart"

    # UESC / Universidade Estadual de Santa Cruz
    if "santa cruz" in sem_acento and ("universidade" in sem_acento or "uesc" in sem_acento):
        return "Universidade Estadual de Santa Cruz (UESC)"

    # IASES
    if "iases" in sem_acento or "socioeducativo" in sem_acento:
        return "Instituto de Atendimento Socioeducativo do Espírito Santo (IASES)"

    # Universidade Gama Filho (UGF)
    if "gama filho" in sem_acento:
        return "Universidade Gama Filho (UGF)"

    # Faculdade de Ciências de Wenceslau Braz
    if "wenceslau braz" in sem_acento:
        return "Faculdade de Ciências de Wenceslau Braz"

    # Scardua Educacional
    if "scardua" in sem_acento or "scarda" in sem_acento:
        return "Scardua Educacional"

    # Faculdade São Geraldo (Multivix)
    if "sao geraldo" in sem_acento:
        return "Faculdade São Geraldo (Multivix)"

    # Faculdade do Vale
    if "faculdade do v ale" in sem_acento or "faculdade do vale" in sem_acento:
        return "Faculdade do Vale"

    # 4. Regras Heurísticas Estruturais para Qualquer Instituição

    # Caso A: 'SIGLA - Nome Extenso' ou 'SIGLA : Nome Extenso' ou 'SIGLA / Nome Extenso'
    m_sigla_ini = re.match(r"^([A-Z0-9]{2,8})\s*[-–—:/|]\s*(.+)$", cleaned)
    if m_sigla_ini:
        sigla = m_sigla_ini.group(1).strip()
        resto = m_sigla_ini.group(2).strip()
        resto = re.sub(r"^[-–—:/|]\s*", "", resto)
        return f"{formatar_titulo_pt(resto)} ({sigla})"

    # Caso B: 'Nome Extenso - SIGLA'
    m_sigla_fim = re.match(r"^(.+?)\s*[-–—:/|]\s*([A-Z0-9]{2,8})$", cleaned)
    if m_sigla_fim:
        resto = m_sigla_fim.group(1).strip()
        sigla = m_sigla_fim.group(2).strip()
        return f"{formatar_titulo_pt(resto)} ({sigla})"

    # Caso C: '(SIGLA) Nome Extenso' -> 'Nome Extenso (SIGLA)'
    m_paren_ini = re.match(r"^\((.+?)\)\s*(.+)$", cleaned)
    if m_paren_ini:
        p1 = m_paren_ini.group(1).strip()
        p2 = m_paren_ini.group(2).strip()
        if len(p1) <= 8:
            return f"{formatar_titulo_pt(p2)} ({p1.upper()})"

    # Caso D: 'Nome Extenso (SIGLA)' -> Preservar e formatar título
    m_paren_fim = re.match(r"^(.+?)\s*\(([A-Za-z0-9\s\-]+)\)$", cleaned)
    if m_paren_fim:
        nome_ext = m_paren_fim.group(1).strip()
        sigla = m_paren_fim.group(2).strip()
        if len(sigla) <= 8:
            return f"{formatar_titulo_pt(nome_ext)} ({sigla.upper()})"

    # 5. Formatação padrão com preservação de conectivos
    return formatar_titulo_pt(cleaned)


def uniformizar_base_dados(
    json_path: str,
    atualizar_individuais: bool = True
) -> Dict[str, Any]:
    """
    Lê o banco de dados consolidado (joakindex.json / classificacao_diplomas.json) e
    as fichas individuais correspondentes, aplicando a normalização
    inteligente de nomes de instituições de ensino sem reprocessar PDFs.

    Salva as alterações de forma atômica.
    """
    p_json = Path(json_path).expanduser().resolve()
    if p_json.is_dir():
        if (p_json / "joakindex.json").exists():
            p_json = p_json / "joakindex.json"
        elif (p_json / "classificacao_diplomas.json").exists():
            p_json = p_json / "classificacao_diplomas.json"
        else:
            p_json = p_json / "joakindex.json"

    if not p_json.exists():
        return {
            "status": "erro",
            "mensagem": f"Arquivo {p_json} não encontrado."
        }

    with open(p_json, "r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, list):
        return {
            "status": "erro",
            "mensagem": "Formato inválido do arquivo JSON consolidado (esperava lista)."
        }

    total_registros = len(data)
    total_modificados = 0
    de_para_amostra = {}
    inst_anteriores = set()
    inst_posteriores = set()

    for item in data:
        if not isinstance(item, dict):
            continue
        original = item.get("faculdade")
        if original:
            inst_anteriores.add(original)

        normalizado = normalizar_instituicao(original)
        if normalizado:
            inst_posteriores.add(normalizado)

        if original != normalizado:
            total_modificados += 1
            if original and len(de_para_amostra) < 15 and original not in de_para_amostra:
                de_para_amostra[original] = normalizado
            item["faculdade"] = normalizado

    # Gravação atômica do arquivo consolidado
    tmp_json = p_json.parent / f".tmp_{p_json.name}"
    with open(tmp_json, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    tmp_json.replace(p_json)

    # Atualização do banco SQLite correspondente se existir
    try:
        p_db = get_db_path(p_json)
        if p_db.exists():
            upsert_documents_batch(p_db, data)
    except Exception as e_db:
        print(f"[Aviso] Não foi possível atualizar SQLite na normalização: {e_db}")

    # Atualização do relatório de texto TXT consolidado
    p_txt = p_json.with_suffix(".txt")
    if p_txt.exists():
        try:
            from io import StringIO
            buf = StringIO()
            buf.write("=" * 80 + "\n")
            buf.write("RELATÓRIO CONSOLIDADO DE CLASSIFICAÇÃO DE DOCUMENTOS (JOAKINDEX)\n")
            buf.write(f"Total de registros processados: {len(data)}\n")
            buf.write(f"Instituições de ensino canônicas distintas: {len(inst_posteriores)}\n")
            buf.write("=" * 80 + "\n\n")

            for idx, it in enumerate(data, 1):
                buf.write(f"[{idx}] {it.get('pdf_name', 'Documento')}\n")
                buf.write(f"  • MD5                : {it.get('md5')}\n")
                buf.write(f"  • Beneficiário       : {it.get('beneficiario') or 'Não identificado'}\n")
                buf.write(f"  • CPF                : {it.get('cpf') or 'Não identificado'}\n")
                buf.write(f"  • RG                 : {it.get('rg') or 'Não identificado'}\n")
                buf.write(f"  • Curso              : {it.get('curso') or 'Não identificado'}\n")
                buf.write(f"  • Natureza           : {it.get('natureza_curso') or 'Não identificada'}\n")
                buf.write(f"  • Faculdade          : {it.get('faculdade') or 'Não informada'}\n")
                buf.write(f"  • Tipo de Documento  : {it.get('tipo_documento') or 'Não identificado'}\n")
                buf.write(f"  • Carga Horária      : {it.get('carga_horaria') or 'Não informada'}\n")
                buf.write(f"  • Data de Conclusão  : {it.get('data') or 'Não informada'}\n")
                buf.write("-" * 80 + "\n")

            tmp_txt = p_txt.parent / f".tmp_{p_txt.name}"
            with open(tmp_txt, "w", encoding="utf-8") as f:
                f.write(buf.getvalue())
            tmp_txt.replace(p_txt)
        except Exception as e:
            print(f"[Aviso] Não foi possível atualizar TXT consolidado: {e}")

    # Atualização das fichas individuais na pasta 'individuais'
    individuais_atualizados = 0
    indiv_dir = p_json.parent / "individuais"
    if atualizar_individuais and indiv_dir.exists():
        for item in data:
            md5 = item.get("md5")
            if not md5:
                continue
            indiv_file = indiv_dir / f"{md5}.json"
            if indiv_file.exists():
                try:
                    with open(indiv_file, "r", encoding="utf-8") as f:
                        indiv_data = json.load(f)
                    if isinstance(indiv_data, dict):
                        orig_fac = indiv_data.get("faculdade")
                        norm_fac = normalizar_instituicao(orig_fac)
                        if orig_fac != norm_fac:
                            indiv_data["faculdade"] = norm_fac
                            tmp_indiv = indiv_dir / f".tmp_{md5}.json"
                            with open(tmp_indiv, "w", encoding="utf-8") as f:
                                json.dump(indiv_data, f, ensure_ascii=False, indent=2)
                            tmp_indiv.replace(indiv_file)
                            individuais_atualizados += 1
                except Exception:
                    pass

    return {
        "status": "sucesso",
        "total_registros": total_registros,
        "total_modificados": total_modificados,
        "individuais_atualizados": individuais_atualizados,
        "instituicoes_antes": len(inst_anteriores),
        "instituicoes_depois": len(inst_posteriores),
        "reducao_fragmentacao": len(inst_anteriores) - len(inst_posteriores),
        "amostra_normalizacoes": de_para_amostra
    }


if __name__ == "__main__":
    caminho = sys.argv[1] if len(sys.argv) > 1 else "./saida/joakindex.json"
    print(f"🚀 Iniciando uniformização de instituições em: {caminho}")
    resultado = uniformizar_base_dados(caminho)
    print(json.dumps(resultado, indent=2, ensure_ascii=False))
