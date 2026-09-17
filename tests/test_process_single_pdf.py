"""
Testes de caracterização de process_single_pdf (src/joakindex/cli.py).

process_single_pdf é o núcleo orquestrador do classificador (~1100 linhas) e nunca teve
teste dedicado. Estes testes fixam o comportamento ATUAL (antes de qualquer extração/
refatoração futura), cobrindo os ramos principais: documento com texto digital, documento
sem texto exigindo OCR, imagem nativa, detecção de boleto/PIX e o fallback híbrido em
cascata pra nuvem. Não recobrem exaustivamente cada heurística de regex interna (essas já
têm teste próprio em test_cpf_rg.py, test_dispatcher.py e test_hybrid_classifier.py).
"""
from PIL import Image
import pytest

from joakindex import cli
from joakindex.llm_clients import BaseLLMClient


class FakeLLMClient(BaseLLMClient):
    provider = "fake"

    def __init__(self, json_result=None, json_error=None, vision_result=None, vision_error=None):
        self.json_result = json_result
        self.json_error = json_error
        self.vision_result = vision_result
        self.vision_error = vision_error
        self.json_calls = []
        self.vision_calls = []

    def generate_json(self, prompt):
        self.json_calls.append(prompt)
        if self.json_error:
            raise self.json_error
        return dict(self.json_result or {})

    def generate_json_with_images(self, prompt, images):
        self.vision_calls.append((prompt, images))
        if self.vision_error:
            raise self.vision_error
        return dict(self.vision_result or {})


@pytest.fixture(autouse=True)
def isolate_external_lookups(monkeypatch):
    # process_single_pdf consulta o banco de "regras aprendidas" real do usuário
    # (há um .joakindex_config.json de verdade na raiz do repo, ver memória
    # joakindex-server-auth) e monta um dossiê multi-página via pdfium/tesseract.
    # Nenhum dos dois deve depender de dados reais da máquina nem de um PDF real
    # em disco pra estes testes de caracterização.
    monkeypatch.setattr(cli, "consultar_regra_para_texto", lambda *a, **k: None)
    monkeypatch.setattr(cli, "analyze_pdf_dossier", lambda *a, **k: {})
    # Rede de segurança do CASO 2 (linha ~1740) chama extract_tesseract_text_from_pdf
    # sem try/except pra caminhos SEM texto digital identificado; sem isso, um
    # pdf_path falso (que não existe em disco) derrubaria testes que nem
    # deveriam entrar nesse ramo.
    monkeypatch.setattr(cli, "extract_tesseract_text_from_pdf", lambda *a, **k: "")
    monkeypatch.setattr(cli, "render_pdf_pages_to_base64", lambda *a, **k: [])


def _meta(md5="abc123def456", extensao=".pdf", nome="doc.pdf"):
    return {
        "md5": md5,
        "caminho_relativo": nome,
        "extensao": extensao,
        "data_modificacao": "01/01/2026 00:00:00",
        "autor": None,
        "dublin_core": None,
        "dc_title": None,
        "dc_subject": None,
        "dc_creator_tool": None,
    }


def _fake_path(tmp_path, name="doc.pdf"):
    return tmp_path / name


# ---------------------------------------------------------------------------
# Ramo B: documento com texto digital (PDF/Word/TXT)
# ---------------------------------------------------------------------------

def test_texto_digital_completo_mapeia_campos_e_sucesso(monkeypatch, tmp_path):
    texto = "Certificado de Conclusão do curso de Engenharia. CPF 111.444.777-35."
    monkeypatch.setattr(cli, "extract_document_text", lambda p, max_pages=4: texto)
    client = FakeLLMClient(json_result={
        "dominio": "academico",
        "tipo_documento": "Certificado",
        "beneficiario": "Carlos Drummond",
        "cpf": "111.444.777-35",
        "curso": "Engenharia",
        "faculdade": "UFMG",
    })

    res = cli.process_single_pdf(_fake_path(tmp_path), client, metadata=_meta())

    assert res["status"] == "sucesso"
    assert res["erro"] is None
    assert res["dominio"] == "academico"
    assert res["tipo_documento"] == "Certificado"
    assert res["beneficiario"] == "Carlos Drummond"
    assert res["cpf"] == "111.444.777-35"
    assert res["curso"] == "Engenharia"
    assert res["metodo_leitura"] == "texto_digital"
    assert res["tentativa_ocr_llm"] is False


