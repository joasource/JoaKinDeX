import pytest
import sqlite3
import json
import tempfile
from pathlib import Path
from joakindex.db import (
    get_connection,
    create_schema,
    upsert_document,
    upsert_documents_batch,
    rebuild_fts_index,
    search_fts,
    get_document_by_md5,
)


@pytest.fixture
def temp_db():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tf:
        db_path = Path(tf.name)
    with get_connection(db_path) as conn:
        create_schema(conn)
    yield db_path
    if db_path.exists():
        db_path.unlink()


def test_fts5_triggers_and_accent_insensitive_search(temp_db):
    doc1 = {
        "md5": "a1b2c3d4e5f67890",
        "nome_arquivo": "comprovante_energia.pdf",
        "tipo_documento": "Comprovante de Pagamento",
        "dominio": "financeiro",
        "faculdade": "Neoenergia Distribuidora",
        "beneficiario": "João Ferreira da Silva",
        "cpf": "123.456.789-00",
        "dados_extras": {
            "texto_transcrito": "Pagamento efetuado com sucesso via PIX para Companhia Elétrica",
            "autenticacao": "ABC-999-XYZ"
        }
    }
    upsert_document(temp_db, doc1)

    # 1. Busca com acentuação vs sem acentuação (unicode61 remove_diacritics)
    results_sem_acento = search_fts(temp_db, "joao")
    assert len(results_sem_acento) == 1
    assert results_sem_acento[0]["md5"] == "a1b2c3d4e5f67890"
    assert "<mark>" in results_sem_acento[0]["fts_snippet"]

    results_com_acento = search_fts(temp_db, "João")
    assert len(results_com_acento) == 1

    # 2. Busca por termo dentro de dados_extras (texto_transcrito)
    results_extra = search_fts(temp_db, "eletrica")
    assert len(results_extra) == 1
    assert "eletrica" in results_extra[0]["fts_snippet"].lower() or "elétrica" in results_extra[0]["fts_snippet"].lower()


def test_fts5_update_and_rebuild(temp_db):
    doc = {
        "md5": "doc_update_123",
        "nome_arquivo": "boleto_antigo.pdf",
        "tipo_documento": "Boleto Bancário",
        "dominio": "financeiro",
        "dados_extras": {"texto_transcrito": "Primeira versao do texto do boleto"}
    }
    upsert_document(temp_db, doc)
    assert len(search_fts(temp_db, "Primeira")) == 1

    # Atualiza documento
    doc["dados_extras"]["texto_transcrito"] = "Segunda versao retificada do boleto"
    upsert_document(temp_db, doc)

    # Verifica se FTS5 atualizou via gatilho
    assert len(search_fts(temp_db, "Primeira")) == 0
    assert len(search_fts(temp_db, "Segunda")) == 1

    # Teste de rebuild_fts_index
    count = rebuild_fts_index(temp_db)
    assert count >= 1
    assert len(search_fts(temp_db, "Segunda")) == 1


def test_fts5_boolean_operators_and_fallback(temp_db):
    doc_a = {
        "md5": "doc_a",
        "nome_arquivo": "contrato_social.pdf",
        "tipo_documento": "Contrato",
        "dominio": "juridico",
        "dados_extras": {"texto_transcrito": "Empresa Alfa e Beta tecnologia"}
    }
    doc_b = {
        "md5": "doc_b",
        "nome_arquivo": "termo_posse.pdf",
        "tipo_documento": "Termo",
        "dominio": "juridico",
        "dados_extras": {"texto_transcrito": "Empresa Alfa consultoria"}
    }
    upsert_documents_batch(temp_db, [doc_a, doc_b])

    # Busca booleana AND
    res_and = search_fts(temp_db, 'Alfa AND Beta')
    assert len(res_and) == 1
    assert res_and[0]["md5"] == "doc_a"

    # Busca booleana NOT
    res_not = search_fts(temp_db, 'Alfa NOT Beta')
    assert len(res_not) == 1
    assert res_not[0]["md5"] == "doc_b"

    # Fallback seguro para caracteres malformados
    res_syntax_err = search_fts(temp_db, 'Alfa AND "termo incompleto')
    assert isinstance(res_syntax_err, list)
