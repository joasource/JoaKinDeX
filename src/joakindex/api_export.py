#!/usr/bin/env python3
"""
JoaKinDeX - API de Exportação Relacional Estruturada
Criado por: Joaquim Ferreira Silva Neto <joaquimfsneto@gmail.com>

Rota HTTP que expõe o export relacional (pessoas físicas, pessoas jurídicas,
endereços, documentos e vínculos) como um ZIP de 5 CSVs, gerado a partir do
banco SQLite inteiro.
"""

__project__ = "JoaKinDeX"
__author__ = "Joaquim Ferreira Silva Neto"
__email__ = "joaquimfsneto@gmail.com"
__version__ = "1.0.0"

from datetime import datetime

from joakindex.export_relacional import build_export_zip


def handle_get_export_relacional_zip(handler, server_ctx, parsed):
    try:
        zip_buffer = build_export_zip(server_ctx.db_path)
    except Exception as e:
        handler.send_error(500, f"Erro ao gerar exportação relacional: {e}")
        return
    zip_bytes = zip_buffer.getvalue()
    handler.send_response(200)
    handler.send_header("Content-Type", "application/zip")
    handler.send_header(
        "Content-Disposition",
        f'attachment; filename="joakindex_export_relacional_{datetime.now().strftime("%Y%m%d_%H%M%S")}.zip"',
    )
    handler.send_header("Content-Length", str(len(zip_bytes)))
    handler.end_headers()
    handler.wfile.write(zip_bytes)
