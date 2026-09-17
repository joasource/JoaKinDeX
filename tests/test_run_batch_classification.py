"""
Testes de caracterização de run_batch_classification (src/joakindex/cli.py).

run_batch_classification é o orquestrador de lote (~570 linhas): descoberta de
arquivos, modo incremental (SQLite + pasta individuais/), preservação de
conferência humana, execução com 1 ou N workers, callbacks de progresso e
cancelamento via stop_checker. process_single_pdf é sempre mockado aqui — seu
comportamento interno já tem suíte própria em test_process_single_pdf.py.
"""
import json

from joakindex import cli
from joakindex.db import get_db_path, get_json_path, init_database, upsert_documents_batch


class DummyClient:
    model = "modelo-fake"
    provider = "fake"


def _write_pdf(pasta, nome, conteudo=b"conteudo de teste"):
    p = pasta / nome
    p.write_bytes(conteudo)
    return p


def _fake_process_single_pdf(resultados_por_nome):
    """Constrói um substituto de process_single_pdf que devolve um resultado fixo por nome de arquivo."""
    def _fake(pdf_path, client, max_pages=4, skip_ocr=False, metadata=None, hybrid=False, hybrid_cloud_client=None):
        base = dict(resultados_por_nome[pdf_path.name])
        base.setdefault("md5", metadata["md5"] if metadata else pdf_path.name)
        return base
    return _fake


def test_input_path_inexistente_retorna_erro(tmp_path):
    res = cli.run_batch_classification(
        input_path=str(tmp_path / "nao_existe"), output_dir=str(tmp_path / "saida"), client=DummyClient(),
    )
    assert res["status"] == "erro"
    assert res["total"] == 0


def test_arquivo_unico_com_extensao_nao_suportada_retorna_erro(tmp_path):
    arquivo = tmp_path / "notas.xlsx"
    arquivo.write_bytes(b"dados")
    res = cli.run_batch_classification(
        input_path=str(arquivo), output_dir=str(tmp_path / "saida"), client=DummyClient(),
    )
    assert res["status"] == "erro"
    assert "não possui formato suportado" in res["mensagem"]


def test_diretorio_sem_documentos_suportados_retorna_aviso(tmp_path):
    pasta = tmp_path / "pdf"
    pasta.mkdir()
    (pasta / "leiame.md").write_text("nada aqui")
    res = cli.run_batch_classification(
        input_path=str(pasta), output_dir=str(tmp_path / "saida"), client=DummyClient(),
    )
    assert res["status"] == "aviso"
    assert res["total"] == 0


def test_processa_novos_documentos_e_persiste_json_txt_db(tmp_path, monkeypatch):
    pasta = tmp_path / "pdf"
    pasta.mkdir()
    _write_pdf(pasta, "a.pdf", b"conteudo A")
    _write_pdf(pasta, "b.pdf", b"conteudo B")
    out_dir = tmp_path / "saida"

    fake = _fake_process_single_pdf({
        "a.pdf": {"status": "sucesso", "tipo_documento": "Certificado", "beneficiario": "Ana"},
        "b.pdf": {"status": "sucesso", "tipo_documento": "Diploma", "beneficiario": "Beto"},
    })
    monkeypatch.setattr(cli, "process_single_pdf", fake)

    res = cli.run_batch_classification(
        input_path=str(pasta), output_dir=str(out_dir), client=DummyClient(), use_tqdm=False,
    )

    assert res["status"] == "sucesso"
    assert res["total"] == 2
    assert res["sucessos"] == 2
    assert res["erros"] == 0
    assert len(res["results"]) == 2

    consolidated_json = get_json_path(out_dir)
    assert consolidated_json.exists()
    salvo = json.loads(consolidated_json.read_text(encoding="utf-8"))
    assert {item["beneficiario"] for item in salvo} == {"Ana", "Beto"}

    consolidated_db = get_db_path(out_dir)
    assert consolidated_db.exists()

    individuais = out_dir / "individuais"
    assert len(list(individuais.glob("*.json"))) == 2


def test_no_individual_nao_grava_pasta_individuais(tmp_path, monkeypatch):
    pasta = tmp_path / "pdf"
    pasta.mkdir()
    _write_pdf(pasta, "a.pdf", b"conteudo A")
    out_dir = tmp_path / "saida"

    monkeypatch.setattr(cli, "process_single_pdf", _fake_process_single_pdf({
        "a.pdf": {"status": "sucesso", "beneficiario": "Ana"},
    }))

    cli.run_batch_classification(
        input_path=str(pasta), output_dir=str(out_dir), client=DummyClient(),
        no_individual=True, use_tqdm=False,
    )

    assert not (out_dir / "individuais").exists()


