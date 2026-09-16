"""
JoaKinDeX - Central Universal de Indexação, Extração Multidomínio, Metadados Forenses e Conferência Documental em Massa
Criado por: Joaquim Ferreira Silva Neto <joaquimfsneto@gmail.com>
"""

__project__ = "JoaKinDeX"
__version__ = "1.0.0"
__author__ = "Joaquim Ferreira Silva Neto"
__email__ = "joaquimfsneto@gmail.com"

from joakindex.cli import (
    main,
    run_batch_classification,
    process_single_pdf,
    extract_file_dublin_core,
    format_cpf,
    is_valid_cpf_syntax,
    extract_cpf_fallback,
    extract_rg_fallback,
    extract_boleto_signals,
    extract_cheque_signals,
    extract_irpf_signals,
    extract_informe_rendimentos_signals,
    extract_contrato_compra_venda_signals,
    extract_nota_promissoria_signals,
    extract_recibo_signals,
)

from joakindex.extractors_texto import validate_cpf_checksum

from joakindex.server import (
    main as server_main,
    ConferenciaServer,
)

from joakindex.db import (
    get_db_path,
    get_json_path,
    init_database,
    get_connection,
    upsert_document,
    upsert_documents_batch,
    get_document_by_md5,
    get_all_documents,
    update_conference_status,
    salvar_regra_aprendida,
    aprender_com_paginas_dossie,
    obter_regras_aprendidas,
    remover_regra_aprendida,
    consultar_regra_para_texto,
    resolve_default_db_path,
    DEFAULT_DB_PATH,
)

from joakindex.config import (
    get_factory_defaults,
    get_classifier_config,
    save_classifier_config,
    get_visualizer_config,
    save_visualizer_config,
    reset_classifier_config,
    reset_visualizer_config,
)

from joakindex.normalizer import (
    normalizar_instituicao,
    remover_acentos,
    formatar_titulo_pt,
)

__all__ = [
    "main",
    "server_main",
    "run_batch_classification",
    "process_single_pdf",
    "extract_file_dublin_core",
    "format_cpf",
    "validate_cpf_checksum",
    "is_valid_cpf_syntax",
    "extract_cpf_fallback",
    "extract_rg_fallback",
    "extract_boleto_signals",
    "extract_cheque_signals",
    "extract_irpf_signals",
    "extract_informe_rendimentos_signals",
    "extract_contrato_compra_venda_signals",
    "extract_nota_promissoria_signals",
    "extract_recibo_signals",
    "ConferenciaServer",
    "get_db_path",
    "get_json_path",
    "init_database",
    "get_connection",
    "upsert_document",
    "upsert_documents_batch",
    "get_document_by_md5",
    "get_all_documents",
    "update_conference_status",
    "salvar_regra_aprendida",
    "aprender_com_paginas_dossie",
    "obter_regras_aprendidas",
    "remover_regra_aprendida",
    "consultar_regra_para_texto",
    "resolve_default_db_path",
    "DEFAULT_DB_PATH",
    "get_factory_defaults",
    "get_classifier_config",
    "save_classifier_config",
    "get_visualizer_config",
    "save_visualizer_config",
    "reset_classifier_config",
    "reset_visualizer_config",
    "normalizar_instituicao",
    "remover_acentos",
    "formatar_titulo_pt",
]
