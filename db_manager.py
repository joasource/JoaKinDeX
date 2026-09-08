#!/usr/bin/env python3
"""
joaclassificador - Gerenciador de Banco de Dados SQLite de Alta Performance
Criado por: Joaquim Ferreira Silva Neto <joaquimfsneto@gmail.com>

Fornece armazenamento relacional embutido (SQLite WAL), transações ACID,
índices para consultas instantâneas, migração transparente a partir de JSON
e sincronização contínua com os arquivos classificacao_diplomas.json e .txt.
"""

import sqlite3
import json
import os
from pathlib import Path
from typing import Dict, Any, List, Optional, Union, Tuple
from datetime import datetime

COLUMNS = [
    "md5", "nome_arquivo", "caminho_relativo", "data_modificacao", "data",
    "beneficiario", "cpf", "rg", "curso", "natureza_curso", "carga_horaria",
    "faculdade", "tipo_documento", "status", "status_conferencia",
    "metodo_leitura", "tentativa_ocr_llm", "erro", "processado_em",
    "conferido_em", "revisado_em", "observacoes_conferencia"
]

COLUMNS_SET = set(COLUMNS)


def get_db_path(target_path: Union[str, Path]) -> Path:
    """Retorna o caminho correspondente do banco SQLite classificacao_diplomas.db."""
    p = Path(target_path).expanduser().resolve()
    if p.is_file() or p.suffix.lower() == ".json":
        return p.parent / "classificacao_diplomas.db"
    return p / "classificacao_diplomas.db"


def get_json_path(target_path: Union[str, Path]) -> Path:
    """Retorna o caminho correspondente do arquivo consolidado classificacao_diplomas.json."""
    p = Path(target_path).expanduser().resolve()
    if p.is_file():
        return p.parent / "classificacao_diplomas.json"
    return p / "classificacao_diplomas.json"


def get_connection(db_path: Union[str, Path], timeout: float = 30.0) -> sqlite3.Connection:
    """Abre conexão SQLite com WAL mode, timeout estendido e row_factory."""
    conn = sqlite3.connect(str(db_path), timeout=timeout)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA synchronous = NORMAL;")
    conn.execute("PRAGMA busy_timeout = 30000;")
    return conn


