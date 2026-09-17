from joakindex.export_relacional import (
    build_vinculos_for_doc,
    resolve_pessoa_fisica_id,
    resolve_pessoa_juridica_id,
)

CPF_VALIDO = "111.444.777-35"
CPF_VALIDO_DIGITS = "11144477735"
CNPJ_VALIDO = "11.222.333/0001-81"
CNPJ_VALIDO_DIGITS = "11222333000181"


def test_resolve_pessoa_fisica_cpf_valido():
    doc = {"md5": "aaa111", "beneficiario": "Fulano de Tal", "cpf": CPF_VALIDO, "rg": "12.345.678-9"}
    entidade_id, incompleta, campos = resolve_pessoa_fisica_id(doc)
    assert entidade_id == f"PF_{CPF_VALIDO_DIGITS}"
    assert incompleta is False
    assert campos["cpf"] == CPF_VALIDO_DIGITS
    assert campos["nome_normalizado"] == "FULANO DE TAL"


def test_resolve_pessoa_fisica_cpf_valido_funde_entre_documentos():
    doc_a = {"md5": "aaa111", "beneficiario": "Fulano de Tal", "cpf": CPF_VALIDO}
    doc_b = {"md5": "bbb222", "beneficiario": "Fulano De Tal", "cpf": CPF_VALIDO}
    id_a, _, _ = resolve_pessoa_fisica_id(doc_a)
    id_b, _, _ = resolve_pessoa_fisica_id(doc_b)
    assert id_a == id_b


def test_resolve_pessoa_fisica_cpf_invalido_cai_para_rg():
    doc = {"md5": "ccc333", "beneficiario": "Ciclano da Silva", "cpf": "111.111.111-11", "rg": "98.765.432-1"}
    entidade_id, incompleta, campos = resolve_pessoa_fisica_id(doc)
    assert entidade_id is not None
    assert entidade_id.startswith("PF_RGNM_")
    assert incompleta is False
    assert campos["cpf"] == ""


def test_resolve_pessoa_fisica_nome_rg_funde_sem_cpf():
    doc_a = {"md5": "ddd444", "beneficiario": "Beltrano Souza", "rg": "11.222.333-4"}
    doc_b = {"md5": "eee555", "beneficiario": "Beltrano Souza", "rg": "11.222.333-4"}
    id_a, incompleta_a, _ = resolve_pessoa_fisica_id(doc_a)
    id_b, incompleta_b, _ = resolve_pessoa_fisica_id(doc_b)
    assert id_a == id_b
    assert incompleta_a is False and incompleta_b is False


def test_resolve_pessoa_fisica_sem_cpf_sem_rg_gera_provisoria_por_documento():
    doc_a = {"md5": "fff666", "beneficiario": "Maria Silva"}
    doc_b = {"md5": "ggg777", "beneficiario": "Maria Silva"}
    id_a, incompleta_a, _ = resolve_pessoa_fisica_id(doc_a)
    id_b, incompleta_b, _ = resolve_pessoa_fisica_id(doc_b)
    # Mesmo nome, sem CPF/RG: NUNCA funde por nome isolado -> entidades distintas
    assert id_a != id_b
    assert id_a.startswith("PF_PROV_fff666")
    assert id_b.startswith("PF_PROV_ggg777")
    assert incompleta_a is True and incompleta_b is True


def test_resolve_pessoa_fisica_duas_pessoas_nao_identificadas_no_mesmo_documento():
    # Mesmo documento (md5 igual), nomes diferentes -> não podem colidir
    # (cenário real: comprador e vendedor de um contrato, ambos sem CPF/RG)
    doc_comprador = {"md5": "contrato001", "beneficiario": "Comprador Um"}
    doc_vendedor = {"md5": "contrato001", "beneficiario": "Vendedor Dois"}
    id_a, _, _ = resolve_pessoa_fisica_id(doc_comprador)
    id_b, _, _ = resolve_pessoa_fisica_id(doc_vendedor)
    assert id_a != id_b


def test_resolve_pessoa_fisica_sem_nenhum_indicio_retorna_none():
    doc = {"md5": "hhh888"}
    entidade_id, incompleta, campos = resolve_pessoa_fisica_id(doc)
    assert entidade_id is None
    assert incompleta is False
    assert campos == {}


def test_resolve_pessoa_juridica_cnpj_valido():
    entidade_id, incompleta, campos = resolve_pessoa_juridica_id("Empresa XYZ Ltda", CNPJ_VALIDO, "iii999")
    assert entidade_id == f"PJ_{CNPJ_VALIDO_DIGITS}"
    assert incompleta is False
    assert campos["cnpj"] == CNPJ_VALIDO_DIGITS
    assert campos["razao_social_normalizada"] == "EMPRESA XYZ LTDA"


def test_resolve_pessoa_juridica_cnpj_valido_funde_entre_documentos():
    id_a, _, _ = resolve_pessoa_juridica_id("Empresa XYZ Ltda", CNPJ_VALIDO, "iii999")
    id_b, _, _ = resolve_pessoa_juridica_id("EMPRESA XYZ LTDA", CNPJ_VALIDO, "jjj000")
    assert id_a == id_b


