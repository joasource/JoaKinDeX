import pytest
from joakindex import (
    format_cpf,
    validate_cpf_checksum,
    is_valid_cpf_syntax,
    extract_cpf_fallback,
    extract_rg_fallback,
)


def test_format_cpf():
    assert format_cpf("12345678909") == "123.456.789-09"
    assert format_cpf("123.456.789-09") == "123.456.789-09"
    assert format_cpf(None) is None
    assert format_cpf("") is None


def test_validate_cpf_checksum():
    # Valid known CPF checksums (generated with standard algorithm)
    # Ex: 111.444.777-35 is a valid CPF format & checksum
    assert validate_cpf_checksum("11144477735") is True
    assert validate_cpf_checksum("111.444.777-35") is True

    # Invalid checksum
    assert validate_cpf_checksum("111.444.777-00") is False

    # Same digits (all 1s, all 0s) are invalid by Receita Federal rules
    assert validate_cpf_checksum("000.000.000-00") is False
    assert validate_cpf_checksum("111.111.111-11") is False

    # Wrong length
    assert validate_cpf_checksum("123456") is False


def test_is_valid_cpf_syntax():
    assert is_valid_cpf_syntax("111.444.777-35") is True
    assert is_valid_cpf_syntax("11144477735") is False  # requires dots and hyphen
    assert is_valid_cpf_syntax("111.444.777-00") is False  # fails checksum
    assert is_valid_cpf_syntax(None) is False
    assert is_valid_cpf_syntax("") is False


def test_extract_cpf_fallback():
    text = "O portador deste diploma, inscrito no CPF 111.444.777-35, concluiu o curso."
    assert extract_cpf_fallback(text) == "111.444.777-35"

    # Digits without dots but with CPF label
    text2 = "Docente sob o C.P.F: 11144477735 aprovado."
    assert extract_cpf_fallback(text2) == "111.444.777-35"

    # No valid CPF
    text_invalid = "Inscrito no CPF 123.456.789-00 sem validador."
    assert extract_cpf_fallback(text_invalid) is None


def test_extract_rg_fallback():
    text = "Identidade RG 12.345.678-9 SSP/SP emitida em 10/10/2020."
    rg = extract_rg_fallback(text)
    assert rg is not None
    assert "12.345.678" in rg
