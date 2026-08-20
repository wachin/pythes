from pathlib import Path
import unicodedata

import pytest

from pythes import (
    ExcLookupMissmatch,
    LookupMismatchError,
    Mean,
    MalformedDataError,
    PyThes,
    PyThesError,
    PyThesIndexWarning,
    ThesaurusEntry,
    ThesaurusMeaning,
)


def _write_thesaurus(
    root: Path,
    *,
    encoding: str = 'UTF-8',
    bom: bool = False,
    malformed_index: bool = False,
    stale_index: bool = False,
    truncated_index: bool = False,
    line_ending: bytes = b'\n',
    entry: str = 'árbol',
) -> Path:
    codec = encoding
    header = encoding.encode('ascii') + line_ending
    if bom:
        header = b'\xef\xbb\xbf' + header

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


def test_regenerate_index_does_not_overwrite_by_default(tmp_path):
    path = _write_thesaurus(tmp_path / 'th_test')
    index_path = path.with_suffix('.idx')
    original_index = index_path.read_bytes()
    thesaurus = PyThes(path)

    with pytest.raises(FileExistsError):
        thesaurus.regenerate_index()

    assert index_path.read_bytes() == original_index


@pytest.mark.parametrize(
    ('encoding', 'bom', 'line_ending'),
    (
        ('UTF-8', True, b'\n'),
        ('ISO8859-1', False, b'\r\n'),
    ),
)
def test_regenerate_missing_index_preserves_source_format_and_offsets(
    tmp_path, encoding, bom, line_ending
):
    path = _write_thesaurus(
        tmp_path / 'th_test', encoding=encoding, bom=bom, line_ending=line_ending
    )
    index_path = path.with_suffix('.idx')
    index_path.unlink()
    thesaurus = PyThes(path)

    generated_path = thesaurus.regenerate_index()

    assert generated_path == index_path
    generated = generated_path.read_bytes()
    expected_header = encoding.encode('ascii') + line_ending
    if bom:
        expected_header = b'\xef\xbb\xbf' + expected_header
    assert generated.startswith(expected_header + b'1' + line_ending)
    with path.open('rb') as data_file:
        data_file.seek(thesaurus.index['árbol'])
        assert data_file.readline().decode(encoding).startswith('árbol|1')
    assert PyThes(generated_path).lookup('árbol') is not None


def test_regenerate_index_can_explicitly_replace_a_stale_index(tmp_path):
    path = _write_thesaurus(tmp_path / 'th_test', stale_index=True)
    index_path = path.with_suffix('.idx')
    with pytest.warns(PyThesIndexWarning, match='rebuilding the index'):
        thesaurus = PyThes(path)
    assert thesaurus.lookup('árbol') is not None
    assert thesaurus._lookup_cache

    generated_path = thesaurus.regenerate_index(overwrite=True)

    assert generated_path == index_path
    assert not thesaurus._lookup_cache
    assert PyThes(generated_path).lookup('árbol') is not None
    assert not list(tmp_path.glob('.th_test.idx.*.tmp'))


@pytest.mark.parametrize('dictionary_form', ['NFC', 'NFD'])
def test_lookup_accepts_canonically_equivalent_unicode(tmp_path, dictionary_form):
    entry = unicodedata.normalize(dictionary_form, 'árbol')
    path = _write_thesaurus(tmp_path / 'th_test', entry=entry)
    thesaurus = PyThes(path)

    result = thesaurus.lookup(unicodedata.normalize('NFD', 'ÁRBOL'))

    assert result.word == 'árbol'
    assert result.mean_tuple[0].main == 'planta alta'


