#!/usr/bin/env python3
"""
Módulo de gerenciamento de configurações persistentes para o joaclassificador-pdf e servidor_visualizador.
Permite salvar opções alteradas pelos usuários, manter padrões de fábrica neutros
e restaurar configurações tanto interativamente quanto via CLI (--reset-config).
"""

import json
import os
from pathlib import Path
from typing import Dict, Any, Optional

CONFIG_FILE_NAME = ".joaclassificador_config.json"


def get_config_file_path() -> Path:
    """Retorna o caminho absoluto do arquivo de configuração no diretório da aplicação."""
    return Path(__file__).resolve().parent / CONFIG_FILE_NAME


def get_factory_defaults() -> Dict[str, Any]:
    """Retorna os padrões de fábrica neutros, sem nomes de usuários ou caminhos absolutos locais."""
    return {
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
        },
        "visualizador": {
            "pdf_dir": "./pdf",
            "json_path": "./saida/classificacao_diplomas.json",
            "port": 8088,
            "html": "./visualizador.html",
            "provider": "ollama",
            "model": None,
            "ollama_url": "http://localhost:11434",
        }
    }


def load_all_config() -> Dict[str, Any]:
    """Carrega o arquivo de configuração ou retorna padrões de fábrica."""
    cfg_file = get_config_file_path()
    defaults = get_factory_defaults()

    if not cfg_file.exists():
        return defaults

    try:
        with open(cfg_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            if not isinstance(data, dict):
                return defaults

            # Mescla recursivamente com padrões de fábrica para garantir todas as chaves
            merged = get_factory_defaults()
            for sec in ["classificador", "visualizador"]:
                if sec in data and isinstance(data[sec], dict):
                    for k, v in data[sec].items():
                        merged[sec][k] = v
            return merged
    except Exception:
        return defaults


def save_all_config(config: Dict[str, Any]) -> None:
    """Salva todas as configurações de forma atômica."""
    cfg_file = get_config_file_path()
    tmp_file = cfg_file.parent / f".tmp_{CONFIG_FILE_NAME}"
    try:
        with open(tmp_file, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        tmp_file.replace(cfg_file)
    except Exception as e:
        print(f"[Aviso] Não foi possível salvar arquivo de configuração: {e}")


def has_custom_config(section: Optional[str] = None) -> bool:
    """Verifica se existe arquivo de configuração salvo e diferente do padrão de fábrica."""
    cfg_file = get_config_file_path()
    if not cfg_file.exists():
        return False
    if not section:
        return True
    try:
        current = load_all_config().get(section, {})
        defaults = get_factory_defaults().get(section, {})
        return current != defaults
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Helpers para o Classificador
# ---------------------------------------------------------------------------
def get_classifier_config() -> Dict[str, Any]:
    """Retorna as configurações do classificador (salvas ou fábrica)."""
    return load_all_config().get("classificador", get_factory_defaults()["classificador"])


def save_classifier_config(updates: Dict[str, Any]) -> None:
    """Atualiza e salva configurações do classificador, sincronizando caminhos com o visualizador."""
    config = load_all_config()
    for k, v in updates.items():
        if k in config["classificador"]:
            config["classificador"][k] = v

    # Sincroniza caminhos com o visualizador para conveniência do usuário
    if "input" in updates and updates["input"]:
        in_p = Path(updates["input"])
        if in_p.is_file():
            config["visualizador"]["pdf_dir"] = str(in_p.parent)
        else:
            config["visualizador"]["pdf_dir"] = str(in_p)

    if "output_dir" in updates and updates["output_dir"]:
        out_p = Path(updates["output_dir"])
        config["visualizador"]["json_path"] = str(out_p / "classificacao_diplomas.json")

    if "provider" in updates and updates["provider"]:
        config["visualizador"]["provider"] = updates["provider"]

    if "model" in updates and updates["model"]:
        config["visualizador"]["model"] = updates["model"]

    if "ollama_url" in updates and updates["ollama_url"]:
        config["visualizador"]["ollama_url"] = updates["ollama_url"]

    save_all_config(config)


def reset_classifier_config() -> Dict[str, Any]:
    """Restaura as configurações do classificador para os padrões de fábrica neutros."""
    config = load_all_config()
    config["classificador"] = get_factory_defaults()["classificador"]
    save_all_config(config)
    return config["classificador"]


# ---------------------------------------------------------------------------
# Helpers para o Visualizador
# ---------------------------------------------------------------------------
def get_visualizer_config() -> Dict[str, Any]:
    """Retorna as configurações do visualizador (salvas ou fábrica)."""
    return load_all_config().get("visualizador", get_factory_defaults()["visualizador"])


def save_visualizer_config(updates: Dict[str, Any]) -> None:
    """Atualiza e salva configurações do visualizador."""
    config = load_all_config()
    for k, v in updates.items():
        if k in config["visualizador"]:
            config["visualizador"][k] = v
    save_all_config(config)


def reset_visualizer_config() -> Dict[str, Any]:
    """Restaura as configurações do visualizador para os padrões de fábrica neutros."""
    config = load_all_config()
    config["visualizador"] = get_factory_defaults()["visualizador"]
    save_all_config(config)
    return config["visualizador"]


def reset_all_config() -> None:
    """Apaga o arquivo de configuração, retornando tudo aos padrões de fábrica."""
    cfg_file = get_config_file_path()
    if cfg_file.exists():
        try:
            cfg_file.unlink()
        except Exception:
            save_all_config(get_factory_defaults())
