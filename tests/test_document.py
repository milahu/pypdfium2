# SPDX-FileCopyrightText: 2023 geisserml <geisserml@gmail.com>
# SPDX-License-Identifier: Apache-2.0 OR BSD-3-Clause

import re
import os
import mmap
import ctypes
import pathlib
import pytest
from .conftest import TestResources

import pypdfium2 as pdfium
import pypdfium2.raw as pdfium_c


parametrize_opener_files = pytest.mark.parametrize("input", [TestResources.empty])


def _check_pdf(pdf):
    
    # call a few methods to confirm document was opened correctly
    
    n_pages = len(pdf)
    assert n_pages > 0
    assert pdf.get_version() > 10
    assert isinstance(pdf.get_identifier(), bytes)
    
    for i in range(n_pages):
        page = pdf[i]
        assert page.get_size() == pdf.get_page_size(i)
        page.close()


@parametrize_opener_files
def test_open_path(input):
    assert isinstance(input, pathlib.Path)
    pdf = pdfium.PdfDocument(input)
    _check_pdf(pdf)
    assert pdf._data_holder == []
    assert pdf._data_closer == []


@parametrize_opener_files
def test_open_str(input):
    input = str(input)
    assert isinstance(input, str)
    pdf = pdfium.PdfDocument(input)
    _check_pdf(pdf)
    assert pdf._data_holder == []
    assert pdf._data_closer == []


@parametrize_opener_files
def test_open_bytes(input):
    input = input.read_bytes()
    assert isinstance(input, bytes)
    pdf = pdfium.PdfDocument(input)
    _check_pdf(pdf)
    assert pdf._data_holder == [input]
    assert pdf._data_closer == []


@parametrize_opener_files
def test_open_ctypes_array(input):
    buffer = input.open("rb")
    buffer.seek(0, os.SEEK_END)
    length = buffer.tell()
    buffer.seek(0)
    
    input = (ctypes.c_ubyte * length)()
    buffer.readinto(input)
    assert isinstance(input, ctypes.Array)
    
    pdf = pdfium.PdfDocument(input)
    _check_pdf(pdf)
    assert pdf._data_holder == [input]
    assert pdf._data_closer == []


@parametrize_opener_files
def test_open_bytearray(input):
    input = bytearray(input.read_bytes())
    assert isinstance(input, bytearray)
    pdf = pdfium.PdfDocument(input)
    _check_pdf(pdf)
    assert isinstance(pdf._input, ctypes.Array)
    assert pdf._data_holder == [pdf._input]
    assert pdf._data_closer == []


@parametrize_opener_files
def test_open_memoryview_writable(input):
    input = memoryview(bytearray( input.read_bytes() ))
    assert isinstance(input, memoryview)
    assert not input.readonly
    pdf = pdfium.PdfDocument(input)
    _check_pdf(pdf)
    assert isinstance(pdf._input, ctypes.Array)
    assert pdf._data_holder == [pdf._input]
    assert pdf._data_closer == []


@parametrize_opener_files
def test_open_memoryview_readonly(input):
    input = memoryview(input.read_bytes())
    assert isinstance(input, memoryview)
    assert input.readonly
    pdf = pdfium.PdfDocument(input)
    _check_pdf(pdf)
    assert isinstance(pdf._input, bytes)
    assert pdf._data_holder == [pdf._input]
    assert pdf._data_closer == []


@parametrize_opener_files
def test_open_mmap(input):
    fh = input.open("r+b")
    input = mmap.mmap(fh.fileno(), 0)
    assert isinstance(input, mmap.mmap)
    pdf = pdfium.PdfDocument(input)
    _check_pdf(pdf)
    assert len(pdf._data_holder) == 1
    assert pdf._data_closer == []


@parametrize_opener_files
@pytest.mark.parametrize("autoclose", [False, True])
def test_open_buffer(input, autoclose):
    input = input.open("rb")
    pdf = pdfium.PdfDocument(input, autoclose=autoclose)
    assert len(pdf._data_holder) == 1
    _check_pdf(pdf)
    assert pdf._data_closer == [input] if autoclose else pdf._data_closer == []
    pdf.close()
    assert input.closed == autoclose


def test_open_raw():
    # not meant for embedders, but works for testing all the same
    pdf = pdfium.PdfDocument(TestResources.empty)
    pdf._finalizer.detach()
    input = pdf.raw
    assert isinstance(input, pdfium_c.FPDF_DOCUMENT)
    pdf_new = pdfium.PdfDocument(input)
    _check_pdf(pdf_new)


def test_open_new():
    pdf = pdfium.PdfDocument.new()
    assert len(pdf) == 0
    size = (595, 842)
    page = pdf.new_page(*size)
    assert len(pdf) == 1
    assert page.get_size() == pdf.get_page_size(0) == size


def _make_encryption_cases(file, passwords):
    input_makers = (
        lambda: file,
        lambda: file.read_bytes(),
        lambda: file.open("rb"),
    )
    for i, pwd in enumerate(passwords):
        for j, maker in enumerate(input_makers):
            # set explicit ID to prevent pytest from printing the whole bytes object
            yield pytest.param(maker(), pwd, id="pwd%s-input%s" % (i, j))