def test_lookup_cache_is_lru_bounded_and_caches_misses(tmp_path, monkeypatch):
    path = _write_thesaurus(tmp_path / 'th_test')
    thesaurus = PyThes(path, cache_size=2)
    uncached_lookup = thesaurus._lookup_uncached
    calls = []

    def counted_lookup(word):
        calls.append(word)
        return uncached_lookup(word)

    monkeypatch.setattr(thesaurus, '_lookup_uncached', counted_lookup)

    assert thesaurus.lookup('árbol') is not None
    assert thesaurus.lookup(unicodedata.normalize('NFD', 'árbol')) is not None
    assert thesaurus.lookup('missing-one') is None
    assert thesaurus.lookup('missing-two') is None
    assert thesaurus.lookup('árbol') is not None
    assert thesaurus.lookup('ÁRBOL') is not None

    assert calls == ['árbol', 'missing-one', 'missing-two', 'árbol']
    assert len(thesaurus._lookup_cache) == 2


def test_lookup_cache_can_be_cleared_or_disabled(tmp_path, monkeypatch):
    path = _write_thesaurus(tmp_path / 'th_test')
    thesaurus = PyThes(path, cache_size=0)
    uncached_lookup = thesaurus._lookup_uncached
    calls = []

    def counted_lookup(word):
        calls.append(word)
        return uncached_lookup(word)

    monkeypatch.setattr(thesaurus, '_lookup_uncached', counted_lookup)
    thesaurus.lookup('árbol')
    thesaurus.lookup('ÁRBOL')
    thesaurus.clear_cache()

    assert calls == ['árbol', 'árbol']
    assert not thesaurus._lookup_cache


@pytest.mark.parametrize('cache_size', [-1, 1.5, '2'])
def test_invalid_cache_size_is_rejected(tmp_path, cache_size):
    path = _write_thesaurus(tmp_path / 'th_test')

    with pytest.raises((TypeError, ValueError)):
        PyThes(path, cache_size=cache_size)


def test_typed_paths_preserve_legacy_string_attributes(tmp_path):
    path = _write_thesaurus(tmp_path / 'th_test')
    thesaurus = PyThes(path)

    assert thesaurus.data_path == path.resolve()
    assert thesaurus.index_path == path.with_suffix('.idx').resolve()
    assert thesaurus.dat_path == str(thesaurus.data_path)
    assert thesaurus.idx_path == str(thesaurus.index_path)

    path.with_suffix('.idx').unlink()
    without_index = PyThes(path)
    assert without_index.index_path is None
    assert without_index.idx_path == ''


def test_structured_results_keep_tuple_compatibility(tmp_path):
    path = _write_thesaurus(tmp_path / 'th_test')

    result = PyThes(path).lookup('árbol')

    assert isinstance(result, ThesaurusEntry)
    assert isinstance(result.meanings[0], ThesaurusMeaning)
    assert Mean is ThesaurusMeaning
    assert result.meanings == result.mean_tuple
    assert result.meanings[0].part_of_speech == result.meanings[0].pos
    assert result.meanings[0].meaning == result.meanings[0].main
    assert result.meanings[0].synonyms == result.meanings[0].syn_tuple
    word, meanings = result
    assert word == 'árbol'
    assert meanings == result.mean_tuple


def test_public_exception_alias_has_structured_context(tmp_path):
    path = _write_thesaurus(tmp_path / 'th_test')
    thesaurus = PyThes(path)

    with pytest.raises(LookupMismatchError) as caught:
        thesaurus.validate_index({'árbol': 0})

    assert ExcLookupMissmatch is LookupMismatchError
    assert isinstance(caught.value, PyThesError)
    assert caught.value.path == path.resolve()
    assert caught.value.offset == 0


def test_truncated_meaning_raises_structured_data_error(tmp_path):
    path = _write_thesaurus(tmp_path / 'th_test')
    thesaurus = PyThes(path)
    header = path.read_bytes().splitlines(keepends=True)[0]
    path.write_bytes(header + 'árbol|1\n'.encode('UTF-8'))

    with pytest.raises(MalformedDataError) as caught:
        thesaurus.lookup('árbol')

    assert caught.value.path == path.resolve()
    assert caught.value.offset == len(header)
