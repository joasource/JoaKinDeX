"""
Testes de caracterização de prompt_interactive_menu (src/joakindex/cli.py).

prompt_interactive_menu é o menu interativo do CLI (~340 linhas): uma sequência
de prompts via input() que preenche um argparse.Namespace (entrada, saída,
provedor de IA, modelo, workers, OCR, estratégia de execução) e no fim persiste
a escolha via save_classifier_config. Todos os helpers de config/detecção de
Ollama são mockados aqui — o objetivo é fixar o CONTRATO de entrada/saída da
função (o que cada resposta de input produz no args final), não testar os
helpers em si (já cobertos em outros arquivos).
"""
import argparse

import pytest

from joakindex import cli


def _make_args(**overrides):
    base = dict(
        input="./pdf",
        output_dir="./saida",
        provider="ollama",
        model=None,
        docker=None,
        ollama_url="http://localhost:11434",
        openai_key=None,
        openai_base_url=None,
        workers=1,
        max_pages=4,
        skip_ocr=False,
        reprocess_ocr=False,
        force=False,
        no_individual=False,
    )
    base.update(overrides)
    return argparse.Namespace(**base)


@pytest.fixture(autouse=True)
def _mock_config_helpers(monkeypatch, tmp_path):
    """Neutraliza I/O de config e detecção de Ollama para todos os testes deste arquivo.

    cli.py roda load_dotenv_if_present() na importação do módulo e carrega o
    .env real da raiz do repo (com OPENAI_API_KEY/OPENAI_BASE_URL reais do
    usuário) para os.environ do processo inteiro de teste. Sem o delenv abaixo,
    prompt_interactive_menu lê essas variáveis reais como fallback e chega a
    IMPRIMIR uma versão mascarada da chave real no resumo final (reproduzido
    nesta sessão via mutação manual) — mesma classe de armadilha do
    JOAKINDEX_AUTH_TOKEN documentada para os testes de server.py.
    """
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    monkeypatch.setattr(cli, "has_custom_config", lambda *a, **k: False)
    monkeypatch.setattr(cli, "reset_classifier_config", lambda: None)
    monkeypatch.setattr(
        cli,
        "get_factory_defaults",
        lambda: {
            "classificador": {
                "input": "./pdf",
                "output_dir": "./saida",
                "provider": "ollama",
                "model": None,
                "docker": None,
                "ollama_url": "http://localhost:11434",
                "openai_key": None,
                "openai_base_url": None,
                "workers": 1,
                "max_pages": 4,
                "skip_ocr": False,
                "reprocess_ocr": False,
                "force": False,
                "no_individual": False,
            }
        },
    )
    monkeypatch.setattr(cli, "resolve_classifier_output_dir", lambda raw: str(raw))
    monkeypatch.setattr(cli, "detect_ollama_environments", lambda base_url=None: [])
    saved = {}
    monkeypatch.setattr(cli, "save_classifier_config", lambda updates: saved.update(updates))
    return saved


def _queue_inputs(monkeypatch, respostas):
    it = iter(respostas)

    def _fake_input(_prompt=""):
        try:
            return next(it)
        except StopIteration:
            raise AssertionError("prompt_interactive_menu pediu mais input() do que o esperado pelo teste")

    monkeypatch.setattr("builtins.input", _fake_input)


def test_fluxo_completo_ollama_incremental_aceita_tudo_por_padrao(monkeypatch, tmp_path):
    pasta = tmp_path / "pdf"
    pasta.mkdir()
    (pasta / "doc.pdf").write_bytes(b"conteudo")
    monkeypatch.setattr(cli, "count_pdfs_in_path", lambda p: 1)

    _queue_inputs(monkeypatch, [
        str(pasta),   # 1. entrada
        "",           # 2. saída (aceita padrão)
        "",           # 3. provedor (aceita ollama)
        "",           # 4. modelo (aceita padrão)
        "",           # 5. workers (aceita padrão)
        "",           # 6. OCR multimodal (aceita ativado)
        "",           # 7. estratégia (aceita incremental)
        "",           # confirmação final (aceita "S")
    ])

    result = cli.prompt_interactive_menu(_make_args())

    assert result.input == str(pasta)
    assert result.provider == "ollama"
    assert result.model == "gemma4:e4b"
    assert result.workers == 1
    assert result.skip_ocr is False
    assert result.force is False
    assert result.reprocess_ocr is False


