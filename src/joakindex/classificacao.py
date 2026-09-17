"""
JoaKinDeX - Núcleo orquestrador de classificação: processamento de um único
documento, dossiê multi-página, geração de relatórios e lote (CLI e Web).
"""

import os
import json
import re
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union, Callable, Set
from concurrent.futures import ThreadPoolExecutor, as_completed

try:
    from tqdm import tqdm
except ImportError:
    tqdm = None

try:
    import pypdfium2 as pdfium
except ImportError:
    pdfium = None

try:
    from PIL import Image
except ImportError:
    Image = None

try:
    from joakindex.db import (
        get_db_path,
        get_json_path,
        init_database,
        upsert_document,
        upsert_documents_batch,
        get_all_documents,
        consultar_regra_para_texto,
        resolve_default_db_path
    )
except ImportError:
    from .db import (
        get_db_path,
        get_json_path,
        init_database,
        upsert_document,
        upsert_documents_batch,
        get_all_documents,
        consultar_regra_para_texto,
        resolve_default_db_path
    )

try:
    from joakindex.llm_clients import (
        BaseLLMClient,
        OllamaClient,
        OpenAIClient
    )
except ImportError:
    from .llm_clients import (
        BaseLLMClient,
        OllamaClient,
        OpenAIClient
    )

try:
    from joakindex.config import (
        clean_path_string,
        resolve_classifier_output_dir
    )
except ImportError:
    from .config import (
        clean_path_string,
        resolve_classifier_output_dir
    )

try:
    from joakindex.normalizer import normalizar_instituicao
except ImportError:
    from .normalizer import normalizar_instituicao

try:
    from joakindex.extractors_texto import (
        format_cpf,
        is_valid_cpf_syntax,
        extract_cpf_fallback,
        extract_rg_fallback,
        format_cnpj,
        is_valid_cnpj_syntax,
        extract_cnpj_fallback,
        extract_cnpj_cadastral_fallback,
        extract_course_fallback,
        extract_monetary_value,
        extract_pix_e2e_id,
        extract_pix_chave,
        extract_pix_authentication,
        sanitize_llm_transcription,
        extract_names_from_document_text,
    )
except ImportError:
    from .extractors_texto import (
        format_cpf,
        is_valid_cpf_syntax,
        extract_cpf_fallback,
        extract_rg_fallback,
        format_cnpj,
        is_valid_cnpj_syntax,
        extract_cnpj_fallback,
        extract_cnpj_cadastral_fallback,
        extract_course_fallback,
        extract_monetary_value,
        extract_pix_e2e_id,
        extract_pix_chave,
        extract_pix_authentication,
        sanitize_llm_transcription,
        extract_names_from_document_text,
    )

try:
    from joakindex.extractors_documento import (
        load_image_to_base64,
        convert_office_to_pdf,
        extract_document_text,
        render_pdf_pages_to_base64,
        run_tesseract_ocr_on_image,
        extract_tesseract_text_from_pdf,
        _PDFIUM_LOCK,
    )
except ImportError:
    from .extractors_documento import (
        load_image_to_base64,
        convert_office_to_pdf,
        extract_document_text,
        render_pdf_pages_to_base64,
        run_tesseract_ocr_on_image,
        extract_tesseract_text_from_pdf,
        _PDFIUM_LOCK,
    )

try:
    from joakindex.extractors_sinais import (
        extract_boleto_signals,
        extract_cheque_signals,
        extract_irpf_signals,
        extract_informe_rendimentos_signals,
        extract_veicular_signals,
        extract_contrato_compra_venda_signals,
        extract_nota_promissoria_signals,
        extract_recibo_signals,
        classify_text_signatures,
    )
except ImportError:
    from .extractors_sinais import (
        extract_boleto_signals,
        extract_cheque_signals,
        extract_irpf_signals,
        extract_informe_rendimentos_signals,
        extract_veicular_signals,
        extract_contrato_compra_venda_signals,
        extract_nota_promissoria_signals,
        extract_recibo_signals,
        classify_text_signatures,
    )

try:
    from joakindex.prompts_universais import (
        build_universal_vision_prompt,
        build_universal_prompt,
        should_trigger_hybrid_fallback,
    )
except ImportError:
    from .prompts_universais import (
        build_universal_vision_prompt,
        build_universal_prompt,
        should_trigger_hybrid_fallback,
    )

IMAGE_EXTENSIONS: Set[str] = {".png", ".jpg", ".jpeg", ".webp"}
WORD_EXTENSIONS: Set[str] = {".docx", ".doc", ".odt", ".rtf"}
TEXT_EXTENSIONS: Set[str] = {".txt"}
DOCUMENT_EXTENSIONS: Set[str] = {".pdf"} | WORD_EXTENSIONS | TEXT_EXTENSIONS
SUPPORTED_EXTENSIONS: Set[str] = DOCUMENT_EXTENSIONS | IMAGE_EXTENSIONS


def get_file_metadata(file_path: Path) -> Dict[str, Any]:
    """
    Calcula o hash MD5, data da última alteração e metadados Dublin Core/Autor do arquivo.
    """
    # Import tardio (não no topo do módulo): extract_file_dublin_core/extract_file_author
    # ficam em cli.py, e cli.py reexporta get_file_metadata daqui — um import no topo
    # do módulo criaria um ciclo cli -> classificacao -> cli no carregamento.
    try:
        from joakindex.cli import extract_file_dublin_core, extract_file_author
    except ImportError:
        from .cli import extract_file_dublin_core, extract_file_author

    hasher = hashlib.md5()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    md5_hash = hasher.hexdigest()

    st = file_path.stat()
    dt_mod = datetime.fromtimestamp(st.st_mtime).strftime("%d/%m/%Y %H:%M:%S")
    dc_meta = extract_file_dublin_core(file_path)
    autor = dc_meta.get("creator") or extract_file_author(file_path)

    return {
        "md5": md5_hash,
        "data_modificacao": dt_mod,
        "autor": autor,
        "dublin_core": dc_meta,
        "dc_title": dc_meta.get("title"),
        "dc_subject": dc_meta.get("subject"),
        "dc_creator_tool": dc_meta.get("creator_tool")
    }


def analyze_pdf_dossier(
    pdf_path: Union[str, Path],
    max_ocr_pages: int = 25
) -> Dict[str, Any]:
    """
    Realiza a varredura completa de todas as páginas do PDF para identificar múltiplos documentos.
    Utiliza leitura digital em 100% das páginas e OCR Tesseract pontual em páginas de imagem.
    Aplica regras de hierarquia e anti-contaminação para consolidar dados do titular.
    """
    p = Path(pdf_path)
    if p.suffix.lower() in WORD_EXTENSIONS:
        cached_pdf = convert_office_to_pdf(p)
        if cached_pdf and cached_pdf.exists():
            p = cached_pdf

    result = {
        "paginas": [],
        "todos_tipos": [],
        "todos_dominios": [],
        "dossie_paginas": [],
        "cpf_titular": None,
        "rg_titular": None,
        "curso_titular": None,
        "faculdade_titular": None,
        "tipo_documento_principal": None,
        "dominio_principal": None,
        "numero_cheque": None,
        "numeros_cheque": [],
        "banco_cheque": None,
        "conta_corrente": None,
        "serie_cheque": None,
        "agencia_cheque": None,
        "numero_recibo": None,
        "exercicio_irpf": None,
        "ano_calendario": None,
        "fonte_pagadora": None,
        "cnpj_fonte_pagadora": None
    }

    if not p.exists() or pdfium is None:
        return result

    pages_info = []
    seen_tipos = []
    seen_dominios = []
    all_cheque_numbers = []
    banco_cheque = None
    conta_corrente = None
    serie_cheque = None
    agencia_cheque = None
    numero_recibo = None
    exercicio_irpf = None
    ano_calendario = None
    fonte_pagadora = None
    cnpj_fonte_pagadora = None

    with _PDFIUM_LOCK:
        pdf = None
        try:
            pdf = pdfium.PdfDocument(str(p))
            total_pages = len(pdf)
            last_tipo = None

            for i in range(total_pages):
                page = None
                p_text = ""
                embedded_texts = []
                ocr_rendered_text = ""
                page_num = i + 1

                try:
                    page = pdf.get_page(i)

                    # 1. Leitura de texto digital da página
                    try:
                        textpage = page.get_textpage()
                        try:
                            p_text = textpage.get_text_range().strip()
                        finally:
                            textpage.close()
                    except Exception:
                        p_text = ""

                    # 2. Se a página for escaneada / imagem pura sem texto digital, renderiza a página completa (respeita /Rotate e orientação)
                    if len(p_text) < 40 and i < max_ocr_pages:
                        try:
                            bitmap = page.render(scale=2.0)
                            try:
                                p_img = bitmap.to_pil()
                                ocr_rendered_text = run_tesseract_ocr_on_image(p_img, try_rotation=True)
                            finally:
                                bitmap.close()
                        except Exception:
                            pass
                    elif len(p_text) >= 40:
                        # Se já tem texto digital, mas pode conter recortes de imagem (ex: CDT/SENATRAN)
                        try:
                            for obj in page.get_objects():
                                if obj.type == pdfium.raw.FPDF_PAGEOBJ_IMAGE:
                                    bm = None
                                    try:
                                        bm = obj.get_bitmap()
                                        pil_img = bm.to_pil()
                                        if pil_img.width >= 200 and pil_img.height >= 200 and (pil_img.width < 1000 or pil_img.height < 1000):
                                            t = run_tesseract_ocr_on_image(pil_img, try_rotation=True)
                                            if t and len(t) >= 15:
                                                embedded_texts.append(t)
                                    finally:
                                        if bm is not None:
                                            bm.close()
                        except Exception:
                            pass
                finally:
                    if page is not None:
                        page.close()

                combined_page_text = "\n".join(
                    x for x in [p_text, "\n".join(embedded_texts), ocr_rendered_text] if x.strip()
                ).strip()

                if not combined_page_text:
                    continue

                is_chk_p, chk_num_p, chk_bco_p, chk_det_p = extract_cheque_signals(combined_page_text)
                is_irpf_p, irpf_tipo_p, irpf_meta_p = extract_irpf_signals(combined_page_text)
                is_inf_p, inf_tipo_p, inf_meta_p = extract_informe_rendimentos_signals(combined_page_text)
                is_veic_p, veic_tipo_p, veic_det_p = extract_veicular_signals(combined_page_text)
                is_cv_p, cv_tipo_p, cv_det_p = extract_contrato_compra_venda_signals(combined_page_text)
                is_np_p, np_tipo_p, np_det_p = extract_nota_promissoria_signals(combined_page_text)
                is_rec_p, rec_tipo_p, rec_det_p = extract_recibo_signals(combined_page_text)

                # 0. Prioridade Máxima: Regras Aprendidas pelo Usuário a partir de Páginas Conferidas
                regra_pg = None
                try:
                    regra_pg = consultar_regra_para_texto(resolve_default_db_path(), combined_page_text)
                    is_bol_p, _, _, _ = extract_boleto_signals(combined_page_text)
                    if regra_pg and is_bol_p and regra_pg.get("valor_atribuido") == "Recibo":
                        regra_pg = None
                except Exception:
                    pass

                if regra_pg and regra_pg.get("valor_atribuido"):
                    tipo = regra_pg["valor_atribuido"]
                    dom = regra_pg.get("dominio") or "academico"

                elif is_veic_p:
                    tipo = veic_tipo_p
                    dom = "juridico" if "citação" in (veic_tipo_p or "").lower() else "veicular"
                elif is_cv_p:
                    tipo = cv_tipo_p
                    dom = "juridico"
                elif is_np_p:
                    tipo = np_tipo_p
                    dom = "financeiro"
                elif is_rec_p:
                    tipo = rec_tipo_p
                    dom = "financeiro"
                elif is_chk_p:
                    tipo = "Talão de Cheques" if chk_det_p.get("is_talao") else "Folha de Cheque"
                    dom = "financeiro"
                elif is_inf_p:
                    tipo = inf_tipo_p
                    dom = "financeiro"
                elif is_irpf_p:
                    if last_tipo == "Recibo de Entrega da Declaração de Ajuste Anual":
                        tipo = "Recibo de Entrega da Declaração de Ajuste Anual"
                    else:
                        tipo = irpf_tipo_p
                    dom = "financeiro"
                else:
                    tipo, dom = classify_text_signatures(combined_page_text)


                # Continuidade de Contrato: se a página anterior era Contrato e a atual tem termos contratuais sem novo cabeçalho
                if not tipo or tipo == "Documento Diverso":
                    if last_tipo in ["Contrato de Compra e Venda", "Contrato Particular de Compra e Venda de Imóvel", "Contrato"] and \
                       any(k in combined_page_text.lower() for k in ["clausula", "cláusula", "foro", "testemunha", "cartorio", "cartório", "vendedor", "comprador", "instrumento", "eviccao", "evicção", "irrevogavel", "irrevogável"]):
                        tipo = last_tipo
                        dom = "juridico"

                if tipo and tipo != "Documento Diverso":
                    last_tipo = tipo

                if is_chk_p or (tipo and "cheque" in tipo.lower()):
                    for n in chk_det_p.get("numeros_cheque", ([chk_num_p] if chk_num_p else [])):
                        if n and n not in all_cheque_numbers:
                            all_cheque_numbers.append(n)
                    if chk_bco_p and not banco_cheque:
                        banco_cheque = chk_bco_p
                    if chk_det_p.get("conta_corrente") and not conta_corrente:
                        conta_corrente = chk_det_p["conta_corrente"]
                    if chk_det_p.get("serie_cheque") and not serie_cheque:
                        serie_cheque = chk_det_p["serie_cheque"]
                    if chk_det_p.get("agencia_cheque") and not agencia_cheque:
                        agencia_cheque = chk_det_p["agencia_cheque"]

                if is_irpf_p or irpf_meta_p:
                    if irpf_meta_p.get("numero_recibo") and not numero_recibo:
                        numero_recibo = irpf_meta_p["numero_recibo"]
                    if irpf_meta_p.get("exercicio") and not exercicio_irpf:
                        exercicio_irpf = irpf_meta_p["exercicio"]
                    if irpf_meta_p.get("ano_calendario") and not ano_calendario:
                        ano_calendario = irpf_meta_p["ano_calendario"]

                if is_inf_p or inf_meta_p:
                    if inf_meta_p.get("fonte_pagadora") and not fonte_pagadora:
                        fonte_pagadora = inf_meta_p["fonte_pagadora"]
                    if inf_meta_p.get("cnpj_fonte_pagadora") and not cnpj_fonte_pagadora:
                        cnpj_fonte_pagadora = inf_meta_p["cnpj_fonte_pagadora"]
                    if inf_meta_p.get("ano_calendario") and not ano_calendario:
                        ano_calendario = inf_meta_p["ano_calendario"]

                p_cpf = extract_cpf_fallback(combined_page_text)
                p_rg = extract_rg_fallback(combined_page_text)
                p_cnpj = extract_cnpj_fallback(combined_page_text)
                p_curso = extract_course_fallback(combined_page_text)

                p_entry = {
                    "pagina": page_num,
                    "dominio": dom or "outros",
                    "tipo": tipo or "Documento Diverso",
                    "cpf": p_cpf,
                    "rg": p_rg,
                    "cnpj": p_cnpj,
                    "curso": p_curso
                }
                pages_info.append(p_entry)

                if tipo and tipo not in seen_tipos:
                    seen_tipos.append(tipo)
                if dom and dom not in seen_dominios:
                    seen_dominios.append(dom)
        except Exception:
            return result
        finally:
            if pdf is not None:
                try:
                    pdf.close()
                except Exception:
                    pass


    # Consolidação de pacotes de IRPF: se houver páginas de Recibo de Entrega da Declaração de Ajuste Anual
    # e páginas de Declaração de Imposto de Renda contíguas, unifica como Recibo de Entrega da Declaração de Ajuste Anual
    has_recibo_irpf = any(p.get("tipo") == "Recibo de Entrega da Declaração de Ajuste Anual" for p in pages_info)
    if has_recibo_irpf:
        for p_info in pages_info:
            if p_info.get("tipo") == "Declaração de Imposto de Renda":
                p_info["tipo"] = "Recibo de Entrega da Declaração de Ajuste Anual"
        seen_tipos = [t for t in seen_tipos if t != "Declaração de Imposto de Renda"]
        if "Recibo de Entrega da Declaração de Ajuste Anual" not in seen_tipos:
            seen_tipos.insert(0, "Recibo de Entrega da Declaração de Ajuste Anual")

    # Hierarquia e Anti-Contaminação
    # CPF: Prioridade 1 = Identificação, 2 = Acadêmico, 3 = Financeiro
    cpf_titular = None
    for target_dom in ["identificacao", "academico", "financeiro", "outros"]:
        for p_info in pages_info:
            if p_info["dominio"] == target_dom and p_info.get("cpf"):
                cpf_titular = p_info["cpf"]
                break
        if cpf_titular:
            break

    # RG: Prioridade 1 = Identificação, 2 = Acadêmico
    rg_titular = None
    for target_dom in ["identificacao", "academico", "outros"]:
        for p_info in pages_info:
            if p_info["dominio"] == target_dom and p_info.get("rg"):
                rg_titular = p_info["rg"]
                break
        if rg_titular:
            break

    # CNPJ: Prioridade 1 = Profissional / Cadastral, 2 = Outros
    cnpj_titular = None
    for target_dom in ["profissional", "identificacao", "financeiro", "outros"]:
        for p_info in pages_info:
            if p_info["dominio"] == target_dom and p_info.get("cnpj"):
                cnpj_titular = p_info["cnpj"]
                break
        if cnpj_titular:
            break

    # Curso: Estritamente de páginas acadêmicas
    curso_titular = None
    for p_info in pages_info:
        if p_info["dominio"] == "academico" and p_info.get("curso"):
            curso_titular = p_info["curso"]
            break

    # Determinação do Tipo e Domínio Principal
    # Se houver Diploma ou documento acadêmico, o dossiê tem primazia acadêmica
    dominio_principal = "academico" if "academico" in seen_dominios else (seen_dominios[0] if seen_dominios else "academico")
    tipo_principal = None
    priority_order = [
        "Diploma", "Certificado", "Histórico Escolar", "Declaração", "Ementa", "Dissertação", "Livro/Publicação",
        "Cartão CNPJ / Situação Cadastral", "Comprovante de Inscrição e de Situação Cadastral", "Currículo", "Declaração de Experiência Profissional",
        "Dossiê Veicular",
        "Certificado de Registro de Veículo (CRV)", "Certificado de Registro e Licenciamento de Veículo (CRLV)",
        "Autorização para Transferência de Propriedade de Veículo (ATPV)",
        "Comunicação de Venda ao DETRAN", "Laudo de Vistoria Veicular", "Guia de Remoção de Veículo",
        "Nota de Arrematação (Leilão)", "Comprovante de Agendamento DETRAN",
        "CNH", "RG", "CPF", "Certidão de Nascimento", "Certidão de Casamento", "Passaporte",
        "Contrato de Compra e Venda", "Contrato Particular de Compra e Venda de Imóvel", "Contrato", "Procuração", "Termo de Posse",
        "Recibo de Entrega da Declaração de Ajuste Anual", "Declaração de Imposto de Renda", "Informe de Rendimentos Financeiros",
        "Talão de Cheques", "Folha de Cheque",
        "Comprovante PIX", "Comprovante de Pagamento", "Boleto", "Boleto Bancário", "Nota Promissória", "Recibo"
    ]

    cheque_pages = [p for p in pages_info if p.get("tipo") in ("Folha de Cheque", "Talão de Cheques")]
    veic_pages = [p for p in pages_info if p.get("dominio") == "veicular"]
    has_academic_prime = any(p["tipo"] in priority_order[:7] for p in pages_info)
    has_id_prime = any(p["tipo"] in ["CNH", "RG", "CPF", "Certidão de Nascimento", "Certidão de Casamento", "Passaporte"] for p in pages_info)

    if (len(cheque_pages) >= 2 or len(all_cheque_numbers) >= 2 or (len(cheque_pages) >= 1 and total_pages > 1 and len(cheque_pages) / max(1, len(pages_info)) >= 0.5)) and not has_academic_prime:
        tipo_principal = "Talão de Cheques"
        dominio_principal = "financeiro"
    elif len(cheque_pages) == 1 and not has_academic_prime and not has_id_prime:
        tipo_principal = "Folha de Cheque"
        dominio_principal = "financeiro"
    elif len(veic_pages) >= 2 and len(set(p.get("tipo") for p in veic_pages)) >= 2 and not has_academic_prime:
        tipo_principal = "Dossiê Veicular"
        dominio_principal = "veicular"
    elif len(veic_pages) >= 1 and not has_academic_prime and not has_id_prime:
        tipo_principal = veic_pages[0]["tipo"]
        dominio_principal = "veicular"
    else:
        for p_tipo in priority_order:
            if p_tipo in seen_tipos:
                tipo_principal = p_tipo
                break
        if not tipo_principal and seen_tipos:
            tipo_principal = seen_tipos[0]

        if tipo_principal:
            for p_info in pages_info:
                if p_info.get("tipo") == tipo_principal:
                    dominio_principal = p_info.get("dominio", dominio_principal)
                    break

    result["paginas"] = pages_info
    result["todos_tipos"] = seen_tipos
    result["todos_dominios"] = seen_dominios
    result["dossie_paginas"] = [{"pagina": p["pagina"], "tipo": p["tipo"], "dominio": p["dominio"]} for p in pages_info]
    result["cpf_titular"] = cpf_titular
    result["rg_titular"] = rg_titular
    result["cnpj_titular"] = cnpj_titular
    result["curso_titular"] = curso_titular
    result["tipo_documento_principal"] = tipo_principal
    result["dominio_principal"] = dominio_principal
    result["numero_cheque"] = all_cheque_numbers[0] if all_cheque_numbers else None
    result["numeros_cheque"] = all_cheque_numbers
    result["banco_cheque"] = banco_cheque
    result["conta_corrente"] = conta_corrente
    result["serie_cheque"] = serie_cheque
    result["agencia_cheque"] = agencia_cheque
    result["numero_recibo"] = numero_recibo
    result["exercicio_irpf"] = exercicio_irpf
    result["ano_calendario"] = ano_calendario
    result["fonte_pagadora"] = fonte_pagadora
    result["cnpj_fonte_pagadora"] = cnpj_fonte_pagadora

    return result


