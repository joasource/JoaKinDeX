import pytest
import argparse
from joakindex.cli import should_trigger_hybrid_fallback, OpenAIClient, clean_and_parse_json, build_universal_vision_prompt, build_universal_prompt
from joakindex.config import get_factory_defaults, load_all_config, save_classifier_config, reset_classifier_config


def test_hybrid_factory_defaults():
    defaults = get_factory_defaults()
    assert defaults["classificador"]["hybrid"] is False
    assert defaults["classificador"]["hybrid_cloud_model"] == "gpt-4o-mini"
    assert defaults["visualizador"]["hybrid"] is False
    assert defaults["visualizador"]["hybrid_cloud_model"] == "gpt-4o-mini"


def test_should_trigger_hybrid_fallback_on_error():
    doc = {"status": "erro", "motivo": "Erro de leitura"}
    trigger, reason = should_trigger_hybrid_fallback(doc, text_length=0)
    assert trigger is True
    assert "falha_leitura" in reason.lower()


def test_should_trigger_hybrid_fallback_on_empty_doc():
    trigger, reason = should_trigger_hybrid_fallback({}, text_length=10)
    assert trigger is True

    trigger, reason = should_trigger_hybrid_fallback(None, text_length=0)
    assert trigger is True


def test_should_trigger_hybrid_fallback_on_unknown_type():
    doc = {
        "status": "sucesso",
        "beneficiario": "Maria Silva",
        "tipo_documento": "Documento não identificado",
        "dominio": "academico",
        "curso": "Direito",
        "faculdade": "USP"
    }
    trigger, reason = should_trigger_hybrid_fallback(doc, text_length=500)
    assert trigger is True
    assert "tipo_documento" in reason.lower()


def test_should_trigger_hybrid_fallback_academic_missing_student():
    doc = {
        "status": "sucesso",
        "beneficiario": "",
        "tipo_documento": "Certificado",
        "dominio": "academico",
        "curso": "Engenharia",
        "faculdade": "UFMG"
    }
    trigger, reason = should_trigger_hybrid_fallback(doc, text_length=400)
    assert trigger is True
    assert "aluno/titular" in reason


def test_should_trigger_hybrid_fallback_academic_missing_course_and_institution():
    doc = {
        "status": "sucesso",
        "beneficiario": "Carlos Drummond",
        "tipo_documento": "Certificado",
        "dominio": "academico",
        "curso": "",
        "faculdade": ""
    }
    trigger, reason = should_trigger_hybrid_fallback(doc, text_length=300)
    assert trigger is True
    assert "curso nem instituição" in reason


def test_should_not_trigger_hybrid_fallback_for_complete_academic_doc():
    doc = {
        "status": "sucesso",
        "beneficiario": "Joaquim Neto",
        "tipo_documento": "Diploma",
        "dominio": "academico",
        "curso": "Ciência da Computação",
        "faculdade": "Universidade Federal",
        "natureza_curso": "Graduação"
    }
    trigger, reason = should_trigger_hybrid_fallback(doc, text_length=1200)
    assert trigger is False
    assert reason == ""


def test_should_trigger_hybrid_fallback_financial_missing_value():
    doc = {
        "status": "sucesso",
        "beneficiario": "",
        "tipo_documento": "Comprovante PIX",
        "dominio": "financeiro",
        "valor_monetario": ""
    }
    trigger, reason = should_trigger_hybrid_fallback(doc, text_length=200)
    assert trigger is True
    assert "valor nem beneficiário" in reason


def test_should_trigger_hybrid_fallback_scanned_pdf_with_short_text():
    doc = {
        "status": "sucesso",
        "beneficiario": "",
        "tipo_documento": "Declaração",
        "dominio": "academico",
        "curso": "Pedagogia",
        "faculdade": "Faculdade Central"
    }
    trigger, reason = should_trigger_hybrid_fallback(doc, text_length=60)
    assert trigger is True


def test_calculate_retry_delay_from_openai_error_ms():
    msg = "Rate limit reached for gpt-4o-mini in organization org-123. Please try again in 1250ms."
    delay = OpenAIClient._calculate_retry_delay(msg, attempt=0)
    assert 1.50 <= delay <= 2.8


def test_calculate_retry_delay_from_openai_error_seconds():
    msg = "Rate limit reached: Please try again in 4.5s."
    delay = OpenAIClient._calculate_retry_delay(msg, attempt=0)
    assert 5.0 <= delay <= 6.8


def test_calculate_retry_delay_exponential_fallback():
    msg = "Connection error or internal server error without explicit delay suggestion."
    delay_0 = OpenAIClient._calculate_retry_delay(msg, attempt=0)
    assert 4.5 <= delay_0 <= 6.5

    delay_2 = OpenAIClient._calculate_retry_delay(msg, attempt=2)
    assert 16.5 <= delay_2 <= 18.5


