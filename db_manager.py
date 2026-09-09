#!/usr/bin/env python3
"""
JoaKinDeX - Gerenciador de Banco de Dados SQLite de Alta Performance
Criado por: Joaquim Ferreira Silva Neto <joaquimfsneto@gmail.com>

Fornece armazenamento relacional embutido (SQLite WAL), transações ACID,
índices para consultas instantâneas, migração transparente a partir de JSON
e sincronização contínua com os arquivos joakindex.json e .txt.
"""

import sqlite3
import json
import os
from pathlib import Path
from typing import Dict, Any, List, Optional, Union, Tuple
from datetime import datetime

COLUMNS = [
    "md5", "nome_arquivo", "caminho_relativo", "extensao", "dominio", "data_modificacao", "autor", "data",
    "beneficiario", "cpf", "rg", "cnpj", "curso", "natureza_curso", "carga_horaria",
    "faculdade", "tipo_documento", "valor_monetario", "status", "status_conferencia",
    "metodo_leitura", "tentativa_ocr_llm", "erro", "processado_em",
    "conferido_em", "revisado_em", "observacoes_conferencia",
    "todos_dominios", "todos_tipos", "dossie_paginas",
    "dublin_core", "dc_title", "dc_subject", "dc_creator_tool",
    "dados_extras"
]

COLUMNS_SET = set(COLUMNS)


def get_db_path(target_path: Union[str, Path]) -> Path:
    """Retorna o caminho correspondente do banco SQLite joakindex.db (com fallback para legados)."""
    p = Path(target_path).expanduser().resolve()
    parent_dir = p.parent if (p.is_file() or p.suffix.lower() in [".json", ".db"]) else p
    
    # Se um arquivo .db explícito e existente foi passado, respeita
    if p.suffix.lower() == ".db" and p.exists():
        return p

    target_db = parent_dir / "joakindex.db"
    if target_db.exists():
        return target_db

    legacy_db = parent_dir / "classificacao_diplomas.db"
    if legacy_db.exists():
        return legacy_db

    return target_db


def get_json_path(target_path: Union[str, Path]) -> Path:
    """Retorna o caminho correspondente do arquivo consolidado joakindex.json (com fallback para legados)."""
    p = Path(target_path).expanduser().resolve()
    parent_dir = p.parent if (p.is_file() or p.suffix.lower() in [".json", ".db"]) else p

    # Se um arquivo .json explícito e existente foi passado, respeita
    if p.suffix.lower() == ".json" and p.exists():
        return p

    target_json = parent_dir / "joakindex.json"
    if target_json.exists():
        return target_json

    legacy_json = parent_dir / "classificacao_diplomas.json"
    if legacy_json.exists():
        return legacy_json

    return target_json


def get_connection(db_path: Union[str, Path], timeout: float = 30.0) -> sqlite3.Connection:
    """Abre conexão SQLite com WAL mode, timeout estendido e row_factory."""
    conn = sqlite3.connect(str(db_path), timeout=timeout)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA synchronous = NORMAL;")
    conn.execute("PRAGMA busy_timeout = 30000;")
    return conn


