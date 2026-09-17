#!/usr/bin/env python3
"""
JoaKinDeX - Central de Indexação & Classificação Documental Multidomínio
Criado por: Joaquim Ferreira Silva Neto <joaquimfsneto@gmail.com>
"""

__project__ = "JoaKinDeX"
__author__ = "Joaquim Ferreira Silva Neto"
__email__ = "joaquimfsneto@gmail.com"
__version__ = "1.0.0"

import os
import sys
import re
import argparse
import warnings
warnings.filterwarnings("ignore", category=UserWarning, module="pypdf")
import subprocess
import shutil
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, Any, List, Optional, Union

try:
    import requests
except ImportError:
    requests = None

try:
    from tqdm import tqdm
except ImportError:
    tqdm = None

try:
    import pypdf
except ImportError:
    pypdf = None


try:
    import pypdfium2 as pdfium
except ImportError:
    pdfium = None

try:
    from PIL import Image
except ImportError:
    Image = None

try:
    from joakindex.classificacao import (
        IMAGE_EXTENSIONS,
        WORD_EXTENSIONS,
        SUPPORTED_EXTENSIONS,
    )
except ImportError:
    from .classificacao import (
        IMAGE_EXTENSIONS,
        WORD_EXTENSIONS,
        SUPPORTED_EXTENSIONS,
    )

try:
    from joakindex.config import (
        get_classifier_config,
        save_classifier_config,
        reset_classifier_config,
        has_custom_config,
        get_factory_defaults,
        clean_path_string,
        resolve_classifier_output_dir,
        resolve_dir_path
    )
except ImportError:
    try:
        from .config import (
            get_classifier_config,
            save_classifier_config,
            reset_classifier_config,
            has_custom_config,
            get_factory_defaults,
            clean_path_string,
            resolve_classifier_output_dir,
            resolve_dir_path
        )
    except ImportError:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from config_manager import (
            get_classifier_config,
            save_classifier_config,
            reset_classifier_config,
            has_custom_config,
            get_factory_defaults,
            clean_path_string,
            resolve_classifier_output_dir,
            resolve_dir_path
        )

try:
    from joakindex.normalizer import uniformizar_base_dados
except ImportError:
    try:
        from .normalizer import uniformizar_base_dados
    except ImportError:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from normalizador_instituicoes import uniformizar_base_dados

try:
    from joakindex.llm_clients import detect_ollama_environments
except ImportError:
    from .llm_clients import detect_ollama_environments


def load_dotenv_if_present(env_path: Optional[Path] = None):
    """
    Carrega automaticamente variáveis do arquivo .env para os.environ sem dependências externas.
    """
    candidates = [
        env_path,
        Path(".env"),
        Path(__file__).parent / ".env",
        Path.cwd() / ".env"
    ] if env_path else [Path(".env"), Path(__file__).parent / ".env", Path.cwd() / ".env"]

    for p in candidates:
        if p and p.exists() and p.is_file():
            try:
                for line in p.read_text(encoding="utf-8").splitlines():
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    k, v = line.split("=", 1)
                    k = k.strip()
                    v = v.strip().strip("'\"")
                    if k and k not in os.environ:
                        os.environ[k] = v
            except Exception:
                pass
            break

# Carrega .env automaticamente
load_dotenv_if_present()


# ---------------------------------------------------------------------------
# Metadados do Arquivo (MD5, Modificação, Autor)
# ---------------------------------------------------------------------------
def extract_file_author(file_path: Union[str, Path]) -> Optional[str]:
    """
    Extrai o autor dos metadados internos de arquivos PDF, DOCX, DOC e imagens.
    Retorna a string higienizada do autor ou None se não houver metadados de autoria.
    """
    p = Path(file_path)
    if not p.exists() or not p.is_file():
        return None

    ext = p.suffix.lower()

    # 1. Arquivos PDF (.pdf)
    if ext == ".pdf":
        if pypdf is not None:
            try:
                reader = pypdf.PdfReader(str(p), strict=False)
                meta = reader.metadata
                if meta and meta.author:
                    author = "".join(ch for ch in str(meta.author) if ch.isprintable()).strip()
                    if author and len(author) >= 2:
                        return author
            except Exception:
                pass
        # Fallback via utilitário pdfinfo do sistema
        if shutil.which("pdfinfo"):
            try:
                res = subprocess.run(["pdfinfo", str(p)], capture_output=True, text=True, timeout=3)
                if res.returncode == 0:
                    for line in res.stdout.splitlines():
                        if line.startswith("Author:"):
                            a = line.split("Author:", 1)[1].strip()
                            if a and len(a) >= 2:
                                return a
            except Exception:
                pass

    # 2. Arquivos Word DOCX (.docx)
    elif ext == ".docx":
        try:
            with zipfile.ZipFile(p, "r") as z:
                if "docProps/core.xml" in z.namelist():
                    xml_data = z.read("docProps/core.xml")
                    root = ET.fromstring(xml_data)
                    for elem in root:
                        if elem.tag.endswith("creator") and elem.text and elem.text.strip():
                            return elem.text.strip()
                        if elem.tag.endswith("lastModifiedBy") and elem.text and elem.text.strip():
                            return elem.text.strip()
        except Exception:
            pass

    # 3. Arquivos Word Legado (.doc 97-2003)
    elif ext == ".doc":
        try:
            with open(p, "rb") as f:
                d = f.read()
            m = re.search(rb"\x1e\x00\x00\x00[\x02-\x80]\x00\x00\x00([A-Za-z\xc0-\xff][A-Za-z0-9\xc0-\xff\s\.\-]{1,60})\x00.*?(?:Normal|Microsoft)", d, re.DOTALL)
            if m:
                s = m.group(1).decode("latin1", errors="ignore").strip()
                if s and len(s) >= 2 and s.lower() not in ["normal", "microsoft"]:
                    return s
        except Exception:
            pass

    # 4. Imagens (JPEG/PNG/TIFF/WEBP)
    elif ext in IMAGE_EXTENSIONS or ext in [".tiff", ".tif"]:
        if Image is not None:
            try:
                with Image.open(p) as im:
                    exif = im.getexif()
                    if exif:
                        from PIL.ExifTags import TAGS
                        for tag_id, val in exif.items():
                            tag = TAGS.get(tag_id, tag_id)
                            if tag in ["Artist", "XPAuthor", "Author"]:
                                s = str(val).strip()
                                if s and len(s) >= 2:
                                    return s
            except Exception:
                pass

    return None