def test_caminho_inexistente_mantido_apos_confirmacao(monkeypatch, tmp_path):
    inexistente = tmp_path / "nao_existe"

    _queue_inputs(monkeypatch, [
        str(inexistente),  # 1. entrada inexistente
        "s",                # confirma manter mesmo assim
        "",                 # 2. saída
        "",                 # 3. provedor
        "",                 # 4. modelo
        "",                 # 5. workers
        "",                 # 6. OCR
        "",                 # 7. estratégia
        "",                 # confirmação final
    ])

    result = cli.prompt_interactive_menu(_make_args())

    assert result.input == str(inexistente.expanduser().resolve())


def test_reset_no_prompt_de_entrada_restaura_padroes_de_fabrica(monkeypatch, tmp_path):
    pasta = tmp_path / "pdf"
    pasta.mkdir()
    monkeypatch.setattr(cli, "count_pdfs_in_path", lambda p: 0)

    _queue_inputs(monkeypatch, [
        "reset",      # aciona reset_classifier_config + get_factory_defaults
        str(pasta),   # entrada válida em seguida
        "s",          # confirma manter mesmo sem PDFs
        "",           # saída
        "",           # provedor
        "",           # modelo
        "",           # workers
        "",           # OCR
        "",           # estratégia
        "",           # confirmação final
    ])

    result = cli.prompt_interactive_menu(_make_args(input="./algo-customizado"))

    assert result.input == str(pasta.expanduser().resolve())


def test_provedor_openai_pede_modelo_chave_e_base_url(monkeypatch, tmp_path):
    pasta = tmp_path / "pdf"
    pasta.mkdir()
    monkeypatch.setattr(cli, "count_pdfs_in_path", lambda p: 0)

    _queue_inputs(monkeypatch, [
        str(pasta), "s",   # entrada (sem PDFs, confirma)
        "",                 # saída
        "2",                # provedor -> openai
        "",                 # modelo (aceita gpt-4o-mini)
        "sk-minha-chave-123456",  # chave OpenAI
        "",                 # base URL (aceita padrão oficial)
        "",                 # workers
        "",                 # OCR
        "",                 # estratégia
        "",                 # confirmação final
    ])

    result = cli.prompt_interactive_menu(_make_args())

    assert result.provider == "openai"
    assert result.model == "gpt-4o-mini"
    assert result.openai_key == "sk-minha-chave-123456"


def test_openai_sem_chave_pode_prosseguir_com_confirmacao_explicita(monkeypatch, tmp_path):
    pasta = tmp_path / "pdf"
    pasta.mkdir()
    monkeypatch.setattr(cli, "count_pdfs_in_path", lambda p: 0)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    _queue_inputs(monkeypatch, [
        str(pasta), "s",
        "",
        "2",     # provedor -> openai
        "",      # modelo
        "",      # chave vazia -> aviso
        "s",     # confirma continuar sem chave
        "",      # base URL
        "",      # workers
        "",      # OCR
        "",      # estratégia
        "",      # confirmação final
    ])

    result = cli.prompt_interactive_menu(_make_args())

    assert result.provider == "openai"
    assert result.openai_key is None


def test_multiplos_ambientes_ollama_permite_escolher_por_indice(monkeypatch, tmp_path):
    pasta = tmp_path / "pdf"
    pasta.mkdir()
    monkeypatch.setattr(cli, "count_pdfs_in_path", lambda p: 0)
    monkeypatch.setattr(
        cli,
        "detect_ollama_environments",
        lambda base_url=None: [
            {"description": "Nativo", "is_running": True, "container": None, "models": ["modelo-a"], "type": "native"},
            {"description": "Docker open-webui", "is_running": True, "container": "open-webui", "models": ["modelo-b"], "type": "docker"},
        ],
    )

    _queue_inputs(monkeypatch, [
        str(pasta), "s",
        "",
        "",       # provedor ollama (padrão)
        "2",      # escolhe o 2º ambiente detectado (Docker)
        "",       # modelo (aceita o padrão do ambiente escolhido)
        "",       # workers
        "",       # OCR
        "",       # estratégia
        "",       # confirmação final
    ])

    result = cli.prompt_interactive_menu(_make_args())

    assert result.docker == "open-webui"
    assert result.model == "modelo-b"


