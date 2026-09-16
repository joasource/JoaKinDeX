#!/usr/bin/env python3
"""
JoaKinDeX - Extração de Texto/Imagem e OCR Local de Documentos
Criado por: Joaquim Ferreira Silva Neto <joaquimfsneto@gmail.com>

Leitores especializados de texto e imagem para PDF, Office (.docx/.doc/.odt/.rtf),
.txt e imagens nativas (PNG/JPG/JPEG/WEBP), incluindo conversão via LibreOffice
Headless, renderização de páginas de PDF para visão multimodal e OCR local de
contingência via Tesseract.
"""

__project__ = "JoaKinDeX"
__author__ = "Joaquim Ferreira Silva Neto"
__email__ = "joaquimfsneto@gmail.com"
__version__ = "1.0.0"

import os
import re
import base64
import io
import subprocess
import shutil
import tempfile
import zipfile
import hashlib
import threading
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, List, Optional, Union

try:
    import pypdf
except ImportError:
    pypdf = None

try:
    import pdfplumber
except ImportError:
    pdfplumber = None

try:
    import pypdfium2 as pdfium
except ImportError:
    pdfium = None

try:
    from PIL import Image, ImageEnhance
except ImportError:
    Image = None
    ImageEnhance = None

try:
    from joakindex.extractors_sinais import classify_text_signatures
except ImportError:
    from .extractors_sinais import classify_text_signatures

_OFFICE_CONVERT_LOCK = threading.Lock()
_PDFIUM_LOCK = threading.RLock()


def load_image_to_base64(
    image_path: Union[str, Path],
    max_dimension: int = 2048,
    quality: int = 85
) -> List[str]:
    """
    Carrega arquivo de imagem nativo (PNG, JPG, JPEG, WEBP) e converte para base64 JPEG
    otimizado para leitura visual (OCR) multimodal via LLM.
    """
    try:
        from PIL import Image
        with Image.open(str(image_path)) as img:
            if img.mode in ("RGBA", "LA", "P"):
                rgb_img = Image.new("RGB", img.size, (255, 255, 255))
                if img.mode == "RGBA":
                    rgb_img.paste(img, mask=img.split()[3])
                else:
                    rgb_img.paste(img.convert("RGB"))
                img = rgb_img
            elif img.mode != "RGB":
                img = img.convert("RGB")

            w, h = img.size
            if max(w, h) > max_dimension:
                scale_ratio = max_dimension / float(max(w, h))
                new_w = int(w * scale_ratio)
                new_h = int(h * scale_ratio)
                resample_filter = getattr(Image, "Resampling", Image).LANCZOS
                img = img.resize((new_w, new_h), resample_filter)

            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=quality, optimize=True)
            return [base64.b64encode(buf.getvalue()).decode("utf-8")]
    except Exception as e:
        print(f"[Aviso] Falha ao converter imagem {image_path} para base64: {e}")
        return []