try:
    from joakindex.prompts_universais import (
        build_universal_vision_prompt,
        build_universal_prompt,
        should_trigger_hybrid_fallback,
    )
except ImportError:
    from .prompts_universais import (
        build_universal_vision_prompt,
        build_universal_prompt,
        should_trigger_hybrid_fallback,
    )


# ---------------------------------------------------------------------------
# Processamento Universal de Documentos (PDF e Imagens PNG/JPG/JPEG/WEBP)
# ---------------------------------------------------------------------------
def process_single_pdf(
    pdf_path: Path,
    client: BaseLLMClient,
    max_pages: int = 4,
    force_ocr: bool = False,
    skip_ocr: bool = False,
    metadata: Optional[Dict[str, str]] = None,
    hybrid: bool = False,
    hybrid_cloud_client: Optional[BaseLLMClient] = None
) -> Dict[str, Any]:
    pdf_path = Path(pdf_path)
    # Metadados do arquivo (MD5, data da última alteração, extensão)
    meta = metadata or get_file_metadata(pdf_path)
    ext = meta.get("extensao") or pdf_path.suffix.lower()
    is_image = ext in IMAGE_EXTENSIONS

    res_dict = {
        "md5": meta["md5"],
        "nome_arquivo": pdf_path.name,
        "caminho_relativo": meta.get("caminho_relativo") or pdf_path.name,
        "extensao": ext,
        "dominio": "academico",
        "data_modificacao": meta.get("data_modificacao"),
        "autor": meta.get("autor"),
        "dublin_core": meta.get("dublin_core"),
        "dc_title": meta.get("dc_title"),
        "dc_subject": meta.get("dc_subject"),
        "dc_creator_tool": meta.get("dc_creator_tool"),
        "data": None,
        "beneficiario": None,
        "cpf": None,
        "rg": None,
        "cnpj": None,
        "curso": None,
        "natureza_curso": None,
        "carga_horaria": None,
        "faculdade": None,
        "tipo_documento": None,
        "valor_monetario": None,
        "todos_dominios": [],
        "todos_tipos": [],
        "dossie_paginas": [],
        "status": "pendente",
        "erro": None,
        "metodo_leitura": "imagem_ocr_llm" if is_image else "texto_digital",
        "tentativa_ocr_llm": is_image,
        "processado_em": datetime.now().isoformat()
    }

    try:
        # Helper para sanitização de strings e listas
        def _clean_str(v):
            if isinstance(v, list):
                return ", ".join(str(x) for x in v if x).strip() or None
            if isinstance(v, str):
                return v.strip() or None
            return v

        text = ""
        has_text = False
        extracted_data = {}

        # ---------------------------------------------------------------------
        # RAMO A: ARQUIVO DE IMAGEM NATIVA (PNG, JPG, JPEG, WEBP)
        # ---------------------------------------------------------------------
        if is_image:
            if skip_ocr:
                res_dict["status"] = "erro"
                res_dict["erro"] = "Arquivo de imagem requer visão computacional (OCR), mas --skip-ocr está ativo."
                return res_dict

            images = load_image_to_base64(pdf_path)
            if not images:
                res_dict["status"] = "erro"
                res_dict["erro"] = f"Falha ao carregar e converter imagem '{pdf_path.name}' para processamento visual."
                return res_dict

            # OCR local preliminar rápido via Tesseract na imagem
            tess_text = ""
            if Image is not None:
                try:
                    pil_im = Image.open(pdf_path)
                    tess_text = run_tesseract_ocr_on_image(pil_im, try_rotation=True)
                except Exception:
                    pass

            try:
                vision_prompt = build_universal_vision_prompt(extra_context=tess_text if tess_text else "")
                extracted_data = client.generate_json_with_images(vision_prompt, images)
                res_dict["metodo_leitura"] = "imagem_ocr_llm"
                res_dict["tentativa_ocr_llm"] = True
            except Exception as e:
                if tess_text:
                    try:
                        prompt = build_universal_prompt(tess_text)
                        extracted_data = client.generate_json(prompt)
                        res_dict["metodo_leitura"] = "imagem_tesseract_llm"
                        res_dict["tentativa_ocr_llm"] = True
                    except Exception as e2:
                        res_dict["status"] = "erro"
                        res_dict["erro"] = f"Falha no processamento visual da imagem ({e}) e no OCR textual ({e2})"
                        res_dict["tentativa_ocr_llm"] = True
                        return res_dict
                else:
                    res_dict["status"] = "erro"
                    res_dict["erro"] = f"Falha no processamento visual da imagem via LLM: {e}"
                    res_dict["tentativa_ocr_llm"] = True
                    return res_dict

        # ---------------------------------------------------------------------
        # RAMO B: DOCUMENTOS (PDF, Word DOCX/DOC, ODT, RTF, TXT)
        # ---------------------------------------------------------------------
        else:
            is_word = ext in WORD_EXTENSIONS
            is_txt = ext in TEXT_EXTENSIONS
            text = extract_document_text(pdf_path, max_pages=max_pages)
            has_text = bool(text and len(text.strip()) >= 15)
            tess_text = ""

            if not has_text or force_ocr:
                if skip_ocr:
                    res_dict["status"] = "erro"
                    res_dict["erro"] = "Documento sem texto legível digitalmente (requer OCR, mas --skip-ocr está ativo)."
                    return res_dict

                # 1. OCR complementar rápido (Tesseract em imagens embutidas e páginas)
                # Para Word, converte para PDF espelho primeiro
                target_pdf_path = convert_office_to_pdf(pdf_path) if is_word else pdf_path

                if target_pdf_path and target_pdf_path.exists():
                    tess_text = extract_tesseract_text_from_pdf(target_pdf_path, max_pages=max_pages)
                    images = render_pdf_pages_to_base64(str(target_pdf_path), max_pages=min(max_pages, 4))
                else:
                    images = []

                combined_text = f"{text}\n\n{tess_text}".strip() if (text and tess_text) else (tess_text or text)

                if not images and not combined_text:
                    res_dict["status"] = "erro"
                    res_dict["erro"] = "Documento sem texto legível digitalmente e falha ao renderizar páginas para OCR."
                    return res_dict

                try:
                    extra_ctx = combined_text if combined_text else None
                    vision_prompt = build_universal_vision_prompt(extra_context=extra_ctx)
                    if images:
                        extracted_data = client.generate_json_with_images(vision_prompt, images)
                    else:
                        prompt = build_universal_prompt(combined_text)
                        extracted_data = client.generate_json(prompt)
                    res_dict["metodo_leitura"] = "ocr_llm" if not has_text else ("office_ocr_llm" if is_word else "hibrido_texto_e_ocr_llm")
                    res_dict["tentativa_ocr_llm"] = True
                except Exception as e:
                    if combined_text:
                        try:
                            print(f"[*] Chamada de visão falhou ({e}). Fazendo fallback para texto OCR Tesseract...")
                            prompt = build_universal_prompt(combined_text)
                            extracted_data = client.generate_json(prompt)
                            res_dict["metodo_leitura"] = "ocr_tesseract_llm"
                            res_dict["tentativa_ocr_llm"] = True
                        except Exception as e2:
                            res_dict["status"] = "erro"
                            res_dict["erro"] = f"Falha no OCR via LLM ({e}) e na leitura textual ({e2})"
                            res_dict["tentativa_ocr_llm"] = True
                            extracted_data = {}
                    else:
                        res_dict["status"] = "erro"
                        res_dict["erro"] = f"Falha no OCR via LLM: {e}"
                        res_dict["tentativa_ocr_llm"] = True
                        return res_dict
            else:
                # Leitura normal da camada de texto digital via LLM
                prompt = build_universal_prompt(text)
                try:
                    extracted_data = client.generate_json(prompt)
                except Exception as e_llm:
                    print(f"[*] Chamada LLM falhou ({e_llm}). Prosseguindo com extração por regras e heurísticas...")
                    extracted_data = {}
                res_dict["metodo_leitura"] = "texto_office" if is_word else ("texto_puro" if is_txt else "texto_digital")

        # Preenchimento e sanitização dos campos gerais
        res_dict["data"] = _clean_str(extracted_data.get("data"))
        res_dict["beneficiario"] = _clean_str(extracted_data.get("beneficiario"))
        dominio_raw = _clean_str(extracted_data.get("dominio"))
        tipo_doc_raw = _clean_str(extracted_data.get("tipo_documento"))
        valor_raw = _clean_str(extracted_data.get("valor_monetario"))
        tipo_lower = str(tipo_doc_raw or "").lower()

        is_academic_doc = any(k in tipo_lower for k in [
            "diploma", "certificado", "histórico", "historico", "declaração", "declaracao",
            "ementa", "dissertação", "dissertacao", "tese", "graduação", "graduacao",
            "pós-graduação", "pos-graduacao", "especialização", "especializacao"
        ]) or (dominio_raw == "academico")

        is_actual_cadastral_doc = any(k in tipo_lower for k in [
            "situação cadastral", "situacao cadastral", "cartão cnpj", "cartao cnpj", "cartão do cnpj", "cartao do cnpj",
            "cadastro nacional da pessoa"
        ]) or (dominio_raw == "profissional" and ("cnpj" in tipo_lower or "cadastral" in tipo_lower))

        # Tratamento e fallback para CPF
        cpf_val = extracted_data.get("cpf")
        formatted_cpf = format_cpf(cpf_val)
        if not formatted_cpf or not is_valid_cpf_syntax(formatted_cpf):
            if has_text:
                formatted_cpf = extract_cpf_fallback(text)
            if (not formatted_cpf or not is_valid_cpf_syntax(formatted_cpf)):
                if not tess_text and not is_image:
                    try:
                        tess_text = extract_tesseract_text_from_pdf(pdf_path, max_pages=max_pages)
                    except Exception:
                        pass
                if tess_text:
                    formatted_cpf = extract_cpf_fallback(tess_text)
        res_dict["cpf"] = formatted_cpf

        # Tratamento e fallback para RG / Identidade
        rg_val = _clean_str(extracted_data.get("rg"))
        if not rg_val:
            if has_text:
                rg_val = extract_rg_fallback(text)
            if not rg_val:
                if not tess_text and not is_image:
                    try:
                        tess_text = extract_tesseract_text_from_pdf(pdf_path, max_pages=max_pages)
                    except Exception:
                        pass
                if tess_text:
                    rg_val = extract_rg_fallback(tess_text)
        res_dict["rg"] = rg_val

        # Tratamento e fallback para CNPJ
        cnpj_val = extracted_data.get("cnpj") or (extracted_data.get("pix_pagador_cpf_cnpj") if (extracted_data.get("pix_pagador_cpf_cnpj") and "/" in str(extracted_data.get("pix_pagador_cpf_cnpj"))) else None)
        formatted_cnpj = format_cnpj(cnpj_val)
        if not formatted_cnpj or not is_valid_cnpj_syntax(formatted_cnpj):
            if has_text:
                formatted_cnpj = extract_cnpj_fallback(text)
            if not formatted_cnpj or not is_valid_cnpj_syntax(formatted_cnpj):
                if not tess_text and not is_image:
                    try:
                        tess_text = extract_tesseract_text_from_pdf(pdf_path, max_pages=max_pages)
                    except Exception:
                        pass
                if tess_text:
                    formatted_cnpj = extract_cnpj_fallback(tess_text)
        res_dict["cnpj"] = formatted_cnpj
        if formatted_cnpj and not res_dict.get("cpf") and is_actual_cadastral_doc:
            res_dict["cpf"] = formatted_cnpj

        # Extração de campos cadastrais (Cartão CNPJ / Receita Federal)
        cadastral_fallback = {}
        if has_text:
            cadastral_fallback = extract_cnpj_cadastral_fallback(text)
        elif tess_text:
            cadastral_fallback = extract_cnpj_cadastral_fallback(tess_text)

        cnpj_fields = {
            "razao_social": _clean_str(extracted_data.get("razao_social")) or cadastral_fallback.get("razao_social"),
            "nome_fantasia": _clean_str(extracted_data.get("nome_fantasia")) or cadastral_fallback.get("nome_fantasia"),
            "situacao_cadastral": _clean_str(extracted_data.get("situacao_cadastral")) or cadastral_fallback.get("situacao_cadastral"),
            "data_situacao": _clean_str(extracted_data.get("data_situacao")) or cadastral_fallback.get("data_situacao"),
            "data_abertura": _clean_str(extracted_data.get("data_abertura")) or cadastral_fallback.get("data_abertura"),
            "cnae_principal": _clean_str(extracted_data.get("cnae_principal")) or cadastral_fallback.get("cnae_principal"),
            "natureza_juridica": _clean_str(extracted_data.get("natureza_juridica")) or cadastral_fallback.get("natureza_juridica"),
            "endereco_completo": _clean_str(extracted_data.get("endereco_completo")) or cadastral_fallback.get("endereco_completo"),
            "telefone": _clean_str(extracted_data.get("telefone")) or cadastral_fallback.get("telefone"),
            "email": _clean_str(extracted_data.get("email")) or cadastral_fallback.get("email"),
        }

        # Se houver dados de CNPJ ou dados cadastrais/endereço, consolida em dados_extras
        if formatted_cnpj or any(cnpj_fields.values()):
            if "dados_extras" not in res_dict or not isinstance(res_dict["dados_extras"], dict):
                res_dict["dados_extras"] = {}
            if formatted_cnpj:
                res_dict["dados_extras"]["cnpj"] = formatted_cnpj
                if is_academic_doc:
                    res_dict["dados_extras"]["cnpj_instituicao"] = formatted_cnpj
            for k_field, v_field in cnpj_fields.items():
                if v_field:
                    res_dict["dados_extras"][k_field] = v_field
                    res_dict[k_field] = v_field

            # Preenchimento inteligente de beneficiário com razão social se vazio (apenas para documentos empresariais/cadastrais)
            if not res_dict.get("beneficiario") and not is_academic_doc:
                if cnpj_fields.get("razao_social"):
                    res_dict["beneficiario"] = cnpj_fields["razao_social"]
                elif cnpj_fields.get("nome_fantasia"):
                    res_dict["beneficiario"] = cnpj_fields["nome_fantasia"]

            # Emissor Receita Federal se não informado (estritamente se for documento cadastral da RFB)
            if not res_dict.get("faculdade") and is_actual_cadastral_doc:
                res_dict["faculdade"] = "Receita Federal do Brasil (RFB)"

            # Data da situação cadastral ou abertura se data vazia
            if not res_dict.get("data") and is_actual_cadastral_doc:
                if cnpj_fields.get("data_situacao"):
                    res_dict["data"] = cnpj_fields["data_situacao"]
                elif cnpj_fields.get("data_abertura"):
                    res_dict["data"] = cnpj_fields["data_abertura"]

        # Campos acadêmicos
        raw_curso = _clean_str(extracted_data.get("curso"))
        if not raw_curso or any(k in raw_curso.lower() for k in ["faculdade", "universidade", "instituto", "colegio", "escola"]):
            c_fallback = (extract_course_fallback(text) if has_text else None) or (extract_course_fallback(tess_text) if tess_text else None)
            if not c_fallback and not tess_text and not is_image:
                try:
                    tess_text = extract_tesseract_text_from_pdf(pdf_path, max_pages=max_pages)
                except Exception:
                    pass
                if tess_text:
                    c_fallback = extract_course_fallback(tess_text)
            if c_fallback:
                raw_curso = c_fallback
            elif any(k in str(raw_curso).lower() for k in ["faculdade", "universidade", "instituto", "colegio", "escola"]):
                raw_curso = None
        res_dict["curso"] = raw_curso
        res_dict["natureza_curso"] = _clean_str(extracted_data.get("natureza_curso"))
        res_dict["carga_horaria"] = _clean_str(extracted_data.get("carga_horaria"))
        res_dict["faculdade"] = normalizar_instituicao(_clean_str(extracted_data.get("faculdade")))

        # Classificação e campos financeiros / PIX
        dominio_raw = _clean_str(extracted_data.get("dominio"))
        tipo_doc_raw = _clean_str(extracted_data.get("tipo_documento"))
        valor_raw = _clean_str(extracted_data.get("valor_monetario"))

        pix_pagador_nome = _clean_str(extracted_data.get("pix_pagador_nome"))
        pix_pagador_cpf_cnpj = _clean_str(extracted_data.get("pix_pagador_cpf_cnpj"))
        pix_pagador_banco = _clean_str(extracted_data.get("pix_pagador_banco"))
        pix_recebedor_banco = _clean_str(extracted_data.get("pix_recebedor_banco"))
        pix_chave = _clean_str(extracted_data.get("pix_chave"))
        pix_e2e_id = _clean_str(extracted_data.get("pix_e2e_id"))
        pix_autenticacao = _clean_str(extracted_data.get("pix_autenticacao"))

        # Fallbacks regex para comprovantes quando houver texto disponível
        if has_text:
            if not valor_raw:
                valor_raw = extract_monetary_value(text)
            if not pix_e2e_id:
                pix_e2e_id = extract_pix_e2e_id(text)
            if not pix_chave:
                pix_chave = extract_pix_chave(text)
            if not pix_autenticacao:
                pix_autenticacao = extract_pix_authentication(text)

        # Validação Estrita Anti-Falso Positivo de PIX (Pilar 1)
        full_text_corpus = f"{text or ''} {tess_text or ''}".lower()
        has_explicit_pix_term = bool(re.search(r'\bpix\b', full_text_corpus) or re.search(r'\bpix\b', tipo_lower))

        # Valida se pix_e2e_id é realmente um identificador E2E BACEN (iniciado por E e alfanumérico longo)
        is_genuine_e2e = bool(pix_e2e_id and re.match(r'^E\d{8}[0-9A-Za-z]{15,35}$', pix_e2e_id))
        if not is_genuine_e2e and pix_e2e_id:
            # Se for CPF ou número de conta ou lote, descarta de pix_e2e_id
            if re.match(r'^\d{11}$', pix_e2e_id) or len(pix_e2e_id) < 20:
                pix_e2e_id = None

        # Valida se pix_chave é realmente uma chave PIX legítima (não confunde com conta bancária ou agência)
        if pix_chave:
            if re.search(r'-\w$', pix_chave) or (len(pix_chave) < 9 and "@" not in pix_chave and not pix_chave.startswith("+")):
                pix_chave = None

        is_legitimate_pix = bool(has_explicit_pix_term or is_genuine_e2e)

        # 0. Consulta dinâmica de Regras Aprendidas pelo Usuário
        regra_aprendida = None
        try:
            full_doc_raw = f"{text or ''}\n{tess_text or ''}".strip()
            regra_aprendida = consultar_regra_para_texto(resolve_default_db_path(), full_doc_raw)
        except Exception:
            pass

        # 0.1 Detecção Universal e Extração de Sinais de Boleto Bancário (FEBRABAN)
        boleto_corpus = f"{text or ''}\n{tess_text or ''}".strip()
        is_boleto, boleto_linha, boleto_barras, boleto_detalhes = extract_boleto_signals(boleto_corpus)

        # 0.2 Detecção Universal e Extração de Sinais de Cheque / Talão de Cheques
        cheque_corpus = f"{text or ''}\n{tess_text or ''}".strip()
        is_cheque, cheque_num, cheque_banco, cheque_detalhes = extract_cheque_signals(cheque_corpus)

        # 0.3 Detecção Universal e Extração de Sinais de IRPF e Informe de Rendimentos
        doc_corpus = f"{text or ''}\n{tess_text or ''}".strip()
        is_irpf, irpf_tipo, irpf_det = extract_irpf_signals(doc_corpus)
        is_informe, informe_tipo, informe_det = extract_informe_rendimentos_signals(doc_corpus)
        is_cv, cv_tipo, cv_det = extract_contrato_compra_venda_signals(doc_corpus)
        is_np, np_tipo, np_det = extract_nota_promissoria_signals(doc_corpus)
        is_rec, rec_tipo, rec_det = extract_recibo_signals(doc_corpus)

        # Se a LLM já extraiu linha_digitavel ou codigo_barras no JSON, consolida
        if not boleto_linha and extracted_data.get("linha_digitavel"):
            boleto_linha = _clean_str(extracted_data.get("linha_digitavel"))
        if not boleto_barras and extracted_data.get("codigo_barras"):
            boleto_barras = _clean_str(extracted_data.get("codigo_barras"))
        if not boleto_detalhes.get("nosso_numero") and extracted_data.get("nosso_numero"):
            boleto_detalhes["nosso_numero"] = _clean_str(extracted_data.get("nosso_numero"))

        if (
            is_boleto
            or boleto_linha
            or boleto_barras
            or "boleto" in tipo_lower
            or (regra_aprendida and "boleto" in str(regra_aprendida.get("valor_atribuido") or "").lower())
        ):
            is_boleto = True
            dominio_raw = "financeiro"
            tipo_doc_raw = "Boleto Bancário"
            tipo_lower = "boleto bancário"
            is_legitimate_pix = False
            has_explicit_pix_term = False
            pix_chave = None
            pix_e2e_id = None
            pix_autenticacao = None
        elif (
            is_cheque
            or "cheque" in tipo_lower
            or "talao" in tipo_lower
            or "talão" in tipo_lower
            or (regra_aprendida and any(k in str(regra_aprendida.get("valor_atribuido") or "").lower() for k in ["cheque", "talao", "talão"]))
        ):
            is_cheque = True
            dominio_raw = "financeiro"
            is_talao_sig = cheque_detalhes.get("is_talao", False) or "talao" in tipo_lower or "talão" in tipo_lower
            tipo_doc_raw = "Talão de Cheques" if is_talao_sig else "Folha de Cheque"
            tipo_lower = tipo_doc_raw.lower()
            is_legitimate_pix = False
            has_explicit_pix_term = False
            pix_chave = None
            pix_e2e_id = None
            pix_autenticacao = None
        elif is_irpf:
            dominio_raw = "financeiro"
            tipo_doc_raw = irpf_tipo
            tipo_lower = tipo_doc_raw.lower()
            is_legitimate_pix = False
            has_explicit_pix_term = False
            pix_chave = None
            pix_e2e_id = None
            pix_autenticacao = None
        elif is_informe:
            dominio_raw = "financeiro"
            tipo_doc_raw = informe_tipo
            tipo_lower = tipo_doc_raw.lower()
            is_legitimate_pix = False
            has_explicit_pix_term = False
            pix_chave = None
            pix_e2e_id = None
            pix_autenticacao = None
        elif is_cv:
            dominio_raw = "juridico"
            tipo_doc_raw = cv_tipo or "Contrato de Compra e Venda"
            tipo_lower = tipo_doc_raw.lower()
            is_legitimate_pix = False
            has_explicit_pix_term = False
            pix_chave = None
            pix_e2e_id = None
            pix_autenticacao = None
        elif is_np:
            dominio_raw = "financeiro"
            tipo_doc_raw = np_tipo or "Nota Promissória"
            tipo_lower = tipo_doc_raw.lower()
            is_legitimate_pix = False
            has_explicit_pix_term = False
            pix_chave = None
            pix_e2e_id = None
            pix_autenticacao = None
        elif is_rec:
            dominio_raw = "financeiro"
            tipo_doc_raw = rec_tipo or "Recibo"
            tipo_lower = tipo_doc_raw.lower()
            is_legitimate_pix = False
            has_explicit_pix_term = False
            pix_chave = None
            pix_e2e_id = None
            pix_autenticacao = None
        elif regra_aprendida:
            tipo_doc_raw = regra_aprendida.get("valor_atribuido") or tipo_doc_raw
            tipo_lower = str(tipo_doc_raw).lower()
            dominio_raw = regra_aprendida.get("dominio") or dominio_raw
            if regra_aprendida.get("remover_pix"):
                is_legitimate_pix = False
                has_explicit_pix_term = False
                pix_chave = None
                pix_e2e_id = None
                pix_autenticacao = None

        # Detecção de outros tipos específicos de documentos financeiros
        is_listagem = bool(
            any(k in full_text_corpus for k in ["listagem", "depósito", "deposito", "relação", "relacao", "borderô", "bordero", "relação de depósitos", "relacao de depositos"])
            or ("titular" in full_text_corpus and "banco" in full_text_corpus and "agência" in full_text_corpus)
            or ("titular" in full_text_corpus and "banco" in full_text_corpus and "agencia" in full_text_corpus)
        )
        is_darf = bool(any(k in full_text_corpus for k in ["darf", "arrecadação", "arrecadacao", "receita federal", "ministerio da fazenda", "ministério da fazenda", "cofins", "pis/pasep"]))
        is_ted = bool(any(k in full_text_corpus for k in ["\bted\b", "\bdoc\b", "transferência bancária", "transferencia bancaria", "transferência entre contas", "transferencia entre contas"]))

        # Se foi sugerido como PIX sem conter termo 'PIX' ou E2E ID oficial, corrige a classificação
        if "pix" in tipo_lower and not is_legitimate_pix and not is_boleto and not is_cheque:
            if is_listagem:
                tipo_doc_raw = "Listagem de Pagamentos / Depósitos"
            elif is_darf:
                tipo_doc_raw = "DARF / Guia de Arrecadação Federal"
            elif is_ted:
                tipo_doc_raw = "Comprovante de Transferência Bancária (TED/DOC)"
            else:
                tipo_doc_raw = "Comprovante de Pagamento Bancário"
            tipo_lower = tipo_doc_raw.lower()
            pix_chave = None
            pix_e2e_id = None

        # Heurística inteligente para consolidação do domínio
        is_non_financial_comprovante = (
            any(k in tipo_lower for k in [
                "inscrição", "inscricao", "situação cadastral", "situacao cadastral", "cnpj",
                "residência", "residencia", "matrícula", "matricula", "votação", "votacao"
            ]) and not any(f in tipo_lower for f in ["informe de rendimentos", "rendimentos financeiros"])
        )

        has_explicit_financial = bool(
            is_boleto or
            is_cheque or
            is_irpf or
            is_informe or
            is_np or
            is_rec or
            is_legitimate_pix or
            is_listagem or
            is_darf or
            is_ted or
            "nota promissória" in tipo_lower or
            "nota promissoria" in tipo_lower or
            "recibo" in tipo_lower or
            "comprovante de pagamento" in tipo_lower or
            "comprovante de transferência" in tipo_lower or
            "comprovante de transferencia" in tipo_lower or
            "comprovante bancário" in tipo_lower or
            "comprovante bancario" in tipo_lower or
            "recibo de pagamento" in tipo_lower or
            "boleto" in tipo_lower or
            "cheque" in tipo_lower or
            "talao" in tipo_lower or
            "talão" in tipo_lower or
            "informe de rendimentos" in tipo_lower or
            "imposto de renda" in tipo_lower or
            "ajuste anual" in tipo_lower or
            ("recibo" in tipo_lower and not is_non_financial_comprovante)
        )

        has_pix_signal = bool(is_legitimate_pix and (pix_e2e_id or pix_chave or has_explicit_pix_term))

        if is_boleto:
            dominio = "financeiro"
            tipo_doc_raw = "Boleto Bancário"
        elif is_cheque:
            dominio = "financeiro"
            is_talao_sig = cheque_detalhes.get("is_talao", False) or "talao" in tipo_lower or "talão" in tipo_lower
            tipo_doc_raw = "Talão de Cheques" if is_talao_sig else "Folha de Cheque"
        elif is_irpf:
            dominio = "financeiro"
            tipo_doc_raw = irpf_tipo
        elif is_informe:
            dominio = "financeiro"
            tipo_doc_raw = informe_tipo
        elif not is_non_financial_comprovante and (has_pix_signal or has_explicit_financial or valor_raw or dominio_raw == "financeiro"):
            dominio = "financeiro"
            if not tipo_doc_raw or tipo_lower in ["não identificado", "nao identificado", "outro", "não informado", "nao informado"]:
                if has_pix_signal:
                    tipo_doc_raw = "Comprovante PIX"
                elif is_listagem:
                    tipo_doc_raw = "Listagem de Pagamentos / Depósitos"
                elif is_darf:
                    tipo_doc_raw = "DARF / Guia de Arrecadação Federal"
                elif is_ted:
                    tipo_doc_raw = "Comprovante de Transferência Bancária (TED/DOC)"
                else:
                    tipo_doc_raw = "Recibo de Pagamento"
            if not res_dict.get("faculdade") and pix_pagador_banco:
                res_dict["faculdade"] = pix_pagador_banco
        elif is_academic_doc:
            dominio = "academico"
        elif is_actual_cadastral_doc or any(k in tipo_lower for k in ["currículo", "curriculo", "experiência profissional", "experiencia profissional", "lattes", "ctps", "carteira de trabalho"]):
            dominio = "profissional"
            if not tipo_doc_raw or tipo_lower in ["não identificado", "nao identificado", "outro", "não informado", "nao informado"]:
                tipo_doc_raw = "Cartão CNPJ / Situação Cadastral"
        elif any(k in tipo_lower for k in ["rg", "cnh", "identidade", "cpf", "certidão", "certidao", "eleitor", "passaporte"]):
            dominio = "identificacao"
        elif any(k in tipo_lower for k in ["contrato", "procuração", "procuracao", "posse", "juridico", "petição", "peticao"]):
            dominio = "juridico"
        elif dominio_raw in ["academico", "financeiro", "identificacao", "juridico", "profissional", "outro"]:
            dominio = dominio_raw
        else:
            dominio = "academico"

        res_dict["dominio"] = dominio
        res_dict["tipo_documento"] = tipo_doc_raw
        res_dict["valor_monetario"] = valor_raw

        # Atribuição de campos específicos de PIX
        if pix_pagador_nome: res_dict["pix_pagador_nome"] = pix_pagador_nome
        if pix_pagador_cpf_cnpj: res_dict["pix_pagador_cpf_cnpj"] = pix_pagador_cpf_cnpj
        if pix_pagador_banco: res_dict["pix_pagador_banco"] = pix_pagador_banco
        if pix_recebedor_banco: res_dict["pix_recebedor_banco"] = pix_recebedor_banco
        if pix_chave: res_dict["pix_chave"] = pix_chave
        if pix_e2e_id: res_dict["pix_e2e_id"] = pix_e2e_id
        if pix_autenticacao: res_dict["pix_autenticacao"] = pix_autenticacao

        # Detecção de escrita manual / preenchimento à mão (caneta/lápis)
        is_manuscrito = bool(
            extracted_data.get("manuscrito") is True
            or str(extracted_data.get("manuscrito") or "").strip().lower() in ["true", "1", "sim", "yes"]
            or any(k in tipo_lower for k in ["manuscrito", "preenchido a mão", "preenchido à mão", "proprio punho", "próprio punho", "recibo manual", "nota promissória manual", "declaracao de proprio punho", "declaração de próprio punho"])
            or (has_text and any(k in text.lower() for k in ["preenchido a mão", "preenchido à mão", "de próprio punho", "de proprio punho"]))
            or (tess_text and any(k in tess_text.lower() for k in ["preenchido a mão", "preenchido à mão", "de próprio punho", "de proprio punho"]))
        )

        if "dados_extras" not in res_dict or not isinstance(res_dict["dados_extras"], dict):
            res_dict["dados_extras"] = {}

        # Atribuição e consolidação dos campos de Boleto Bancário
        if is_boleto:
            if boleto_linha:
                res_dict["linha_digitavel"] = boleto_linha
                res_dict["dados_extras"]["linha_digitavel"] = boleto_linha
            if boleto_barras:
                res_dict["codigo_barras"] = boleto_barras
                res_dict["dados_extras"]["codigo_barras"] = boleto_barras
            if boleto_detalhes.get("nosso_numero"):
                res_dict["nosso_numero"] = boleto_detalhes["nosso_numero"]
                res_dict["dados_extras"]["nosso_numero"] = boleto_detalhes["nosso_numero"]

        # Atribuição e consolidação dos campos de Cheque / Talão de Cheques
        if is_cheque or cheque_num or cheque_banco:
            if cheque_num:
                res_dict["dados_extras"]["numero_cheque"] = cheque_num
            if cheque_detalhes.get("numeros_cheque"):
                res_dict["dados_extras"]["numeros_cheque"] = cheque_detalhes["numeros_cheque"]
            if cheque_banco or cheque_detalhes.get("banco_cheque"):
                b_chk = cheque_banco or cheque_detalhes.get("banco_cheque")
                res_dict["dados_extras"]["banco_cheque"] = b_chk
                if not res_dict.get("faculdade"):
                    res_dict["faculdade"] = b_chk
            if cheque_detalhes.get("serie_cheque"):
                res_dict["dados_extras"]["serie_cheque"] = cheque_detalhes["serie_cheque"]
            if cheque_detalhes.get("agencia_cheque"):
                res_dict["dados_extras"]["agencia_cheque"] = cheque_detalhes["agencia_cheque"]
            if cheque_detalhes.get("conta_corrente"):
                res_dict["dados_extras"]["conta_corrente"] = cheque_detalhes["conta_corrente"]

        # Atribuição e consolidação dos campos de IRPF e Informe de Rendimentos
        if is_irpf or irpf_det:
            if irpf_det.get("numero_recibo"):
                res_dict["dados_extras"]["numero_recibo"] = irpf_det["numero_recibo"]
            if irpf_det.get("exercicio"):
                res_dict["dados_extras"]["exercicio"] = irpf_det["exercicio"]
                res_dict["dados_extras"]["exercicio_irpf"] = irpf_det["exercicio"]
            if irpf_det.get("ano_calendario"):
                res_dict["dados_extras"]["ano_calendario"] = irpf_det["ano_calendario"]
            if irpf_det.get("total_rendimentos_tributaveis"):
                res_dict["dados_extras"]["total_rendimentos_tributaveis"] = irpf_det["total_rendimentos_tributaveis"]
            if not res_dict.get("faculdade"):
                res_dict["faculdade"] = "Secretaria da Receita Federal do Brasil (RFB)"

        if is_informe or informe_det:
            if informe_det.get("fonte_pagadora"):
                res_dict["dados_extras"]["fonte_pagadora"] = informe_det["fonte_pagadora"]
                if not res_dict.get("faculdade"):
                    res_dict["faculdade"] = informe_det["fonte_pagadora"]
            if informe_det.get("cnpj_fonte_pagadora"):
                res_dict["dados_extras"]["cnpj_fonte_pagadora"] = informe_det["cnpj_fonte_pagadora"]
            if informe_det.get("ano_calendario") and not res_dict["dados_extras"].get("ano_calendario"):
                res_dict["dados_extras"]["ano_calendario"] = informe_det["ano_calendario"]

        if is_manuscrito:
            res_dict["manuscrito"] = True
            res_dict["dados_extras"]["manuscrito"] = True

        emitente_val = _clean_str(extracted_data.get("emitente"))
        if emitente_val:
            res_dict["emitente"] = emitente_val
            res_dict["dados_extras"]["emitente"] = emitente_val

        referente_val = _clean_str(extracted_data.get("referente_a"))
        if referente_val:
            res_dict["referente_a"] = referente_val
            res_dict["dados_extras"]["referente_a"] = referente_val

        conteudo_manuscrito_val = _clean_str(extracted_data.get("conteudo_manuscrito"))
        if conteudo_manuscrito_val:
            res_dict["conteudo_manuscrito"] = conteudo_manuscrito_val
            res_dict["dados_extras"]["conteudo_manuscrito"] = conteudo_manuscrito_val

        # Captura e higienização da transcrição textual integral (OCR / Leitura Completa)
        raw_transcrito = _clean_str(
            extracted_data.get("texto_transcrito")
            or extracted_data.get("texto_ocr")
            or extracted_data.get("transcricao_completa")
        )
        sanitized_transcrito = sanitize_llm_transcription(raw_transcrito) if raw_transcrito else None
        if sanitized_transcrito:
            res_dict["texto_transcrito"] = sanitized_transcrito
            res_dict["dados_extras"]["texto_transcrito"] = sanitized_transcrito

        if text and text.strip():
            res_dict["dados_extras"]["texto_digital"] = text.strip()
        if tess_text and tess_text.strip():
            res_dict["dados_extras"]["texto_tesseract"] = tess_text.strip()

        # Extração e Consolidação de Múltiplos Nomes / Titulares (Pilar 3)
        detected_names_list: List[str] = []
        raw_llm_names = extracted_data.get("nomes_detectados")
        if isinstance(raw_llm_names, list):
            for nm in raw_llm_names:
                if isinstance(nm, str) and len(nm.strip()) >= 3:
                    c_nm = re.sub(r'\s+', ' ', nm).strip()
                    if c_nm not in detected_names_list:
                        detected_names_list.append(c_nm)
        elif isinstance(raw_llm_names, str) and len(raw_llm_names.strip()) >= 3:
            detected_names_list.append(raw_llm_names.strip())

        heur_names = []
        if has_text:
            heur_names.extend(extract_names_from_document_text(text))
        if tess_text:
            heur_names.extend(extract_names_from_document_text(tess_text))

        for hn in heur_names:
            if hn not in detected_names_list:
                detected_names_list.append(hn)

        benef_curr = res_dict.get("beneficiario")
        if benef_curr and benef_curr not in detected_names_list and len(benef_curr.split()) >= 2:
            detected_names_list.insert(0, benef_curr)
        elif not benef_curr and detected_names_list:
            res_dict["beneficiario"] = detected_names_list[0]

        if detected_names_list:
            res_dict["nomes_detectados"] = detected_names_list
            res_dict["dados_extras"]["nomes_detectados"] = detected_names_list

        # Consolidação de quaisquer atributos adicionais da LLM em dados_extras
        known_top_level = {
            "dominio", "tipo_documento", "data", "beneficiario", "cpf", "rg", "cnpj",
            "valor_monetario", "curso", "natureza_curso", "carga_horaria", "faculdade",
            "pix_pagador_nome", "pix_pagador_cpf_cnpj", "pix_pagador_banco", "pix_recebedor_banco",
            "pix_chave", "pix_e2e_id", "pix_autenticacao", "razao_social", "nome_fantasia",
            "situacao_cadastral", "data_situacao", "data_abertura", "cnae_principal",
            "natureza_juridica", "endereco_completo", "telefone", "email", "manuscrito",
            "emitente", "referente_a", "conteudo_manuscrito", "texto_transcrito", "texto_ocr",
            "transcricao_completa", "nomes_detectados", "dados_extras"
        }
        for k_dyn, v_dyn in extracted_data.items():
            if k_dyn not in known_top_level and v_dyn is not None:
                v_clean = _clean_str(v_dyn) if isinstance(v_dyn, str) else v_dyn
                if v_clean not in [None, "", "null", "N/A", "none"]:
                    res_dict["dados_extras"][k_dyn] = v_clean
                    res_dict[k_dyn] = v_clean

        # ---------------------------------------------------------------------
        # CASO 2 (Somente PDF com texto digital): Se dados essenciais falharam,
        # faz tentativa de OCR local rápido (Tesseract) e/ou multimodal via LLM
        # ---------------------------------------------------------------------
        if not is_image and has_text and dominio != "financeiro" and not res_dict.get("tentativa_ocr_llm") and not skip_ocr:
            tipo_atual = (res_dict.get("tipo_documento") or "").strip().lower()
            is_tipo_unidentified = (not tipo_atual) or tipo_atual in [
                "não identificado", "nao identificado", "outro", "não informado", "nao informado"
            ]
            cpf_atual = res_dict.get("cpf")
            is_cpf_flawed = bool(not cpf_atual or not is_valid_cpf_syntax(cpf_atual))
            is_dados_principais_missing = (not res_dict.get("beneficiario")) and (not res_dict.get("curso"))

            if is_tipo_unidentified or is_cpf_flawed or is_dados_principais_missing:
                # 1. Tenta resgatar dados críticos via Tesseract local rápido
                if not tess_text:
                    tess_text = extract_tesseract_text_from_pdf(pdf_path, max_pages=max_pages)

                if tess_text:
                    if is_cpf_flawed:
                        cand_cpf = extract_cpf_fallback(tess_text)
                        if cand_cpf and is_valid_cpf_syntax(cand_cpf):
                            res_dict["cpf"] = cand_cpf
                            is_cpf_flawed = False
                    if not res_dict.get("rg"):
                        cand_rg = extract_rg_fallback(tess_text)
                        if cand_rg:
                            res_dict["rg"] = cand_rg

                # 2. Se o documento ainda estiver sem tipo ou sem dados principais, escala para OCR Multimodal
                if is_tipo_unidentified or is_dados_principais_missing:
                    res_dict["tentativa_ocr_llm"] = True
                    try:
                        images = render_pdf_pages_to_base64(str(pdf_path), max_pages=min(max_pages, 4))
                        if images:
                            context_msg = f"{text}\n\nTexto OCR complementar:\n{tess_text}\n\nAtenção: O tipo de documento ou titular não puderam ser plenamente identificados no texto. Verifique visualmente."
                            vision_prompt = build_universal_vision_prompt(extra_context=context_msg)
                            ocr_data = client.generate_json_with_images(vision_prompt, images)

                            if is_tipo_unidentified:
                                new_tipo = _clean_str(ocr_data.get("tipo_documento"))
                                if new_tipo and new_tipo.lower() not in ["não identificado", "nao identificado", "outro"]:
                                    res_dict["tipo_documento"] = new_tipo
                                    res_dict["metodo_leitura"] = "hibrido_texto_e_ocr_llm"

                            new_cpf_raw = ocr_data.get("cpf")
                            if new_cpf_raw:
                                formatted_new_cpf = format_cpf(new_cpf_raw)
                                if formatted_new_cpf and is_valid_cpf_syntax(formatted_new_cpf):
                                    res_dict["cpf"] = formatted_new_cpf
                                    res_dict["metodo_leitura"] = "hibrido_texto_e_ocr_llm"

                            if not res_dict["beneficiario"] and ocr_data.get("beneficiario"):
                                res_dict["beneficiario"] = _clean_str(ocr_data.get("beneficiario"))
                            if not res_dict["rg"] and ocr_data.get("rg"):
                                res_dict["rg"] = _clean_str(ocr_data.get("rg"))
                            if not res_dict["curso"] or any(k in str(res_dict["curso"]).lower() for k in ["faculdade", "universidade", "instituto", "colegio"]):
                                if ocr_data.get("curso") and not any(k in str(ocr_data.get("curso")).lower() for k in ["faculdade", "universidade", "instituto", "colegio"]):
                                    res_dict["curso"] = _clean_str(ocr_data.get("curso"))
                                else:
                                    cf = (extract_course_fallback(text) if has_text else None) or (extract_course_fallback(tess_text) if tess_text else None)
                                    if cf:
                                        res_dict["curso"] = cf
                            if not res_dict["natureza_curso"] and ocr_data.get("natureza_curso"):
                                res_dict["natureza_curso"] = _clean_str(ocr_data.get("natureza_curso"))
                            if not res_dict["carga_horaria"] and ocr_data.get("carga_horaria"):
                                res_dict["carga_horaria"] = _clean_str(ocr_data.get("carga_horaria"))
                            if not res_dict["faculdade"] and ocr_data.get("faculdade"):
                                res_dict["faculdade"] = normalizar_instituicao(_clean_str(ocr_data.get("faculdade")))
                            if not res_dict["data"] and ocr_data.get("data"):
                                res_dict["data"] = _clean_str(ocr_data.get("data"))
                            if ocr_data.get("manuscrito"):
                                res_dict["manuscrito"] = True
                                if "dados_extras" in res_dict and isinstance(res_dict["dados_extras"], dict):
                                    res_dict["dados_extras"]["manuscrito"] = True
                            if not res_dict.get("emitente") and ocr_data.get("emitente"):
                                res_dict["emitente"] = _clean_str(ocr_data.get("emitente"))
                                res_dict["dados_extras"]["emitente"] = res_dict["emitente"]
                            if not res_dict.get("referente_a") and ocr_data.get("referente_a"):
                                res_dict["referente_a"] = _clean_str(ocr_data.get("referente_a"))
                                res_dict["dados_extras"]["referente_a"] = res_dict["referente_a"]
                            if not res_dict.get("conteudo_manuscrito") and ocr_data.get("conteudo_manuscrito"):
                                res_dict["conteudo_manuscrito"] = _clean_str(ocr_data.get("conteudo_manuscrito"))
                                res_dict["dados_extras"]["conteudo_manuscrito"] = res_dict["conteudo_manuscrito"]
                    except Exception:
                        pass

        # 3. Rede de segurança final para CPF, RG e Curso caso ainda estejam vazios e haja texto do Tesseract
        if (not res_dict.get("cpf") or not is_valid_cpf_syntax(res_dict.get("cpf"))) and tess_text:
            cand_cpf = extract_cpf_fallback(tess_text)
            if cand_cpf and is_valid_cpf_syntax(cand_cpf):
                res_dict["cpf"] = cand_cpf
        if not res_dict.get("rg") and tess_text:
            cand_rg = extract_rg_fallback(tess_text)
            if cand_rg:
                res_dict["rg"] = cand_rg
        if not res_dict.get("curso") or any(k in str(res_dict.get("curso")).lower() for k in ["faculdade", "universidade", "instituto", "colegio"]):
            cf = (extract_course_fallback(text) if has_text else None) or (extract_course_fallback(tess_text) if tess_text else None)
            if cf:
                res_dict["curso"] = cf

        # 4. Integração do Dossiê Multi-Páginas e Hierarquia Anti-Contaminação
        if not is_image:
            try:
                dossier = analyze_pdf_dossier(pdf_path, max_ocr_pages=max(max_pages, 25))
                todos_tipos = list(dossier.get("todos_tipos", []))
                todos_dominios = list(dossier.get("todos_dominios", []))

                prim_tipo = res_dict.get("tipo_documento")
                prim_dom = res_dict.get("dominio")

                # Se o classificador ou LLM definiu um tipo primário, assegura presença em todos_tipos
                if prim_tipo and prim_tipo not in todos_tipos:
                    todos_tipos.insert(0, prim_tipo)
                if prim_dom and prim_dom not in todos_dominios:
                    todos_dominios.insert(0, prim_dom)

                # Se o LLM não identificou o tipo principal, assume a primazia do dossiê
                if (not res_dict.get("tipo_documento") or res_dict.get("tipo_documento") in ["Outro", "não identificado", "nao identificado"]) and dossier.get("tipo_documento_principal"):
                    res_dict["tipo_documento"] = dossier["tipo_documento_principal"]
                    if not res_dict.get("dominio") or res_dict.get("dominio") == "outros":
                        res_dict["dominio"] = dossier.get("dominio_principal", "academico")

                # Resgate prioritário de CPF do titular (CNH / CPF / RG têm prioridade máxima sobre comprovantes PIX)
                if (not res_dict.get("cpf") or not is_valid_cpf_syntax(res_dict.get("cpf"))) and dossier.get("cpf_titular"):
                    res_dict["cpf"] = dossier["cpf_titular"]

                # Resgate de RG do titular
                if not res_dict.get("rg") and dossier.get("rg_titular"):
                    res_dict["rg"] = dossier["rg_titular"]

                # Resgate de CNPJ do titular
                if not res_dict.get("cnpj") and dossier.get("cnpj_titular"):
                    res_dict["cnpj"] = dossier["cnpj_titular"]

                # Resgate do curso (estritamente de páginas acadêmicas)
                if (not res_dict.get("curso") or any(k in str(res_dict.get("curso")).lower() for k in ["faculdade", "universidade", "instituto", "colegio"])) and dossier.get("curso_titular"):
                    res_dict["curso"] = dossier["curso_titular"]

                if is_boleto:
                    res_dict["tipo_documento"] = "Boleto Bancário"
                    res_dict["dominio"] = "financeiro"
                    if "Boleto Bancário" not in todos_tipos:
                        todos_tipos.insert(0, "Boleto Bancário")
                    else:
                        todos_tipos.remove("Boleto Bancário")
                        todos_tipos.insert(0, "Boleto Bancário")
                    if "financeiro" not in todos_dominios:
                        todos_dominios.insert(0, "financeiro")
                elif dossier.get("tipo_documento_principal") in ("Talão de Cheques", "Folha de Cheque") or is_cheque:
                    tag_chk = dossier.get("tipo_documento_principal") or ("Talão de Cheques" if cheque_detalhes.get("is_talao") else "Folha de Cheque")
                    res_dict["tipo_documento"] = tag_chk
                    res_dict["dominio"] = "financeiro"
                    if tag_chk not in todos_tipos:
                        todos_tipos.insert(0, tag_chk)
                    else:
                        todos_tipos.remove(tag_chk)
                        todos_tipos.insert(0, tag_chk)
                    if "financeiro" not in todos_dominios:
                        todos_dominios.insert(0, "financeiro")
                    # Remove false PIX remnants
                    res_dict["pix_chave"] = None
                    res_dict["pix_e2e_id"] = None
                    res_dict["pix_autenticacao"] = None
                    for k_pix in ["pix_chave", "pix_e2e_id", "pix_autenticacao", "pix_pagador_nome", "pix_pagador_cpf_cnpj", "pix_pagador_banco", "pix_recebedor_banco", "pix_recebedor_nome", "pix_recebedor_cpf_cnpj"]:
                        res_dict.pop(k_pix, None)
                        if "dados_extras" in res_dict and isinstance(res_dict["dados_extras"], dict):
                            res_dict["dados_extras"].pop(k_pix, None)
                elif is_irpf or is_informe or (dossier.get("tipo_documento_principal") and ("imposto de renda" in dossier.get("tipo_documento_principal").lower() or "recibo de entrega" in dossier.get("tipo_documento_principal").lower() or "informe de rendimentos" in dossier.get("tipo_documento_principal").lower())):
                    tag_ir = (irpf_tipo if is_irpf else (informe_tipo if is_informe else None)) or dossier.get("tipo_documento_principal") or "Declaração de Imposto de Renda"
                    res_dict["tipo_documento"] = tag_ir
                    res_dict["dominio"] = "financeiro"
                    if tag_ir not in todos_tipos:
                        todos_tipos.insert(0, tag_ir)
                    if "financeiro" not in todos_dominios:
                        todos_dominios.insert(0, "financeiro")
                    # Remove false PIX remnants
                    res_dict["pix_chave"] = None
                    res_dict["pix_e2e_id"] = None
                    res_dict["pix_autenticacao"] = None
                    for k_pix in ["pix_chave", "pix_e2e_id", "pix_autenticacao", "pix_pagador_nome", "pix_pagador_cpf_cnpj", "pix_pagador_banco", "pix_recebedor_banco", "pix_recebedor_nome", "pix_recebedor_cpf_cnpj"]:
                        res_dict.pop(k_pix, None)
                        if "dados_extras" in res_dict and isinstance(res_dict["dados_extras"], dict):
                            res_dict["dados_extras"].pop(k_pix, None)
                elif is_cv or (dossier.get("tipo_documento_principal") and ("compra e venda" in dossier.get("tipo_documento_principal").lower() or "contrato" in dossier.get("tipo_documento_principal").lower())):
                    tag_cv = (cv_tipo if is_cv else None) or dossier.get("tipo_documento_principal") or "Contrato de Compra e Venda"
                    res_dict["tipo_documento"] = tag_cv
                    res_dict["dominio"] = "juridico"
                    if tag_cv not in todos_tipos:
                        todos_tipos.insert(0, tag_cv)
                    if "juridico" not in todos_dominios:
                        todos_dominios.insert(0, "juridico")
                elif is_np or (dossier.get("tipo_documento_principal") and "promissória" in dossier.get("tipo_documento_principal").lower()):
                    tag_np = (np_tipo if is_np else None) or dossier.get("tipo_documento_principal") or "Nota Promissória"
                    res_dict["tipo_documento"] = tag_np
                    res_dict["dominio"] = "financeiro"
                    if tag_np not in todos_tipos:
                        todos_tipos.insert(0, tag_np)
                    if "financeiro" not in todos_dominios:
                        todos_dominios.insert(0, "financeiro")
                elif is_rec or (dossier.get("tipo_documento_principal") and "recibo" in dossier.get("tipo_documento_principal").lower()):
                    tag_rec = (rec_tipo if is_rec else None) or dossier.get("tipo_documento_principal") or "Recibo"
                    res_dict["tipo_documento"] = tag_rec
                    res_dict["dominio"] = "financeiro"
                    if tag_rec not in todos_tipos:
                        todos_tipos.insert(0, tag_rec)
                    if "financeiro" not in todos_dominios:
                        todos_dominios.insert(0, "financeiro")

                # Consolida campos de cheque vindos do dossier
                if dossier.get("numero_cheque") and "numero_cheque" not in res_dict.get("dados_extras", {}):
                    res_dict.setdefault("dados_extras", {})["numero_cheque"] = dossier["numero_cheque"]
                if dossier.get("numeros_cheque"):
                    res_dict.setdefault("dados_extras", {})["numeros_cheque"] = dossier["numeros_cheque"]
                if dossier.get("banco_cheque"):
                    res_dict.setdefault("dados_extras", {})["banco_cheque"] = dossier["banco_cheque"]
                    if not res_dict.get("faculdade"):
                        res_dict["faculdade"] = dossier["banco_cheque"]
                if dossier.get("conta_corrente") and "conta_corrente" not in res_dict.get("dados_extras", {}):
                    res_dict.setdefault("dados_extras", {})["conta_corrente"] = dossier["conta_corrente"]
                if dossier.get("serie_cheque") and "serie_cheque" not in res_dict.get("dados_extras", {}):
                    res_dict.setdefault("dados_extras", {})["serie_cheque"] = dossier["serie_cheque"]
                if dossier.get("agencia_cheque") and "agencia_cheque" not in res_dict.get("dados_extras", {}):
                    res_dict.setdefault("dados_extras", {})["agencia_cheque"] = dossier["agencia_cheque"]

                # Consolida campos de IRPF e Informe vindos do dossier
                if dossier.get("numero_recibo") and "numero_recibo" not in res_dict.get("dados_extras", {}):
                    res_dict.setdefault("dados_extras", {})["numero_recibo"] = dossier["numero_recibo"]
                if dossier.get("exercicio_irpf") and "exercicio" not in res_dict.get("dados_extras", {}):
                    res_dict.setdefault("dados_extras", {})["exercicio"] = dossier["exercicio_irpf"]
                    res_dict.setdefault("dados_extras", {})["exercicio_irpf"] = dossier["exercicio_irpf"]
                if dossier.get("ano_calendario") and "ano_calendario" not in res_dict.get("dados_extras", {}):
                    res_dict.setdefault("dados_extras", {})["ano_calendario"] = dossier["ano_calendario"]
                if dossier.get("fonte_pagadora") and "fonte_pagadora" not in res_dict.get("dados_extras", {}):
                    res_dict.setdefault("dados_extras", {})["fonte_pagadora"] = dossier["fonte_pagadora"]
                    if not res_dict.get("faculdade"):
                        is_doc_irpf = is_irpf or any(k in (res_dict.get("tipo_documento") or "").lower() for k in ["ajuste anual", "imposto de renda"])
                        if not is_doc_irpf:
                            res_dict["faculdade"] = dossier["fonte_pagadora"]
                        else:
                            res_dict["faculdade"] = "Secretaria da Receita Federal do Brasil (RFB)"
                if dossier.get("cnpj_fonte_pagadora") and "cnpj_fonte_pagadora" not in res_dict.get("dados_extras", {}):
                    res_dict.setdefault("dados_extras", {})["cnpj_fonte_pagadora"] = dossier["cnpj_fonte_pagadora"]

                res_dict["todos_tipos"] = todos_tipos if todos_tipos else ([prim_tipo] if prim_tipo else [])
                res_dict["todos_dominios"] = todos_dominios if todos_dominios else ([prim_dom] if prim_dom else [])
                res_dict["dossie_paginas"] = dossier.get("dossie_paginas", [])
            except Exception:
                prim_tipo = res_dict.get("tipo_documento")
                prim_dom = res_dict.get("dominio")
                if is_boleto:
                    prim_tipo = "Boleto Bancário"
                    prim_dom = "financeiro"
                elif is_cheque:
                    prim_tipo = "Talão de Cheques" if cheque_detalhes.get("is_talao") else "Folha de Cheque"
                    prim_dom = "financeiro"
                elif is_irpf:
                    prim_tipo = irpf_tipo
                    prim_dom = "financeiro"
                elif is_informe:
                    prim_tipo = informe_tipo
                    prim_dom = "financeiro"
                res_dict["todos_tipos"] = [prim_tipo] if prim_tipo else []
                res_dict["todos_dominios"] = [prim_dom] if prim_dom else []
                res_dict["dossie_paginas"] = []
        else:
            prim_tipo = res_dict.get("tipo_documento")
            prim_dom = res_dict.get("dominio")
            if is_boleto:
                prim_tipo = "Boleto Bancário"
                prim_dom = "financeiro"
            elif is_cheque:
                prim_tipo = "Talão de Cheques" if cheque_detalhes.get("is_talao") else "Folha de Cheque"
                prim_dom = "financeiro"
            elif is_irpf:
                prim_tipo = irpf_tipo
                prim_dom = "financeiro"
            elif is_informe:
                prim_tipo = informe_tipo
                prim_dom = "financeiro"
            res_dict["todos_tipos"] = [prim_tipo] if prim_tipo else []
            res_dict["todos_dominios"] = [prim_dom] if prim_dom else []
            res_dict["dossie_paginas"] = [{"pagina": 1, "tipo": prim_tipo or "Documento", "dominio": prim_dom or "outros"}]

        # Se for identificado como manuscrito ou preenchido à mão, adiciona a tag "Manuscrito"
        if res_dict.get("manuscrito"):
            tem_tag_man = any("manuscrito" in str(t).lower() or "mão" in str(t).lower() or "mao" in str(t).lower() for t in res_dict.get("todos_tipos", []))
            if not tem_tag_man:
                res_dict["todos_tipos"].append("Manuscrito")

        # Validação de sucesso adaptativa para múltiplos domínios
        campos_uteis = [
            res_dict.get("beneficiario"),
            res_dict.get("curso"),
            res_dict.get("cpf"),
            res_dict.get("rg"),
            res_dict.get("cnpj"),
            res_dict.get("faculdade"),
            res_dict.get("tipo_documento"),
            res_dict.get("valor_monetario"),
            res_dict.get("linha_digitavel"),
            res_dict.get("codigo_barras"),
            res_dict.get("nosso_numero"),
            res_dict.get("pix_pagador_nome"),
            res_dict.get("pix_e2e_id"),
            res_dict.get("emitente"),
            res_dict.get("referente_a"),
            res_dict.get("conteudo_manuscrito")
        ]
        if any(campos_uteis):
            res_dict["status"] = "sucesso"
            res_dict["erro"] = None
        else:
            res_dict["status"] = "erro"
            res_dict["erro"] = "Documento sem informações identificáveis após análise."

    except Exception as e:
        res_dict["status"] = "erro"
        res_dict["erro"] = str(e)

    # -------------------------------------------------------------------------
    # MODO HÍBRIDO EM CASCATA: Fallback para Modelo de Nuvem (Item 4)
    # -------------------------------------------------------------------------
    if hybrid and hybrid_cloud_client is not None:
        raw_text_len = len(text.strip()) if ('text' in locals() and text and isinstance(text, str)) else 0
        if raw_text_len == 0 and 'tess_text' in locals() and tess_text and isinstance(tess_text, str):
            raw_text_len = len(tess_text.strip())

        should_fallback, reason = should_trigger_hybrid_fallback(res_dict, text_length=raw_text_len)
        if should_fallback:
            try:
                cloud_doc = process_single_pdf(
                    pdf_path=pdf_path,
                    client=hybrid_cloud_client,
                    max_pages=max_pages,
                    force_ocr=True,
                    skip_ocr=False,
                    metadata=meta,
                    hybrid=False,  # Evita recursão infinita
                    hybrid_cloud_client=None
                )
                cloud_doc["metodo_leitura"] = "hibrido_fallback_openai"
                cloud_doc["provedor_primario"] = getattr(client, "provider", "ollama")
                cloud_doc["provedor_final"] = "openai"
                cloud_doc["motivo_fallback"] = reason
                return cloud_doc
            except Exception as ex_cloud:
                res_dict["erro_fallback_nuvem"] = str(ex_cloud)

    return res_dict


