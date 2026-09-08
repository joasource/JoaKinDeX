#!/usr/bin/env python3
"""
JoaKinDeX - Gerenciador de Configurações Persistentes
Criado por: Joaquim Ferreira Silva Neto <joaquimfsneto@gmail.com>

Módulo de gerenciamento de configurações persistentes para o JoaKinDeX e servidor_visualizador.
Permite salvar opções alteradas pelos usuários, manter padrões de fábrica neutros
e restaurar configurações tanto interativamente quanto via CLI (--reset-config).
"""

__project__ = "JoaKinDeX"
__author__ = "Joaquim Ferreira Silva Neto"
__email__ = "joaquimfsneto@gmail.com"
__version__ = "1.0.0"

import json
import os
from pathlib import Path
from typing import Dict, Any, Optional

CONFIG_FILE_NAME = ".joakindex_config.json"
LEGACY_CONFIG_FILE_NAME = ".joaclassificador_config.json"


def get_config_file_path() -> Path:
    """Retorna o caminho absoluto do arquivo de configuração no diretório da aplicação."""
    p = Path(__file__).resolve().parent / CONFIG_FILE_NAME
    if not p.exists():
        legacy = Path(__file__).resolve().parent / LEGACY_CONFIG_FILE_NAME
        if legacy.exists():
            return legacy
    return p


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
            "openai_key": None,
            "openai_base_url": None,
        }
    }


def clean_path_string(raw: Any) -> str:
    """Remove aspas e espaços de caminhos colados no console ou enviados via payload."""
    if not raw:
        return ""
    s = str(raw).strip()
    while (s.startswith('"') and s.endswith('"')) or (s.startswith("'") and s.endswith("'")):
        s = s[1:-1].strip()
    if len(s) > 1 and s.endswith("/"):
        s = s.rstrip("/")
    return s


def resolve_classifier_output_dir(raw: Any) -> str:
    """Garante que output_dir do classificador seja SEMPRE um diretório."""
    s = clean_path_string(raw)
    if not s or s in ["./saida", "saida"]:
        return "./saida"
    p = Path(s).expanduser()
    if p.is_file() or p.suffix.lower() == ".json":
        p = p.parent
    return str(p.resolve())


def resolve_visualizer_json_path(raw: Any) -> str:
    """Garante que json_path do visualizador seja SEMPRE um arquivo .json válido."""
    s = clean_path_string(raw)
    if not s or s in ["./saida/classificacao_diplomas.json", "saida/classificacao_diplomas.json", "./saida", "saida"]:
        return "./saida/classificacao_diplomas.json"
    p = Path(s).expanduser()
    if p.is_dir() or p.suffix.lower() != ".json":
        p = p / "classificacao_diplomas.json"
    return str(p.resolve())


def resolve_dir_path(raw: Any, default: str = "./pdf") -> str:
    """Garante que seja um diretório (se for arquivo, usa o pai)."""
    s = clean_path_string(raw)
    if not s or s in [default, default.lstrip("./")]:
        return default
    p = Path(s).expanduser()
    if p.is_file():
        p = p.parent
    return str(p.resolve())


def load_all_config() -> Dict[str, Any]:
    """Carrega o arquivo de configuração, normaliza caminhos ou retorna padrões de fábrica."""
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

            # Auto-repara e higieniza caminhos para evitar corrupções salvas
            if "classificador" in merged and isinstance(merged["classificador"], dict):
                if merged["classificador"].get("output_dir"):
                    merged["classificador"]["output_dir"] = resolve_classifier_output_dir(merged["classificador"]["output_dir"])
                if merged["classificador"].get("input"):
                    merged["classificador"]["input"] = resolve_dir_path(merged["classificador"]["input"], default="./pdf")

            if "visualizador" in merged and isinstance(merged["visualizador"], dict):
                if merged["visualizador"].get("json_path"):
                    merged["visualizador"]["json_path"] = resolve_visualizer_json_path(merged["visualizador"]["json_path"])
                if merged["visualizador"].get("pdf_dir"):
                    merged["visualizador"]["pdf_dir"] = resolve_dir_path(merged["visualizador"]["pdf_dir"], default="./pdf")

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

    # Sincroniza caminhos garantindo tipos corretos (output_dir = pasta, json_path = arquivo)
    if "input" in updates and updates["input"]:
        resolved_in = resolve_dir_path(updates["input"], default="./pdf")
        config["classificador"]["input"] = resolved_in
        config["visualizador"]["pdf_dir"] = resolved_in

    if "output_dir" in updates and updates["output_dir"]:
        resolved_out = resolve_classifier_output_dir(updates["output_dir"])
        json_file = resolve_visualizer_json_path(resolved_out)
        config["classificador"]["output_dir"] = resolved_out
        config["visualizador"]["json_path"] = json_file

    if "provider" in updates and updates["provider"]:
        config["visualizador"]["provider"] = updates["provider"]

    if "model" in updates and updates["model"]:
        config["visualizador"]["model"] = updates["model"]

    if "ollama_url" in updates and updates["ollama_url"]:
        config["visualizador"]["ollama_url"] = updates["ollama_url"]

    if "openai_key" in updates and updates["openai_key"]:
        config["visualizador"]["openai_key"] = updates["openai_key"]

    if "openai_base_url" in updates and updates["openai_base_url"]:
        config["visualizador"]["openai_base_url"] = updates["openai_base_url"]

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
    """Atualiza e salva configurações do visualizador garantindo caminhos limpos e sincronizados."""
    config = load_all_config()
    for k, v in updates.items():
        if k in config["visualizador"]:
            config["visualizador"][k] = v

    # Sincroniza caminhos com o classificador garantindo tipos corretos (output_dir = pasta, json_path = arquivo)
    if "json_path" in updates and updates["json_path"]:
        json_file = resolve_visualizer_json_path(updates["json_path"])
        out_dir = resolve_classifier_output_dir(json_file)
        config["visualizador"]["json_path"] = json_file
        config["classificador"]["output_dir"] = out_dir

    if "pdf_dir" in updates and updates["pdf_dir"]:
        resolved_pdf = resolve_dir_path(updates["pdf_dir"], default="./pdf")
        config["visualizador"]["pdf_dir"] = resolved_pdf
        config["classificador"]["input"] = resolved_pdf

    if "openai_key" in updates and updates["openai_key"]:
        config["classificador"]["openai_key"] = updates["openai_key"]

    if "openai_base_url" in updates and updates["openai_base_url"]:
        config["classificador"]["openai_base_url"] = updates["openai_base_url"]

    if "provider" in updates and updates["provider"]:
        config["classificador"]["provider"] = updates["provider"]

    if "model" in updates and updates["model"]:
        config["classificador"]["model"] = updates["model"]

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