# ---------------------------------------------------------------------------
# Conversão e Extração de Documentos Word e Suíte Office (.docx, .doc, .odt, .rtf, .txt)
# ---------------------------------------------------------------------------
def convert_office_to_pdf(
    office_path: Union[str, Path],
    cache_dir: Optional[Union[str, Path]] = None,
    timeout: int = 45
) -> Optional[Path]:
    """
    Converte documento do Microsoft Word ou OpenOffice (.docx, .doc, .odt, .rtf) para PDF
    utilizando LibreOffice Headless com cache persistente baseado no hash MD5.
    Garante fidelidade 100% de layout, tabelas e tipografia sem conflitos com LibreOffice desktop.
    """
    p = Path(office_path).resolve()
    if not p.exists() or not p.is_file():
        return None

    ext = p.suffix.lower()
    if ext == ".pdf":
        return p

    # Determina pasta de cache
    if cache_dir:
        c_dir = Path(cache_dir).resolve()
    else:
        env_cache = os.environ.get("JOAKINDEX_PDF_CACHE")
        if env_cache:
            c_dir = Path(env_cache).resolve()
        else:
            c_dir = p.parent / ".cache_pdf"

    try:
        c_dir.mkdir(parents=True, exist_ok=True)
    except Exception:
        c_dir = Path(tempfile.gettempdir()) / "joakindex_pdf_cache"
        c_dir.mkdir(parents=True, exist_ok=True)

    # Nome do arquivo de cache pelo MD5 do conteúdo do arquivo
    try:
        md5_val = hashlib.md5(p.read_bytes()).hexdigest()
    except Exception:
        md5_val = hashlib.md5(p.name.encode("utf-8")).hexdigest()

    target_pdf = c_dir / f"{md5_val}.pdf"

    # Se já existir e for válido, reaproveita instantaneamente
    if target_pdf.exists() and target_pdf.stat().st_size > 500:
        return target_pdf

    # Detecta executável do LibreOffice
    lo_bin = shutil.which("libreoffice") or shutil.which("soffice")
    if not lo_bin:
        print(f"[Aviso Office] LibreOffice não encontrado no sistema para converter {p.name}")
        return None

    with _OFFICE_CONVERT_LOCK:
        # Re-checa após adquirir o lock (evita trabalho redundante)
        if target_pdf.exists() and target_pdf.stat().st_size > 500:
            return target_pdf

        try:
            # Perfil isolado para nunca travar com LibreOffice do usuário
            user_inst = f"file://{tempfile.gettempdir()}/libreoffice_headless_joakindex"
            cmd = [
                lo_bin,
                f"-env:UserInstallation={user_inst}",
                "--headless",
                "--convert-to", "pdf",
                "--outdir", str(c_dir),
                str(p)
            ]
            subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)

            # O LibreOffice gera o PDF com o mesmo stem do arquivo de origem na pasta outdir
            lo_output = c_dir / f"{p.stem}.pdf"
            if lo_output.exists() and lo_output.stat().st_size > 500:
                if lo_output != target_pdf:
                    shutil.copy2(lo_output, target_pdf)
                return target_pdf
        except Exception as e:
            print(f"[Aviso Office] Falha ao converter {p.name} para PDF via LibreOffice: {e}")

    return None


def extract_docx_text(docx_path: Union[str, Path]) -> str:
    """
    Extrai texto estruturado de arquivo .docx diretamente do XML interno (word/document.xml)
    em Python puro com zero dependências externas.
    """
    p = Path(docx_path)
    if not p.exists() or not p.is_file():
        return ""
    try:
        with zipfile.ZipFile(p, "r") as zf:
            if "word/document.xml" not in zf.namelist():
                return ""
            xml_content = zf.read("word/document.xml")
            tree = ET.fromstring(xml_content)
            paragraphs = []
            for p_node in tree.iter():
                if p_node.tag.endswith("}p"):
                    texts = [node.text for node in p_node.iter() if node.tag.endswith("}t") and node.text]
                    if texts:
                        paragraphs.append("".join(texts).strip())

            # Coleta também cabeçalhos e rodapés se existirem
            for name in zf.namelist():
                if (name.startswith("word/header") or name.startswith("word/footer")) and name.endswith(".xml"):
                    try:
                        h_tree = ET.fromstring(zf.read(name))
                        for p_node in h_tree.iter():
                            if p_node.tag.endswith("}p"):
                                texts = [node.text for node in p_node.iter() if node.tag.endswith("}t") and node.text]
                                if texts:
                                    paragraphs.append("".join(texts).strip())
                    except Exception:
                        pass

            return "\n\n".join(paragraphs).strip()
    except Exception as e:
        print(f"[Aviso DOCX] Falha ao ler XML de {p.name}: {e}")
        return ""


