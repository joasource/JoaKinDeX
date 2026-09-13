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
from typing import Dict, Any, List, Optional, Union, Tuple, Set
from collections import defaultdict
from joakindex.db import get_connection, get_all_documents, row_to_doc


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
    Retorna uma lista de grupos/pares de duplicatas detectadas.
    """
    db = Path(db_path).expanduser().resolve()
    docs = get_all_documents(db)
    if not docs:
        return []

    # Extrai texto de comparação para cada documento
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
        doc_entries.append({
            "md5": md5,
            "nome_arquivo": d.get("nome_arquivo", ""),
            "classe": d.get("tipo_documento") or d.get("classe") or "Desconhecido",
            "valor": d.get("valor_monetario") or "",
            "cpf": d.get("cpf") or "",
            "texto_norm": norm,
            "tamanho": len(norm)
        })

    # Agrupa duplicatas
    pairs_found = []
    marked_as_duplicate = set()

    n = len(doc_entries)
    for i in range(n):
        e1 = doc_entries[i]
        if e1["md5"] in marked_as_duplicate:
            continue
        if e1["tamanho"] < 20:  # Ignora documentos praticamente vazios
            continue

        for j in range(i + 1, n):
            e2 = doc_entries[j]
            if e2["md5"] in marked_as_duplicate:
                continue

            # Se possuírem mesmo CPF e mesmo Valor Monetário (quando presentes), a chance é alta
            if e1["cpf"] and e2["cpf"] and e1["cpf"] != e2["cpf"]:
                continue

            sim = calculate_text_similarity(e1["texto_norm"], e2["texto_norm"])
            if sim >= threshold:
                pairs_found.append({
                    "canonico_md5": e1["md5"],
                    "canonico_nome": e1["nome_arquivo"],
                    "duplicata_md5": e2["md5"],
                    "duplicata_nome": e2["nome_arquivo"],
                    "classe": e1["classe"],
                    "similaridade": sim,
                    "tipo": "Exata" if sim >= 0.99 else "Quase-Duplicata"
                })
                marked_as_duplicate.add(e2["md5"])

    return pairs_found


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
            # Mantém marcado, mas pode mudar status_conferencia para duplicado
            cur.execute("UPDATE documentos SET status_conferencia = 'duplicado' WHERE md5 = ?", (md5,))
        conn.commit()
        return cur.rowcount > 0
