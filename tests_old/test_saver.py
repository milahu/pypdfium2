# SPDX-FileCopyrightText: 2023 geisserml <geisserml@gmail.com>
# SPDX-License-Identifier: Apache-2.0 OR BSD-3-Clause

import io
import pypdfium2 as pdfium
import pypdfium2.raw as pdfium_r
from .conftest import TestFiles, OutputDir


def test_save():
    
    src_pdf = pdfium.PdfDocument(TestFiles.multipage)
    new_pdf_raw = pdfium_r.FPDF_ImportNPagesToOne(
        src_pdf.raw,
        595, 842,
        2, 2,
    )
    
    new_pdf = pdfium.PdfDocument(new_pdf_raw)
    assert len(new_pdf) == 1
    page = new_pdf[0]
    assert page.get_size() == (595, 842)
    
    output_file = OutputDir / "tiling.pdf"
    new_pdf.save(output_file)
    assert output_file.exists()
    

def test_save_withversion():
    
    pdf = pdfium.PdfDocument(TestFiles.multipage)
    pre_id_p = pdf.get_identifier(pdfium_r.FILEIDTYPE_PERMANENT)
    pre_id_c = pdf.get_identifier(pdfium_r.FILEIDTYPE_CHANGING)
    assert isinstance(pre_id_p, bytes)
    pdf.del_page(1)
    
    buffer = io.BytesIO()
    pdf.save(buffer, version=17)
    
    buffer.seek(0)
    data = buffer.read()
    buffer.seek(0)
    
    exp_start = b"%PDF-1.7"
    exp_end = b"%EOF\r\n"
    assert data[:len(exp_start)] == exp_start
    assert data[-len(exp_end):] == exp_end
    
    reopened_pdf = pdfium.PdfDocument(buffer, autoclose=True)
    assert len(reopened_pdf) == 2
    
    post_id_p = reopened_pdf.get_identifier(pdfium_r.FILEIDTYPE_PERMANENT)
    post_id_c = reopened_pdf.get_identifier(pdfium_r.FILEIDTYPE_CHANGING)
    assert pre_id_p == post_id_p
    assert pre_id_c != post_id_c