def extract_odt_text(odt_path: Union[str, Path]) -> str:
    """Extrai texto estruturado de arquivo .odt diretamente do content.xml interno."""
    p = Path(odt_path)
    if not p.exists() or not p.is_file():
        return ""
    try:
        with zipfile.ZipFile(p, "r") as zf:
            if "content.xml" not in zf.namelist():
                return ""
            xml_content = zf.read("content.xml")
            tree = ET.fromstring(xml_content)
            paragraphs = []
            for node in tree.iter():
                if node.tag.endswith("}p") or node.tag.endswith("}h"):
                    t = "".join(node.itertext()).strip()
                    if t:
                        paragraphs.append(t)
            return "\n\n".join(paragraphs).strip()
    except Exception as e:
        print(f"[Aviso ODT] Falha ao ler content.xml de {p.name}: {e}")
        return ""


def extract_txt_text(txt_path: Union[str, Path]) -> str:
    """Extrai texto de arquivo .txt com detecção inteligente de encodings (UTF-8, CP1252, Latin-1)."""
    p = Path(txt_path)
    if not p.exists() or not p.is_file():
        return ""
    for enc in ["utf-8-sig", "utf-8", "cp1252", "latin-1"]:
        try:
            return p.read_text(encoding=enc).strip()
        except Exception:
            continue
    return ""


def extract_document_text(file_path: Union[str, Path], max_pages: int = 4) -> str:
    """
    Roteia a extração de texto para o leitor especializado de acordo com a extensão do documento:
    PDF, DOCX, DOC, ODT, RTF ou TXT.
    """
    p = Path(file_path)
    ext = p.suffix.lower()

    if ext == ".pdf":
        return extract_pdf_text(str(p), max_pages=max_pages)

    if ext == ".docx":
        t = extract_docx_text(p)
        if len(t) >= 20:
            return t
        pdf_c = convert_office_to_pdf(p)
        if pdf_c and pdf_c.exists():
            return extract_pdf_text(str(pdf_c), max_pages=max_pages)
        return t

    if ext == ".odt":
        t = extract_odt_text(p)
        if len(t) >= 20:
            return t
        pdf_c = convert_office_to_pdf(p)
        if pdf_c and pdf_c.exists():
            return extract_pdf_text(str(pdf_c), max_pages=max_pages)
        return t

    if ext == ".txt":
        return extract_txt_text(p)

    if ext in [".doc", ".rtf"]:
        pdf_c = convert_office_to_pdf(p)
        if pdf_c and pdf_c.exists():
            return extract_pdf_text(str(pdf_c), max_pages=max_pages)
        return ""

    return ""


# ---------------------------------------------------------------------------
# Extração de texto de PDF
# ---------------------------------------------------------------------------
def extract_pdf_text(pdf_path: str, max_pages: int = 4) -> str:
    """
    Extrai texto do PDF usando pypdf com fallback para pdfplumber.
    Limita ao número máximo de páginas para otimizar velocidade e tokens.
    """
    extracted_text = ""

    # Tentativa 1: pypdf (mais rápido)
    if pypdf is not None:
        try:
            reader = pypdf.PdfReader(pdf_path)
            num_pages = min(len(reader.pages), max_pages)
            pages_text = []
            for i in range(num_pages):
                page_text = reader.pages[i].extract_text() or ""
                if page_text.strip():
                    pages_text.append(page_text.strip())
            extracted_text = "\n\n".join(pages_text)
        except Exception:
            extracted_text = ""

    # Tentativa 2: pdfplumber se pypdf falhar ou extrair pouco texto
    if len(extracted_text.strip()) < 40 and pdfplumber is not None:
        try:
            with pdfplumber.open(pdf_path) as pdf:
                num_pages = min(len(pdf.pages), max_pages)
                pages_text = []
                for i in range(num_pages):
                    page_text = pdf.pages[i].extract_text() or ""
                    if page_text.strip():
                        pages_text.append(page_text.strip())
                extracted_text = "\n\n".join(pages_text)
        except Exception:
            pass

    return extracted_text.strip()