@pytest.mark.parametrize(
    ["input", "password"],
    _make_encryption_cases(TestResources.encrypted, ["test_user", "test_owner"]),
)
def test_open_encrypted(input, password):
    pdf = pdfium.PdfDocument(input, password, autoclose=True)
    _check_pdf(pdf)


@pytest.mark.parametrize(
    ["input", "password"],
    _make_encryption_cases(TestResources.empty, ["superfluous"]),
)
def test_open_with_excessive_password(input, password):
    pdf = pdfium.PdfDocument(input, password, autoclose=True)
    _check_pdf(pdf)


def test_open_invalid():
    with pytest.raises(TypeError):
        pdf = pdfium.PdfDocument(123)
    with pytest.raises(FileNotFoundError):
        pdf = pdfium.PdfDocument("invalid/path")
    with pytest.raises(pdfium.PdfiumError, match=re.escape("Failed to load document (PDFium: Incorrect password error).")):
        pdf = pdfium.PdfDocument(TestResources.encrypted, password="wrong_password")


def test_misc():
    pdf = pdfium.PdfDocument(TestResources.empty)
    assert pdf.get_formtype() == pdfium_c.FORMTYPE_NONE
    assert pdf.get_version() == 15
    assert pdf.get_identifier(pdfium_c.FILEIDTYPE_PERMANENT) == b"\xec\xe5!\x04\xd6\x1b(R\x1a\x89f\x85\n\xbe\xa4"
    assert pdf.get_identifier(pdfium_c.FILEIDTYPE_CHANGING) == b"\xec\xe5!\x04\xd6\x1b(R\x1a\x89f\x85\n\xbe\xa4"
    assert pdf.get_pagemode() == pdfium_c.PAGEMODE_USENONE
    page = pdf[0]
    assert pdf.get_page_size(0) == page.get_size()
    assert pdf.get_page_label(0) == ""


def test_page_labels():
    # incidentally, it happens that this TOC test file also has page labels
    pdf = pdfium.PdfDocument(TestResources.toc_viewmodes)
    exp_labels = ["i", "ii", "appendix-C", "appendix-D", "appendix-E", "appendix-F", "appendix-G", "appendix-H"]
    assert exp_labels == [pdf.get_page_label(i) for i in range(len(pdf))]


def _compare_metadata(pdf, metadata, exp_metadata):
    all_keys = pdfium.PdfDocument.METADATA_KEYS
    assert all_keys == ("Title", "Author", "Subject", "Keywords", "Creator", "Producer", "CreationDate", "ModDate")
    assert len(metadata) == len(all_keys)
    assert all(k in metadata for k in all_keys)
    for k in all_keys:
        assert metadata[k] == pdf.get_metadata_value(k)
        if k in exp_metadata:
            assert metadata[k] == exp_metadata[k]
        else:
            assert metadata[k] == ""


def test_metadata_dict():
    pdf = pdfium.PdfDocument(TestResources.empty)
    metadata = pdf.get_metadata_dict()
    exp_metadata = {
        "Producer": "LibreOffice 6.4",
        "Creator": "Writer",
        "CreationDate": "D:20220520145414+02'00'",
    }
    _compare_metadata(pdf, metadata, exp_metadata)


@pytest.mark.parametrize(
    "new_pages",
    [
        [ (210, 298), (420, 595) ]
    ]
)
def test_new_page_on_new_pdf(new_pages):
    pdf = pdfium.PdfDocument.new()
    for i, size in enumerate(new_pages):
        page = pdf.new_page(*size)
        assert page.get_size() == pdf.get_page_size(i) == size


@pytest.mark.parametrize(
    "new_pages",
    [
        [ [0, (210, 298)], [2, (420, 595)], [None, (842, 1190)] ]
    ]
)
def test_new_page_on_existing_pdf(new_pages):
    pdf = pdfium.PdfDocument(TestResources.multipage)
    for index, size in new_pages:
        page = pdf.new_page(*size, index=index)
        if index is None:
            index = len(pdf) - 1
        assert page.get_size() == pdf.get_page_size(index) == size
    

def test_del_page():
    pass


ImportTestSequence = [
    (TestResources.empty, None, None, 1),
    (TestResources.empty, "", 0, 1),
    (TestResources.multipage, [1, 0, 1, 2, 1], 1, 5),
    (TestResources.multipage, "2,1-3, 2", 4, 5),
]

@pytest.mark.parametrize("sequence", [ImportTestSequence])
def test_import_pages(sequence):
    dest_pdf = pdfium.PdfDocument.new()
    exp_len = 0
    for args in sequence:
        resource, pages, index, n_pages = args
        src_pdf = pdfium.PdfDocument(resource)
        dest_pdf.import_pages(src_pdf, pages=pages, index=index)
        exp_len += n_pages
        assert len(dest_pdf) == exp_len


def test_formenv():
    pass


def test_closing_parent_closes_kids():
    
    pdf = pdfium.PdfDocument(TestResources.multipage)
    pages = list(pdf)
    assert len(pages) == 3
    pdf.close()
    
    # confirm that closing the pdf automatically closes pages as well
    for p in pages:
        assert p.raw is None


def test_post_close():
    pdf = pdfium.PdfDocument(TestResources.empty)
    pdf.close()
    with pytest.raises(ctypes.ArgumentError):
        pdf.get_version()