process_single_document = process_single_pdf


def format_single_txt(item: Dict[str, Any]) -> str:
    metodo = item.get("metodo_leitura", "texto_digital")
    if item.get("tentativa_ocr_llm") and "ocr" not in metodo.lower():
        metodo += " (OCR LLM acionado)"

    dom = item.get("dominio") or "academico"
    ext = item.get("extensao") or ""
    todos_tipos = item.get("todos_tipos") or []
    dossie_line = f"\nDocumentos no Arquivo  : {', '.join(str(t) for t in todos_tipos)}" if (isinstance(todos_tipos, list) and len(todos_tipos) > 1) else ""
    de = item.get("dados_extras") if isinstance(item.get("dados_extras"), dict) else {}
    if isinstance(de, str):
        try:
            de = json.loads(de)
        except Exception:
            de = {}

    lines = [
        "-" * 80,
        f"MD5                     : {item.get('md5')}",
        f"Status                  : {str(item.get('status', '')).upper()}",
        f"Domínio                 : {dom.upper()}",
        f"Tipo Documento          : {item.get('tipo_documento') or 'Não identificado'}{dossie_line}",
        f"Extensão                : {ext.upper() if ext else 'N/A'}",
        f"Método de Leitura       : {metodo}",
        f"Data da Última Alteração: {item.get('data_modificacao') or 'N/A'}",
    ]

    # REGRA ZERO NOISE: Somente inclui campos que realmente possuem valor substantivo
    def _add_if_val(label: str, val: Any):
        if val is None:
            return
        s_val = str(val).strip()
        if not s_val or s_val.lower() in [
            "não informado", "não identificada", "não identificado",
            "nao informado", "nao identificada", "nao identificado",
            "none", "null", "n/a", "-", "--"
        ]:
            return
        lines.append(f"{label:<24}: {s_val}")

    _add_if_val("dc:creator", item.get("autor"))
    _add_if_val("dc:title", item.get("dc_title"))
    _add_if_val("dc:tool", item.get("dc_creator_tool"))
    _add_if_val("Beneficiário / Titular", item.get("beneficiario"))
    _add_if_val("CPF", item.get("cpf"))
    _add_if_val("RG / Identidade", item.get("rg"))
    _add_if_val("CNPJ", item.get("cnpj") or de.get("cnpj"))
    _add_if_val("Valor Monetário", item.get("valor_monetario"))
    _add_if_val("Data do Documento", item.get("data"))
    _add_if_val("Instituição / Faculdade", item.get("faculdade"))

    if dom == "academico":
        _add_if_val("Curso", item.get("curso"))
        _add_if_val("Natureza do Curso", item.get("natureza_curso"))
        _add_if_val("Carga Horária", item.get("carga_horaria"))
    elif dom == "financeiro":
        _add_if_val("Número do Cheque", de.get("numero_cheque"))
        if de.get("numeros_cheque") and len(de.get("numeros_cheque")) > 1:
            amostra_chk = ", ".join(str(n) for n in de["numeros_cheque"][:8])
            if len(de["numeros_cheque"]) > 8:
                amostra_chk += f" ... (+{len(de['numeros_cheque']) - 8} cheques)"
            _add_if_val("Cheques no Talão", f"{amostra_chk} (Total: {len(de['numeros_cheque'])})")
        _add_if_val("Banco do Cheque", de.get("banco_cheque"))
        _add_if_val("Série do Cheque", de.get("serie_cheque"))
        _add_if_val("Agência", de.get("agencia_cheque"))
        _add_if_val("Conta Corrente", de.get("conta_corrente"))
        _add_if_val("Pagador", item.get("pix_pagador_nome"))
        _add_if_val("CPF/CNPJ do Pagador", item.get("pix_pagador_cpf_cnpj"))
        _add_if_val("Banco Origem (Pagador)", item.get("pix_pagador_banco"))
        _add_if_val("Banco Destino (Receb.)", item.get("pix_recebedor_banco"))
        _add_if_val("Chave PIX", item.get("pix_chave"))
        _add_if_val("ID Fim-a-Fim (E2E)", item.get("pix_e2e_id"))
        _add_if_val("Autenticação Bancária", item.get("pix_autenticacao"))
    elif dom == "profissional":
        _add_if_val("Razão Social", de.get("razao_social") or item.get("beneficiario"))
        _add_if_val("Nome Fantasia", de.get("nome_fantasia"))
        _add_if_val("Situação Cadastral", de.get("situacao_cadastral"))
        _add_if_val("Data da Situação", de.get("data_situacao"))
        _add_if_val("Data de Abertura", de.get("data_abertura"))
        _add_if_val("CNAE Principal", de.get("cnae_principal"))
        _add_if_val("Natureza Jurídica", de.get("natureza_juridica"))
        _add_if_val("Endereço Completo", de.get("endereco_completo"))
        _add_if_val("Telefone", de.get("telefone"))
        _add_if_val("E-mail", de.get("email"))
    elif dom == "veicular":
        _add_if_val("Placa", de.get("placa"))
        _add_if_val("Renavam", de.get("renavam"))
        _add_if_val("Chassi", de.get("chassi"))
        _add_if_val("Marca / Modelo", de.get("marca_modelo"))
        _add_if_val("Ano Fab / Modelo", de.get("ano_fabricacao_modelo") or de.get("ano_veiculo"))
        _add_if_val("Órgão de Trânsito", de.get("orgao_transito") or item.get("faculdade"))
        _add_if_val("Proprietário / Vendedor", de.get("vendedor") or de.get("proprietario_anterior") or item.get("beneficiario"))
        _add_if_val("Comprador", de.get("comprador"))

    # Dados de manuscrito
    if de.get("manuscrito") or item.get("manuscrito"):
        _add_if_val("Preenchimento Manual", "Sim (Documento manuscrito)")
        _add_if_val("Emitente / Assinante", de.get("emitente") or item.get("emitente"))
        _add_if_val("Referente a", de.get("referente_a") or item.get("referente_a"))
        _add_if_val("Conteúdo Manuscrito", de.get("conteudo_manuscrito") or item.get("conteudo_manuscrito"))

    # Múltiplos Nomes Detectados (Listagens e Relações)
    nomes_det = item.get("nomes_detectados") or de.get("nomes_detectados")
    if isinstance(nomes_det, list) and len(nomes_det) > 1:
        amostra = ", ".join(str(n) for n in nomes_det[:6])
        if len(nomes_det) > 6:
            amostra += f" ... (+{len(nomes_det) - 6} nomes)"
        _add_if_val("Titulares / Nomes Det.", f"{amostra} (Total: {len(nomes_det)})")

    # Outros campos dinâmicos em dados_extras
    ignore_keys = {
        "razao_social", "nome_fantasia", "situacao_cadastral", "data_situacao",
        "data_abertura", "cnae_principal", "natureza_juridica", "endereco_completo",
        "telefone", "email", "manuscrito", "emitente", "referente_a", "conteudo_manuscrito",
        "texto_transcrito", "texto_ocr", "texto_digital", "texto_tesseract", "transcricao_completa",
        "nomes_detectados", "dossie_paginas", "todos_dominios", "todos_tipos", "data_criacao",
        "numero_cheque", "numeros_cheque", "banco_cheque", "serie_cheque", "agencia_cheque", "conta_corrente",
        "placa", "renavam", "chassi", "marca_modelo", "ano_fabricacao_modelo", "ano_veiculo",
        "orgao_transito", "vendedor", "proprietario_anterior", "comprador", "cnpj"
    }
    for k, v in de.items():
        if k not in ignore_keys:
            label = k.replace("_", " ").title()
            _add_if_val(label, v)

    _add_if_val("Processado em", item.get("processado_em"))
    if item.get("erro"):
        lines.append(f"Erro                    : {item.get('erro')}")

    lines.append("-" * 80)

    # Hierarquia de Verdade Textual (Ground Truth First):
    # 1. Camada Digital Nativa -> 2. Tesseract OCR -> 3. Transcrição IA Sanitizada
    texto_puro = None
    if de.get("texto_digital") and len(str(de.get("texto_digital")).strip()) >= 30:
        texto_puro = str(de.get("texto_digital")).strip()
    elif de.get("texto_tesseract") and len(str(de.get("texto_tesseract")).strip()) >= 30:
        texto_puro = str(de.get("texto_tesseract")).strip()
    else:
        raw_t = de.get("texto_transcrito") or de.get("texto_ocr") or item.get("texto_transcrito")
        clean_t = sanitize_llm_transcription(str(raw_t)) if raw_t else None
        if clean_t:
            texto_puro = clean_t
        elif de.get("texto_digital") and str(de.get("texto_digital")).strip():
            texto_puro = str(de.get("texto_digital")).strip()
        elif de.get("texto_tesseract") and str(de.get("texto_tesseract")).strip():
            texto_puro = str(de.get("texto_tesseract")).strip()

    if texto_puro:
        lines.append("\n" + "=" * 80)
        lines.append("TEXTO INTEGRAL / TRANSCRIÇÃO OCR")
        lines.append("=" * 80)
        lines.append(texto_puro)
        lines.append("\n" + "-" * 80)

    return "\n".join(lines) + "\n"