def render_pdf_pages_to_base64(
    pdf_path: str,
    max_pages: int = 4,
    scale: float = 1.6,
    quality: int = 85
) -> List[str]:
    """
    Renderiza páginas do PDF em imagens JPEG codificadas em base64 para leitura visual (OCR) via LLM.
    Utiliza pypdfium2 com fallback para pdfplumber.
    """
    images_b64: List[str] = []

    # Tentativa 1: pypdfium2 (rápido e alta fidelidade com lock thread-safe)
    if pdfium is not None:
        with _PDFIUM_LOCK:
            pdf = None
            try:
                pdf = pdfium.PdfDocument(str(pdf_path))
                num_pages = min(len(pdf), max_pages)
                for i in range(num_pages):
                    page = pdf.get_page(i)
                    try:
                        bitmap = page.render(scale=scale)
                        try:
                            img = bitmap.to_pil()
                            buf = io.BytesIO()
                            img.save(buf, format="JPEG", quality=quality)
                            images_b64.append(base64.b64encode(buf.getvalue()).decode("utf-8"))
                        finally:
                            bitmap.close()
                    finally:
                        page.close()
                if images_b64:
                    return images_b64
            except Exception:
                images_b64 = []
            finally:
                if pdf is not None:
                    try:
                        pdf.close()
                    except Exception:
                        pass

    # Tentativa 2: pdfplumber (fallback)
    if pdfplumber is not None:
        try:
            with pdfplumber.open(str(pdf_path)) as pdf:
                num_pages = min(len(pdf.pages), max_pages)
                for i in range(num_pages):
                    page = pdf.pages[i]
                    pimg = page.to_image(resolution=int(72 * scale))
                    buf = io.BytesIO()
                    pimg.original.save(buf, format="JPEG", quality=quality)
                    images_b64.append(base64.b64encode(buf.getvalue()).decode("utf-8"))
        except Exception:
            pass

    return images_b64


# ---------------------------------------------------------------------------
# OCR Local Rápido de Contingência (Tesseract)
# ---------------------------------------------------------------------------
def run_tesseract_ocr_on_image(img: Any, try_rotation: bool = True) -> str:
    """
    Executa OCR local rápido via Tesseract em uma imagem PIL ou array.
    Testa automaticamente rotação em 180° se a primeira passada não encontrar CPF ou texto suficiente.
    """
    if not shutil.which("tesseract"):
        return ""

    if Image is not None and not isinstance(img, Image.Image):
        try:
            img = Image.fromarray(img)
        except Exception:
            return ""

    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        tmp_path = f.name
        img.save(tmp_path)

    def _exec_tess(p: str, extra_args: Optional[List[str]] = None) -> str:
        for lang in ["por+eng", "eng"]:
            try:
                cmd = ["tesseract", p, "stdout", "-l", lang]
                if extra_args:
                    cmd.extend(extra_args)
                proc = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=12
                )
                if proc.returncode == 0 and proc.stdout.strip():
                    return proc.stdout.strip()
            except Exception:
                pass
        return ""

    text = _exec_tess(tmp_path)

    # Se o texto for curto ou vazio (típico de notas promissórias em papel moeda/fundo padronizado ou recibos com baixo contraste)
    if len(text.strip()) < 80 and ImageEnhance is not None:
        try:
            enh_img = ImageEnhance.Contrast(img.convert("L")).enhance(2.5)
            enh_img.save(tmp_path)
            for psm in ["6", "3"]:
                t_enh = _exec_tess(tmp_path, ["--psm", psm])
                if len(t_enh.strip()) > len(text.strip()):
                    text = t_enh
                    if len(text.strip()) >= 80:
                        break
        except Exception:
            pass

    # Se não encontrou CPF ou assinatura conhecida, tenta rotação de 180 graus (documentos de cabeça para baixo)
    if try_rotation:
        has_cpf = bool(re.search(r"\d{3}\.?\d{3}\.?\d{3}-?\d{2}", text))
        has_sig = bool(classify_text_signatures(text)[0])
        # Só testa rotação 180° se não houver CPF E (não houver assinatura conhecida OU o texto for muito curto)
        if not has_cpf and (not has_sig or len(text) < 60):
            try:
                img_180 = img.rotate(180, expand=True)
                img_180.save(tmp_path)
                text_180 = _exec_tess(tmp_path)
                has_cpf_180 = bool(re.search(r"\d{3}\.?\d{3}\.?\d{3}-?\d{2}", text_180))
                has_sig_180 = bool(classify_text_signatures(text_180)[0])
                if has_cpf_180 or (not has_sig and has_sig_180):
                    text = text_180
            except Exception:
                pass
        elif not has_cpf:
            # Já tem assinatura de documento (ex: certidão), mas se 180° encontrar um CPF válido, pode ser anexo invertido
            try:
                img_180 = img.rotate(180, expand=True)
                img_180.save(tmp_path)
                text_180 = _exec_tess(tmp_path)
                if re.search(r"\d{3}\.?\d{3}\.?\d{3}-?\d{2}", text_180):
                    text = text_180
            except Exception:
                pass

    if os.path.exists(tmp_path):
        try:
            os.remove(tmp_path)
        except Exception:
            pass

    return text.strip()


