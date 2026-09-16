#!/usr/bin/env python3
"""
JoaKinDeX - Motor de Detecção de Duplicatas e Quase-Duplicatas
Criado por: Joaquim Ferreira Silva Neto <joaquimfsneto@gmail.com>

Utiliza token shingling, Jaccard Similarity e razão de similaridade de Levenshtein
para detectar documentos idênticos ou escaneados em diferentes resoluções/versões.
"""

import re
import difflib
from pathlib import Path
from typing import Dict, Any, List, Union, Set
from joakindex.db import get_connection, get_all_documents, get_document_by_md5


def _normalize_text_for_comparison(text: str) -> str:
    """Limpa e normaliza o texto para comparação robusta de conteúdo."""
    if not text:
        return ""
    # Remove quebras de linha e pontuação excessiva
    t = re.sub(r"[^\w\s]", " ", text.lower())
    # Colapsa espaços em branco múltiplos
    return " ".join(t.split())


def _get_token_shingles(words: List[str], k: int = 3) -> Set[str]:
    """Gera conjunto de n-gramas (shingles) para cálculo ultra-rápido de Jaccard."""
    if len(words) < k:
        return set(words)
    return {" ".join(words[i:i + k]) for i in range(len(words) - k + 1)}


def calculate_text_similarity(text1: str, text2: str) -> float:
    """Calcula a similaridade combinada (Jaccard + SequenceMatcher) entre dois textos."""
    if not text1 or not text2:
        return 0.0
    if text1 == text2:
        return 1.0

    w1 = text1.split()
    w2 = text2.split()
    len1, len2 = len(w1), len(w2)
    if len1 == 0 or len2 == 0:
        return 0.0

    # Poda rápida: se a proporção de tamanho for muito discrepante, não podem ser quase-duplicatas
    ratio_len = min(len1, len2) / max(len1, len2)
    if ratio_len < 0.65:
        return 0.0

    s1 = _get_token_shingles(w1, k=3)
    s2 = _get_token_shingles(w2, k=3)
    if not s1 or not s2:
        return 0.0

    inter = len(s1 & s2)
    union = len(s1 | s2)
    jaccard = inter / union if union > 0 else 0.0

    # Se Jaccard for alto, calcula SequenceMatcher em amostra do texto
    if jaccard >= 0.70:
        sample1 = text1[:2000]
        sample2 = text2[:2000]
        seq_ratio = difflib.SequenceMatcher(None, sample1, sample2).quick_ratio()
        return round((jaccard * 0.5) + (seq_ratio * 0.5), 4)

    return round(jaccard, 4)


def detect_duplicates(
    db_path: Union[str, Path],
    threshold: float = 0.88
) -> List[Dict[str, Any]]:
    """
    Varre todos os documentos do banco de dados para encontrar duplicatas e quase-duplicatas.
    Retorna uma lista de grupos/pares de duplicatas detectadas com metadados detalhados.
    """
    db = Path(db_path).expanduser().resolve()
    docs = get_all_documents(db)
    if not docs:
        return []

    # Extrai texto e pré-calcula shingles para cada documento
    doc_entries = []
    for d in docs:
        md5 = d.get("md5")
        if not md5:
            continue
        extras = d.get("dados_extras") or {}
        raw_text = (
            extras.get("texto_transcrito") or
            extras.get("texto_tesseract") or
            d.get("nome_arquivo") or ""
        )
        norm = _normalize_text_for_comparison(raw_text)
        words = norm.split()
        shingles = _get_token_shingles(words, k=3) if len(norm) >= 20 else set()
        doc_entries.append({
            "md5": md5,
            "nome_arquivo": d.get("nome_arquivo", ""),
            "classe": d.get("tipo_documento") or d.get("classe") or "Desconhecido",
            "valor": d.get("valor_monetario") or "",
            "cpf": d.get("cpf") or "",
            "data": d.get("data") or "",
            "beneficiario": d.get("beneficiario") or "",
            "extensao": d.get("extensao") or "",
            "texto_norm": norm,
            "words_len": len(words),
            "shingles": shingles,
            "tamanho": len(norm)
        })

    # Agrupa duplicatas
    pairs_found = []
    marked_as_duplicate = set()

    n = len(doc_entries)
    for i in range(n):
        e1 = doc_entries[i]
        if e1["md5"] in marked_as_duplicate or e1["tamanho"] < 20 or not e1["shingles"]:
            continue

        for j in range(i + 1, n):
            e2 = doc_entries[j]
            if e2["md5"] in marked_as_duplicate or e2["tamanho"] < 20 or not e2["shingles"]:
                continue

            # Se ambos tiverem CPF e forem divergentes, não podem ser a mesma operação
            if e1["cpf"] and e2["cpf"] and e1["cpf"] != e2["cpf"]:
                continue

            # Poda por tamanho de palavras
            w1, w2 = e1["words_len"], e2["words_len"]
            if w1 == 0 or w2 == 0:
                continue
            ratio_len = min(w1, w2) / max(w1, w2)
            if ratio_len < 0.65:
                continue

            # Cálculo de Jaccard O(1) usando shingles pré-computados
            s1, s2 = e1["shingles"], e2["shingles"]
            inter = len(s1 & s2)
            if inter == 0:
                continue
            union = len(s1 | s2)
            jaccard = inter / union if union > 0 else 0.0

            if jaccard < 0.60:
                continue

            # Se Jaccard indicar forte correlação, executa SequenceMatcher de refinamento
            sample1 = e1["texto_norm"][:2000]
            sample2 = e2["texto_norm"][:2000]
            seq_ratio = difflib.SequenceMatcher(None, sample1, sample2).quick_ratio()
            sim = round((jaccard * 0.5) + (seq_ratio * 0.5), 4)

            if sim >= threshold:
                pairs_found.append({
                    "canonico_md5": e1["md5"],
                    "canonico_nome": e1["nome_arquivo"],
                    "canonico_classe": e1["classe"],
                    "canonico_valor": e1["valor"],
                    "canonico_cpf": e1["cpf"],
                    "canonico_data": e1["data"],
                    "canonico_beneficiario": e1["beneficiario"],
                    "canonico_extensao": e1["extensao"],
                    "duplicata_md5": e2["md5"],
                    "duplicata_nome": e2["nome_arquivo"],
                    "duplicata_classe": e2["classe"],
                    "duplicata_valor": e2["valor"],
                    "duplicata_cpf": e2["cpf"],
                    "duplicata_data": e2["data"],
                    "duplicata_beneficiario": e2["beneficiario"],
                    "duplicata_extensao": e2["extensao"],
                    "classe": e1["classe"],
                    "similaridade": sim,
                    "similaridade_pct": round(sim * 100, 1),
                    "tipo": "Exata" if sim >= 0.99 else "Quase-Duplicata"
                })
                marked_as_duplicate.add(e2["md5"])

    return pairs_found


