from pathlib import Path

import pytest

from pythes import PyThes, PyThesIndexWarning


def _write_thesaurus(
    root: Path,
    *,
    encoding: str = 'UTF-8',
    bom: bool = False,
    malformed_index: bool = False,
    stale_index: bool = False,
    truncated_index: bool = False,
    line_ending: bytes = b'\n',
) -> Path:
    codec = encoding
    header = encoding.encode('ascii') + line_ending
    if bom:
        header = b'\xef\xbb\xbf' + header

    entry = 'árbol'
    body = (
        f'{entry}|1\n'
        '(sustantivo)|planta alta|vegetal\n'
    ).replace('\n', line_ending.decode('ascii')).encode(codec)
    dat_path = root.with_suffix('.dat')
    dat_path.write_bytes(header + body)

    idx_path = root.with_suffix('.idx')
    if malformed_index:
        index_body = entry.encode(codec) + line_ending
    else:
        offset = len(header) + int(stale_index)
        index_body = f'{entry}|{offset}'.encode(codec) + line_ending
    idx_header = encoding.encode('ascii') + line_ending
    if not truncated_index:
        idx_header += b'1' + line_ending
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


def test_stale_index_offset_falls_back_to_data_file(tmp_path):
    path = _write_thesaurus(tmp_path / 'th_test', stale_index=True)

    with pytest.warns(PyThesIndexWarning, match='rebuilding the index'):
        thesaurus = PyThes(path)

    assert thesaurus.lookup('árbol') is not None


def test_truncated_index_falls_back_to_data_file(tmp_path):
    path = _write_thesaurus(tmp_path / 'th_test', truncated_index=True)

    with pytest.warns(PyThesIndexWarning, match='rebuilding the index'):
        thesaurus = PyThes(path)

    assert thesaurus.lookup('árbol') is not None


def test_index_rebuild_skips_a_malformed_data_header(tmp_path):
    path = _write_thesaurus(tmp_path / 'th_test')
    contents = path.read_bytes()
    header, body = contents.split(b'\n', maxsplit=1)
    path.write_bytes(header + b'\nbroken entry header\n' + body)
    path.with_suffix('.idx').unlink()

    with pytest.warns(PyThesIndexWarning, match='malformed data line'):
        thesaurus = PyThes(path)

    assert thesaurus.lookup('árbol') is not None


def test_missing_optional_index_is_rebuilt_from_data(tmp_path):
    path = _write_thesaurus(tmp_path / 'th_test')
    path.with_suffix('.idx').unlink()

    thesaurus = PyThes(path)

    assert thesaurus.lookup('árbol') is not None


def test_crlf_data_and_index_preserve_byte_offsets(tmp_path):
    path = _write_thesaurus(tmp_path / 'th_test', line_ending=b'\r\n')

    thesaurus = PyThes(path)

    assert thesaurus.lookup('árbol') is not None