def extract_tesseract_text_from_pdf(
    pdf_path: Union[str, Path],
    max_pages: int = 4
) -> str:
    """
    Extrai texto complementar via Tesseract local das imagens embutidas e das páginas do PDF.
    Captura CPFs, RGs e dados pessoais em alta resolução (ex: recortes do app CDT/SENATRAN).
    """
    if not shutil.which("tesseract"):
        return ""

    extracted_parts: List[str] = []

    # 1. Analisa imagens embutidas em alta resolução (fotos de CNH, RG, CPF inseridas no PDF)
    if pdfium is not None:
        with _PDFIUM_LOCK:
            pdf = None
            try:
                pdf = pdfium.PdfDocument(str(pdf_path))
                num_pages = min(len(pdf), max_pages)
                for i in range(num_pages):
                    page = pdf.get_page(i)
                    try:
                        for obj in page.get_objects():
                            if obj.type == pdfium.raw.FPDF_PAGEOBJ_IMAGE:
                                bm = None
                                try:
                                    bm = obj.get_bitmap()
                                    pil_img = bm.to_pil()
                                    if pil_img.width >= 200 and pil_img.height >= 200:
                                        t = run_tesseract_ocr_on_image(pil_img, try_rotation=True)
                                        if t and len(t) >= 15:
                                            extracted_parts.append(t)
                                finally:
                                    if bm is not None:
                                        bm.close()
                    finally:
                        page.close()
            except Exception:
                pass
            finally:
                if pdf is not None:
                    try:
                        pdf.close()
                    except Exception:
                        pass

    # 2. Se nenhuma imagem embutida foi encontrada ou se ainda não achou CPF, renderiza as páginas
    combined = "\n\n".join(extracted_parts)
    if not re.search(r"\d{3}\.?\d{3}\.?\d{3}-?\d{2}", combined):
        if pdfium is not None:
            with _PDFIUM_LOCK:
                pdf = None
                try:
                    pdf = pdfium.PdfDocument(str(pdf_path))
                    num_pages = min(len(pdf), max_pages)
                    for i in range(num_pages):
                        page = pdf.get_page(i)
                        try:
                            bitmap = page.render(scale=2.0)
                            try:
                                p_img = bitmap.to_pil()
                                t = run_tesseract_ocr_on_image(p_img, try_rotation=True)
                                if t and len(t) >= 15:
                                    extracted_parts.append(t)
                            finally:
                                bitmap.close()
                        finally:
                            page.close()
                except Exception:
                    pass
                finally:
                    if pdf is not None:
                        try:
                            pdf.close()
                        except Exception:
                            pass

    return "\n\n".join(extracted_parts).strip()
