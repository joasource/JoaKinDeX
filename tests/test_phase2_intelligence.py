import pytest
import tempfile
from pathlib import Path
from joakindex.db import get_connection, create_schema, upsert_document, upsert_documents_batch
from joakindex.inspector import inspect_pdf
from joakindex.deduplication import calculate_text_similarity, detect_duplicates, apply_detected_duplicates, resolve_duplicate
from joakindex.dossier import build_and_save_dossiers, get_all_dossiers


@pytest.fixture
def temp_db():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tf:
        db_path = Path(tf.name)
    with get_connection(db_path) as conn:
        create_schema(conn)
    yield db_path
    if db_path.exists():
        db_path.unlink()


def test_calculate_text_similarity():
    # Textos idênticos
    t1 = "Comprovante de pagamento de boleto bancario neoenergia valor 150"
    assert calculate_text_similarity(t1, t1) == 1.0

    # Textos com leve variação de OCR
    t2 = "Comprovante de pagamento de boleto bancario neoenergia valor 150 data 12/03"
    sim = calculate_text_similarity(t1, t2)
    assert sim >= 0.80

    # Textos completamente diferentes
    t3 = "Diploma de graduacao em medicina veterinaria faculdade federal"
    assert calculate_text_similarity(t1, t3) < 0.20


def test_detect_and_apply_duplicates(temp_db):
    doc1 = {
        "md5": "md5_original",
        "nome_arquivo": "boleto_bb_scan1.pdf",
        "tipo_documento": "Boleto Bancário",
        "dados_extras": {"texto_transcrito": "Boleto de cobranca Banco do Brasil beneficiario Silva valor 450 reais linha digitavel 1234"}
    }
    doc2 = {
        "md5": "md5_copia",
        "nome_arquivo": "boleto_bb_scan2.pdf",
        "tipo_documento": "Boleto Bancário",
        "dados_extras": {"texto_transcrito": "Boleto de cobranca Banco do Brasil beneficiario Silva valor 450 reais linha digitavel 1234"}
    }
    upsert_documents_batch(temp_db, [doc1, doc2])

    pairs = detect_duplicates(temp_db, threshold=0.90)
    assert len(pairs) == 1
    found_md5s = {pairs[0]["canonico_md5"], pairs[0]["duplicata_md5"]}
    assert found_md5s == {"md5_original", "md5_copia"}

    updated = apply_detected_duplicates(temp_db, pairs)
    assert updated == 1

    # Testa resolução
    ok = resolve_duplicate(temp_db, "md5_copia", descartar=True)
    assert ok is True


def test_dossier_clustering_by_cpf_and_name(temp_db):
    doc_cpf1 = {
        "md5": "doc_cpf_1",
        "nome_arquivo": "rg_joaquim.pdf",
        "tipo_documento": "RG",
        "cpf": "111.222.333-44",
        "beneficiario": "Joaquim Ferreira"
    }
    doc_cpf2 = {
        "md5": "doc_cpf_2",
        "nome_arquivo": "comprovante_residencia.pdf",
        "tipo_documento": "Comprovante de Residência",
        "cpf": "111.222.333-44",
        "beneficiario": "Joaquim Ferreira"
    }
    doc_isolado = {
        "md5": "doc_outro",
        "nome_arquivo": "outra_pessoa.pdf",
        "tipo_documento": "Certidão",
        "cpf": "999.888.777-66",
        "beneficiario": "Maria Souza"
    }
    upsert_documents_batch(temp_db, [doc_cpf1, doc_cpf2, doc_isolado])

    dossiers = build_and_save_dossiers(temp_db)
    assert len(dossiers) == 1
    assert dossiers[0]["identificador"] == "111.222.333-44"
    assert dossiers[0]["total_documentos"] == 2

    # Verifica recuperação
    all_d = get_all_dossiers(temp_db)
    assert len(all_d) == 1
    assert len(all_d[0]["documentos"]) == 2


def test_inspector_non_existent():
    res = inspect_pdf("/caminho/que/nao/existe.pdf")
    assert res["eh_nativo_digital"] is False
    assert res["tem_assinatura_digital"] is False


def test_update_inspection_status(temp_db):
    from joakindex.db import update_inspection_status, get_document_by_md5

    doc = {
        "md5": "md5_assinado_test",
        "nome_arquivo": "peticao_assinada.pdf",
        "tipo_documento": "Petição",
    }
    upsert_document(temp_db, doc)

    ok = update_inspection_status(
        temp_db,
        "md5_assinado_test",
        eh_nativo_digital=True,
        tem_assinatura_digital=True,
        info_assinaturas=[{"tipo": "PAdES", "assinado_por": "Dr. Advogado", "data": "2026-09-13"}]
    )
    assert ok is True

    loaded = get_document_by_md5(temp_db, "md5_assinado_test")
    assert loaded["eh_nativo_digital"] is True
    assert loaded["tem_assinatura_digital"] is True
    assert len(loaded["info_assinaturas_json"]) == 1
    assert loaded["info_assinaturas_json"][0]["assinado_por"] == "Dr. Advogado"

