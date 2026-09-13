#!/usr/bin/env python3
"""
JoaKinDeX - Gerador de Relatório Executivo de Auditoria e Estatísticas Gerenciais
Criado por: Joaquim Ferreira Silva Neto <joaquimfsneto@gmail.com>

Gera relatórios executivos em formato PDF e dados analíticos consolidados
para o dashboard com métricas de conformidade, valores financeiros e status de conferência.
"""

import os
import re
from pathlib import Path
from typing import Dict, Any, List, Optional, Union, Tuple
from collections import Counter
from datetime import datetime

from joakindex.db import get_connection, get_all_documents, row_to_doc

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable, KeepTogether
    )
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    HAS_REPORTLAB = True
except ImportError:
    HAS_REPORTLAB = False


def _parse_monetary_value(val_str: Optional[str]) -> float:
    """Converte strings monetárias brasileiras (ex: 'R$ 1.250,50' ou '450.00') para float."""
    if not val_str:
        return 0.0
    clean = re.sub(r"[^\d,\.]", "", str(val_str))
    if not clean:
        return 0.0
    try:
        if "," in clean and "." in clean:
            clean = clean.replace(".", "").replace(",", ".")
        elif "," in clean:
            clean = clean.replace(",", ".")
        return float(clean)
    except Exception:
        return 0.0


def get_management_statistics(db_path: Union[str, Path]) -> Dict[str, Any]:
    """
    Calcula todas as estatísticas e métricas analíticas para o Dashboard Gerencial.
    """
    db = Path(db_path).expanduser().resolve()
    docs = get_all_documents(db)
    total_docs = len(docs)
    if total_docs == 0:
        return {
            "total_docs": 0,
            "total_financeiro_reais": 0.0,
            "total_financeiro_fmt": "R$ 0,00",
            "classes_distribuicao": {},
            "status_conferencia": {},
            "dominios": {},
            "assinaturas_count": 0,
            "nativos_digitais_count": 0,
            "duplicatas_count": 0,
            "confiabilidade": {"alta": 0, "media": 0, "baixa": 0}
        }

    classes = Counter()
    status_conf = Counter()
    dominios = Counter()
    total_financeiro = 0.0
    assinaturas_count = 0
    nativos_count = 0
    duplicatas_count = 0
    conf_alta = 0
    conf_media = 0
    conf_baixa = 0

    for d in docs:
        c = d.get("tipo_documento") or "Não identificado"
        classes[c] += 1

        sc = d.get("status_conferencia") or "pendente"
        status_conf[sc] += 1

        dom = d.get("dominio") or "academico"
        dominios[dom] += 1

        if d.get("tem_assinatura_digital"):
            assinaturas_count += 1
        if d.get("eh_nativo_digital"):
            nativos_count += 1
        if d.get("duplicata_de"):
            duplicatas_count += 1

        val = _parse_monetary_value(d.get("valor_monetario"))
        total_financeiro += val

        # Confiabilidade heurística
        if d.get("erro") or c in ["Não identificado", "Desconhecido"]:
            conf_baixa += 1
        elif d.get("metodo_leitura") == "texto_digital" or d.get("status_conferencia") == "aprovado":
            conf_alta += 1
        else:
            conf_media += 1

    return {
        "total_docs": total_docs,
        "total_financeiro_reais": round(total_financeiro, 2),
        "total_financeiro_fmt": f"R$ {total_financeiro:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."),
        "classes_distribuicao": dict(classes.most_common()),
        "status_conferencia": dict(status_conf),
        "dominios": dict(dominios),
        "assinaturas_count": assinaturas_count,
        "nativos_digitais_count": nativos_count,
        "duplicatas_count": duplicatas_count,
        "confiabilidade": {
            "alta": conf_alta,
            "media": conf_media,
            "baixa": conf_baixa
        }
    }