def test_resolve_pessoa_juridica_sem_cnpj_valido_gera_provisoria_por_documento():
    id_a, incompleta_a, _ = resolve_pessoa_juridica_id("Empresa Fantasma", None, "kkk111")
    id_b, incompleta_b, _ = resolve_pessoa_juridica_id("Empresa Fantasma", None, "lll222")
    # Mesma razão social, sem CNPJ válido: entidades distintas (escopadas por documento)
    assert id_a != id_b
    assert incompleta_a is True and incompleta_b is True


def test_resolve_pessoa_juridica_duas_pj_nao_identificadas_no_mesmo_documento():
    id_a, _, _ = resolve_pessoa_juridica_id("Empresa A", None, "mmm333")
    id_b, _, _ = resolve_pessoa_juridica_id("Empresa B", None, "mmm333")
    # Mesmo documento, razões sociais diferentes -> não colidem
    assert id_a != id_b


def test_build_vinculos_documento_simples_so_titular():
    doc = {"md5": "doc001", "beneficiario": "Fulano de Tal", "cpf": CPF_VALIDO}
    vinculos = build_vinculos_for_doc(doc)
    papeis = {v["papel"] for v in vinculos}
    assert papeis == {"titular"}
    assert vinculos[0]["entidade_id"] == f"PF_{CPF_VALIDO_DIGITS}"


def test_build_vinculos_cartao_cnpj_titular_pj():
    doc = {"md5": "doc002", "razao_social": "Empresa XYZ Ltda", "cnpj": CNPJ_VALIDO}
    vinculos = build_vinculos_for_doc(doc)
    assert len(vinculos) == 1
    assert vinculos[0]["papel"] == "titular"
    assert vinculos[0]["tipo_entidade"] == "PJ"
    assert vinculos[0]["entidade_id"] == f"PJ_{CNPJ_VALIDO_DIGITS}"


def test_build_vinculos_contrato_compra_venda_multiplas_partes():
    doc = {
        "md5": "doc003",
        "beneficiario": "Comprador Um",
        "vendedor": "Vendedor Dois",
        "comprador": "Comprador Um",
        "proprietario_anterior": "Vendedor Dois",
    }
    vinculos = build_vinculos_for_doc(doc)
    papeis = [v["papel"] for v in vinculos]
    assert "titular" in papeis
    assert "vendedor" in papeis
    assert "comprador" in papeis
    assert "proprietario_anterior" in papeis
    entidades = {v["entidade_id"] for v in vinculos}
    # Comprador e vendedor são pessoas distintas, sem CPF/RG -> ids distintos
    assert len(entidades) >= 2


def test_build_vinculos_informe_rendimentos_titular_pf_e_fonte_pagadora_pj():
    doc = {
        "md5": "doc004",
        "beneficiario": "Fulano de Tal",
        "cpf": CPF_VALIDO,
        "fonte_pagadora": "Empresa XYZ Ltda",
        "cnpj_fonte_pagadora": CNPJ_VALIDO,
    }
    vinculos = build_vinculos_for_doc(doc)
    assert len(vinculos) == 2
    by_papel = {v["papel"]: v for v in vinculos}
    assert by_papel["titular"]["tipo_entidade"] == "PF"
    assert by_papel["fonte_pagadora"]["tipo_entidade"] == "PJ"
    assert by_papel["fonte_pagadora"]["entidade_id"] == f"PJ_{CNPJ_VALIDO_DIGITS}"


def test_build_vinculos_fonte_pagadora_sem_cnpj_valido_vira_pf():
    doc = {"md5": "doc005", "beneficiario": "Fulano de Tal", "fonte_pagadora": "Sicrano Pagador"}
    vinculos = build_vinculos_for_doc(doc)
    by_papel = {v["papel"]: v for v in vinculos}
    assert by_papel["fonte_pagadora"]["tipo_entidade"] == "PF"


def test_build_vinculos_nomes_detectados_gera_um_vinculo_por_nome_extra():
    doc = {
        "md5": "doc006",
        "beneficiario": "Fulano de Tal",
        "nomes_detectados": ["Fulano de Tal", "Ciclano da Silva", "Beltrano Souza"],
    }
    vinculos = build_vinculos_for_doc(doc)
    listados = [v for v in vinculos if v["papel"] == "listado"]
    # O próprio beneficiário aparece em nomes_detectados (comportamento do prompt de extração
    # para documentos de 1 pessoa só) e não deve duplicar o vínculo "titular"
    assert len(listados) == 2
    entidades_listadas = {v["entidade_id"] for v in listados}
    assert len(entidades_listadas) == 2


def test_build_vinculos_documento_sem_nenhum_campo_retorna_lista_vazia():
    doc = {"md5": "doc007"}
    assert build_vinculos_for_doc(doc) == []
