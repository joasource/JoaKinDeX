#!/usr/bin/env python3
"""
JoaKinDeX - Agrupador Inteligente de Dossiês e Documentos Relacionados
Criado por: Joaquim Ferreira Silva Neto <joaquimfsneto@gmail.com>

Cruza entidades unívocas (CPF, CNPJ, Nome do Beneficiário) para agrupar
documentos esparsos em dossiês consolidados com suporte a exportação unificada.
"""

import re
import json
from pathlib import Path
from typing import Dict, Any, List, Optional, Union, Tuple
from collections import defaultdict
from datetime import datetime

try:
    import pypdf
except ImportError:
    pypdf = None

from joakindex.db import get_connection, get_all_documents, row_to_doc


def _clean_cpf_cnpj(val: Optional[str]) -> Optional[str]:
    """Extrai apenas dígitos de CPF/CNPJ."""
    if not val:
        return None
    digits = re.sub(r"\D", "", str(val))
    if len(digits) == 11:
        return f"{digits[:3]}.{digits[3:6]}.{digits[6:9]}-{digits[9:]}"
    elif len(digits) == 14:
        return f"{digits[:2]}.{digits[2:5]}.{digits[5:8]}/{digits[8:12]}-{digits[12:]}"
    return None


def build_and_save_dossiers(db_path: Union[str, Path]) -> List[Dict[str, Any]]:
    """
    Analisa os documentos e cria agrupamentos em Dossiês baseados em CPF, CNPJ ou Nome.
    Salva na tabela 'dossies' e atualiza a coluna 'dossie_id' nos documentos.
    """
    db = Path(db_path).expanduser().resolve()
    docs = get_all_documents(db)
    if not docs:
        return []

    # Dicionário de agrupamento: chave -> lista de documentos
    clusters: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    cluster_meta: Dict[str, Dict[str, Any]] = {}

    for d in docs:
        cpf = _clean_cpf_cnpj(d.get("cpf"))
        cnpj = _clean_cpf_cnpj(d.get("cnpj"))
        beneficiario = (d.get("beneficiario") or "").strip()

        cluster_key = None
        tipo_entidade = None
        identificador = None
        nome_titular = beneficiario or None

        if cpf:
            cluster_key = f"CPF_{cpf}"
            tipo_entidade = "CPF"
            identificador = cpf
        elif cnpj:
            cluster_key = f"CNPJ_{cnpj}"
            tipo_entidade = "CNPJ"
            identificador = cnpj
        elif beneficiario and len(beneficiario.split()) >= 2 and len(beneficiario) >= 8:
            # Normalização de nome para chave
            nome_norm = re.sub(r"\s+", " ", beneficiario.upper())
            cluster_key = f"NOME_{nome_norm}"
            tipo_entidade = "NOME"
            identificador = nome_norm

        if cluster_key:
            clusters[cluster_key].append(d)
            if cluster_key not in cluster_meta:
                cluster_meta[cluster_key] = {
                    "id": f"dossie_{re.sub(r'[^a-zA-Z0-9_]', '_', cluster_key.lower())}",
                    "tipo_entidade": tipo_entidade,
                    "identificador": identificador,
                    "nome_titular": nome_titular
                }
            elif nome_titular and not cluster_meta[cluster_key]["nome_titular"]:
                cluster_meta[cluster_key]["nome_titular"] = nome_titular

    # Filtra apenas agrupamentos com pelo menos 2 documentos (dossiê real)
    dossiers_created = []
    now_iso = datetime.now().isoformat()

    with get_connection(db) as conn:
        cur = conn.cursor()
        # Limpa dossiês anteriores para reconstrução limpa
        cur.execute("DELETE FROM dossies;")
        cur.execute("UPDATE documentos SET dossie_id = NULL;")

        for k, items in clusters.items():
            if len(items) >= 2:
                meta = cluster_meta[k]
                dossie_id = meta["id"]
                total = len(items)

                cur.execute("""
                    INSERT INTO dossies (id, tipo_entidade, identificador, nome_titular, total_documentos, criado_em)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    dossie_id,
                    meta["tipo_entidade"],
                    meta["identificador"],
                    meta["nome_titular"] or meta["identificador"],
                    total,
                    now_iso
                ))

                # Atualiza os documentos que pertencem a este dossiê
                md5s = [doc["md5"] for doc in items if doc.get("md5")]
                cur.executemany("""
                    UPDATE documentos SET dossie_id = ? WHERE md5 = ?
                """, [(dossie_id, m) for m in md5s])

                dossiers_created.append({
                    "id": dossie_id,
                    "tipo_entidade": meta["tipo_entidade"],
                    "identificador": meta["identificador"],
                    "nome_titular": meta["nome_titular"] or meta["identificador"],
                    "total_documentos": total,
                    "documentos": items
                })

        conn.commit()

    return dossiers_created


def get_all_dossiers(db_path: Union[str, Path]) -> List[Dict[str, Any]]:
    """Retorna a lista estruturada de todos os dossiês com seus respectivos documentos."""
    db = Path(db_path).expanduser().resolve()
    if not db.exists():
        return []

    with get_connection(db) as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM dossies ORDER BY total_documentos DESC, nome_titular ASC;")
        dossie_rows = cur.fetchall()

        result = []
        for d in dossie_rows:
            d_dict = dict(d)
            # Busca documentos do dossiê
            cur.execute("SELECT * FROM documentos WHERE dossie_id = ? ORDER BY data ASC, nome_arquivo ASC", (d["id"],))
            doc_rows = cur.fetchall()
            d_dict["documentos"] = [row_to_doc(r) for r in doc_rows]
            result.append(d_dict)

        return result


def export_dossier_pdf(
    db_path: Union[str, Path],
    dossie_id: str,
    output_pdf_path: Union[str, Path],
    pdf_base_dir: Optional[Union[str, Path]] = None
) -> Tuple[bool, str]:
    """
    Funde todos os PDFs de um dossiê em um único PDF unificado.
    """
    if not pypdf:
        return False, "Biblioteca pypdf não instalada."

    db = Path(db_path).expanduser().resolve()
    with get_connection(db) as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM documentos WHERE dossie_id = ? ORDER BY data ASC, nome_arquivo ASC", (dossie_id,))
        docs = cur.fetchall()

    if not docs:
        return False, "Nenhum documento encontrado para este dossiê."

    merger = pypdf.PdfMerger()
    added_count = 0

    base_dir = Path(pdf_base_dir) if pdf_base_dir else db.parent

    for doc in docs:
        caminho = doc["caminho_relativo"] or doc["nome_arquivo"]
        full_p = base_dir / caminho
        if not full_p.exists():
            full_p = base_dir / doc["nome_arquivo"]

        if full_p.exists() and full_p.suffix.lower() == ".pdf":
            try:
                merger.append(str(full_p))
                added_count += 1
            except Exception as e:
                pass

    if added_count == 0:
        return False, "Nenhum arquivo PDF válido pôde ser anexado."

    out_p = Path(output_pdf_path).expanduser().resolve()
    out_p.parent.mkdir(parents=True, exist_ok=True)
    with open(out_p, "wb") as f_out:
        merger.write(f_out)
    merger.close()

    return True, f"Dossiê exportado com sucesso contendo {added_count} PDFs."
