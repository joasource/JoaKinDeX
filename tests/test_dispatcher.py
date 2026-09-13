import pytest
import tempfile
import csv
from pathlib import Path
from joakindex.db import get_connection, create_schema, upsert_document
from joakindex.dispatcher import sanitize_filename_part, build_organized_path, organize_files


@pytest.fixture
def temp_env():
    with tempfile.TemporaryDirectory() as td:
        base = Path(td)
        db_path = base / "test.db"
        with get_connection(db_path) as conn:
            create_schema(conn)
        src_dir = base / "origem"
        src_dir.mkdir()
        out_dir = base / "saida_organizada"

        # Cria PDF simulado
        pdf1 = src_dir / "boleto_bb.pdf"
        pdf1.write_bytes(b"%PDF-1.4 simulated pdf")

        doc1 = {
            "md5": "abc123md5",
            "nome_arquivo": "boleto_bb.pdf",
            "tipo_documento": "Boleto Bancário",
            "beneficiario": "Banco do Brasil",
            "valor_monetario": "R$ 150,00",
            "data": "2024-03-15",
            "caminho_relativo": "boleto_bb.pdf"
        }
        upsert_document(db_path, doc1)

        yield {"db": db_path, "src": src_dir, "out": out_dir, "file": pdf1}


def test_sanitize_filename_part():
    assert sanitize_filename_part("Nome / com * barras ? e : dois_pontos") == "Nome___com___barras___e___dois_pontos"
    assert sanitize_filename_part("") == "Nao_Informado"


def test_smart_dispatcher_dry_run_and_execution(temp_env):
    db = temp_env["db"]
    src = temp_env["src"]
    out = temp_env["out"]

    # 1. Simulação (dry_run=True): não deve criar arquivos na pasta de destino
    res_sim = organize_files(db, out, pdf_source_dir=src, mode="copy", dry_run=True)
    assert res_sim["dry_run"] is True
    assert res_sim["total_planejado"] == 1
    assert not out.exists()

    # 2. Execução Real (dry_run=False, mode="copy")
    res_exec = organize_files(db, out, pdf_source_dir=src, mode="copy", dry_run=False)
    assert res_exec["status"] == "sucesso"
    assert res_exec["total_organizados"] == 1

    # Verifica se a pasta e o arquivo foram criados
    manifesto = out / "manifesto_organizacao.csv"
    assert manifesto.exists()

    with open(manifesto, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        assert len(rows) == 1
        assert rows[0]["md5"] == "abc123md5"
        assert "Boleto" in rows[0]["classe"]

    # Verifica se o arquivo original ainda existe intacto (modo cópia)
    assert temp_env["file"].exists()