def create_schema(conn: sqlite3.Connection) -> None:
    """Cria tabela e índices no banco SQLite se não existirem, ou aplica migrações incrementais."""
    conn.execute("""
    CREATE TABLE IF NOT EXISTS documentos (
        md5 TEXT PRIMARY KEY,
        nome_arquivo TEXT,
        caminho_relativo TEXT,
        extensao TEXT,
        dominio TEXT DEFAULT 'academico',
        data_modificacao TEXT,
        autor TEXT,
        data TEXT,
        beneficiario TEXT,
        cpf TEXT,
        rg TEXT,
        cnpj TEXT,
        curso TEXT,
        natureza_curso TEXT,
        carga_horaria TEXT,
        faculdade TEXT,
        tipo_documento TEXT,
        valor_monetario TEXT,
        status TEXT DEFAULT 'pendente',
        status_conferencia TEXT DEFAULT 'pendente',
        metodo_leitura TEXT DEFAULT 'texto_digital',
        tentativa_ocr_llm INTEGER DEFAULT 0,
        erro TEXT,
        processado_em TEXT,
        conferido_em TEXT,
        revisado_em TEXT,
        observacoes_conferencia TEXT,
        todos_dominios TEXT,
        todos_tipos TEXT,
        dossie_paginas TEXT,
        dublin_core TEXT,
        dc_title TEXT,
        dc_subject TEXT,
        dc_creator_tool TEXT,
        dados_extras TEXT
    );
    """)

    # Migração incremental transparente de colunas caso a tabela já exista
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(documentos);")
    existing_cols = {row["name"] for row in cur.fetchall()}

    if "extensao" not in existing_cols:
        conn.execute("ALTER TABLE documentos ADD COLUMN extensao TEXT;")
    if "dominio" not in existing_cols:
        conn.execute("ALTER TABLE documentos ADD COLUMN dominio TEXT DEFAULT 'academico';")
    if "cnpj" not in existing_cols:
        conn.execute("ALTER TABLE documentos ADD COLUMN cnpj TEXT;")
    if "valor_monetario" not in existing_cols:
        conn.execute("ALTER TABLE documentos ADD COLUMN valor_monetario TEXT;")
    if "todos_dominios" not in existing_cols:
        conn.execute("ALTER TABLE documentos ADD COLUMN todos_dominios TEXT;")
    if "todos_tipos" not in existing_cols:
        conn.execute("ALTER TABLE documentos ADD COLUMN todos_tipos TEXT;")
    if "dossie_paginas" not in existing_cols:
        conn.execute("ALTER TABLE documentos ADD COLUMN dossie_paginas TEXT;")
    if "autor" not in existing_cols:
        conn.execute("ALTER TABLE documentos ADD COLUMN autor TEXT;")
    if "dublin_core" not in existing_cols:
        conn.execute("ALTER TABLE documentos ADD COLUMN dublin_core TEXT;")
    if "dc_title" not in existing_cols:
        conn.execute("ALTER TABLE documentos ADD COLUMN dc_title TEXT;")
    if "dc_subject" not in existing_cols:
        conn.execute("ALTER TABLE documentos ADD COLUMN dc_subject TEXT;")
    if "dc_creator_tool" not in existing_cols:
        conn.execute("ALTER TABLE documentos ADD COLUMN dc_creator_tool TEXT;")

    # Índices para consultas instantâneas
    conn.execute("CREATE INDEX IF NOT EXISTS idx_doc_status ON documentos(status);")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_doc_status_conf ON documentos(status_conferencia);")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_doc_cpf ON documentos(cpf);")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_doc_cnpj ON documentos(cnpj);")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_doc_faculdade ON documentos(faculdade);")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_doc_natureza ON documentos(natureza_curso);")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_doc_tipo ON documentos(tipo_documento);")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_doc_dominio ON documentos(dominio);")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_doc_extensao ON documentos(extensao);")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_doc_autor ON documentos(autor);")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_doc_dc_title ON documentos(dc_title);")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_doc_dc_subject ON documentos(dc_subject);")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_doc_dc_tool ON documentos(dc_creator_tool);")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_doc_todos_tipos ON documentos(todos_tipos);")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_doc_todos_dominios ON documentos(todos_dominios);")

    # Tabela de Regras e Aprendizado Incremental do Usuário
    conn.execute("""
    CREATE TABLE IF NOT EXISTS regras_aprendidas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        termo_chave TEXT NOT NULL,
        campo_alvo TEXT NOT NULL DEFAULT 'tipo_documento',
        valor_atribuido TEXT NOT NULL,
        dominio TEXT NOT NULL,
        remover_pix INTEGER DEFAULT 0,
        origem_md5 TEXT,
        criado_em TEXT NOT NULL
    );
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_regra_termo ON regras_aprendidas(termo_chave);")

    # Garante preenchimento de domínio retroativo nos registros antigos
    conn.execute("UPDATE documentos SET dominio = 'academico' WHERE dominio IS NULL OR dominio = '';")
    conn.commit()


def doc_to_row_data(doc: Dict[str, Any]) -> Tuple:
    """Converte dicionário de documento para tupla compatível com SQLite (removendo data_criacao)."""
    item = dict(doc)
    item.pop("data_criacao", None)

    md5 = str(item.get("md5", "")).strip().lower()
    nome_arquivo = item.get("nome_arquivo")
    caminho_relativo = item.get("caminho_relativo")

    extensao = item.get("extensao")
    if not extensao and nome_arquivo:
        extensao = Path(nome_arquivo).suffix.lower()

    tipo_documento = item.get("tipo_documento")
    valor_monetario = item.get("valor_monetario")

    dominio = item.get("dominio")
    if not dominio:
        tipo_lower = str(tipo_documento or "").lower()
        is_non_fin = any(k in tipo_lower for k in ["inscrição", "inscricao", "situação", "situacao", "cnpj", "residência", "residencia", "matrícula", "matricula", "rendimentos", "votação", "votacao"])
        if not is_non_fin and ("pix" in tipo_lower or "comprovante de pagamento" in tipo_lower or "comprovante pix" in tipo_lower or "recibo de pagamento" in tipo_lower or "boleto" in tipo_lower or valor_monetario):
            dominio = "financeiro"
        elif any(k in tipo_lower for k in ["situação cadastral", "situacao cadastral", "cnpj", "currículo", "curriculo", "experiência profissional", "experiencia profissional"]):
            dominio = "profissional"
        elif any(k in tipo_lower for k in ["rg", "cnh", "identidade", "cpf", "certidão", "certidao"]):
            dominio = "identificacao"
        elif any(k in tipo_lower for k in ["contrato", "procuração", "procuracao", "posse", "juridico"]):
            dominio = "juridico"
        else:
            dominio = "academico"

    data_modificacao = item.get("data_modificacao")
    autor = item.get("autor")
    data = item.get("data")
    beneficiario = item.get("beneficiario")
    cpf = item.get("cpf")
    rg = item.get("rg")
    cnpj = item.get("cnpj")
    curso = item.get("curso")
    natureza_curso = item.get("natureza_curso")
    carga_horaria = item.get("carga_horaria")
    faculdade = item.get("faculdade")
    status = item.get("status", "pendente")
    status_conferencia = item.get("status_conferencia", "pendente")
    metodo_leitura = item.get("metodo_leitura", "texto_digital")
    tentativa_ocr = 1 if item.get("tentativa_ocr_llm") else 0
    erro = item.get("erro")
    processado_em = item.get("processado_em")
    conferido_em = item.get("conferido_em")
    revisado_em = item.get("revisado_em")
    obs_conf = item.get("observacoes_conferencia")

    # Multi-classificação e dossiê
    todos_dominios = item.get("todos_dominios")
    if isinstance(todos_dominios, list):
        todos_dominios = json.dumps([str(x).strip() for x in todos_dominios if x], ensure_ascii=False)
    elif isinstance(todos_dominios, str) and todos_dominios.strip():
        todos_dominios = todos_dominios.strip()
    elif dominio:
        todos_dominios = json.dumps([dominio], ensure_ascii=False)
    else:
        todos_dominios = None

    todos_tipos = item.get("todos_tipos")
    if isinstance(todos_tipos, list):
        todos_tipos = json.dumps([str(x).strip() for x in todos_tipos if x], ensure_ascii=False)
    elif isinstance(todos_tipos, str) and todos_tipos.strip():
        todos_tipos = todos_tipos.strip()
    elif tipo_documento:
        todos_tipos = json.dumps([tipo_documento], ensure_ascii=False)
    else:
        todos_tipos = None

    dossie_paginas = item.get("dossie_paginas")
    if isinstance(dossie_paginas, (list, dict)):
        dossie_paginas = json.dumps(dossie_paginas, ensure_ascii=False)
    elif isinstance(dossie_paginas, str) and dossie_paginas.strip():
        dossie_paginas = dossie_paginas.strip()
    else:
        dossie_paginas = None

    dublin_core = item.get("dublin_core")
    if isinstance(dublin_core, (dict, list)):
        dublin_core = json.dumps(dublin_core, ensure_ascii=False)
    elif isinstance(dublin_core, str) and dublin_core.strip():
        dublin_core = dublin_core.strip()
    else:
        dublin_core = None

    dc_title = item.get("dc_title")
    dc_subject = item.get("dc_subject")
    dc_creator_tool = item.get("dc_creator_tool")
    if isinstance(item.get("dublin_core"), dict):
        dc_dict = item["dublin_core"]
        if not dc_title:
            dc_title = dc_dict.get("title")
        if not dc_subject:
            dc_subject = dc_dict.get("subject")
        if not dc_creator_tool:
            dc_creator_tool = dc_dict.get("creator_tool")

    # Campos extras não mapeados nas colunas fixas são serializados em JSON
    extras = {}
    if isinstance(item.get("dados_extras"), dict):
        extras.update(item["dados_extras"])
    for k, v in item.items():
        if k not in COLUMNS_SET and k != "dados_extras":
            extras[k] = v
    dados_extras = json.dumps(extras, ensure_ascii=False) if extras else None

    return (
        md5, nome_arquivo, caminho_relativo, extensao, dominio, data_modificacao, autor, data,
        beneficiario, cpf, rg, cnpj, curso, natureza_curso, carga_horaria,
        faculdade, tipo_documento, valor_monetario, status, status_conferencia,
        metodo_leitura, tentativa_ocr, erro, processado_em,
        conferido_em, revisado_em, obs_conf,
        todos_dominios, todos_tipos, dossie_paginas,
        dublin_core, dc_title, dc_subject, dc_creator_tool,
        dados_extras
    )


def row_to_doc(row: sqlite3.Row) -> Dict[str, Any]:
    """Converte registro do SQLite para dicionário compatível com a aplicação e JSON."""
    d = {}
    row_keys = set(row.keys())
    for col in COLUMNS:
        if col in row_keys:
            d[col] = row[col]

    # Converte booleano
    d["tentativa_ocr_llm"] = bool(d.get("tentativa_ocr_llm", False))

    # Desserializa dublin_core JSON se necessário
    if "dublin_core" in row_keys and d.get("dublin_core"):
        raw_dc = d["dublin_core"]
        if isinstance(raw_dc, str):
            try:
                d["dublin_core"] = json.loads(raw_dc)
            except Exception:
                d["dublin_core"] = {}

    # Mescla campos extras caso existam
    if "dados_extras" in row_keys:
        extras_raw = row["dados_extras"]
        if extras_raw:
            try:
                extras_dict = json.loads(extras_raw)
                if isinstance(extras_dict, dict):
                    d["dados_extras"] = extras_dict
                    for k, v in extras_dict.items():
                        if k not in d and k != "data_criacao":
                            d[k] = v
            except Exception:
                pass

    # Normalização de listas de tipos e domínios para consumo da aplicação e frontend
    if "todos_dominios" in row_keys and d.get("todos_dominios"):
        td = d["todos_dominios"]
        if isinstance(td, str):
            try:
                parsed = json.loads(td)
                d["todos_dominios"] = parsed if isinstance(parsed, list) else [s.strip() for s in td.split(",") if s.strip()]
            except Exception:
                d["todos_dominios"] = [s.strip() for s in td.split(",") if s.strip()]
    else:
        d["todos_dominios"] = [d["dominio"]] if d.get("dominio") else []

    if "todos_tipos" in row_keys and d.get("todos_tipos"):
        tt = d["todos_tipos"]
        if isinstance(tt, str):
            try:
                parsed = json.loads(tt)
                d["todos_tipos"] = parsed if isinstance(parsed, list) else [s.strip() for s in tt.split(",") if s.strip()]
            except Exception:
                d["todos_tipos"] = [s.strip() for s in tt.split(",") if s.strip()]
    else:
        d["todos_tipos"] = [d["tipo_documento"]] if d.get("tipo_documento") else []

    if "dossie_paginas" in row_keys and d.get("dossie_paginas"):
        dp = d["dossie_paginas"]
        if isinstance(dp, str):
            try:
                d["dossie_paginas"] = json.loads(dp)
            except Exception:
                d["dossie_paginas"] = []
    else:
        d["dossie_paginas"] = []

    # Assegura que todos os tipos mapeados (inclusive em páginas de dossiê) constem em todos_tipos
    cur_tipos = list(d.get("todos_tipos") or [])
    seen_k = {t.strip().lower() for t in cur_tipos if t and t.strip()}
    if d.get("tipo_documento"):
        mt = d["tipo_documento"].strip()
        if mt and mt.lower() not in seen_k:
            cur_tipos.insert(0, mt)
            seen_k.add(mt.lower())
    if isinstance(d.get("dossie_paginas"), list):
        for p in d["dossie_paginas"]:
            if isinstance(p, dict) and p.get("tipo"):
                pt = str(p["tipo"]).strip()
                if pt and pt.lower() not in seen_k and pt not in ["Documento", "Não identificado"]:
                    cur_tipos.append(pt)
                    seen_k.add(pt.lower())
    d["todos_tipos"] = cur_tipos

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
        md5, nome_arquivo, caminho_relativo, extensao, dominio, data_modificacao, autor, data,
        beneficiario, cpf, rg, cnpj, curso, natureza_curso, carga_horaria,
        faculdade, tipo_documento, valor_monetario, status, status_conferencia,
        metodo_leitura, tentativa_ocr_llm, erro, processado_em,
        conferido_em, revisado_em, observacoes_conferencia,
        todos_dominios, todos_tipos, dossie_paginas,
        dublin_core, dc_title, dc_subject, dc_creator_tool, dados_extras
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ON CONFLICT(md5) DO UPDATE SET
        nome_arquivo = COALESCE(excluded.nome_arquivo, documentos.nome_arquivo),
        caminho_relativo = COALESCE(excluded.caminho_relativo, documentos.caminho_relativo),
        extensao = COALESCE(excluded.extensao, documentos.extensao),
        dominio = COALESCE(excluded.dominio, documentos.dominio),
        data_modificacao = COALESCE(excluded.data_modificacao, documentos.data_modificacao),
        autor = COALESCE(excluded.autor, documentos.autor),
        data = excluded.data,
        beneficiario = excluded.beneficiario,
        cpf = excluded.cpf,
        rg = excluded.rg,
        cnpj = excluded.cnpj,
        curso = excluded.curso,
        natureza_curso = excluded.natureza_curso,
        carga_horaria = excluded.carga_horaria,
        faculdade = excluded.faculdade,
        tipo_documento = excluded.tipo_documento,
        valor_monetario = excluded.valor_monetario,
        status = excluded.status,
        status_conferencia = excluded.status_conferencia,
        metodo_leitura = excluded.metodo_leitura,
        tentativa_ocr_llm = excluded.tentativa_ocr_llm,
        erro = excluded.erro,
        processado_em = excluded.processado_em,
        conferido_em = COALESCE(excluded.conferido_em, documentos.conferido_em),
        revisado_em = COALESCE(excluded.revisado_em, documentos.revisado_em),
        observacoes_conferencia = COALESCE(excluded.observacoes_conferencia, documentos.observacoes_conferencia),
        todos_dominios = excluded.todos_dominios,
        todos_tipos = excluded.todos_tipos,
        dossie_paginas = excluded.dossie_paginas,
        dublin_core = COALESCE(excluded.dublin_core, documentos.dublin_core),
        dc_title = COALESCE(excluded.dc_title, documentos.dc_title),
        dc_subject = COALESCE(excluded.dc_subject, documentos.dc_subject),
        dc_creator_tool = COALESCE(excluded.dc_creator_tool, documentos.dc_creator_tool),
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
        md5, nome_arquivo, caminho_relativo, extensao, dominio, data_modificacao, autor, data,
        beneficiario, cpf, rg, cnpj, curso, natureza_curso, carga_horaria,
        faculdade, tipo_documento, valor_monetario, status, status_conferencia,
        metodo_leitura, tentativa_ocr_llm, erro, processado_em,
        conferido_em, revisado_em, observacoes_conferencia,
        todos_dominios, todos_tipos, dossie_paginas,
        dublin_core, dc_title, dc_subject, dc_creator_tool, dados_extras
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ON CONFLICT(md5) DO UPDATE SET
        nome_arquivo = COALESCE(excluded.nome_arquivo, documentos.nome_arquivo),
        caminho_relativo = COALESCE(excluded.caminho_relativo, documentos.caminho_relativo),
        extensao = COALESCE(excluded.extensao, documentos.extensao),
        dominio = COALESCE(excluded.dominio, documentos.dominio),
        data_modificacao = COALESCE(excluded.data_modificacao, documentos.data_modificacao),
        autor = COALESCE(excluded.autor, documentos.autor),
        data = excluded.data,
        beneficiario = excluded.beneficiario,
        cpf = excluded.cpf,
        rg = excluded.rg,
        cnpj = excluded.cnpj,
        curso = excluded.curso,
        natureza_curso = excluded.natureza_curso,
        carga_horaria = excluded.carga_horaria,
        faculdade = excluded.faculdade,
        tipo_documento = excluded.tipo_documento,
        valor_monetario = excluded.valor_monetario,
        status = excluded.status,
        status_conferencia = excluded.status_conferencia,
        metodo_leitura = excluded.metodo_leitura,
        tentativa_ocr_llm = excluded.tentativa_ocr_llm,
        erro = excluded.erro,
        processado_em = excluded.processado_em,
        conferido_em = COALESCE(excluded.conferido_em, documentos.conferido_em),
        revisado_em = COALESCE(excluded.revisado_em, documentos.revisado_em),
        observacoes_conferencia = COALESCE(excluded.observacoes_conferencia, documentos.observacoes_conferencia),
        todos_dominios = excluded.todos_dominios,
        todos_tipos = excluded.todos_tipos,
        dossie_paginas = excluded.dossie_paginas,
        dublin_core = COALESCE(excluded.dublin_core, documentos.dublin_core),
        dc_title = COALESCE(excluded.dc_title, documentos.dc_title),
        dc_subject = COALESCE(excluded.dc_subject, documentos.dc_subject),
        dc_creator_tool = COALESCE(excluded.dc_creator_tool, documentos.dc_creator_tool),
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


def batch_update_conference_status(
    db_path: Union[str, Path],
    md5s: List[str],
    status_conferencia: str,
    observacoes: Optional[str] = None
) -> int:
    """Atualiza aprovação de conferência para múltiplos documentos em uma transação única."""
    if not md5s:
        return 0
    db = Path(db_path).expanduser().resolve()
    if not db.exists():
        return 0
    clean_md5s = [str(m).strip().lower() for m in md5s if m]
    if not clean_md5s:
        return 0

    now_iso = datetime.now().isoformat()
    with get_connection(db) as conn:
        cur = conn.cursor()
        if observacoes is not None:
            params = [(status_conferencia, now_iso, observacoes, m) for m in clean_md5s]
            cur.executemany("""
                UPDATE documentos
                SET status_conferencia = ?, conferido_em = ?, observacoes_conferencia = ?
                WHERE md5 = ?
            """, params)
        else:
            params = [(status_conferencia, now_iso, m) for m in clean_md5s]
            cur.executemany("""
                UPDATE documentos
                SET status_conferencia = ?, conferido_em = ?
                WHERE md5 = ?
            """, params)
        total_updated = cur.rowcount
        conn.commit()
    return total_updated


def batch_update_tag_domain(
    db_path: Union[str, Path],
    md5s: List[str],
    tipo_documento: Optional[str] = None,
    dominio: Optional[str] = None,
    faculdade: Optional[str] = None,
    status_conferencia: Optional[str] = None
) -> int:
    """Atualiza tipo, domínio, emissor ou status para múltiplos documentos em uma transação única."""
    if not md5s:
        return 0
    db = Path(db_path).expanduser().resolve()
    if not db.exists():
        return 0
    clean_md5s = [str(m).strip().lower() for m in md5s if m]
    if not clean_md5s:
        return 0

    set_clauses = []
    base_values = []
    now_iso = datetime.now().isoformat()

    if tipo_documento is not None and str(tipo_documento).strip():
        t_clean = str(tipo_documento).strip()
        set_clauses.append("tipo_documento = ?")
        base_values.append(t_clean)
        set_clauses.append("todos_tipos = ?")
        base_values.append(json.dumps([t_clean], ensure_ascii=False))

    if dominio is not None and str(dominio).strip():
        d_clean = str(dominio).strip().lower()
        set_clauses.append("dominio = ?")
        base_values.append(d_clean)
        set_clauses.append("todos_dominios = ?")
        base_values.append(json.dumps([d_clean], ensure_ascii=False))

    if faculdade is not None and str(faculdade).strip():
        f_clean = str(faculdade).strip()
        set_clauses.append("faculdade = ?")
        base_values.append(f_clean)

    if status_conferencia is not None and str(status_conferencia).strip():
        s_clean = str(status_conferencia).strip().lower()
        set_clauses.append("status_conferencia = ?")
        base_values.append(s_clean)
        if s_clean == "aprovado":
            set_clauses.append("conferido_em = ?")
            base_values.append(now_iso)

    if not set_clauses:
        return 0

    set_clauses.append("revisado_em = ?")
    base_values.append(now_iso)

    sql = f"UPDATE documentos SET {', '.join(set_clauses)} WHERE md5 = ?"

    with get_connection(db) as conn:
        cur = conn.cursor()
        params = [tuple(base_values + [m]) for m in clean_md5s]
        cur.executemany(sql, params)
        total_updated = cur.rowcount
        conn.commit()
    return total_updated



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


def salvar_regra_aprendida(
    db_path: Union[str, Path],
    termo_chave: str,
    valor_atribuido: str,
    dominio: str,
    campo_alvo: str = "tipo_documento",
    remover_pix: bool = False,
    origem_md5: Optional[str] = None
) -> int:
    """Registra uma regra aprendida a partir de conferência ou correção manual do usuário."""
    db = Path(db_path).expanduser().resolve()
    with get_connection(db) as conn:
        create_schema(conn)
        cur = conn.cursor()
        cur.execute(
            "SELECT id FROM regras_aprendidas WHERE LOWER(termo_chave) = LOWER(?) AND LOWER(campo_alvo) = LOWER(?)",
            (termo_chave.strip(), campo_alvo.strip())
        )
        row = cur.fetchone()
        now_str = datetime.now().isoformat()
        if row:
            cur.execute("""
                UPDATE regras_aprendidas
                SET valor_atribuido = ?, dominio = ?, remover_pix = ?, origem_md5 = ?, criado_em = ?
                WHERE id = ?
            """, (valor_atribuido.strip(), dominio.strip(), 1 if remover_pix else 0, origem_md5, now_str, row["id"]))
            conn.commit()
            return row["id"]
        else:
            cur.execute("""
                INSERT INTO regras_aprendidas (termo_chave, campo_alvo, valor_atribuido, dominio, remover_pix, origem_md5, criado_em)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (termo_chave.strip(), campo_alvo.strip(), valor_atribuido.strip(), dominio.strip(), 1 if remover_pix else 0, origem_md5, now_str))
            conn.commit()
            return cur.lastrowid


def obter_regras_aprendidas(db_path: Union[str, Path]) -> List[Dict[str, Any]]:
    """Retorna todas as regras aprendidas cadastradas pelo usuário."""
    db = Path(db_path).expanduser().resolve()
    with get_connection(db) as conn:
        create_schema(conn)
        cur = conn.cursor()
        cur.execute("SELECT * FROM regras_aprendidas ORDER BY id DESC")
        return [dict(r) for r in cur.fetchall()]


def remover_regra_aprendida(db_path: Union[str, Path], regra_id: int) -> bool:
    """Exclui uma regra aprendida pelo seu ID."""
    db = Path(db_path).expanduser().resolve()
    with get_connection(db) as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM regras_aprendidas WHERE id = ?", (regra_id,))
        conn.commit()
        return cur.rowcount > 0


def consultar_regra_para_texto(db_path: Union[str, Path], texto: str) -> Optional[Dict[str, Any]]:
    """Verifica se algum termo-chave de regra aprendida ocorre no texto."""
    if not texto:
        return None
    t_lower = texto.lower()
    regras = obter_regras_aprendidas(db_path)
    for r in regras:
        termo = (r.get("termo_chave") or "").strip().lower()
        if termo and termo in t_lower:
            return r
    return None