def generate_executive_audit_report(
    db_path: Union[str, Path],
    output_pdf_path: Union[str, Path]
) -> Path:
    """
    Gera o Relatório Executivo de Auditoria em formato PDF com layout de alta fidelidade.
    """
    stats = get_management_statistics(db_path)
    out_path = Path(output_pdf_path).expanduser().resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if not HAS_REPORTLAB:
        raise RuntimeError("ReportLab não está instalado para gerar o relatório PDF.")

    doc = SimpleDocTemplate(
        str(out_path),
        pagesize=A4,
        leftMargin=40,
        rightMargin=40,
        topMargin=40,
        bottomMargin=40
    )

    styles = getSampleStyleSheet()
    primary_color = colors.HexColor("#0f172a")  # Slate 900
    brand_blue = colors.HexColor("#2563eb")     # Blue 600
    gray_bg = colors.HexColor("#f8fafc")        # Slate 50
    gray_border = colors.HexColor("#cbd5e1")    # Slate 300

    title_style = ParagraphStyle(
        "ReportTitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=20,
        leading=24,
        textColor=primary_color
    )
    subtitle_style = ParagraphStyle(
        "ReportSubtitle",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=11,
        leading=15,
        textColor=colors.HexColor("#64748b")
    )
    h2_style = ParagraphStyle(
        "ReportH2",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=13,
        leading=17,
        textColor=brand_blue,
        spaceBefore=14,
        spaceAfter=6
    )
    cell_style = ParagraphStyle(
        "CellText",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=12,
        textColor=primary_color
    )
    cell_bold = ParagraphStyle(
        "CellBold",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=9,
        leading=12,
        textColor=primary_color
    )

    story = []

    # Cabeçalho Principal
    story.append(Paragraph("JoaKinDeX • Relatório Executivo de Auditoria", title_style))
    story.append(Paragraph(f"Responsável Técnico: Joaquim Ferreira Silva Neto | Emissão: {datetime.now().strftime('%d/%m/%Y às %H:%M')}", subtitle_style))
    story.append(Spacer(1, 10))
    story.append(HRFlowable(width="100%", thickness=1.5, color=brand_blue, spaceBefore=4, spaceAfter=14))

    # Tabela de KPIs Principais
    total_docs = stats["total_docs"]
    total_fin = stats["total_financeiro_fmt"]
    conf = stats["confiabilidade"]
    pct_alta = round((conf["alta"] / total_docs * 100), 1) if total_docs else 0

    kpi_data = [
        [
            Paragraph("<b>Total de Documentos</b>", cell_style),
            Paragraph("<b>Volume Financeiro Total</b>", cell_style),
            Paragraph("<b>Índice de Confiabilidade</b>", cell_style),
            Paragraph("<b>Assinaturas ICP-Brasil</b>", cell_style)
        ],
        [
            Paragraph(f"<font size=14 color='#2563eb'><b>{total_docs}</b></font>", cell_style),
            Paragraph(f"<font size=14 color='#16a34a'><b>{total_fin}</b></font>", cell_style),
            Paragraph(f"<font size=14 color='#0284c7'><b>{pct_alta}% Alta</b></font>", cell_style),
            Paragraph(f"<font size=14 color='#7c3aed'><b>{stats['assinaturas_count']} docs</b></font>", cell_style)
        ]
    ]
    t_kpi = Table(kpi_data, colWidths=[125, 140, 130, 120])
    t_kpi.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), gray_bg),
        ('BOX', (0, 0), (-1, -1), 1, gray_border),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, gray_border),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
    ]))
    story.append(t_kpi)
    story.append(Spacer(1, 14))

    # Distribuição por Classes Documentais
    story.append(Paragraph("1. Distribuição Analítica por Classe Documental", h2_style))
    classes_rows = [
        [Paragraph("<b>Tipo de Documento / Classe</b>", cell_bold), Paragraph("<b>Qtd.</b>", cell_bold), Paragraph("<b>% do Lote</b>", cell_bold)]
    ]
    for c_name, count in list(stats["classes_distribuicao"].items())[:15]:
        pct = round((count / total_docs * 100), 1) if total_docs else 0
        classes_rows.append([
            Paragraph(str(c_name), cell_style),
            Paragraph(str(count), cell_style),
            Paragraph(f"{pct}%", cell_style)
        ])

    t_classes = Table(classes_rows, colWidths=[315, 100, 100])
    t_classes.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#e2e8f0")),
        ('BOX', (0, 0), (-1, -1), 1, gray_border),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(t_classes)
    story.append(Spacer(1, 14))

    # Seção de Status e Duplicatas
    story.append(Paragraph("2. Status de Conferência e Integridade do Acervo", h2_style))
    status_rows = [
        [Paragraph("<b>Métrica de Governança</b>", cell_bold), Paragraph("<b>Resultado / Volume</b>", cell_bold), Paragraph("<b>Observação Técnica</b>", cell_bold)],
        [Paragraph("Documentos Nativos Digitais", cell_style), Paragraph(str(stats["nativos_digitais_count"]), cell_style), Paragraph("Camada digital original preservada", cell_style)],
        [Paragraph("Documentos Escaneados (OCR)", cell_style), Paragraph(str(total_docs - stats["nativos_digitais_count"]), cell_style), Paragraph("Processados via OCR Tesseract / LLM Vision", cell_style)],
        [Paragraph("Possíveis Duplicatas Detectadas", cell_style), Paragraph(str(stats["duplicatas_count"]), cell_style), Paragraph("Requer conferência para evitar pagamento/arquivamento duplo", cell_style)],
        [Paragraph("Documentos com Baixa Confiança", cell_style), Paragraph(str(conf["baixa"]), cell_style), Paragraph("Sugerida revisão humana no visualizador", cell_style)],
    ]
    t_status = Table(status_rows, colWidths=[180, 115, 220])
    t_status.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#e2e8f0")),
        ('BOX', (0, 0), (-1, -1), 1, gray_border),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(t_status)
    story.append(Spacer(1, 20))

    # Rodapé de Encerramento
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#cbd5e1"), spaceBefore=10, spaceAfter=8))
    story.append(Paragraph(
        "<i>Este relatório foi consolidado automaticamente pelo motor de inteligência JoaKinDeX v2.0 com integridade referencial SQLite WAL.</i>",
        subtitle_style
    ))

    doc.build(story)
    return out_path