def test_texto_digital_llm_falha_usa_fallback_regex_de_cpf(monkeypatch, tmp_path):
    texto = "Contrato de prestação de serviços. CPF: 111.444.777-35."
    monkeypatch.setattr(cli, "extract_document_text", lambda p, max_pages=4: texto)
    client = FakeLLMClient(json_error=RuntimeError("timeout do modelo"))

    res = cli.process_single_pdf(_fake_path(tmp_path), client, metadata=_meta())

    # Mesmo com a chamada LLM falhando, o fallback regex de extractors_texto
    # ainda resgata o CPF do texto digital e isso basta pra status "sucesso".
    assert res["cpf"] == "111.444.777-35"
    assert res["status"] == "sucesso"
    assert res["metodo_leitura"] == "texto_digital"


def test_texto_digital_sem_dados_uteis_retorna_erro_final(monkeypatch, tmp_path):
    texto = "Página em branco sem nenhuma informação relevante para classificação."
    monkeypatch.setattr(cli, "extract_document_text", lambda p, max_pages=4: texto)
    client = FakeLLMClient(json_result={})

    res = cli.process_single_pdf(_fake_path(tmp_path), client, metadata=_meta())

    assert res["status"] == "erro"
    assert res["erro"] == "Documento sem informações identificáveis após análise."


# ---------------------------------------------------------------------------
# Ramo B: documento SEM texto digital (exige OCR)
# ---------------------------------------------------------------------------

def test_documento_sem_texto_com_skip_ocr_retorna_erro(monkeypatch, tmp_path):
    monkeypatch.setattr(cli, "extract_document_text", lambda p, max_pages=4: "")
    client = FakeLLMClient()

    res = cli.process_single_pdf(_fake_path(tmp_path), client, metadata=_meta(), skip_ocr=True)

    assert res["status"] == "erro"
    assert "skip-ocr" in res["erro"]


def test_documento_sem_texto_sem_paginas_renderizaveis_retorna_erro(monkeypatch, tmp_path):
    # pdf_path não existe em disco -> target_pdf_path.exists() é False -> nunca
    # chega a chamar extract_tesseract_text_from_pdf/render_pdf_pages_to_base64,
    # cai direto no "sem texto e falha ao renderizar".
    monkeypatch.setattr(cli, "extract_document_text", lambda p, max_pages=4: "")
    client = FakeLLMClient()

    res = cli.process_single_pdf(_fake_path(tmp_path), client, metadata=_meta())

    assert res["status"] == "erro"
    assert "falha ao renderizar páginas" in res["erro"]


def test_documento_sem_texto_ocr_visao_sucesso(monkeypatch, tmp_path):
    pdf_path = _fake_path(tmp_path)
    pdf_path.write_bytes(b"")  # só precisa existir pra passar no .exists()
    monkeypatch.setattr(cli, "extract_document_text", lambda p, max_pages=4: "")
    monkeypatch.setattr(cli, "render_pdf_pages_to_base64", lambda *a, **k: ["b64img"])
    client = FakeLLMClient(vision_result={
        "dominio": "financeiro",
        "tipo_documento": "Boleto Bancário",
        "valor_monetario": "R$ 100,00",
    })

    res = cli.process_single_pdf(pdf_path, client, metadata=_meta())

    assert res["status"] == "sucesso"
    assert res["metodo_leitura"] == "ocr_llm"
    assert res["tentativa_ocr_llm"] is True
    assert len(client.vision_calls) == 1


def test_documento_sem_texto_visao_falha_sem_fallback_retorna_erro_especifico(monkeypatch, tmp_path):
    pdf_path = _fake_path(tmp_path)
    pdf_path.write_bytes(b"")
    monkeypatch.setattr(cli, "extract_document_text", lambda p, max_pages=4: "")
    monkeypatch.setattr(cli, "render_pdf_pages_to_base64", lambda *a, **k: ["b64img"])
    monkeypatch.setattr(cli, "extract_tesseract_text_from_pdf", lambda *a, **k: "")
    client = FakeLLMClient(vision_error=RuntimeError("modelo indisponível"))

    res = cli.process_single_pdf(pdf_path, client, metadata=_meta())

    # Sem tess_text (combined_text vazio), o erro de visão é retornado direto
    # (early return) e NÃO é sobrescrito pela mensagem genérica do fim da função.
    assert res["status"] == "erro"
    assert res["erro"] == "Falha no OCR via LLM: modelo indisponível"