def compare_duplicate_pair(
    db_path: Union[str, Path],
    md5_a: str,
    md5_b: str
) -> Dict[str, Any]:
    """
    Retorna uma comparação completa e detalhada entre dois documentos para conferência humana,
    incluindo metadados, textos integrais, similaridade e percentual.
    """
    db = Path(db_path).expanduser().resolve()
    doc_a = get_document_by_md5(db, md5_a)
    doc_b = get_document_by_md5(db, md5_b)
    if not doc_a or not doc_b:
        return {"erro": "Um ou ambos os documentos não foram localizados no banco de dados."}

    extras_a = doc_a.get("dados_extras") or {}
    text_a = (extras_a.get("texto_transcrito") or extras_a.get("texto_tesseract") or "").strip()
    extras_b = doc_b.get("dados_extras") or {}
    text_b = (extras_b.get("texto_transcrito") or extras_b.get("texto_tesseract") or "").strip()

    norm_a = _normalize_text_for_comparison(text_a or doc_a.get("nome_arquivo", ""))
    norm_b = _normalize_text_for_comparison(text_b or doc_b.get("nome_arquivo", ""))
    sim = calculate_text_similarity(norm_a, norm_b)

    return {
        "status": "sucesso",
        "doc_a": doc_a,
        "doc_b": doc_b,
        "texto_a": text_a,
        "texto_b": text_b,
        "similaridade": sim,
        "similaridade_pct": round(sim * 100, 1),
        "tipo": "Exata" if sim >= 0.99 else "Quase-Duplicata"
    }


def apply_detected_duplicates(
    db_path: Union[str, Path],
    pairs: List[Dict[str, Any]]
) -> int:
    """Persiste os relacionamentos de duplicata detectados na tabela documentos."""
    if not pairs:
        return 0
    db = Path(db_path).expanduser().resolve()
    with get_connection(db) as conn:
        cur = conn.cursor()
        params = [(p["canonico_md5"], p["similaridade"], p["duplicata_md5"]) for p in pairs]
        cur.executemany("""
            UPDATE documentos
            SET duplicata_de = ?, similaridade_duplicata = ?
            WHERE md5 = ?
        """, params)
        conn.commit()
        return cur.rowcount


def resolve_duplicate(
    db_path: Union[str, Path],
    md5: str,
    descartar: bool = False
) -> bool:
    """Permite ao usuário confirmar ou descartar uma indicação de duplicata."""
    db = Path(db_path).expanduser().resolve()
    with get_connection(db) as conn:
        cur = conn.cursor()
        if descartar:
            cur.execute("UPDATE documentos SET duplicata_de = NULL, similaridade_duplicata = 0.0 WHERE md5 = ?", (md5,))
        else:
            # Mantém marcado, mas muda status_conferencia para duplicado
            cur.execute("UPDATE documentos SET status_conferencia = 'duplicado' WHERE md5 = ?", (md5,))
        conn.commit()
        return cur.rowcount > 0
