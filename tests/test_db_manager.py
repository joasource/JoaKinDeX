import pytest
import sqlite3
import json
from pathlib import Path
from db_manager import (
    get_db_path,
    get_json_path,
    get_connection,
    init_database,
    upsert_documents_batch,
    get_document_by_md5,
    get_all_documents,
    update_conference_status,
)


def test_get_db_and_json_paths(tmp_path):
    # Testing directory resolution
    db_p = get_db_path(tmp_path)
    assert db_p.name == "joakindex.db"
    assert db_p.parent == tmp_path

    json_p = get_json_path(tmp_path)
    assert json_p.name == "joakindex.json"
    assert json_p.parent == tmp_path

    # Explicit .db file
    custom_db = tmp_path / "custom.db"
    custom_db.touch()
    assert get_db_path(custom_db) == custom_db


def test_database_init_and_wal(tmp_path):
    db_file = tmp_path / "test_joakindex.db"
    init_database(db_file)
    conn = get_connection(db_file)
    try:
        # Check journal mode is WAL
        cur = conn.execute("PRAGMA journal_mode;")
        row = cur.fetchone()
        assert row[0].upper() == "WAL"

        # Check table documentos exists
        cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='documentos';")
        assert cur.fetchone() is not None
    finally:
        conn.close()


def test_upsert_and_retrieve_document(tmp_path):
    db_file = tmp_path / "test_joakindex.db"
    init_database(db_file)

    doc = {
        "md5": "abc1234567890abcdef1234567890abc",
        "nome_arquivo": "diploma_teste.pdf",
        "caminho_relativo": "diploma_teste.pdf",
        "extensao": ".pdf",
        "beneficiario": "Maria Silva",
        "cpf": "111.444.777-35",
        "curso": "Direito",
        "natureza_curso": "Graduação / Curso Superior",
        "faculdade": "USP",
        "status": "sucesso",
        "dublin_core": {
            "title": "Diploma de Maria Silva",
            "creator": "Secretaria Academica",
            "creator_tool": "Adobe Acrobat Pro"
        }
    }

    upsert_documents_batch(db_file, [doc])

    retrieved = get_document_by_md5(db_file, "abc1234567890abcdef1234567890abc")
    assert retrieved is not None
    assert retrieved["beneficiario"] == "Maria Silva"
    assert retrieved["cpf"] == "111.444.777-35"
    assert retrieved["curso"] == "Direito"
    assert isinstance(retrieved["dublin_core"], dict)
    assert retrieved["dublin_core"]["title"] == "Diploma de Maria Silva"
    assert retrieved["dc_creator_tool"] == "Adobe Acrobat Pro"

    # Test conference update
    success = update_conference_status(
        db_path=db_file,
        md5="abc1234567890abcdef1234567890abc",
        status_conferencia="aprovado",
        observacoes="Conferido com sucesso"
    )
    assert success is True

    updated = get_document_by_md5(db_file, "abc1234567890abcdef1234567890abc")
    assert updated["status_conferencia"] == "aprovado"
    assert updated["observacoes_conferencia"] == "Conferido com sucesso"


def test_load_documents_from_db(tmp_path):
    db_file = tmp_path / "test_joakindex.db"
    init_database(db_file)

    docs = [
        {"md5": f"md5_{i:03d}", "nome_arquivo": f"doc_{i}.pdf", "beneficiario": f"Pessoa {i}"}
        for i in range(5)
    ]
    upsert_documents_batch(db_file, docs)

    all_docs = get_all_documents(db_file)
    assert len(all_docs) == 5
