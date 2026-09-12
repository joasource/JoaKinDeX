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


def test_sanitize_llm_transcription_valid_and_loop_hallucination():
    from joakindex.cli import sanitize_llm_transcription
    # 1. Texto legítimo e limpo
    valid_text = "FRACAROLI IMP. E EXP. DE CAFE\nListagem para depósito\nValor Total: R$ 2.358.691,00\nData: 26/11/2025"
    assert sanitize_llm_transcription(valid_text) == valid_text

    # 2. Loop de alucinação com repetição consecutiva (ex: data repetida 5 vezes)
    loop_text = "FRACAROLI IMP. E EXP. DE CAFE\n26/11/2025\n26/11/2025\n26/11/2025\n26/11/2025\n26/11/2025"
    assert sanitize_llm_transcription(loop_text) is None

    # 3. Dominância excessiva de linha única repetida (>35% do documento)
    repeated_line_doc = "\n".join(["Linha normal de conteúdo A", "26/11/2025"] * 5)
    assert sanitize_llm_transcription(repeated_line_doc) is None


def test_extract_names_from_document_text():
    from joakindex.cli import extract_names_from_document_text
    sample_text = """
    FRACAROLI IMP. E EXP. DE CAFE
    Listagem para depósito
    Valor Titular Banco Agência Nº Conta CPF/CNPJ Conc Lote
    1150000,00 JOSE MAGNO BUFON 1 5610 1070800 85034193787 C Corrente TES
    20000,00 WODIELEN CARMINATI 756 3007 34711 09741174713 C.Correnta DEP
    52000,00 LUCAS GIURIATO 756 3007 875520 16934394763 C.Corrente DEP
    490000,00 ANACLETO DADALTO 1 19224 8090-X 47122552772 C.Correnta TED
    Titular: ESVERALDO LOSS GAMBERT
    Favorecido: DANILO BALLAFILHO
    """
    detected = extract_names_from_document_text(sample_text)
    assert "JOSE MAGNO BUFON" in detected
    assert "WODIELEN CARMINATI" in detected
    assert "LUCAS GIURIATO" in detected
    assert "ANACLETO DADALTO" in detected
    assert "ESVERALDO LOSS GAMBERT" in detected
    assert "DANILO BALLAFILHO" in detected
    assert len(detected) >= 6


def test_universal_prompt_has_nomes_detectados_and_anti_pix_rules():
    from joakindex.cli import build_universal_prompt
    prompt = build_universal_prompt("Texto de teste...")
    assert "nomes_detectados" in prompt
    assert "Listagem de Pagamentos / Depósitos" in prompt
    assert "Comprovante de Transferência Bancária (TED/DOC)" in prompt
    assert "DARF / Guia de Arrecadação Federal" in prompt
    assert "REGRA DO PIX" in prompt


def test_format_single_txt_displays_nomes_detectados():
    from joakindex.cli import format_single_txt
    item = {
        "md5": "1234567890abcdef",
        "status": "sucesso",
        "dominio": "financeiro",
        "tipo_documento": "Listagem de Pagamentos / Depósitos",
        "beneficiario": "JOSE MAGNO BUFON",
        "nomes_detectados": ["JOSE MAGNO BUFON", "WODIELEN CARMINATI", "LUCAS GIURIATO", "ANACLETO DADALTO"],
        "dados_extras": {
            "texto_digital": "Listagem bancária de depósitos em lote com quatro titulares."
        }
    }
    txt = format_single_txt(item)
    assert "Titulares / Nomes Det." in txt
    assert "JOSE MAGNO BUFON" in txt
    assert "WODIELEN CARMINATI" in txt
    assert "Total: 4" in txt




