from pathlib import Path
from joakindex.config import (
    get_factory_defaults,
    clean_path_string,
    resolve_classifier_output_dir,
)


def test_get_factory_defaults():
    defaults = get_factory_defaults()
    assert "classificador" in defaults
    assert "visualizador" in defaults
    assert defaults["classificador"]["provider"] == "ollama"
    assert defaults["visualizador"]["port"] == 8088


def test_clean_path_string():
    assert clean_path_string("  'path/to/folder'  ") == "path/to/folder"
    assert clean_path_string('"/home/user/docs"') == "/home/user/docs"
    assert clean_path_string(None) == ""


def test_resolve_classifier_output_dir(tmp_path):
    # Default fallback
    assert resolve_classifier_output_dir(None) == "./saida"
    assert resolve_classifier_output_dir("saida") == "./saida"

    # Custom directory
    custom_dir = tmp_path / "minha_saida"
    custom_dir.mkdir()
    resolved = resolve_classifier_output_dir(str(custom_dir))
    assert Path(resolved).resolve() == custom_dir.resolve()
