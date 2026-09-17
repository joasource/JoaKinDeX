from joakindex.export_relacional import resolve_pessoa_fisica_id, resolve_pessoa_juridica_id

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
    assert id_a == "PF_PROV_fff666"
    assert id_b == "PF_PROV_ggg777"
    assert incompleta_a is True and incompleta_b is True


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