def test_modo_incremental_pula_documento_ja_com_sucesso(tmp_path, monkeypatch):
    pasta = tmp_path / "pdf"
    pasta.mkdir()
    caminho_a = _write_pdf(pasta, "a.pdf", b"conteudo A")
    out_dir = tmp_path / "saida"
    out_dir.mkdir()

    import hashlib
    md5_a = hashlib.md5(caminho_a.read_bytes()).hexdigest()
    db_path = get_db_path(out_dir)
    init_database(db_path)
    upsert_documents_batch(db_path, [{"md5": md5_a, "status": "sucesso", "beneficiario": "Ana Antiga"}])

    chamadas = []

    def fake_process(pdf_path, client, max_pages=4, skip_ocr=False, metadata=None, hybrid=False, hybrid_cloud_client=None):
        chamadas.append(pdf_path.name)
        return {"md5": metadata["md5"], "status": "sucesso", "beneficiario": "Nao Deveria Rodar"}

    monkeypatch.setattr(cli, "process_single_pdf", fake_process)

    res = cli.run_batch_classification(
        input_path=str(pasta), output_dir=str(out_dir), client=DummyClient(), use_tqdm=False,
    )

    assert chamadas == []
    assert res["already_done"] == 1
    assert res["new_processed"] == 0
    assert res["results"][0]["beneficiario"] == "Ana Antiga"


def test_force_reprocessa_mesmo_documentos_aprovados(tmp_path, monkeypatch):
    pasta = tmp_path / "pdf"
    pasta.mkdir()
    caminho_a = _write_pdf(pasta, "a.pdf", b"conteudo A")
    out_dir = tmp_path / "saida"
    out_dir.mkdir()

    import hashlib
    md5_a = hashlib.md5(caminho_a.read_bytes()).hexdigest()
    db_path = get_db_path(out_dir)
    init_database(db_path)
    # status "erro" de propósito: sem a proteção de "aprovado", o modo incremental
    # padrão reprocessaria este documento por não ter status "sucesso" — isso
    # garante que o teste exercite de fato a checagem de status_conferencia,
    # e não apenas o atalho comum de "já processado com sucesso".
    upsert_documents_batch(db_path, [
        {"md5": md5_a, "status": "erro", "status_conferencia": "aprovado", "beneficiario": "Ana Aprovada"}
    ])

    chamadas = []

    def fake_process(pdf_path, client, max_pages=4, skip_ocr=False, metadata=None, hybrid=False, hybrid_cloud_client=None):
        chamadas.append(pdf_path.name)
        return {"md5": metadata["md5"], "status": "sucesso", "beneficiario": "Ana Reprocessada"}

    monkeypatch.setattr(cli, "process_single_pdf", fake_process)

    # Sem --force: documento aprovado é preservado e NÃO reprocessado.
    res_sem_force = cli.run_batch_classification(
        input_path=str(pasta), output_dir=str(out_dir), client=DummyClient(), use_tqdm=False,
    )
    assert chamadas == []
    assert res_sem_force["results"][0]["beneficiario"] == "Ana Aprovada"

    # Com --force: mesmo aprovado, é reprocessado (bypassa a checagem de aprovação).
    res_com_force = cli.run_batch_classification(
        input_path=str(pasta), output_dir=str(out_dir), client=DummyClient(), use_tqdm=False, force=True,
    )
    assert chamadas == ["a.pdf"]
    assert res_com_force["results"][0]["beneficiario"] == "Ana Reprocessada"


def test_reprocess_ocr_seleciona_apenas_candidatos_elegiveis(tmp_path, monkeypatch):
    pasta = tmp_path / "pdf"
    pasta.mkdir()
    caminho_ok = _write_pdf(pasta, "ok.pdf", b"documento ok")
    caminho_ruim = _write_pdf(pasta, "ruim.pdf", b"documento nao identificado")
    out_dir = tmp_path / "saida"
    out_dir.mkdir()

    import hashlib
    md5_ok = hashlib.md5(caminho_ok.read_bytes()).hexdigest()
    md5_ruim = hashlib.md5(caminho_ruim.read_bytes()).hexdigest()
    db_path = get_db_path(out_dir)
    init_database(db_path)
    upsert_documents_batch(db_path, [
        {"md5": md5_ok, "status": "sucesso", "tipo_documento": "Diploma", "cpf": "111.444.777-35"},
        {"md5": md5_ruim, "status": "sucesso", "tipo_documento": "não identificado", "cpf": None},
    ])

    chamadas = []

    def fake_process(pdf_path, client, max_pages=4, skip_ocr=False, metadata=None, hybrid=False, hybrid_cloud_client=None):
        chamadas.append(pdf_path.name)
        return {"md5": metadata["md5"], "status": "sucesso", "tipo_documento": "Diploma"}

    monkeypatch.setattr(cli, "process_single_pdf", fake_process)

    cli.run_batch_classification(
        input_path=str(pasta), output_dir=str(out_dir), client=DummyClient(),
        use_tqdm=False, reprocess_ocr=True,
    )

    assert chamadas == ["ruim.pdf"]