def test_documento_sem_texto_visao_falha_fallback_textual_tesseract_sucesso(monkeypatch, tmp_path):
    pdf_path = _fake_path(tmp_path)
    pdf_path.write_bytes(b"")
    monkeypatch.setattr(cli, "extract_document_text", lambda p, max_pages=4: "")
    monkeypatch.setattr(cli, "render_pdf_pages_to_base64", lambda *a, **k: ["b64img"])
    monkeypatch.setattr(cli, "extract_tesseract_text_from_pdf", lambda *a, **k: "Texto reconhecido via OCR local")
    client = FakeLLMClient(
        vision_error=RuntimeError("modelo indisponível"),
        json_result={"dominio": "academico", "tipo_documento": "Declaração", "beneficiario": "Ana Paula"},
    )

    res = cli.process_single_pdf(pdf_path, client, metadata=_meta())

    assert res["status"] == "sucesso"
    assert res["metodo_leitura"] == "ocr_tesseract_llm"
    assert res["beneficiario"] == "Ana Paula"
    assert len(client.json_calls) == 1


def test_documento_sem_texto_visao_e_fallback_textual_falham_gera_erro_generico_final(monkeypatch, tmp_path):
    pdf_path = _fake_path(tmp_path)
    pdf_path.write_bytes(b"")
    monkeypatch.setattr(cli, "extract_document_text", lambda p, max_pages=4: "")
    monkeypatch.setattr(cli, "render_pdf_pages_to_base64", lambda *a, **k: ["b64img"])
    monkeypatch.setattr(cli, "extract_tesseract_text_from_pdf", lambda *a, **k: "conteúdo ilegível sem dados úteis")
    client = FakeLLMClient(
        vision_error=RuntimeError("falha visão"),
        json_error=RuntimeError("falha texto"),
    )

    res = cli.process_single_pdf(pdf_path, client, metadata=_meta())

    # Este ramo NÃO retorna cedo (só o ramo sem combined_text retorna cedo) -
    # segue processando e a checagem final de "campos úteis" sobrescreve a
    # mensagem de erro específica pela genérica, já que nada foi extraído.
    assert res["status"] == "erro"
    assert res["erro"] == "Documento sem informações identificáveis após análise."


# ---------------------------------------------------------------------------
# Ramo A: imagem nativa (PNG/JPG/JPEG/WEBP)
# ---------------------------------------------------------------------------

def test_imagem_com_skip_ocr_retorna_erro(tmp_path):
    client = FakeLLMClient()
    res = cli.process_single_pdf(
        _fake_path(tmp_path, "foto.png"), client, metadata=_meta(extensao=".png", nome="foto.png"), skip_ocr=True
    )
    assert res["status"] == "erro"
    assert "visão computacional" in res["erro"]


def test_imagem_falha_ao_carregar_retorna_erro(monkeypatch, tmp_path):
    monkeypatch.setattr(cli, "load_image_to_base64", lambda p: [])
    client = FakeLLMClient()
    res = cli.process_single_pdf(
        _fake_path(tmp_path, "foto.png"), client, metadata=_meta(extensao=".png", nome="foto.png")
    )
    assert res["status"] == "erro"
    assert "Falha ao carregar e converter imagem" in res["erro"]


def test_imagem_visao_sucesso(monkeypatch, tmp_path):
    monkeypatch.setattr(cli, "load_image_to_base64", lambda p: ["b64img"])
    client = FakeLLMClient(vision_result={
        "dominio": "identificacao", "tipo_documento": "RG", "beneficiario": "João Souza", "rg": "12.345.678-9",
    })

    res = cli.process_single_pdf(
        _fake_path(tmp_path, "foto.png"), client, metadata=_meta(extensao=".png", nome="foto.png")
    )

    assert res["status"] == "sucesso"
    assert res["metodo_leitura"] == "imagem_ocr_llm"
    assert res["tentativa_ocr_llm"] is True
    assert res["beneficiario"] == "João Souza"


def _real_png(tmp_path, name="foto.png"):
    path = tmp_path / name
    Image.new("RGB", (2, 2), color="white").save(path)
    return path


def test_imagem_visao_falha_fallback_tesseract_sucesso(monkeypatch, tmp_path):
    img_path = _real_png(tmp_path)
    monkeypatch.setattr(cli, "load_image_to_base64", lambda p: ["b64img"])
    monkeypatch.setattr(cli, "run_tesseract_ocr_on_image", lambda pil_im, try_rotation=True: "texto ocr da imagem")
    client = FakeLLMClient(
        vision_error=RuntimeError("falha visão"),
        json_result={"dominio": "financeiro", "tipo_documento": "Recibo", "valor_monetario": "R$ 50,00"},
    )

    res = cli.process_single_pdf(img_path, client, metadata=_meta(extensao=".png", nome="foto.png"))

    assert res["status"] == "sucesso"
    assert res["metodo_leitura"] == "imagem_tesseract_llm"


