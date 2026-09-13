import pytest
import tempfile
from pathlib import Path
from joakindex.db import get_connection, create_schema, upsert_document
from joakindex.audit_report import (
    get_management_statistics,
    generate_executive_audit_report,
    _parse_monetary_value,
    HAS_REPORTLAB,
)


def test_parse_monetary_value():
    assert _parse_monetary_value("R$ 1.250,50") == 1250.50
    assert _parse_monetary_value("450,00") == 450.00
    assert _parse_monetary_value("100.25") == 100.25
    assert _parse_monetary_value(None) == 0.0


@pytest.mark.skipif(not HAS_REPORTLAB, reason="ReportLab não está instalado no ambiente")
def test_statistics_and_report_generation():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tf:
        db_path = Path(tf.name)
    with get_connection(db_path) as conn:
        create_schema(conn)

    doc1 = {
        "md5": "doc1_audit",
        "nome_arquivo": "boleto1.pdf",
        "tipo_documento": "Boleto Bancário",
        "valor_monetario": "R$ 500,00",
        "status_conferencia": "aprovado"
    }
    doc2 = {
        "md5": "doc2_audit",
        "nome_arquivo": "comprovante1.pdf",
        "tipo_documento": "Comprovante de Pagamento",
        "valor_monetario": "R$ 250,00",
        "status_conferencia": "pendente"
    }
    upsert_document(db_path, doc1)
    upsert_document(db_path, doc2)

    stats = get_management_statistics(db_path)
    assert stats["total_docs"] == 2
    assert stats["total_financeiro_reais"] == 750.00
    assert "Boleto Bancário" in stats["classes_distribuicao"]

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as out_pdf:
        pdf_out_path = Path(out_pdf.name)

    res_path = generate_executive_audit_report(db_path, pdf_out_path)
    assert res_path.exists()
    assert res_path.stat().st_size > 500

    if db_path.exists():
        db_path.unlink()
    if pdf_out_path.exists():
        pdf_out_path.unlink()
