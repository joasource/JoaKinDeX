#!/usr/bin/env python3
"""
JoaKinDeX - Smart Dispatcher (Organização Física & Renomeação de Arquivos)
Criado por: Joaquim Ferreira Silva Neto <joaquimfsneto@gmail.com>

Organiza fisicamente os arquivos PDF em diretórios estruturados com
renomeação semântica padronizada, suporte a dry-run (simulação) e manifesto CSV.
"""

import os
import re
import csv
import shutil
from pathlib import Path
from typing import Dict, Any, List, Optional, Union, Tuple
from datetime import datetime
from joakindex.db import get_connection, get_all_documents


def sanitize_filename_part(text: Optional[str], default: str = "Nao_Informado") -> str:
    """Remove caracteres proibidos para nomes de arquivos em Linux e Windows."""
    if not text or not str(text).strip():
        return default
    s = str(text).strip()
    # Substitui caracteres inválidos / \ : * ? " < > | por sublinhado
    s = re.sub(r'[/\\:*?"<>|]', '_', s)
    # Remove espaços excessivos
    s = re.sub(r'\s+', '_', s)
    # Limita tamanho para segurança do filesystem
    return s[:60].strip('._') or default


def build_organized_path(doc: Dict[str, Any], output_root: Path) -> Tuple[Path, str]:
    """
    Calcula a subpasta e o nome padronizado do arquivo com base nos metadados.
    Padrão: {classe}/{ano}/{data}_{classe}_{entidade}_{valor}_{md5_curto}.pdf
    """
    classe = sanitize_filename_part(doc.get("tipo_documento") or doc.get("classe"), default="Documentos_Diversos")
    
    # Extrai ano a partir de data ou data_modificacao
    raw_date = doc.get("data") or doc.get("data_modificacao") or ""
    ano = "Sem_Ano"
    match_ano = re.search(r"\b(19\d\d|20\d\d)\b", raw_date)
    if match_ano:
        ano = match_ano.group(1)

    data_prefix = sanitize_filename_part(raw_date[:10], default="Data_Desconhecida")
    entidade = sanitize_filename_part(doc.get("beneficiario") or doc.get("faculdade") or doc.get("cpf"), default="Geral")
    valor = sanitize_filename_part(doc.get("valor_monetario"), default="")
    md5_curto = (doc.get("md5") or "")[:8]

    # Monta o nome do arquivo
    parts = [data_prefix, classe, entidade]
    if valor and valor != "Nao_Informado":
        parts.append(valor)
    if md5_curto:
        parts.append(md5_curto)

    ext = doc.get("extensao") or ".pdf"
    if not ext.startswith("."):
        ext = f".{ext}"

    nome_final = "_".join(parts) + ext.lower()
    pasta_destino = output_root / classe / ano

    return pasta_destino / nome_final, nome_final


def organize_files(
    db_path: Union[str, Path],
    output_dir: Union[str, Path],
    pdf_source_dir: Optional[Union[str, Path]] = None,
    mode: str = "copy",
    dry_run: bool = True
) -> Dict[str, Any]:
    """
    Executa ou simula a organização de arquivos no disco.
    
    Parâmetros:
    - db_path: Caminho para o banco joakindex.db.
    - output_dir: Diretório onde os arquivos organizados serão criados.
    - pdf_source_dir: Pasta onde os PDFs originais se encontram.
    - mode: "copy" (não-destrutivo, padrão) ou "move".
    - dry_run: Se True, apenas simula e retorna o plano de ação sem tocar o disco.
    """
    db = Path(db_path).expanduser().resolve()
    out_dir = Path(output_dir).expanduser().resolve()
    base_src = Path(pdf_source_dir).expanduser().resolve() if pdf_source_dir else db.parent

    docs = get_all_documents(db)
    if not docs:
        return {"status": "vazio", "mensagem": "Nenhum documento encontrado no banco de dados.", "total": 0, "itens": []}

    plan = []
    success_count = 0
    skipped_count = 0
    errors = []

    for d in docs:
        md5 = d.get("md5")
        nome_orig = d.get("nome_arquivo") or ""
        rel_path = d.get("caminho_relativo") or nome_orig

        # Localiza o arquivo físico de origem
        src_path = base_src / rel_path
        if not src_path.exists():
            src_path = base_src / nome_orig
        if not src_path.exists():
            skipped_count += 1
            errors.append(f"Arquivo não encontrado no disco: {nome_orig} ({md5})")
            continue

        target_file, nome_final = build_organized_path(d, out_dir)

        item_plan = {
            "md5": md5,
            "origem": str(src_path),
            "origem_nome": nome_orig,
            "destino": str(target_file),
            "destino_nome": nome_final,
            "classe": d.get("tipo_documento") or "Geral"
        }
        plan.append(item_plan)

    if dry_run:
        return {
            "status": "sucesso_simulacao",
            "dry_run": True,
            "modo": mode,
            "total_planejado": len(plan),
            "total_ignorados": skipped_count,
            "diretorio_destino": str(out_dir),
            "itens": plan[:100],  # Pré-visualização dos 100 primeiros
            "erros": errors
        }

    # Execução Real (Copiar ou Mover)
    out_dir.mkdir(parents=True, exist_ok=True)
    manifesto_csv = out_dir / "manifesto_organizacao.csv"
    manifesto_rows = []

    db_updates = []

    for item in plan:
        src = Path(item["origem"])
        dst = Path(item["destino"])
        dst.parent.mkdir(parents=True, exist_ok=True)

        try:
            if mode == "move":
                shutil.move(str(src), str(dst))
            else:
                shutil.copy2(str(src), str(dst))

            success_count += 1
            rel_org = str(dst.relative_to(out_dir))
            db_updates.append((rel_org, item["md5"]))
            manifesto_rows.append([
                item["md5"],
                item["origem_nome"],
                item["origem"],
                rel_org,
                item["classe"],
                datetime.now().isoformat()
            ])
        except Exception as e:
            errors.append(f"Falha ao transferir {item['origem_nome']}: {e}")

    # Escreve o manifesto CSV de auditoria
    try:
        with open(manifesto_csv, "w", newline="", encoding="utf-8") as f_csv:
            writer = csv.writer(f_csv)
            writer.writerow(["md5", "nome_original", "caminho_origem", "caminho_organizado", "classe", "organizado_em"])
            writer.writerows(manifesto_rows)
    except Exception as e:
        errors.append(f"Falha ao gerar manifesto CSV: {e}")

    # Atualiza a coluna caminho_organizado no SQLite
    if db_updates:
        with get_connection(db) as conn:
            cur = conn.cursor()
            cur.executemany("UPDATE documentos SET caminho_organizado = ? WHERE md5 = ?", db_updates)
            conn.commit()

    return {
        "status": "sucesso",
        "dry_run": False,
        "modo": mode,
        "total_organizados": success_count,
        "total_erros": len(errors),
        "manifesto_csv": str(manifesto_csv),
        "diretorio_destino": str(out_dir),
        "erros": errors
    }