def test_clean_and_parse_json_user_truncated_string():
    raw = '{"dominio": "financeiro", "tipo_documento": "Comprovante de Pagamento/Recibo", "data": "25/11/2024", "beneficiario": null, "cpf": null, "rg": null, "cnpj": null, "'
    res = clean_and_parse_json(raw)
    assert res["dominio"] == "financeiro"
    assert res["tipo_documento"] == "Comprovante de Pagamento/Recibo"
    assert res["data"] == "25/11/2024"
    assert res["beneficiario"] is None
    assert res["cnpj"] is None


def test_clean_and_parse_json_unclosed_string_value():
    raw = '{"dominio": "financeiro", "beneficiario": "Maria Silva'
    res = clean_and_parse_json(raw)
    assert res["dominio"] == "financeiro"
    assert res["beneficiario"] == "Maria Silva"


def test_clean_and_parse_json_markdown_with_trailing_comma():
    raw = '```json\n{"dominio": "academico", "curso": "Direito",}\n```'
    res = clean_and_parse_json(raw)
    assert res["dominio"] == "academico"
    assert res["curso"] == "Direito"


def test_clean_and_parse_json_regex_fallback():
    raw = 'Aqui esta o JSON: {"dominio": "juridico", "tipo_documento": "Procuracao" e parou aqui antes de fechar'
    res = clean_and_parse_json(raw)
    assert res["dominio"] == "juridico"
    assert res["tipo_documento"] == "Procuracao"


def test_should_trigger_hybrid_fallback_on_incomplete_handwritten_doc():
    doc = {
        "status": "sucesso",
        "tipo_documento": "Recibo Manual",
        "dominio": "financeiro",
        "manuscrito": True,
        "beneficiario": None,
        "valor_monetario": None,
        "curso": None
    }
    trigger, reason = should_trigger_hybrid_fallback(doc, text_length=50)
    assert trigger is True
    assert "manuscrito_incompleto" in reason


def test_should_not_trigger_hybrid_fallback_on_complete_handwritten_doc():
    doc = {
        "status": "sucesso",
        "tipo_documento": "Recibo Manual",
        "dominio": "financeiro",
        "manuscrito": True,
        "beneficiario": "Antônio Ferreira",
        "valor_monetario": "R$ 350,00",
        "emitente": "Oficina do Zé"
    }
    trigger, reason = should_trigger_hybrid_fallback(doc, text_length=60)
    assert trigger is False
    assert reason == ""


def test_universal_vision_prompt_has_handwriting_instructions():
    prompt = build_universal_vision_prompt(extra_context="Recibo manual de papelaria")
    assert "manuscrito" in prompt.lower()
    assert "preenchido à mão" in prompt.lower() or "preenchimento à mão" in prompt.lower()
    assert "emitente" in prompt.lower()
    assert "referente_a" in prompt.lower()
    assert "conteudo_manuscrito" in prompt.lower()


def test_universal_text_prompt_has_handwriting_instructions():
    prompt = build_universal_prompt(document_text="Recebi de João Silva a quantia...")
    assert "manuscrito" in prompt.lower()
    assert "emitente" in prompt.lower()
    assert "referente_a" in prompt.lower()


def test_universal_vision_prompt_has_ocr_transcription_instruction():
    prompt = build_universal_vision_prompt()
    assert "texto_transcrito" in prompt
    assert "transcrição textual contínua e integral" in prompt.lower() or "ocr completo" in prompt.lower()


def test_format_single_txt_zero_noise_and_appends_ocr():
    from joakindex.cli import format_single_txt
    item = {
        "md5": "abc1234567890def",
        "status": "sucesso",
        "dominio": "academico",
        "tipo_documento": "Certificado de Conclusão",
        "beneficiario": "Carlos Drummond de Andrade",
        "curso": "Letras",
        "cpf": None,
        "rg": "",
        "cnpj": "Não informado",
        "dados_extras": {
            "texto_transcrito": "Certificamos que Carlos Drummond de Andrade concluiu o curso de Letras em 1950 com nota máxima."
        }
    }
    txt = format_single_txt(item)
    assert "Carlos Drummond de Andrade" in txt
    assert "Letras" in txt
    # Zero Noise: não deve imprimir campos vazios como "Não informado"
    assert "CPF                     :" not in txt
    assert "RG / Identidade         :" not in txt
    assert "CNPJ                    :" not in txt
    assert "Não informado" not in txt
    # Transcrição OCR anexada
    assert "TEXTO INTEGRAL / TRANSCRIÇÃO OCR" in txt
    assert "Certificamos que Carlos Drummond" in txt