def extract_file_dublin_core(file_path: Union[str, Path]) -> Dict[str, Any]:
    """
    Extrai metadados estruturados do padrão Dublin Core (DCMES ISO 15836) e XMP.
    Retorna um dicionário higienizado contendo chaves como:
    title, creator, subject, description, publisher, contributor, date, modified,
    type, format, identifier, source, language, rights, keywords, creator_tool, producer.
    """
    p = Path(file_path)
    if not p.exists() or not p.is_file():
        return {}

    ext = p.suffix.lower()
    res: Dict[str, Any] = {}

    def _clean_str(val: Any) -> Optional[str]:
        if val is None:
            return None
        if isinstance(val, (list, tuple, set)):
            items = [_clean_str(x) for x in val if x is not None]
            items = [x for x in items if x]
            return ", ".join(items) if items else None
        if isinstance(val, dict):
            items = [f"{k}: {_clean_str(v)}" for k, v in val.items() if v is not None]
            return ", ".join(items) if items else None
        s = "".join(ch for ch in str(val) if ch.isprintable() or ch in " \t\n\r").strip()
        return s if len(s) >= 1 else None

    # 1. Arquivos PDF (.pdf)
    if ext == ".pdf":
        if pypdf is not None:
            try:
                reader = pypdf.PdfReader(str(p), strict=False)
                # Dicionário clássico Info
                meta = reader.metadata
                if meta:
                    if meta.title: res["title"] = _clean_str(meta.title)
                    if meta.author: res["creator"] = _clean_str(meta.author)
                    if meta.subject: res["subject"] = _clean_str(meta.subject)
                    if "/Keywords" in meta and meta["/Keywords"]: res["keywords"] = _clean_str(meta["/Keywords"])
                    if meta.creator: res["creator_tool"] = _clean_str(meta.creator)
                    if meta.producer: res["producer"] = _clean_str(meta.producer)
                    if meta.creation_date: res["date"] = _clean_str(meta.creation_date)
                    if meta.modification_date: res["modified"] = _clean_str(meta.modification_date)
                # XMP Metadata estruturado Dublin Core
                xmp = reader.xmp_metadata
                if xmp:
                    dc_attrs = {
                        "dc_title": "title",
                        "dc_creator": "creator",
                        "dc_subject": "subject",
                        "dc_description": "description",
                        "dc_publisher": "publisher",
                        "dc_contributor": "contributor",
                        "dc_date": "date",
                        "dc_type": "type",
                        "dc_format": "format",
                        "dc_identifier": "identifier",
                        "dc_source": "source",
                        "dc_language": "language",
                        "dc_rights": "rights",
                        "dc_coverage": "coverage",
                        "dc_relation": "relation"
                    }
                    for xmp_attr, dc_key in dc_attrs.items():
                        v = getattr(xmp, xmp_attr, None)
                        if v is not None:
                            cleaned = _clean_str(v)
                            if cleaned:
                                res[dc_key] = cleaned
                    if xmp.xmp_creator_tool and not res.get("creator_tool"):
                        res["creator_tool"] = _clean_str(xmp.xmp_creator_tool)
                    if xmp.pdf_producer and not res.get("producer"):
                        res["producer"] = _clean_str(xmp.pdf_producer)
                    if xmp.pdf_keywords and not res.get("keywords"):
                        res["keywords"] = _clean_str(xmp.pdf_keywords)
                    if xmp.xmp_create_date and not res.get("date"):
                        res["date"] = _clean_str(xmp.xmp_create_date)
                    if xmp.xmp_modify_date and not res.get("modified"):
                        res["modified"] = _clean_str(xmp.xmp_modify_date)
            except Exception:
                pass

        # Fallback pdfinfo
        if shutil.which("pdfinfo") and (not res or not res.get("creator")):
            try:
                proc = subprocess.run(["pdfinfo", str(p)], capture_output=True, text=True, timeout=3)
                if proc.returncode == 0:
                    for line in proc.stdout.splitlines():
                        if ":" in line:
                            k, v = line.split(":", 1)
                            k, v = k.strip(), v.strip()
                            if not v: continue
                            if k == "Title" and not res.get("title"): res["title"] = v
                            elif k == "Author" and not res.get("creator"): res["creator"] = v
                            elif k == "Subject" and not res.get("subject"): res["subject"] = v
                            elif k == "Keywords" and not res.get("keywords"): res["keywords"] = v
                            elif k == "Creator" and not res.get("creator_tool"): res["creator_tool"] = v
                            elif k == "Producer" and not res.get("producer"): res["producer"] = v
                            elif k == "CreationDate" and not res.get("date"): res["date"] = v
                            elif k == "ModDate" and not res.get("modified"): res["modified"] = v
            except Exception:
                pass

    # 2. Arquivos Word DOCX (.docx)
    elif ext == ".docx":
        try:
            with zipfile.ZipFile(p, "r") as z:
                if "docProps/core.xml" in z.namelist():
                    xml_data = z.read("docProps/core.xml")
                    root = ET.fromstring(xml_data)
                    for elem in root:
                        tag_name = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
                        val = _clean_str(elem.text)
                        if not val: continue
                        if tag_name == "title": res["title"] = val
                        elif tag_name == "creator": res["creator"] = val
                        elif tag_name == "subject": res["subject"] = val
                        elif tag_name == "description": res["description"] = val
                        elif tag_name == "keywords": res["keywords"] = val
                        elif tag_name == "lastModifiedBy":
                            res["contributor"] = val
                            if not res.get("creator_tool"): res["creator_tool"] = f"Microsoft Word ({val})"
                        elif tag_name == "created": res["date"] = val
                        elif tag_name == "modified": res["modified"] = val
                        elif tag_name == "category": res["type"] = val
                        elif tag_name == "language": res["language"] = val
        except Exception:
            pass

    # 3. Arquivos Word Legado (.doc 97-2003)
    elif ext == ".doc":
        try:
            with open(p, "rb") as f:
                d = f.read()
            # Autor
            m = re.search(rb"\x1e\x00\x00\x00[\x02-\x80]\x00\x00\x00([A-Za-z\xc0-\xff][A-Za-z0-9\xc0-\xff\s\.\-]{1,60})\x00.*?(?:Normal|Microsoft)", d, re.DOTALL)
            if m:
                s = m.group(1).decode("latin1", errors="ignore").strip()
                if s and s.lower() not in ["normal", "microsoft"]:
                    res["creator"] = s
            # Template / Creator Tool
            if b"Microsoft Word" in d:
                res["creator_tool"] = "Microsoft Word (97-2003)"
            elif b"Normal.dot" in d:
                res["creator_tool"] = "Microsoft Word (Normal.dot)"
        except Exception:
            pass

    # 4. Imagens
    elif ext in IMAGE_EXTENSIONS or ext in [".tiff", ".tif"]:
        if Image is not None:
            try:
                with Image.open(p) as im:
                    exif = im.getexif()
                    if exif:
                        from PIL.ExifTags import TAGS
                        for tag_id, val in exif.items():
                            tag = TAGS.get(tag_id, tag_id)
                            cleaned = _clean_str(val)
                            if not cleaned: continue
                            if tag in ["Artist", "XPAuthor", "Author"]: res["creator"] = cleaned
                            elif tag in ["ImageDescription", "XPComment"]: res["description"] = cleaned
                            elif tag in ["XPTitle"]: res["title"] = cleaned
                            elif tag in ["XPSubject"]: res["subject"] = cleaned
                            elif tag in ["XPKeywords"]: res["keywords"] = cleaned
                            elif tag in ["Software"]: res["creator_tool"] = cleaned
                            elif tag in ["DateTime", "DateTimeOriginal"]: res["date"] = cleaned
                            elif tag in ["Copyright"]: res["rights"] = cleaned
            except Exception:
                pass

    # Se creator não foi encontrado e extract_file_author tiver outro detalhe, harmoniza
    if not res.get("creator"):
        aut = extract_file_author(p)
        if aut:
            res["creator"] = aut

    return {k: v for k, v in res.items() if v}