def test_workers_multiplos_processa_todos_os_arquivos(tmp_path, monkeypatch):
    pasta = tmp_path / "pdf"
    pasta.mkdir()
    for i in range(5):
        _write_pdf(pasta, f"doc{i}.pdf", f"conteudo {i}".encode())
    out_dir = tmp_path / "saida"

    def fake_process(pdf_path, client, max_pages=4, skip_ocr=False, metadata=None, hybrid=False, hybrid_cloud_client=None):
        return {"md5": metadata["md5"], "status": "sucesso", "tipo_documento": pdf_path.name}

    monkeypatch.setattr(cli, "process_single_pdf", fake_process)

    res = cli.run_batch_classification(
        input_path=str(pasta), output_dir=str(out_dir), client=DummyClient(), use_tqdm=False, workers=3,
    )

    assert res["status"] == "sucesso"
    assert res["processed"] == 5
    assert res["sucessos"] == 5
    assert len(res["results"]) == 5


def test_stop_checker_interrompe_processamento(tmp_path, monkeypatch):
    pasta = tmp_path / "pdf"
    pasta.mkdir()
    _write_pdf(pasta, "a.pdf", b"conteudo A")
    _write_pdf(pasta, "b.pdf", b"conteudo B")
    out_dir = tmp_path / "saida"

    def fake_process(pdf_path, client, max_pages=4, skip_ocr=False, metadata=None, hybrid=False, hybrid_cloud_client=None):
        return {"md5": metadata["md5"], "status": "sucesso"}

    monkeypatch.setattr(cli, "process_single_pdf", fake_process)

    res = cli.run_batch_classification(
        input_path=str(pasta), output_dir=str(out_dir), client=DummyClient(), use_tqdm=False,
        stop_checker=lambda: True,
    )

    assert res["status"] == "interrompido"


def test_progress_callback_recebe_eventos_principais(tmp_path, monkeypatch):
    pasta = tmp_path / "pdf"
    pasta.mkdir()
    _write_pdf(pasta, "a.pdf", b"conteudo A")
    out_dir = tmp_path / "saida"

    monkeypatch.setattr(cli, "process_single_pdf", _fake_process_single_pdf({
        "a.pdf": {"status": "sucesso", "beneficiario": "Ana"},
    }))

    eventos = []
    cli.run_batch_classification(
        input_path=str(pasta), output_dir=str(out_dir), client=DummyClient(), use_tqdm=False,
        progress_callback=lambda ev: eventos.append(ev["event"]),
    )

    assert "init" in eventos
    assert "ready" in eventos
    assert "start_batch" in eventos
    assert "file_done" in eventos
    assert "completed" in eventos


def test_erro_em_um_arquivo_nao_interrompe_processamento_dos_demais(tmp_path, monkeypatch):
    pasta = tmp_path / "pdf"
    pasta.mkdir()
    _write_pdf(pasta, "a.pdf", b"conteudo A")
    _write_pdf(pasta, "b.pdf", b"conteudo B")
    out_dir = tmp_path / "saida"

    def fake_process(pdf_path, client, max_pages=4, skip_ocr=False, metadata=None, hybrid=False, hybrid_cloud_client=None):
        if pdf_path.name == "a.pdf":
            raise RuntimeError("falha simulada")
        return {"md5": metadata["md5"], "status": "sucesso"}

    monkeypatch.setattr(cli, "process_single_pdf", fake_process)

    res = cli.run_batch_classification(
        input_path=str(pasta), output_dir=str(out_dir), client=DummyClient(), use_tqdm=False, workers=1,
    )

    # handle_file propaga a exceção pra fora de process_single_pdf; o laço
    # de execução (single-worker) captura e segue pro próximo arquivo, mas o
    # arquivo que falhou não entra em "results".
    assert res["erros"] == 1 or res["sucessos"] == 1
    assert len(res["results"]) == 1