def test_workers_invalido_repete_prompt_ate_valor_valido(monkeypatch, tmp_path):
    pasta = tmp_path / "pdf"
    pasta.mkdir()
    monkeypatch.setattr(cli, "count_pdfs_in_path", lambda p: 0)

    _queue_inputs(monkeypatch, [
        str(pasta), "s",
        "",
        "",
        "",
        "abc",   # inválido: não é inteiro
        "0",     # inválido: menor que 1
        "3",     # válido
        "",      # OCR
        "",      # estratégia
        "",      # confirmação final
    ])

    result = cli.prompt_interactive_menu(_make_args())

    assert result.workers == 3


def test_skip_ocr_desativado_quando_usuario_responde_nao(monkeypatch, tmp_path):
    pasta = tmp_path / "pdf"
    pasta.mkdir()
    monkeypatch.setattr(cli, "count_pdfs_in_path", lambda p: 0)

    _queue_inputs(monkeypatch, [
        str(pasta), "s",
        "",
        "",
        "",
        "",
        "n",     # desativa OCR
        "",      # estratégia
        "",      # confirmação final
    ])

    result = cli.prompt_interactive_menu(_make_args())

    assert result.skip_ocr is True


@pytest.mark.parametrize(
    "resposta_estrategia,esperado_force,esperado_reprocess_ocr",
    [
        ("1", False, False),
        ("2", False, True),
        ("3", True, False),
    ],
)
def test_estrategia_de_processamento_mapeia_force_e_reprocess_ocr(
    monkeypatch, tmp_path, resposta_estrategia, esperado_force, esperado_reprocess_ocr
):
    pasta = tmp_path / "pdf"
    pasta.mkdir()
    monkeypatch.setattr(cli, "count_pdfs_in_path", lambda p: 0)

    _queue_inputs(monkeypatch, [
        str(pasta), "s",
        "",
        "",
        "",
        "",
        "",
        resposta_estrategia,
        "",   # confirmação final
    ])

    result = cli.prompt_interactive_menu(_make_args())

    assert result.force is esperado_force
    assert result.reprocess_ocr is esperado_reprocess_ocr


def test_cancelar_na_confirmacao_final_sai_com_sys_exit_0(monkeypatch, tmp_path):
    pasta = tmp_path / "pdf"
    pasta.mkdir()
    monkeypatch.setattr(cli, "count_pdfs_in_path", lambda p: 0)

    _queue_inputs(monkeypatch, [
        str(pasta), "s",
        "",
        "",
        "",
        "",
        "",
        "",
        "n",   # recusa iniciar a classificação
    ])

    with pytest.raises(SystemExit) as exc_info:
        cli.prompt_interactive_menu(_make_args())

    assert exc_info.value.code == 0


def test_eof_durante_prompt_sai_com_sys_exit_0(monkeypatch):
    def _raise_eof(_prompt=""):
        raise EOFError()

    monkeypatch.setattr("builtins.input", _raise_eof)

    with pytest.raises(SystemExit) as exc_info:
        cli.prompt_interactive_menu(_make_args())

    assert exc_info.value.code == 0


def test_config_final_e_persistida_com_save_classifier_config(monkeypatch, tmp_path):
    pasta = tmp_path / "pdf"
    pasta.mkdir()
    monkeypatch.setattr(cli, "count_pdfs_in_path", lambda p: 0)

    saved = {}
    monkeypatch.setattr(cli, "save_classifier_config", lambda updates: saved.update(updates))

    _queue_inputs(monkeypatch, [
        str(pasta), "s",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
    ])

    result = cli.prompt_interactive_menu(_make_args())

    assert saved["input"] == result.input
    assert saved["output_dir"] == result.output_dir
    assert saved["provider"] == "ollama"
    assert saved["workers"] == 1