try:
    from joakindex.classificacao import run_batch_classification
except ImportError:
    from .classificacao import run_batch_classification


try:
    from joakindex.extractors_documento import (
        load_image_to_base64,
        convert_office_to_pdf,
        render_pdf_pages_to_base64,
    )
except ImportError:
    from .extractors_documento import (
        load_image_to_base64,
        convert_office_to_pdf,
        render_pdf_pages_to_base64,
    )


def get_document_images_for_vision(
    file_path: Union[str, Path],
    max_pages: int = 2,
    scale: float = 1.5,
    quality: int = 80
) -> List[str]:
    """
    Retorna lista de imagens base64 seja o arquivo um PDF ou imagem nativa (PNG, JPG, JPEG, WEBP).
    """
    p = Path(file_path)
    ext = p.suffix.lower()
    if ext in IMAGE_EXTENSIONS:
        return load_image_to_base64(p, quality=quality)
    elif ext == ".pdf":
        return render_pdf_pages_to_base64(str(p), max_pages=max_pages, scale=scale, quality=quality)
    elif ext in WORD_EXTENSIONS:
        pdf_cached = convert_office_to_pdf(p)
        if pdf_cached and pdf_cached.exists():
            return render_pdf_pages_to_base64(str(pdf_cached), max_pages=max_pages, scale=scale, quality=quality)
    return []


