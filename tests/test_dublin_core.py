import zipfile
from joakindex import extract_file_dublin_core


def test_extract_dublin_core_nonexistent():
    res = extract_file_dublin_core("/caminho/inexistente/arquivo_falso.pdf")
    assert res == {}


def test_extract_dublin_core_pdf(tmp_path):
    import pypdf
    writer = pypdf.PdfWriter()
    writer.add_blank_page(width=72, height=72)
    writer.add_metadata({
        "/Title": "Documento Teste JoaKinDeX",
        "/Author": "Joaquim Neto",
        "/Subject": "Conferencia Documental",
        "/Creator": "JoaKinDeX Test Suite"
    })
    pdf_path = tmp_path / "test_meta.pdf"
    with open(pdf_path, "wb") as f:
        writer.write(f)

    res = extract_file_dublin_core(pdf_path)
    assert isinstance(res, dict)
    assert res.get("title") == "Documento Teste JoaKinDeX"
    assert res.get("creator") == "Joaquim Neto"
    assert res.get("subject") == "Conferencia Documental"
    assert res.get("creator_tool") == "JoaKinDeX Test Suite"


def test_extract_dublin_core_docx(tmp_path):
    docx_path = tmp_path / "documento.docx"
    core_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
    <cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties"
                       xmlns:dc="http://purl.org/dc/elements/1.1/">
        <dc:title>Artigo Jurídico</dc:title>
        <dc:creator>Dr. Joaquim</dc:creator>
        <dc:subject>Direito Civil</dc:subject>
    </cp:coreProperties>
    """
    with zipfile.ZipFile(docx_path, "w") as z:
        z.writestr("docProps/core.xml", core_xml)

    res = extract_file_dublin_core(docx_path)
    assert isinstance(res, dict)
    assert res.get("title") == "Artigo Jurídico"
    assert res.get("creator") == "Dr. Joaquim"
    assert res.get("subject") == "Direito Civil"
