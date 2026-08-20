from pathlib import Path

import pytest

from pythes import PyThes, PyThesIndexWarning


def _write_thesaurus(
    root: Path,
    *,
    encoding: str = 'UTF-8',
    bom: bool = False,
    malformed_index: bool = False,
) -> Path:
    codec = encoding
    header = encoding.encode('ascii') + b'\n'
    if bom:
        header = b'\xef\xbb\xbf' + header

    entry = 'árbol'
    body = (
        f'{entry}|1\n'
        '(sustantivo)|planta alta|vegetal\n'
    ).encode(codec)
    dat_path = root.with_suffix('.dat')
    dat_path.write_bytes(header + body)

    idx_path = root.with_suffix('.idx')
    if malformed_index:
        index_body = f'{entry}\n'.encode(codec)
    else:
        index_body = f'{entry}|{len(header)}\n'.encode(codec)
    idx_header = encoding.encode('ascii') + b'\n1\n'
    if bom:
        idx_header = b'\xef\xbb\xbf' + idx_header
    idx_path.write_bytes(idx_header + index_body)
    return dat_path


@pytest.mark.parametrize('encoding', ['UTF-8', 'ISO8859-1', 'ISO8859-2'])
def test_lookup_preserves_declared_encoding_and_byte_offsets(tmp_path, encoding):
    thesaurus = PyThes(_write_thesaurus(tmp_path / 'th_test', encoding=encoding))

    result = thesaurus.lookup('ÁRBOL')

    assert result.word == 'árbol'
    assert result.mean_tuple[0].main == 'planta alta'
    assert result.mean_tuple[0].syn_tuple == ('vegetal',)


def test_utf8_bom_is_accepted_in_data_and_index(tmp_path):
    thesaurus = PyThes(_write_thesaurus(tmp_path / 'th_test', bom=True))

    assert thesaurus.lookup('árbol') is not None


def test_malformed_index_falls_back_to_data_file(tmp_path):
    path = _write_thesaurus(tmp_path / 'th_test', malformed_index=True)

    with pytest.warns(PyThesIndexWarning, match='rebuilding the index'):
        thesaurus = PyThes(path)

    assert thesaurus.lookup('árbol') is not None