# ---------------------------------------------------------------------------
# Menu Interativo e Auxiliares de Configuração
# ---------------------------------------------------------------------------
def resolve_default_input_path(specified: Optional[str] = None) -> str:
    if not specified:
        return "./pdf"
    clean = clean_path_string(specified)
    if clean in ["./pdf", "pdf", ""]:
        return "./pdf"
    p = Path(clean).expanduser()
    return str(p.resolve())


def count_pdfs_in_path(p: Path) -> int:
    if not p.exists():
        return 0
    if p.is_file():
        return 1 if p.suffix.lower() in SUPPORTED_EXTENSIONS else 0
    cnt = 0
    for ext in SUPPORTED_EXTENSIONS:
        cnt += len(list(p.glob(f"*{ext}"))) + len(list(p.glob(f"*{ext.upper()}")))
    return cnt


count_documents_in_path = count_pdfs_in_path


def get_available_ollama_models(
    base_url: str = "http://localhost:11434",
    docker_container: Optional[str] = None
) -> List[str]:
    envs = detect_ollama_environments(base_url=base_url)
    if docker_container:
        for e in envs:
            if e.get("container") == docker_container:
                return e.get("models", [])
    for e in envs:
        if e.get("is_running") and e.get("models"):
            return e.get("models", [])
    return []