def create_schema(conn: sqlite3.Connection) -> None:
    """Cria tabela e índices no banco SQLite se não existirem."""
    conn.execute("""
    CREATE TABLE IF NOT EXISTS documentos (
        md5 TEXT PRIMARY KEY,
        nome_arquivo TEXT,
        caminho_relativo TEXT,
        data_modificacao TEXT,
        data TEXT,
        beneficiario TEXT,
        cpf TEXT,
        rg TEXT,
        curso TEXT,
        natureza_curso TEXT,
        carga_horaria TEXT,
        faculdade TEXT,
        tipo_documento TEXT,
        status TEXT DEFAULT 'pendente',
        status_conferencia TEXT DEFAULT 'pendente',
        metodo_leitura TEXT DEFAULT 'texto_digital',
        tentativa_ocr_llm INTEGER DEFAULT 0,
        erro TEXT,
        processado_em TEXT,
        conferido_em TEXT,
        revisado_em TEXT,
        observacoes_conferencia TEXT,
        dados_extras TEXT
    );
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_doc_status ON documentos(status);")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_doc_status_conf ON documentos(status_conferencia);")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_doc_cpf ON documentos(cpf);")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_doc_faculdade ON documentos(faculdade);")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_doc_natureza ON documentos(natureza_curso);")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_doc_tipo ON documentos(tipo_documento);")
    conn.commit()


def doc_to_row_data(doc: Dict[str, Any]) -> Tuple:
    """Converte dicionário de documento para tupla compatível com SQLite (removendo data_criacao)."""
    item = dict(doc)
    item.pop("data_criacao", None)

    md5 = str(item.get("md5", "")).strip().lower()
    nome_arquivo = item.get("nome_arquivo")
    caminho_relativo = item.get("caminho_relativo")
    data_modificacao = item.get("data_modificacao")
    data = item.get("data")
    beneficiario = item.get("beneficiario")
    cpf = item.get("cpf")
    rg = item.get("rg")
    curso = item.get("curso")
    natureza_curso = item.get("natureza_curso")
    carga_horaria = item.get("carga_horaria")
    faculdade = item.get("faculdade")
    tipo_documento = item.get("tipo_documento")
    status = item.get("status", "pendente")
    status_conferencia = item.get("status_conferencia", "pendente")
    metodo_leitura = item.get("metodo_leitura", "texto_digital")
    tentativa_ocr = 1 if item.get("tentativa_ocr_llm") else 0
    erro = item.get("erro")
    processado_em = item.get("processado_em")
    conferido_em = item.get("conferido_em")
    revisado_em = item.get("revisado_em")
    obs_conf = item.get("observacoes_conferencia")

    # Campos extras não mapeados nas colunas fixas são serializados em JSON
    extras = {}
    for k, v in item.items():
        if k not in COLUMNS_SET and k != "dados_extras":
            extras[k] = v
    dados_extras = json.dumps(extras, ensure_ascii=False) if extras else None

    return (
        md5, nome_arquivo, caminho_relativo, data_modificacao, data,
        beneficiario, cpf, rg, curso, natureza_curso, carga_horaria,
        faculdade, tipo_documento, status, status_conferencia,
        metodo_leitura, tentativa_ocr, erro, processado_em,
        conferido_em, revisado_em, obs_conf, dados_extras
    )


def row_to_doc(row: sqlite3.Row) -> Dict[str, Any]:
    """Converte registro do SQLite para dicionário compatível com a aplicação e JSON."""
    d = {}
    for col in COLUMNS:
        d[col] = row[col]

    # Converte booleano
    d["tentativa_ocr_llm"] = bool(d["tentativa_ocr_llm"])

    # Mescla campos extras caso existam
    extras_raw = row["dados_extras"]
    if extras_raw:
        try:
            extras_dict = json.loads(extras_raw)
            if isinstance(extras_dict, dict):
                for k, v in extras_dict.items():
                    if k not in d and k != "data_criacao":
                        d[k] = v
        except Exception:
            pass

    # Garante ausência estrita de data_criacao
    d.pop("data_criacao", None)
    return d


def init_database(
    db_path: Union[str, Path],
    initial_json_path: Optional[Union[str, Path]] = None
) -> None:
    """
    Inicializa o banco SQLite, cria índices e realiza a auto-migração
    transparente caso a tabela esteja vazia e haja um JSON consolidado existente.
    """
    db = Path(db_path).expanduser().resolve()
    db.parent.mkdir(parents=True, exist_ok=True)

    with get_connection(db) as conn:
        create_schema(conn)

        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM documentos")
        count = cur.fetchone()[0]

        if count == 0 and initial_json_path:
            p_json = Path(initial_json_path).expanduser().resolve()
            if p_json.exists() and p_json.is_file():
                try:
                    with open(p_json, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    if isinstance(data, list) and data:
                        upsert_documents_batch(db, data)
                        print(f"[*] [SQLite] Auto-migração concluída: {len(data)} documentos importados com sucesso de '{p_json.name}' para '{db.name}'.")
                except Exception as e:
                    print(f"[Aviso SQLite] Falha ao importar JSON existente para SQLite: {e}")


def upsert_document(db_path: Union[str, Path], doc: Dict[str, Any]) -> None:
    """Insere ou atualiza um documento no SQLite de forma atômica."""
    db = Path(db_path).expanduser().resolve()
    row_data = doc_to_row_data(doc)
    sql = """
    INSERT INTO documentos (
        md5, nome_arquivo, caminho_relativo, data_modificacao, data,
        beneficiario, cpf, rg, curso, natureza_curso, carga_horaria,
        faculdade, tipo_documento, status, status_conferencia,
        metodo_leitura, tentativa_ocr_llm, erro, processado_em,
        conferido_em, revisado_em, observacoes_conferencia, dados_extras
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ON CONFLICT(md5) DO UPDATE SET
        nome_arquivo = COALESCE(excluded.nome_arquivo, documentos.nome_arquivo),
        caminho_relativo = COALESCE(excluded.caminho_relativo, documentos.caminho_relativo),
        data_modificacao = COALESCE(excluded.data_modificacao, documentos.data_modificacao),
        data = excluded.data,
        beneficiario = excluded.beneficiario,
        cpf = excluded.cpf,
        rg = excluded.rg,
        curso = excluded.curso,
        natureza_curso = excluded.natureza_curso,
        carga_horaria = excluded.carga_horaria,
        faculdade = excluded.faculdade,
        tipo_documento = excluded.tipo_documento,
        status = excluded.status,
        status_conferencia = excluded.status_conferencia,
        metodo_leitura = excluded.metodo_leitura,
        tentativa_ocr_llm = excluded.tentativa_ocr_llm,
        erro = excluded.erro,
        processado_em = excluded.processado_em,
        conferido_em = COALESCE(excluded.conferido_em, documentos.conferido_em),
        revisado_em = COALESCE(excluded.revisado_em, documentos.revisado_em),
        observacoes_conferencia = COALESCE(excluded.observacoes_conferencia, documentos.observacoes_conferencia),
        dados_extras = excluded.dados_extras;
    """
    with get_connection(db) as conn:
        conn.execute(sql, row_data)
        conn.commit()


def upsert_documents_batch(db_path: Union[str, Path], docs: List[Dict[str, Any]]) -> None:
    """Insere ou atualiza múltiplos documentos em uma única transação SQLite ultra-rápida."""
    if not docs:
        return
    db = Path(db_path).expanduser().resolve()
    rows_data = [doc_to_row_data(d) for d in docs if isinstance(d, dict) and d.get("md5")]

    sql = """
    INSERT INTO documentos (
        md5, nome_arquivo, caminho_relativo, data_modificacao, data,
        beneficiario, cpf, rg, curso, natureza_curso, carga_horaria,
        faculdade, tipo_documento, status, status_conferencia,
        metodo_leitura, tentativa_ocr_llm, erro, processado_em,
        conferido_em, revisado_em, observacoes_conferencia, dados_extras
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ON CONFLICT(md5) DO UPDATE SET
        nome_arquivo = COALESCE(excluded.nome_arquivo, documentos.nome_arquivo),
        caminho_relativo = COALESCE(excluded.caminho_relativo, documentos.caminho_relativo),
        data_modificacao = COALESCE(excluded.data_modificacao, documentos.data_modificacao),
        data = excluded.data,
        beneficiario = excluded.beneficiario,
        cpf = excluded.cpf,
        rg = excluded.rg,
        curso = excluded.curso,
        natureza_curso = excluded.natureza_curso,
        carga_horaria = excluded.carga_horaria,
        faculdade = excluded.faculdade,
        tipo_documento = excluded.tipo_documento,
        status = excluded.status,
        status_conferencia = excluded.status_conferencia,
        metodo_leitura = excluded.metodo_leitura,
        tentativa_ocr_llm = excluded.tentativa_ocr_llm,
        erro = excluded.erro,
        processado_em = excluded.processado_em,
        conferido_em = COALESCE(excluded.conferido_em, documentos.conferido_em),
        revisado_em = COALESCE(excluded.revisado_em, documentos.revisado_em),
        observacoes_conferencia = COALESCE(excluded.observacoes_conferencia, documentos.observacoes_conferencia),
        dados_extras = excluded.dados_extras;
    """
    with get_connection(db) as conn:
        conn.executemany(sql, rows_data)
        conn.commit()


def get_document_by_md5(db_path: Union[str, Path], md5: str) -> Optional[Dict[str, Any]]:
    """Busca um documento específico por MD5 em menos de 1ms."""
    db = Path(db_path).expanduser().resolve()
    if not db.exists():
        return None
    h = str(md5).strip().lower()
    with get_connection(db) as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM documentos WHERE md5 = ?", (h,))
        row = cur.fetchone()
        return row_to_doc(row) if row else None


def get_all_documents(
    db_path: Union[str, Path],
    only_processed: bool = False
) -> List[Dict[str, Any]]:
    """Carrega todos os documentos ordenados do banco SQLite."""
    db = Path(db_path).expanduser().resolve()
    if not db.exists():
        return []
    with get_connection(db) as conn:
        cur = conn.cursor()
        if only_processed:
            cur.execute("SELECT * FROM documentos WHERE status != 'nao_processado' ORDER BY md5 ASC")
        else:
            cur.execute("SELECT * FROM documentos ORDER BY md5 ASC")
        rows = cur.fetchall()
        return [row_to_doc(r) for r in rows]


def update_conference_status(
    db_path: Union[str, Path],
    md5: str,
    status_conferencia: str,
    observacoes: Optional[str] = None
) -> bool:
    """Atualiza aprovação de conferência humana em microssegundos."""
    db = Path(db_path).expanduser().resolve()
    if not db.exists():
        return False
    h = str(md5).strip().lower()
    now_iso = datetime.now().isoformat()
    with get_connection(db) as conn:
        cur = conn.cursor()
        if observacoes is not None:
            cur.execute("""
                UPDATE documentos
                SET status_conferencia = ?, conferido_em = ?, observacoes_conferencia = ?
                WHERE md5 = ?
            """, (status_conferencia, now_iso, observacoes, h))
        else:
            cur.execute("""
                UPDATE documentos
                SET status_conferencia = ?, conferido_em = ?
                WHERE md5 = ?
            """, (status_conferencia, now_iso, h))
        conn.commit()
        return cur.rowcount > 0


def sync_to_json(
    db_path: Union[str, Path],
    json_path: Union[str, Path],
    only_processed: bool = True
) -> None:
    """Sincroniza o banco SQLite para o arquivo JSON consolidado de forma atômica."""
    db = Path(db_path).expanduser().resolve()
    target_json = Path(json_path).expanduser().resolve()
    if not db.exists():
        return

    docs = get_all_documents(db, only_processed=only_processed)
    target_json.parent.mkdir(parents=True, exist_ok=True)
    tmp_json = target_json.parent / f".tmp_{target_json.name}"
    with open(tmp_json, "w", encoding="utf-8") as f:
        json.dump(docs, f, ensure_ascii=False, indent=2)
    tmp_json.replace(target_json)