def test_imagem_visao_e_tesseract_falham_retorna_erro_combinado(monkeypatch, tmp_path):
    img_path = _real_png(tmp_path)
    monkeypatch.setattr(cli, "load_image_to_base64", lambda p: ["b64img"])
    monkeypatch.setattr(cli, "run_tesseract_ocr_on_image", lambda pil_im, try_rotation=True: "texto ocr")
    client = FakeLLMClient(vision_error=RuntimeError("falha visão"), json_error=RuntimeError("falha texto"))

    res = cli.process_single_pdf(img_path, client, metadata=_meta(extensao=".png", nome="foto.png"))

    assert res["status"] == "erro"
    assert "falha visão" in res["erro"] and "falha texto" in res["erro"]


def test_imagem_visao_falha_sem_texto_ocr_retorna_erro_visao(monkeypatch, tmp_path):
    # Image.open falha (arquivo não existe de verdade) -> tess_text fica vazio.
    monkeypatch.setattr(cli, "load_image_to_base64", lambda p: ["b64img"])
    client = FakeLLMClient(vision_error=RuntimeError("falha visão"))

    res = cli.process_single_pdf(
        _fake_path(tmp_path, "foto.png"), client, metadata=_meta(extensao=".png", nome="foto.png")
    )

    assert res["status"] == "erro"
    assert res["erro"] == "Falha no processamento visual da imagem via LLM: falha visão"


# ---------------------------------------------------------------------------
# Detecção universal de sinais (boleto / PIX) sobrepõe o que a LLM disse
# ---------------------------------------------------------------------------

def test_sinais_de_boleto_sobrepoem_classificacao_da_llm(monkeypatch, tmp_path):
    texto = (
        "001-9 00190.00009 03183.378003 00078.500170 6 12780001804302 "
        "PAGAVEL EM QUALQUER BANCO Vencimento 27/11/2025"
    )
    monkeypatch.setattr(cli, "extract_document_text", lambda p, max_pages=4: texto)
    # LLM erra a classificação de propósito, pra provar que o detector de sinais universal vence.
    client = FakeLLMClient(json_result={"dominio": "academico", "tipo_documento": "Recibo"})

    res = cli.process_single_pdf(_fake_path(tmp_path), client, metadata=_meta())

    assert res["dominio"] == "financeiro"
    assert res["tipo_documento"] == "Boleto Bancário"
    assert res["linha_digitavel"] == "00190.00009 03183.378003 00078.500170 6 12780001804302"
    assert "pix_chave" not in res or res.get("pix_chave") is None


def test_pix_legitimo_com_e2e_id_e_mantido(monkeypatch, tmp_path):
    texto = "Comprovante de transferência via PIX realizada com sucesso."
    monkeypatch.setattr(cli, "extract_document_text", lambda p, max_pages=4: texto)
    client = FakeLLMClient(json_result={
        "dominio": "financeiro",
        "tipo_documento": "Comprovante PIX",
        "pix_e2e_id": "E12345678202601011200abcdEFGH123",
    })

    res = cli.process_single_pdf(_fake_path(tmp_path), client, metadata=_meta())

    assert res["status"] == "sucesso"
    assert res["dominio"] == "financeiro"
    assert res["tipo_documento"] == "Comprovante PIX"
    assert res["pix_e2e_id"] == "E12345678202601011200abcdEFGH123"


# ---------------------------------------------------------------------------
# Modo híbrido em cascata: fallback pra cliente de nuvem
# ---------------------------------------------------------------------------

def test_modo_hibrido_recorre_ao_cliente_de_nuvem_quando_local_falha(monkeypatch, tmp_path):
    texto = "Documento sem nenhum dado extraível pela primeira passada."
    monkeypatch.setattr(cli, "extract_document_text", lambda p, max_pages=4: texto)

    primary_client = FakeLLMClient(json_result={})
    primary_client.provider = "ollama"
    cloud_client = FakeLLMClient(json_result={
        "dominio": "academico", "tipo_documento": "Diploma", "beneficiario": "Maria Eduarda", "curso": "Direito",
    })

    res = cli.process_single_pdf(
        _fake_path(tmp_path), primary_client, metadata=_meta(),
        hybrid=True, hybrid_cloud_client=cloud_client,
    )

    assert res["metodo_leitura"] == "hibrido_fallback_openai"
    assert res["provedor_primario"] == "ollama"
    assert res["provedor_final"] == "openai"
    assert res["motivo_fallback"]
    assert res["beneficiario"] == "Maria Eduarda"
    assert res["status"] == "sucesso"