def prompt_interactive_menu(args: argparse.Namespace) -> argparse.Namespace:
    print("\n" + "=" * 70)
    print("🎓 JoaKinDeX - MENU INTERATIVO DE CLASSIFICAÇÃO")
    print("   Criado por: Joaquim Ferreira Silva Neto <joaquimfsneto@gmail.com>")
    print("=" * 70)
    print("Pressione ENTER para aceitar o valor padrão sugerido entre colchetes [ ].")

    # Opção inicial se houver configurações personalizadas salvas
    if has_custom_config("classificador"):
        print("\n⚙️  Configurações salvas da execução anterior detectadas:")
        print("   1) Continuar e personalizar configurações salvas [Padrão]")
        print("   2) Restaurar todos os padrões de fábrica (limpar configurações salvas)")
        try:
            init_choice = input("Escolha a opção (1 ou 2) [1]: ").strip()
            if init_choice == "2":
                reset_classifier_config()
                factory = get_factory_defaults()["classificador"]
                for k, v in factory.items():
                    setattr(args, k, v)
                print("   [✓] Configurações restauradas com sucesso para os padrões de fábrica neutros!\n")
        except (EOFError, KeyboardInterrupt):
            print("\n[Operação cancelada pelo usuário]")
            sys.exit(0)

    # 1. Pasta ou arquivo de entrada
    default_input = resolve_default_input_path(args.input)
    while True:
        try:
            resp_input = input(f"\n📁 Pasta ou arquivo PDF de entrada [{default_input}]: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n[Operação cancelada pelo usuário]")
            sys.exit(0)

        clean_input = clean_path_string(resp_input)
        if clean_input.lower() in ["reset", "resetar", "padrao", "fábrica", "fabrica"]:
            reset_classifier_config()
            factory = get_factory_defaults()["classificador"]
            for k, v in factory.items():
                setattr(args, k, v)
            default_input = resolve_default_input_path(args.input)
            print("   [✓] Configurações restauradas para os padrões de fábrica neutros!")
            continue

        raw_chosen = clean_input if clean_input else default_input
        chosen_path = Path(raw_chosen).expanduser().resolve()
        if not chosen_path.exists():
            print(f"   ⚠️  Aviso: Caminho '{chosen_path}' não foi encontrado.")
            try:
                conf = input("   Deseja manter esse caminho mesmo assim? (s/N): ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                sys.exit(0)
            if conf in ["s", "sim", "y", "yes"]:
                args.input = str(chosen_path)
                break
        else:
            pdf_count = count_pdfs_in_path(chosen_path)
            if pdf_count == 0:
                print(f"   ⚠️  Aviso: Nenhum arquivo PDF encontrado em '{chosen_path}'.")
                try:
                    conf = input("   Deseja manter esse caminho mesmo assim? (s/N): ").strip().lower()
                except (EOFError, KeyboardInterrupt):
                    sys.exit(0)
                if conf in ["s", "sim", "y", "yes"]:
                    args.input = str(chosen_path)
                    break
            else:
                print(f"   ↳ {pdf_count} arquivo(s) PDF localizado(s) para processar.")
                args.input = str(chosen_path)
                break

    # 2. Pasta de saída
    default_out = resolve_classifier_output_dir(args.output_dir or "./saida")
    while True:
        try:
            resp_out = input(f"\n📄 Pasta de saída dos relatórios [{default_out}]: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n[Operação cancelada pelo usuário]")
            sys.exit(0)

        clean_out = clean_path_string(resp_out)
        if clean_out.lower() in ["reset", "resetar", "padrao", "fábrica", "fabrica"]:
            factory = get_factory_defaults()["classificador"]
            default_out = resolve_classifier_output_dir(factory.get("output_dir", "./saida"))
            print("   [✓] Pasta de saída restaurada para o padrão de fábrica neutro!")
            continue

        raw_out = clean_out if clean_out else default_out
        args.output_dir = resolve_classifier_output_dir(raw_out)
        break

    # 3. Provedor de IA
    print("\n🤖 Provedor de Inteligência Artificial:")
    print("   1) Ollama (Modelos locais ou Docker open-webui) [Padrão]")
    print("   2) OpenAI (Modelos em nuvem via API)")
    while True:
        try:
            resp_prov = input("Escolha o provedor (1 ou 2) [1]: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n[Operação cancelada pelo usuário]")
            sys.exit(0)

        if resp_prov in ["", "1", "ollama"]:
            args.provider = "ollama"
            break
        elif resp_prov in ["2", "openai"]:
            args.provider = "openai"
            break
        else:
            print("   ⚠️  Opção inválida. Digite 1 ou 2.")

    # 4. Modelo de IA
    if args.provider == "ollama":
        print("\n🔍 Detectando ambientes Ollama (Nativo no sistema, Docker oficial puro, Open-WebUI)...")
        detected_envs = detect_ollama_environments(base_url=args.ollama_url)
        running_envs = [e for e in detected_envs if e.get("is_running")]

        chosen_env = None
        if len(running_envs) == 1:
            chosen_env = running_envs[0]
            print(f"   [✓] {chosen_env['description']}")
            if chosen_env["container"]:
                args.docker = chosen_env["container"]
        elif len(running_envs) > 1:
            print(f"   [✓] Foram identificados {len(running_envs)} ambientes Ollama ativos:")
            for idx, env_opt in enumerate(running_envs, 1):
                m_prev = f" (Modelos: {', '.join(env_opt['models'][:3])})" if env_opt.get("models") else " (Sem modelos baixados)"
                print(f"      {idx}) {env_opt['description']}{m_prev}")
            try:
                resp_env = input(f"   Selecione o ambiente Ollama desejado (1-{len(running_envs)}) [1]: ").strip()
                sel_idx = int(resp_env) - 1 if (resp_env.isdigit() and 1 <= int(resp_env) <= len(running_envs)) else 0
                chosen_env = running_envs[sel_idx]
                if chosen_env["container"]:
                    args.docker = chosen_env["container"]
                else:
                    args.docker = None
            except (EOFError, KeyboardInterrupt):
                print("\n[Operação cancelada pelo usuário]")
                sys.exit(0)
        else:
            stopped_native = next((e for e in detected_envs if e.get("type") == "native_binary_stopped"), None)
            if stopped_native:
                print(f"   ⚠️  {stopped_native['description']}")
            else:
                print("   ⚠️  Nenhum servidor Ollama detectado (nem nativo em localhost:11434, nem em containers Docker).")

        available_models = chosen_env["models"] if chosen_env else []
        models_display = chosen_env.get("models_display", []) if chosen_env else []

        if available_models:
            print(f"   ↳ Modelos baixados encontrados: {', '.join(models_display or available_models)}")
            default_model = args.model or available_models[0]
        else:
            default_model = args.model or "gemma4:e4b"

        while True:
            try:
                resp_mod = input(f"\n🧠 Modelo Ollama [{default_model}]: ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\n[Operação cancelada pelo usuário]")
                sys.exit(0)
            args.model = resp_mod if resp_mod else default_model
            break
    else:
        default_model = args.model or "gpt-4o-mini"
        while True:
            try:
                resp_mod = input(f"\n🧠 Modelo OpenAI [{default_model}]: ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\n[Operação cancelada pelo usuário]")
                sys.exit(0)
            args.model = resp_mod if resp_mod else default_model
            break

        # Chave da OpenAI
        current_key = args.openai_key or os.environ.get("OPENAI_API_KEY", "")
        if current_key:
            masked = (current_key[:7] + "..." + current_key[-4:]) if len(current_key) > 12 else "********"
            prompt_key_str = f"🔑 Chave de API OpenAI [{masked} - ENTER para manter]: "
        else:
            prompt_key_str = "🔑 Chave de API OpenAI (sk-...): "

        while True:
            try:
                resp_key = input(prompt_key_str).strip()
            except (EOFError, KeyboardInterrupt):
                print("\n[Operação cancelada pelo usuário]")
                sys.exit(0)

            if resp_key:
                args.openai_key = resp_key
                break
            elif current_key:
                args.openai_key = current_key
                break
            else:
                print("   ⚠️  Aviso: O uso da OpenAI requer uma chave de API válida.")
                try:
                    conf_no_key = input("   Deseja continuar sem informar a chave agora? (s/N): ").strip().lower()
                except (EOFError, KeyboardInterrupt):
                    sys.exit(0)
                if conf_no_key in ["s", "sim", "y", "yes"]:
                    break

        # Base URL opcional (para compatibilidade com Groq, OpenRouter, vLLM, etc.)
        current_base_url = args.openai_base_url or os.environ.get("OPENAI_BASE_URL", "")
        default_url_desc = current_base_url if current_base_url else "padrão oficial OpenAI"
        try:
            resp_base = input(f"🌐 OpenAI Base URL (opcional para Groq/OpenRouter) [{default_url_desc}]: ").strip()
            if resp_base:
                args.openai_base_url = resp_base
            elif current_base_url:
                args.openai_base_url = current_base_url
        except (EOFError, KeyboardInterrupt):
            print("\n[Operação cancelada pelo usuário]")
            sys.exit(0)

    # 5. Threads de processamento (Workers)
    default_workers = args.workers if (args.workers and args.workers > 1) else (4 if args.provider == "openai" else 1)
    while True:
        try:
            resp_w = input(f"\n⚡ Concorrência / Threads simultâneas [{default_workers}]: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n[Operação cancelada pelo usuário]")
            sys.exit(0)

        if not resp_w:
            args.workers = default_workers
            break
        try:
            w_val = int(resp_w)
            if w_val >= 1:
                args.workers = w_val
                break
            else:
                print("   ⚠️  O número de workers deve ser pelo menos 1.")
        except ValueError:
            print("   ⚠️  Digite um número inteiro válido.")

    # 6. OCR Multimodal via LLM
    print("\n🔍 OCR Multimodal via LLM (para PDFs digitalizados e correções de CPF/Tipo):")
    default_ocr_str = "N" if args.skip_ocr else "S"
    try:
        resp_ocr = input(f"Deseja manter o OCR multimodal ativado? (S/n) [{default_ocr_str}]: ").strip().lower()
        if resp_ocr in ["n", "nao", "não", "no"]:
            args.skip_ocr = True
        elif resp_ocr in ["s", "sim", "y", "yes", ""]:
            args.skip_ocr = False
    except (EOFError, KeyboardInterrupt):
        print("\n[Operação cancelada pelo usuário]")
        sys.exit(0)

    # 7. Estratégia de Processamento
    print("\n⚙️  Estratégia de Processamento:")
    print("   1) Incremental: Processar novos e pendentes (ignora já concluídos com sucesso) [Padrão]")
    print("   2) Reprocessar documentos que necessitam de OCR (erros ou não identificados)")
    print("   3) Forçar reprocessamento de TODOS os documentos do zero")
    while True:
        try:
            resp_mode = input("Escolha o modo de execução (1, 2 ou 3) [1]: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n[Operação cancelada pelo usuário]")
            sys.exit(0)

        if resp_mode in ["", "1"]:
            args.force = False
            args.reprocess_ocr = False
            break
        elif resp_mode == "2":
            args.force = False
            args.reprocess_ocr = True
            break
        elif resp_mode == "3":
            args.force = True
            args.reprocess_ocr = False
            break
        else:
            print("   ⚠️  Opção inválida. Digite 1, 2 ou 3.")

    # Resumo
    in_p = Path(args.input)
    pdf_qtd = count_pdfs_in_path(in_p)
    mode_desc = (
        "Reprocessar TUDO do zero (--force)" if args.force
        else ("Reprocessar pendentes de OCR (--reprocess-ocr)" if args.reprocess_ocr
        else "Incremental (apenas novos e pendentes)")
    )
    ocr_desc = "Desativado (--skip-ocr)" if args.skip_ocr else "Ativado (Automático para escaneados e erros de CPF/Tipo)"

    print("\n" + "=" * 70)
    print("📋 RESUMO DA CONFIGURAÇÃO DO CLASSIFICADOR")
    print("=" * 70)
    print(f"• Entrada      : {args.input} ({pdf_qtd} arquivo(s) PDF)")
    print(f"• Saída        : {args.output_dir}")
    if args.provider == "openai":
        k_val = args.openai_key or os.environ.get("OPENAI_API_KEY", "")
        masked_k = (k_val[:7] + "..." + k_val[-4:]) if (k_val and len(k_val) > 12) else ("Configurada" if k_val else "Não informada")
        print(f"• Provedor     : OPENAI (Modelo: {args.model} | Chave: {masked_k})")
        if args.openai_base_url:
            print(f"• Base URL     : {args.openai_base_url}")
    else:
        print(f"• Provedor     : OLLAMA (Modelo: {args.model})")
    print(f"• Concorrência : {args.workers} thread(s)")
    print(f"• OCR com LLM  : {ocr_desc}")
    print(f"• Execução     : {mode_desc}")
    print("=" * 70)

    try:
        conf_start = input("Deseja iniciar a classificação agora? (S/n) [S]: ").strip().lower()
        if conf_start in ["n", "nao", "não", "no"]:
            print("\n[Operação cancelada pelo usuário]")
            sys.exit(0)
    except (EOFError, KeyboardInterrupt):
        print("\n[Operação cancelada pelo usuário]")
        sys.exit(0)

    # Salva opções configuradas pelo usuário para persistência
    save_classifier_config({
        "input": str(args.input),
        "output_dir": str(args.output_dir),
        "provider": args.provider,
        "model": args.model,
        "docker": args.docker,
        "ollama_url": args.ollama_url,
        "openai_key": args.openai_key,
        "openai_base_url": args.openai_base_url,
        "workers": args.workers,
        "max_pages": args.max_pages,
        "skip_ocr": args.skip_ocr,
        "no_individual": args.no_individual
    })

    print("\n" + "=" * 70 + "\n")
    return args

# ---------------------------------------------------------------------------
# Pipeline de Processamento em Lote (Compartilhado entre CLI e Web)
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Execução Principal (CLI)
# ---------------------------------------------------------------------------
def main():
    # Subcomando 'server' ou 'web' para iniciar a interface gráfica
    if len(sys.argv) > 1 and sys.argv[1].lower() in ["server", "web", "servidor"]:
        server_args = sys.argv[2:]
        try:
            from joakindex.server import main as server_main
        except ImportError:
            try:
                from .server import main as server_main
            except ImportError:
                sys.path.insert(0, str(Path(__file__).resolve().parent))
                import joakindex_server
                server_main = joakindex_server.main
        sys.exit(server_main(server_args))

    parser = argparse.ArgumentParser(
        prog="joakindex",
        description="JoaKinDeX - Central de Indexação e Classificação Documental Multidomínio (Acadêmico, Civil e Financeiro)."
    )
    parser.add_argument(
        "-i", "--input",
        type=str,
        default="./pdf",
        help="Caminho do diretório de PDFs ou de um arquivo PDF específico (padrão: %(default)s)."
    )
    parser.add_argument(
        "-o", "--output-dir",
        type=str,
        default="./saida",
        help="Diretório onde os relatórios JSON e TXT serão salvos (padrão: %(default)s)."
    )
    parser.add_argument(
        "-p", "--provider",
        choices=["ollama", "openai"],
        default="ollama",
        help="Provedor de IA a utilizar: 'ollama' ou 'openai' (padrão: %(default)s)."
    )
    parser.add_argument(
        "-m", "--model",
        type=str,
        default=None,
        help="Nome do modelo. Padrão: 'gemma4:e4b' para Ollama ou 'gpt-4o-mini' para OpenAI."
    )
    parser.add_argument(
        "--docker",
        type=str,
        default=None,
        help="Nome do container Docker do Ollama (padrão: auto-detecta 'open-webui')."
    )
    parser.add_argument(
        "--ollama-url",
        type=str,
        default="http://localhost:11434",
        help="URL base da API do Ollama (padrão: http://localhost:11434)."
    )
    parser.add_argument(
        "-k", "--key", "--openai-key",
        dest="openai_key",
        type=str,
        default=None,
        help="Chave de API da OpenAI (se omitido, lê de OPENAI_API_KEY ou do arquivo .env)."
    )
    parser.add_argument(
        "--openai-base-url", "--base-url",
        dest="openai_base_url",
        type=str,
        default=None,
        help="URL base personalizada para OpenAI ou endpoints compatíveis (Groq, OpenRouter, vLLM)."
    )
    parser.add_argument(
        "-w", "--workers",
        type=int,
        default=1,
        help="Número de threads simultâneas para processamento (padrão: 1 para Ollama local)."
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=4,
        help="Máximo de páginas a ler por PDF (padrão: 4)."
    )
    parser.add_argument(
        "-f", "--force",
        action="store_true",
        help="Força o reprocessamento de todos os PDFs, ignorando os já processados com sucesso."
    )
    parser.add_argument(
        "--skip-ocr",
        action="store_true",
        help="Desativa tentativas de OCR via LLM para documentos escaneados ou não identificados."
    )
    parser.add_argument(
        "--reprocess-ocr",
        action="store_true",
        help="Força o reprocessamento de documentos que necessitam de OCR (erros de leitura e tipos não identificados)."
    )
    parser.add_argument(
        "--no-individual",
        action="store_true",
        help="Desativa a criação de arquivos JSON e TXT individuais por PDF (nomeados por MD5)."
    )
    parser.add_argument(
        "--prompt", "--interativo",
        dest="force_prompt",
        action="store_true",
        help="Abre o menu interativo no console para configurar as opções antes de iniciar."
    )
    parser.add_argument(
        "-y", "--no-prompt", "--batch",
        dest="no_prompt",
        action="store_true",
        help="Executa diretamente sem perguntas interativas no console."
    )
    parser.add_argument(
        "--reset-config", "--reset", "--factory-reset",
        dest="reset_config",
        action="store_true",
        help="Restaura todas as configurações salvas para os padrões de fábrica neutros."
    )
    parser.add_argument(
        "--uniformizar-instituicoes", "--normalizar-instituicoes",
        dest="uniformizar_instituicoes",
        action="store_true",
        help="Executa a uniformização e consolidação inteligente de nomes de instituições na base de dados sem reprocessar PDFs."
    )
    parser.add_argument(
        "--hibrido", "--hybrid",
        dest="hybrid",
        action="store_true",
        default=False,
        help="Ativa o modo cascata híbrido: tenta primeiro modelo local e faz fallback para OpenAI se inconclusivo (padrão: %(default)s)."
    )
    parser.add_argument(
        "--no-hibrido", "--no-hybrid",
        dest="hybrid",
        action="store_false",
        help="Desativa forçadamente o modo cascata híbrido."
    )
    parser.add_argument(
        "--hybrid-cloud-model",
        dest="hybrid_cloud_model",
        type=str,
        default="gpt-4o-mini",
        help="Modelo OpenAI para fallback no modo híbrido (padrão: %(default)s)."
    )

    # Carrega configurações salvas prévias como padrões do parser
    saved_cfg = get_classifier_config()
    parser.set_defaults(
        input=saved_cfg.get("input", "./pdf"),
        output_dir=saved_cfg.get("output_dir", "./saida"),
        provider=saved_cfg.get("provider", "ollama"),
        model=saved_cfg.get("model", None),
        docker=saved_cfg.get("docker", None),
        ollama_url=saved_cfg.get("ollama_url", "http://localhost:11434"),
        openai_key=saved_cfg.get("openai_key", None),
        openai_base_url=saved_cfg.get("openai_base_url", None),
        workers=saved_cfg.get("workers", 1),
        max_pages=saved_cfg.get("max_pages", 4),
        skip_ocr=saved_cfg.get("skip_ocr", False),
        no_individual=saved_cfg.get("no_individual", False),
        hybrid=saved_cfg.get("hybrid", False),
        hybrid_cloud_model=saved_cfg.get("hybrid_cloud_model", "gpt-4o-mini"),
    )

    args = parser.parse_args()

    if args.reset_config:
        reset_classifier_config()
        print("[✓] Configurações do classificador restauradas para os padrões de fábrica neutros com sucesso.")
        other_flags = [a for a in sys.argv[1:] if a not in ["--reset-config", "--reset", "--factory-reset"]]
        if not other_flags:
            sys.exit(0)
        defaults = get_factory_defaults()["classificador"]
        for k, v in defaults.items():
            setattr(args, k, v)

    if getattr(args, "uniformizar_instituicoes", False):
        print("\n" + "=" * 70)
        print("🎓 JoaKinDeX - UNIFORMIZAÇÃO INTELIGENTE DE INSTITUIÇÕES")
        print("   Criado por: Joaquim Ferreira Silva Neto <joaquimfsneto@gmail.com>")
        print("=" * 70)
        out_target = args.output_dir or "./saida"
        print(f"\n[✨] Processando arquivo e fichas em: {out_target}")
        res = uniformizar_base_dados(out_target, atualizar_individuais=not args.no_individual)
        if res.get("status") == "sucesso":
            print("[✓] Base de dados consolidada com sucesso!")
            print(f"    • Total de registros analisados : {res.get('total_registros')}")
            print(f"    • Documentos normalizados       : {res.get('total_modificados')}")
            print(f"    • Fichas individuais salvas     : {res.get('individuais_atualizados')}")
            print(f"    • Instituições únicas (antes)   : {res.get('instituicoes_antes')}")
            print(f"    • Instituições canônicas (após) : {res.get('instituicoes_depois')}")
            print(f"    • Variações unificadas          : {res.get('reducao_fragmentacao')}")
            if res.get("amostra_normalizacoes"):
                print("\n[Exemplos de unificações aplicadas]:")
                for orig, norm in list(res.get("amostra_normalizacoes").items())[:8]:
                    print(f"  • '{orig}' ➔ '{norm}'")
        else:
            print(f"[x] Erro: {res.get('mensagem')}")
            sys.exit(1)
        sys.exit(0)

    # Detecta se foram passados argumentos explícitos via CLI
    explicit_cli_args = [
        arg for arg in sys.argv[1:]
        if arg not in ["--prompt", "--interativo", "-y", "--no-prompt", "--batch", "--reset-config", "--reset", "--factory-reset", "--uniformizar-instituicoes", "--normalizar-instituicoes"]
    ]
    is_tty = sys.stdin.isatty()
    should_prompt = args.force_prompt or (
        is_tty
        and not args.no_prompt
        and len(explicit_cli_args) == 0
    )

    if should_prompt:
        args = prompt_interactive_menu(args)
    else:
        print("\n" + "=" * 70)
        print("🎓 JoaKinDeX - CLASSIFICAÇÃO DE DOCUMENTOS EM MASSA")
        print("   Criado por: Joaquim Ferreira Silva Neto <joaquimfsneto@gmail.com>")
        print("=" * 70)
        args.input = resolve_dir_path(args.input, default="./pdf") if (args.input and not (Path(clean_path_string(args.input)).is_file() and Path(clean_path_string(args.input)).suffix.lower() == ".pdf")) else (str(Path(clean_path_string(args.input)).expanduser().resolve()) if args.input else "./pdf")
        args.output_dir = resolve_classifier_output_dir(args.output_dir)
        # Salva opções configuradas via CLI para persistência
        save_classifier_config({
            "input": str(args.input),
            "output_dir": str(args.output_dir),
            "provider": args.provider,
            "model": args.model,
            "docker": args.docker,
            "ollama_url": args.ollama_url,
            "openai_key": args.openai_key,
            "openai_base_url": args.openai_base_url,
            "workers": args.workers,
            "max_pages": args.max_pages,
            "skip_ocr": args.skip_ocr,
            "no_individual": args.no_individual,
            "hybrid": getattr(args, "hybrid", False),
            "hybrid_cloud_model": getattr(args, "hybrid_cloud_model", "gpt-4o-mini")
        })

    try:
        summary = run_batch_classification(
            input_path=args.input,
            output_dir=args.output_dir,
            provider=args.provider,
            model=args.model,
            ollama_url=args.ollama_url,
            docker=args.docker,
            openai_key=args.openai_key,
            openai_base_url=args.openai_base_url,
            workers=args.workers,
            max_pages=args.max_pages,
            skip_ocr=args.skip_ocr,
            reprocess_ocr=args.reprocess_ocr,
            force=args.force,
            no_individual=args.no_individual,
            use_tqdm=True,
            hybrid=getattr(args, "hybrid", False),
            hybrid_cloud_model=getattr(args, "hybrid_cloud_model", "gpt-4o-mini")
        )
        if summary.get("status") == "erro":
            sys.exit(1)
        elif summary.get("status") == "interrompido":
            sys.exit(130)
    except KeyboardInterrupt:
        print("\n\n[!] Execução encerrada pelo usuário.")
        sys.exit(130)


if __name__ == "__main__":
    main()