def generate_consolidated_txt(
    results: List[Dict[str, Any]],
    provider_name: str,
    model_name: str
) -> str:
    total = len(results)
    sucesso = sum(1 for r in results if r.get("status") == "sucesso")
    erros = total - sucesso
    now_str = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

    lines = [
        "=" * 80,
        "JOAKINDEX - RELATÓRIO CONSOLIDADO DE CLASSIFICAÇÃO",
        "Criado por: Joaquim Ferreira Silva Neto <joaquimfsneto@gmail.com>",
        f"Data/Hora de Geração : {now_str}",
        f"Provedor LLM         : {provider_name.upper()} (Modelo: {model_name})",
        f"Total de Documentos  : {total}",
        f"Classificados com OK : {sucesso}",
        f"Falhas / Erros       : {erros}",
        "=" * 80,
        ""
    ]

    for idx, item in enumerate(results, 1):
        dom = item.get("dominio") or "academico"
        lines.append(f"[{idx}/{total}] MD5: {item.get('md5')}")
        lines.append(f"  • Status                  : {item.get('status', '').upper()}")
        lines.append(f"  • Domínio                 : {dom.upper()}")
        lines.append(f"  • Tipo Documento          : {item.get('tipo_documento') or 'Não identificado'}")
        lines.append(f"  • Data da Última Alteração: {item.get('data_modificacao')}")
        lines.append(f"  • dc:creator              : {item.get('autor') or 'Não informado'}")
        if item.get("dc_title"):
            lines.append(f"  • dc:title                : {item.get('dc_title')}")
        if item.get("dc_creator_tool"):
            lines.append(f"  • dc:tool                 : {item.get('dc_creator_tool')}")
        lines.append(f"  • Beneficiário / Titular  : {item.get('beneficiario') or 'Não informado'}")
        lines.append(f"  • CPF                     : {item.get('cpf') or 'Não informado'}")
        lines.append(f"  • RG / Identidade         : {item.get('rg') or 'Não informado'}")
        if dom == "financeiro" or item.get("valor_monetario") or item.get("pix_pagador_nome"):
            lines.append(f"  • Valor Monetário         : {item.get('valor_monetario') or 'Não informado'}")
            lines.append(f"  • Data da Transação       : {item.get('data') or 'Não informada'}")
            lines.append(f"  • Instituição / Banco     : {item.get('faculdade') or 'Não informada'}")
            if item.get("pix_pagador_nome"):
                lines.append(f"  • Pagador                 : {item.get('pix_pagador_nome')}")
            if item.get("pix_e2e_id"):
                lines.append(f"  • ID Fim-a-Fim (E2E)      : {item.get('pix_e2e_id')}")
        else:
            lines.append(f"  • Curso                   : {item.get('curso') or 'Não informado'}")
            lines.append(f"  • Natureza do Curso       : {item.get('natureza_curso') or 'Não identificada'}")
            lines.append(f"  • Carga Horária           : {item.get('carga_horaria') or 'Não informada'}")
            lines.append(f"  • Faculdade               : {item.get('faculdade') or 'Não informada'}")
            lines.append(f"  • Data do Documento       : {item.get('data') or 'Não informada'}")
        if item.get("erro"):
            lines.append(f"  • Detalhe do Erro         : {item.get('erro')}")
        lines.append("-" * 80)

    lines.append("")
    lines.append("=" * 80)
    lines.append("FIM DO RELATÓRIO")
    lines.append("=" * 80)

    return "\n".join(lines)


