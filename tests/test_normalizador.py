import pytest
from normalizador_instituicoes import (
    remover_acentos,
    formatar_titulo_pt,
    normalizar_instituicao,
)


def test_remover_acentos():
    assert remover_acentos("São Paulo - Educação e Saúde") == "Sao Paulo - Educacao e Saude"
    assert remover_acentos("É óbvio até a última análise") == "E obvio ate a ultima analise"
    assert remover_acentos("") == ""
    assert remover_acentos(None) == ""


def test_formatar_titulo_pt():
    # Connectives stay lowercase, acronyms uppercase
    res = formatar_titulo_pt("faculdades integradas do brasil")
    assert "do" in res
    assert res.startswith("Faculdades Integradas")

    # Acronym in parentheses
    res_par = formatar_titulo_pt("Universidade de Sao Paulo (USP)")
    assert res_par == "Universidade de Sao Paulo (USP)"


def test_normalizar_instituicao_null_and_empty():
    assert normalizar_instituicao(None) is None
    assert normalizar_instituicao("") is None
    assert normalizar_instituicao("   ") is None
    assert normalizar_instituicao("Nao Informada") is None
    assert normalizar_instituicao("N/A") is None
    assert normalizar_instituicao("Desconhecido") is None


def test_normalizar_instituicao_canonicas():
    # FIVAR
    assert normalizar_instituicao("FIVAR - Faculdades Integradas Vale do Rio Verde") == "Faculdades Integradas Vale do Rio Verde (FIVAR)"
    assert normalizar_instituicao("Faculdades Integradas Vale do Rio Verde") == "Faculdades Integradas Vale do Rio Verde (FIVAR)"
    assert normalizar_instituicao("FIVAR") == "Faculdades Integradas Vale do Rio Verde (FIVAR)"

    # FAB / Alfa do Brasil
    assert normalizar_instituicao("Faculdade Alfa do Brasil") == "Faculdade Alfa do Brasil (FAB)" or normalizar_instituicao("Faculdade Alfa do Brasil") == "Faculdade Alffa do Brasil (FAB)"
    assert "FAB" in normalizar_instituicao("FAB - Faculdade Alfa do Brasil")

    # UNIFTB
    assert normalizar_instituicao("Faculdade Tobias Barreto") == "Faculdade UNIFTB"
    assert normalizar_instituicao("UNIFTB") == "Faculdade UNIFTB"


def test_normalizar_instituicao_limpeza_sufixos_empresariais():
    # Suffixes like LTDA, S/A, ME should be stripped from education names
    res = normalizar_instituicao("Centro Educacional São Lucas LTDA")
    assert "LTDA" not in res
    assert "Sao Lucas" in remover_acentos(res)