def save_consolidated_reports(
    items_dict: Dict[str, Any],
    out_dir: Path,
    provider_name: str,
    model_name: str
) -> None:
    """
    Salva os relatórios consolidado SQLite, JSON e TXT de forma atômica para evitar perda ou
    corrupção de dados em caso de parada forçada (Ctrl+C, kill ou reinicialização).
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    consolidated_json_path = out_dir / "joakindex.json"
    consolidated_txt_path = out_dir / "joakindex.txt"
    consolidated_db_path = get_db_path(out_dir)
    results = sorted(list(items_dict.values()), key=lambda x: str(x.get("md5", "")))
    for r in results:
        if isinstance(r, dict):
            r.pop("data_criacao", None)

    # 1. Banco SQLite relacional (WAL mode e ACID)
    try:
        init_database(consolidated_db_path)
        upsert_documents_batch(consolidated_db_path, results)
    except Exception as e:
        print(f"[Aviso] Falha ao gravar SQLite {consolidated_db_path.name}: {e}")

    # 2. JSON consolidado atômico
    tmp_json = out_dir / f".tmp_{consolidated_json_path.name}"
    try:
        with open(tmp_json, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        tmp_json.replace(consolidated_json_path)
    except Exception as e:
        print(f"[Aviso] Falha ao gravar {consolidated_json_path.name}: {e}")

    # 3. TXT consolidado atômico
    try:
        report_text = generate_consolidated_txt(results, provider_name, model_name)
        tmp_txt = out_dir / f".tmp_{consolidated_txt_path.name}"
        with open(tmp_txt, "w", encoding="utf-8") as f:
            f.write(report_text)
        tmp_txt.replace(consolidated_txt_path)
    except Exception as e:
        print(f"[Aviso] Falha ao gravar {consolidated_txt_path.name}: {e}")


def run_batch_classification(
    input_path: Union[str, Path],
    output_dir: Union[str, Path],
    provider: str = "ollama",
    model: Optional[str] = None,
    ollama_url: str = "http://localhost:11434",
    docker: Optional[str] = None,
    openai_key: Optional[str] = None,
    openai_base_url: Optional[str] = None,
    workers: int = 1,
    max_pages: int = 4,
    skip_ocr: bool = False,
    reprocess_ocr: bool = False,
    force: bool = False,
    no_individual: bool = False,
    progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
    stop_checker: Optional[Callable[[], bool]] = None,
    use_tqdm: bool = True,
    client: Optional[Any] = None,
    hybrid: bool = False,
    hybrid_cloud_model: str = "gpt-4o-mini",
    hybrid_openai_key: Optional[str] = None,
    hybrid_openai_base_url: Optional[str] = None
) -> Dict[str, Any]:
    """
    Executa a classificação em lote de documentos PDF com suporte a:
    - Execução concorrente (workers)
    - Modo incremental inteligente (recuperação contínua de individuais/ e JSON consolidado)
    - Preservação estrita de aprovações de conferência humana prévia
    - Callbacks de progresso em tempo real (compatível com visualizador web e CLI)
    - Cancelamento seguro e gracioso via stop_checker()
    """
    def notify(event: Dict[str, Any]):
        if progress_callback:
            try:
                progress_callback(event)
            except Exception as ex_cb:
                print(f"[Aviso Callback] Erro ao notificar: {ex_cb}")

    in_clean = clean_path_string(input_path) if input_path else "./pdf"
    in_p = Path(in_clean).expanduser().resolve()
    if not in_p.exists():
        err_msg = f"Caminho de entrada não encontrado: {in_p}"
        print(f"[ERRO] {err_msg}")
        notify({"event": "error", "error": err_msg})
        return {"status": "erro", "mensagem": err_msg, "total": 0, "results": []}

    pdf_files = []
    if in_p.is_file():
        if in_p.suffix.lower() in SUPPORTED_EXTENSIONS:
            pdf_files.append(in_p)
        else:
            err_msg = f"O arquivo indicado não possui formato suportado (PDF, PNG, JPG, JPEG, WEBP): {in_p}"
            print(f"[ERRO] {err_msg}")
            notify({"event": "error", "error": err_msg})
            return {"status": "erro", "mensagem": err_msg, "total": 0, "results": []}
    else:
        found_set = set()
        for ext in SUPPORTED_EXTENSIONS:
            found_set |= set(in_p.glob(f"*{ext}")) | set(in_p.glob(f"*{ext.upper()}"))
        if not found_set:
            for ext in SUPPORTED_EXTENSIONS:
                found_set |= set(in_p.rglob(f"*{ext}")) | set(in_p.rglob(f"*{ext.upper()}"))
        pdf_files = sorted(list(found_set))

    if not pdf_files:
        msg = f"Nenhum documento suportado (PDF/Imagem) encontrado em: {in_p}"
        print(f"[AVISO] {msg}")
        notify({"event": "warning", "message": msg})
        return {"status": "aviso", "mensagem": msg, "total": 0, "results": []}

    print(f"[*] Total de documentos identificados: {len(pdf_files)}")
    notify({"event": "init", "total_files": len(pdf_files), "message": f"{len(pdf_files)} documentos identificados."})

    # Inicialização do Cliente LLM
    if client is None:
        if provider == "ollama":
            model_name = model or "gemma4:e4b"
            print(f"[*] Inicializando cliente Ollama (Modelo: {model_name})...")
            client = OllamaClient(
                model=model_name,
                base_url=ollama_url or "http://localhost:11434",
                docker_container=docker
            )
            if client.use_docker:
                c_name_lower = client.docker_container.lower()
                c_label = "Open-WebUI" if "open-webui" in c_name_lower else ("Oficial Puro" if "ollama" in c_name_lower else "Docker")
                print(f"[*] Modo de conexão: Docker exec [{c_label}] (container: '{client.docker_container}')")
            else:
                print(f"[*] Modo de conexão: Ollama Nativo / HTTP direto ({client.base_url})")
        else:
            model_name = model or "gpt-4o-mini"
            print(f"[*] Inicializando cliente OpenAI (Modelo: {model_name})...")
            client = OpenAIClient(
                model=model_name,
                api_key=openai_key,
                base_url=openai_base_url
            )
    else:
        model_name = getattr(client, "model", model or "llm")

    out_dir = Path(resolve_classifier_output_dir(output_dir)).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    indiv_dir = out_dir / "individuais"
    if not no_individual:
        indiv_dir.mkdir(parents=True, exist_ok=True)

    consolidated_json_path = get_json_path(out_dir)
    consolidated_txt_path = out_dir / "joakindex.txt"
    if not consolidated_txt_path.exists() and (out_dir / "classificacao_diplomas.txt").exists():
        consolidated_txt_path = out_dir / "classificacao_diplomas.txt"
    consolidated_db_path = get_db_path(out_dir)
    existing_by_md5 = {}

    # Inicializa banco SQLite (auto-migra do JSON consolidado caso o banco esteja vazio)
    init_database(consolidated_db_path, initial_json_path=consolidated_json_path)

    # 1. Carrega processamentos anteriores prioritariamente do SQLite
    count_from_db = 0
    count_from_consolidated = 0
    if not force:
        try:
            db_docs = get_all_documents(consolidated_db_path)
            if db_docs:
                for item in db_docs:
                    if isinstance(item, dict) and "md5" in item:
                        item.pop("data_criacao", None)
                        existing_by_md5[item["md5"]] = item
                        count_from_db += 1
            elif consolidated_json_path.exists():
                with open(consolidated_json_path, "r", encoding="utf-8") as f:
                    old_data = json.load(f)
                    if isinstance(old_data, list):
                        for item in old_data:
                            if isinstance(item, dict) and "md5" in item:
                                item.pop("data_criacao", None)
                                existing_by_md5[item["md5"]] = item
                                count_from_consolidated += 1
                        if old_data:
                            upsert_documents_batch(consolidated_db_path, old_data)
        except Exception as e:
            print(f"[Aviso] Não foi possível ler histórico do banco de dados: {e}")

    # 2. Carrega / reconcilia arquivos da pasta 'individuais'
    count_from_indiv = 0
    indiv_recovered = []
    if indiv_dir.exists() and not force:
        try:
            for entry in os.scandir(indiv_dir):
                if entry.is_file() and entry.name.endswith(".json") and not entry.name.startswith("."):
                    h = entry.name[:-5].lower()
                    if h not in existing_by_md5:
                        try:
                            with open(entry.path, "r", encoding="utf-8") as f:
                                item = json.load(f)
                                if isinstance(item, dict) and item.get("md5"):
                                    item.pop("data_criacao", None)
                                    existing_by_md5[item["md5"]] = item
                                    indiv_recovered.append(item)
                                    count_from_indiv += 1
                        except Exception:
                            continue
        except Exception as e:
            print(f"[Aviso] Erro ao ler pasta de arquivos individuais: {e}")

        if indiv_recovered:
            try:
                upsert_documents_batch(consolidated_db_path, indiv_recovered)
            except Exception:
                pass

    effective_model_name = getattr(client, "model", model_name)

    if existing_by_md5:
        details = []
        if count_from_db > 0:
            details.append(f"{count_from_db} do banco SQLite")
        elif count_from_consolidated > 0:
            details.append(f"{count_from_consolidated} do JSON consolidado")
        if count_from_indiv > 0:
            details.append(f"{count_from_indiv} recuperados da pasta individuais/")
        det_str = f" ({', '.join(details)})" if details else ""
        print(f"[*] Histórico carregado: {len(existing_by_md5)} documento(s) já classificados{det_str}.")

        if count_from_indiv > 0:
            save_consolidated_reports(existing_by_md5, out_dir, provider, effective_model_name)
            print(f"[*] Relatórios sincronizados com sucesso ({len(existing_by_md5)} documentos salvos).")

    # 3. Indexa hashes MD5 dos PDFs de entrada
    if stop_checker and stop_checker():
        return {
            "status": "interrompido",
            "total": len(pdf_files),
            "processed": 0,
            "already_done": len(existing_by_md5),
            "new_processed": 0,
            "sucessos": sum(1 for r in existing_by_md5.values() if r.get("status") == "sucesso"),
            "erros": sum(1 for r in existing_by_md5.values() if r.get("status") != "sucesso"),
            "results": list(existing_by_md5.values()),
            "json_path": str(consolidated_json_path),
            "txt_path": str(consolidated_txt_path),
            "mensagem": "Interrompido antes da indexação."
        }

    print(f"[*] Indexando e verificando integridade de {len(pdf_files)} PDF(s)...")
    notify({"event": "indexing", "total_files": len(pdf_files), "message": f"Indexando integridade de {len(pdf_files)} PDFs..."})

    pdf_meta_map = {}
    if len(pdf_files) > 20:
        workers_idx = min(16, (os.cpu_count() or 4) * 2)
        with ThreadPoolExecutor(max_workers=workers_idx) as executor:
            future_to_pdf = {executor.submit(get_file_metadata, p): p for p in pdf_files}
            iterator = as_completed(future_to_pdf)
            if use_tqdm and tqdm:
                iterator = tqdm(iterator, total=len(pdf_files), desc="Indexando PDFs (MD5)", unit="doc")
            for idx_i, fut in enumerate(iterator, 1):
                if stop_checker and stop_checker():
                    executor.shutdown(wait=False, cancel_futures=True)
                    return {
                        "status": "interrompido",
                        "total": len(pdf_files),
                        "processed": 0,
                        "already_done": len(existing_by_md5),
                        "new_processed": 0,
                        "sucessos": sum(1 for r in existing_by_md5.values() if r.get("status") == "sucesso"),
                        "erros": sum(1 for r in existing_by_md5.values() if r.get("status") != "sucesso"),
                        "results": list(existing_by_md5.values()),
                        "json_path": str(consolidated_json_path),
                        "txt_path": str(consolidated_txt_path),
                        "mensagem": "Interrompido durante a indexação."
                    }
                p = future_to_pdf[fut]
                try:
                    pdf_meta_map[p] = fut.result()
                except Exception:
                    pdf_meta_map[p] = {"md5": "", "data_modificacao": "", "autor": None}
                if idx_i % 25 == 0:
                    notify({"event": "indexing_progress", "indexed": idx_i, "total": len(pdf_files)})
    else:
        for p in pdf_files:
            try:
                pdf_meta_map[p] = get_file_metadata(p)
            except Exception:
                pdf_meta_map[p] = {"md5": "", "data_modificacao": "", "autor": None}

    # 4. Separa os arquivos entre já processados e novos/pendentes
    files_to_process = []
    already_done_results = []
    ocr_candidate_count = 0
    seen_md5_to_process = set()

    for pdf in pdf_files:
        meta = pdf_meta_map.get(pdf) or get_file_metadata(pdf)
        h = meta.get("md5", "")
        if not h:
            files_to_process.append(pdf)
            continue

        if h in existing_by_md5 and not force:
            item = existing_by_md5[h]
            # Respeita sempre aprovação manual humana
            if item.get("status_conferencia") == "aprovado":
                already_done_results.append(item)
                continue

            # Se o usuário solicitou reprocessamento de OCR (--reprocess-ocr / Opção 2)
            if reprocess_ocr:
                tipo_atual = (item.get("tipo_documento") or "").strip().lower()
                tipo_nao_identificado = (not tipo_atual) or tipo_atual in [
                    "não identificado", "nao identificado", "outro", "não informado", "nao informado"
                ]
                cpf_item = item.get("cpf")
                cpf_invalido = bool(cpf_item and not is_valid_cpf_syntax(cpf_item))
                teve_tentativa_ocr = item.get("tentativa_ocr_llm", False)
                teve_erro_ocr = (item.get("status") == "erro") and ("OCR" in (item.get("erro") or ""))

                precisa_ocr = (teve_erro_ocr or ((tipo_nao_identificado or cpf_invalido) and not teve_tentativa_ocr))

                if not skip_ocr and precisa_ocr:
                    if h not in seen_md5_to_process:
                        files_to_process.append(pdf)
                        seen_md5_to_process.add(h)
                    ocr_candidate_count += 1
                else:
                    already_done_results.append(item)
            else:
                # Modo Incremental padrão
                if item.get("status") == "sucesso":
                    already_done_results.append(item)
                else:
                    if h not in seen_md5_to_process:
                        files_to_process.append(pdf)
                        seen_md5_to_process.add(h)
        else:
            if h not in seen_md5_to_process:
                files_to_process.append(pdf)
                seen_md5_to_process.add(h)

    if ocr_candidate_count > 0:
        print(f"[*] Identificados {ocr_candidate_count} documento(s) elegíveis para OCR via LLM (erros de leitura, tipo não identificado ou CPF com sintaxe errada).")

    print(f"[*] Total de PDFs: {len(pdf_files)} | Já concluídos: {len(already_done_results)} | A processar: {len(files_to_process)}")
    notify({
        "event": "ready",
        "total_files": len(pdf_files),
        "already_done": len(already_done_results),
        "to_process": len(files_to_process),
        "ocr_candidates": ocr_candidate_count,
        "message": f"Pronto. {len(files_to_process)} a processar, {len(already_done_results)} já concluídos."
    })

    # Mantém um dicionário global unificado com todo o histórico acumulado
    active_results = dict(existing_by_md5)
    new_results = []
    processed_count = 0
    success_count = 0
    error_count = 0
    save_interval = 10
    was_stopped = False

    # Inicialização do Cliente Cloud para Modo Híbrido se ativo
    hybrid_cloud_client = None
    if hybrid:
        cloud_key = hybrid_openai_key or openai_key or os.environ.get("OPENAI_API_KEY")
        if not cloud_key:
            print("[*] [Aviso Híbrido] Modo híbrido ativado, mas nenhuma chave da OpenAI foi configurada. Modo híbrido desativado.")
            hybrid = False
        else:
            cloud_mod = hybrid_cloud_model or "gpt-4o-mini"
            cloud_base = hybrid_openai_base_url or openai_base_url or os.environ.get("OPENAI_BASE_URL")
            print(f"[*] [Modo Híbrido Ativado] Fallback configurado para OpenAI ({cloud_mod}).")
            try:
                hybrid_cloud_client = OpenAIClient(
                    model=cloud_mod,
                    api_key=cloud_key,
                    base_url=cloud_base
                )
            except Exception as ex_init_h:
                print(f"[*] [Aviso Híbrido] Falha ao inicializar cliente de fallback OpenAI ({ex_init_h}). Modo híbrido desativado.")
                hybrid = False

    if provider == "ollama" and workers > 2:
        print(f"[*] [Dica de Performance] Executando Ollama local com {workers} workers. Em GPUs domésticas (12GB VRAM), recomenda-se 1 ou 2 workers para evitar fila de inferência.")

    if files_to_process:
        print(f"[*] Iniciando classificação de {len(files_to_process)} documento(s) com {workers} worker(s)...")
        notify({"event": "start_batch", "to_process": len(files_to_process), "workers": workers})

        def handle_file(pdf: Path):
            meta = pdf_meta_map.get(pdf) or get_file_metadata(pdf)
            h = meta.get("md5")
            old_item = existing_by_md5.get(h)

            res = process_single_pdf(
                pdf,
                client,
                max_pages=max_pages,
                skip_ocr=skip_ocr,
                metadata=meta,
                hybrid=hybrid,
                hybrid_cloud_client=hybrid_cloud_client
            )

            # Preserva metadados de conferência humana caso já existissem
            if old_item:
                if "status_conferencia" in old_item:
                    res["status_conferencia"] = old_item["status_conferencia"]
                if "observacoes_conferencia" in old_item:
                    res["observacoes_conferencia"] = old_item["observacoes_conferencia"]
                if "conferido_em" in old_item:
                    res["conferido_em"] = old_item["conferido_em"]

            res.pop("data_criacao", None)
            if not no_individual:
                file_identifier = res["md5"]
                single_json_path = indiv_dir / f"{file_identifier}.json"
                tmp_single_json = indiv_dir / f".{file_identifier}.json.tmp"
                try:
                    with open(tmp_single_json, "w", encoding="utf-8") as f:
                        json.dump(res, f, ensure_ascii=False, indent=2)
                    tmp_single_json.replace(single_json_path)
                except Exception as e:
                    print(f"[Aviso] Falha ao gravar {single_json_path.name}: {e}")

                single_txt_path = indiv_dir / f"{file_identifier}.txt"
                tmp_single_txt = indiv_dir / f".{file_identifier}.txt.tmp"
                try:
                    with open(tmp_single_txt, "w", encoding="utf-8") as f:
                        f.write(format_single_txt(res))
                    tmp_single_txt.replace(single_txt_path)
                except Exception as e:
                    print(f"[Aviso] Falha ao gravar {single_txt_path.name}: {e}")

            # Persiste imediatamente no SQLite para garantia ACID e tolerância a falhas
            try:
                upsert_document(consolidated_db_path, res)
            except Exception as e_up:
                print(f"[Aviso] Falha ao persistir no SQLite ({res.get('md5')}): {e_up}")

            return res

        if workers > 1:
            executor = ThreadPoolExecutor(max_workers=workers)
            try:
                future_to_file = {executor.submit(handle_file, f): f for f in files_to_process}
                iterator = as_completed(future_to_file)
                if use_tqdm and tqdm:
                    iterator = tqdm(iterator, total=len(files_to_process), desc="Processando Novos PDFs", unit="doc")
                for future in iterator:
                    if stop_checker and stop_checker():
                        print("\n[!] Interrupção solicitada pelo usuário. Encerrando lote...")
                        was_stopped = True
                        executor.shutdown(wait=False, cancel_futures=True)
                        break

                    try:
                        res = future.result()
                        new_results.append(res)
                        active_results[res["md5"]] = res
                        processed_count += 1
                        if res.get("status") == "sucesso":
                            success_count += 1
                        else:
                            error_count += 1

                        cur_file = future_to_file[future].name
                        notify({
                            "event": "file_done",
                            "current_file": cur_file,
                            "processed_count": processed_count,
                            "to_process_count": len(files_to_process),
                            "total_files": len(pdf_files),
                            "success_count": success_count,
                            "error_count": error_count,
                            "item": res
                        })

                        if processed_count % save_interval == 0:
                            save_consolidated_reports(active_results, out_dir, provider, effective_model_name)
                            notify({"event": "periodic_save", "total_saved": len(active_results)})
                    except Exception as e:
                        error_count += 1
                        print(f"[Erro no processamento de arquivo] {e}")
            except KeyboardInterrupt:
                print("\n\n[!] Interrupção solicitada pelo usuário (Ctrl+C). Cancelando fila e salvando dados...")
                executor.shutdown(wait=False, cancel_futures=True)
                was_stopped = True
            finally:
                executor.shutdown(wait=False)
        else:
            iterator = files_to_process
            if use_tqdm and tqdm:
                iterator = tqdm(files_to_process, desc="Processando Novos PDFs", unit="doc")
            try:
                for f in iterator:
                    if stop_checker and stop_checker():
                        print("\n[!] Interrupção solicitada pelo usuário. Encerrando lote...")
                        was_stopped = True
                        break

                    try:
                        notify({"event": "file_start", "current_file": f.name})
                        res = handle_file(f)
                        new_results.append(res)
                        active_results[res["md5"]] = res
                        processed_count += 1
                        if res.get("status") == "sucesso":
                            success_count += 1
                        else:
                            error_count += 1

                        notify({
                            "event": "file_done",
                            "current_file": f.name,
                            "processed_count": processed_count,
                            "to_process_count": len(files_to_process),
                            "total_files": len(pdf_files),
                            "success_count": success_count,
                            "error_count": error_count,
                            "item": res
                        })

                        if processed_count % save_interval == 0:
                            save_consolidated_reports(active_results, out_dir, provider, effective_model_name)
                            notify({"event": "periodic_save", "total_saved": len(active_results)})
                    except Exception as e:
                        error_count += 1
                        print(f"[Erro no processamento do arquivo {f.name}] {e}")
            except KeyboardInterrupt:
                print("\n\n[!] Interrupção solicitada pelo usuário (Ctrl+C). Salvando dados...")
                was_stopped = True
    else:
        print("[*] Todos os documentos já estão atualizados no banco de dados!")
        notify({"event": "up_to_date", "message": "Todos os documentos já estão atualizados."})

    # Gravação final consolidada
    save_consolidated_reports(active_results, out_dir, provider, effective_model_name)
    results = sorted(list(active_results.values()), key=lambda x: str(x.get("md5", "")))
    sucessos_totais = sum(1 for r in results if r.get("status") == "sucesso")
    erros_totais = len(results) - sucessos_totais

    if was_stopped:
        print(f"[✓] Progresso salvo com sucesso! ({len(active_results)} documentos totais no consolidado e individuais)")
        print("[*] Você pode retomar a qualquer momento escolhendo a Opção 1 (Incremental).")
        notify({
            "event": "stopped",
            "message": f"Processamento interrompido. {processed_count} novos processados. Total consolidado: {len(active_results)}.",
            "processed_count": processed_count,
            "total_files": len(pdf_files),
            "sucessos": sucessos_totais,
            "erros": erros_totais
        })
        return {
            "status": "interrompido",
            "total": len(pdf_files),
            "processed": processed_count,
            "already_done": len(already_done_results),
            "new_processed": len(new_results),
            "sucessos": sucessos_totais,
            "erros": erros_totais,
            "results": results,
            "json_path": str(consolidated_json_path),
            "db_path": str(consolidated_db_path),
            "txt_path": str(consolidated_txt_path),
            "mensagem": "Processamento interrompido pelo usuário."
        }

    print("\n" + "=" * 60)
    print("PROCESSAMENTO CONCLUÍDO COM SUCESSO!")
    print(f"Total processados : {len(results)}")
    print(f"Classificados OK  : {sucessos_totais}")
    print(f"Erros             : {erros_totais}")
    print("-" * 60)
    print(f"Banco SQLite consolidado   : {consolidated_db_path}")
    print(f"Relatório JSON consolidado : {consolidated_json_path}")
    print(f"Relatório TXT consolidado  : {consolidated_txt_path}")
    if not no_individual:
        print(f"Arquivos individuais (MD5) : {indiv_dir}/")
    print("=" * 60 + "\n")

    notify({
        "event": "completed",
        "message": f"Processamento concluído com sucesso! {len(results)} documentos consolidados.",
        "total_files": len(pdf_files),
        "processed_count": processed_count,
        "sucessos": sucessos_totais,
        "erros": erros_totais
    })

    return {
        "status": "sucesso",
        "total": len(pdf_files),
        "processed": processed_count,
        "already_done": len(already_done_results),
        "new_processed": len(new_results),
        "sucessos": sucessos_totais,
        "erros": erros_totais,
        "results": results,
        "json_path": str(consolidated_json_path),
        "db_path": str(consolidated_db_path),
        "txt_path": str(consolidated_txt_path),
        "mensagem": "Processamento concluído com sucesso!"
    }
