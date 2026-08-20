'''Hunspell Thesaurus Class

Hunspell is a spell checker.
- Home page: http://hunspell.github.io

PyThes is a Python port of C++ MyThes class, whose project page is:
- https://github.com/hunspell/mythes

PyThes class uses Hunspell structured thesaurus data files
whose description can be found in the original project repository:
- https://github.com/hunspell/mythes/blob/master/data_layout.txt

Thesaurus files are bundled in LibreOffice / OpenOffice Language Packs
together spellchecking and hyphenation dictionaries used for stemming
and morphological generation.

The root name of thesaurus files is prefixed by th_ following Language
and Country Code, more an optional suffix, e.g.:

th_en_US_v2.dat th_en_US_v2.idx
th_it_IT_v2.dat th_it_IT_v2.idx

LibreOffice language bundles
----------------------------
- https://cgit.freedesktop.org/libreoffice/dictionaries/tree/
- https://wiki.documentfoundation.org/Language_support_of_LibreOffice
- https://github.com/LibreOffice/dictionaries

Language bundles are deployed in a single .oxt compressed file.
If your archive manager doesn't open .oxt file, then rename it as .zip
and there you have it.

Disclaimer
----------
The author of this software is not affiliated, associated, authorized,
endorsed by, or in any way officially connected with any of the companies,
organizations and individuals mentioned above.

None of them can be hold liable for any damages arising out of the use
of this software.

MIT License
---------------
Copyright (c) 2019 Corrado Ubezio
https://github.com/corerd/pythes

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
'''
from __future__ import annotations

from collections import OrderedDict
import os
from os.path import abspath
from pathlib import Path
import tempfile
from threading import RLock
from typing import Dict, NamedTuple, Optional, Tuple, Union
import unicodedata
import warnings


PathInput = Union[str, os.PathLike]


class ThesaurusMeaning(NamedTuple):
    '''One meaning, its part of speech, and related synonyms.'''

    pos: str
    main: str
    syn_tuple: Tuple[str, ...]

    @property
    def part_of_speech(self) -> str:
        return self.pos

    @property
    def meaning(self) -> str:
        return self.main

    @property
    def synonyms(self) -> Tuple[str, ...]:
        return self.syn_tuple


Mean = ThesaurusMeaning


class ThesaurusEntry(NamedTuple):
    '''A normalized lookup word and all of its thesaurus meanings.'''

    word: str
    mean_tuple: Tuple[ThesaurusMeaning, ...]

    @property
    def meanings(self) -> Tuple[ThesaurusMeaning, ...]:
        return self.mean_tuple


class PyThesError(Exception):
    '''Base class for structured PyThes data and index errors.'''

    def __init__(
        self,
        message: str,
        *,
        path: Optional[PathInput] = None,
        line_number: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> None:
        super().__init__(message)
        self.path = Path(abspath(Path(path).expanduser())) if path is not None else None
        self.line_number = line_number
        self.offset = offset


class IndexLineCountError(PyThesError):
    '''The declared index entry count does not match its contents.'''


class LookupMismatchError(PyThesError):
    '''An index byte offset does not point to the requested data entry.'''


class MalformedIndexError(PyThesError):
    '''A thesaurus index line is missing or invalid.'''


class MalformedDataError(PyThesError):
    '''A thesaurus data entry is incomplete or invalid.'''


# Backwards-compatible names from the original project.
ExcPyThes = PyThesError
ExcIndexLinesCount = IndexLineCountError
ExcLookupMissmatch = LookupMismatchError
ExcMalformedIndex = MalformedIndexError
ExcMalformedData = MalformedDataError


class PyThesIndexWarning(RuntimeWarning):
    '''The external index required recovery or contains ignored corruption'''
    pass


class PyThes:

    def __init__(self, thes_filepath: PathInput, cache_size: int = 256) -> None:
        '''Gets from thes_filepath the thesaurus files names
        and loads the index file content as a dictionary of pairs
        { entry: byte_offset_into_data_file }

        thes_filepath can be:
            - root name of files
            - path to the thesaurus index file
            - path to the thesaurus data file

        cache_size limits the per-instance LRU lookup cache. Set it to zero to
        disable caching.
        '''
        if isinstance(cache_size, bool) or not isinstance(cache_size, int):
            raise TypeError('cache_size must be an integer')
        if cache_size < 0:
            raise ValueError('cache_size must be zero or greater')
        self._cache_size = cache_size
        self._lookup_cache = OrderedDict()
        self._cache_lock = RLock()

        self.index_path, self.data_path = self.resolve_filenames(thes_filepath)
        self.idx_path = str(self.index_path) if self.index_path is not None else ''
        self.dat_path = str(self.data_path)
        self.dat_encoding = self.get_encoding(self.data_path)
        if self.index_path is None:
            self.index = self.load_index_from_dat(self.data_path)
        else:
            try:
                self.index = self.load_index(self.index_path)
                self.validate_index(self.index)
            except (IndexLineCountError, LookupMismatchError, MalformedIndexError) as error:
                warnings.warn(
                    '{}; rebuilding the index from {!r}'.format(error, self.dat_path),
                    PyThesIndexWarning,
                    stacklevel=2,
                )
                self.index = self.load_index_from_dat(self.data_path)

    def getIndex(self) -> Dict[str, int]:
        '''Returns the index dictionary'''
        return self.index

    @property
    def cache_size(self) -> int:
        '''Maximum number of cached lookup results; zero means disabled.'''
        return self._cache_size

    @staticmethod
    def normalize_word(word: str) -> str:
        '''Return the canonical, case-insensitive form used by the index.'''
        if not isinstance(word, str):
            raise TypeError('lookup word must be a string')
        return unicodedata.normalize('NFC', word.lower())

    def clear_cache(self) -> None:
        '''Discard all cached lookup hits and misses.'''
        with self._cache_lock:
            self._lookup_cache.clear()

    @staticmethod
    def resolve_filenames(filepath: PathInput) -> Tuple[Optional[Path], Path]:
        '''Resolve the optional index and required data paths.'''
        supplied_path = Path(filepath).expanduser()
        extension = supplied_path.suffix.lower()
        if extension == '.idx':
            index_path = supplied_path
            data_path = supplied_path.with_suffix('.dat')
        elif extension == '.dat':
            index_path = supplied_path.with_suffix('.idx')
            data_path = supplied_path
        else:
            index_path = supplied_path.with_suffix('.idx')
            data_path = supplied_path.with_suffix('.dat')

        data_path = Path(abspath(data_path))
        index_path = Path(abspath(index_path))
        return (index_path if index_path.is_file() else None), data_path

    def get_filenames(self, filepath: PathInput) -> Tuple[str, str]:
        '''Returns the couple of index, data files names from filepath

        The thesaurus consist of two files:
            - an optional index file (".idx" extension)
            - the data file (".dat" extension)

        filepath can be:
            - root name of files (without extemsion)
            - path to the thesaurus index file
            - path to the thesaurus data file
        '''
        index_path, data_path = self.resolve_filenames(filepath)
        return (str(index_path) if index_path is not None else ''), str(data_path)

    def lookup(self, word: str) -> Optional[ThesaurusEntry]:
        '''Returns ThesaurusEntry namedtuple related to the word
        fetched from thesaurus data file.

        Thesaurus data is a text file with the following lines content:
            Line 1: a string describes the encoding subsequently used.

            All of the remaning lines of the file follow this structure:
                entry|num_mean
                pos|syn1_mean|syn2|...
                .
                .
                .
                pos|mean_syn1|syn2|...
                        
            where:
                entry    - lowercase version of the word or phrase being described
                num_mean - number of meanings for this entry
            
            There is one meaning per line and each meaning is comprised of:
                pos       - part of speech or other meaning specific description
                syn1_mean - synonym 1 also used to describe the meaning itself 
                syn2      - synonym 2 for that meaning etc.
        '''
        word = self.normalize_word(word)
        if self.cache_size:
            with self._cache_lock:
                if word in self._lookup_cache:
                    result = self._lookup_cache.pop(word)
                    self._lookup_cache[word] = result
                    return result

        result = self._lookup_uncached(word)
        if self.cache_size:
            with self._cache_lock:
                self._lookup_cache[word] = result
                self._lookup_cache.move_to_end(word)
                while len(self._lookup_cache) > self.cache_size:
                    self._lookup_cache.popitem(last=False)
        return result

    def _lookup_uncached(self, word: str) -> Optional[ThesaurusEntry]:
        '''Read one already-normalized lookup word from the data file.'''
        try:
            # find word in the index
            offset_into_dat = self.index[word]
        except KeyError:
            # not found
            return None

        meanings: Tuple[ThesaurusMeaning, ...] = ()
        with self.data_path.open('r', encoding=self.dat_encoding) as dat_f:
            dat_f.seek(offset_into_dat)

            # grab entry and count of the number of meanings
            line = dat_f.readline().rstrip('\r\n')
            entry, separator, num_mean_text = line.rpartition('|')
            if not separator or not entry:
                raise MalformedDataError(
                    'invalid entry header at byte offset {}'.format(offset_into_dat),
                    path=self.data_path,
                    offset=offset_into_dat,
                )
            if self.normalize_word(entry) != word:
                raise LookupMismatchError(
                    'search "{}", get "{}"'.format(word, entry),
                    path=self.data_path,
                    offset=offset_into_dat,
                )
            try:
                num_mean = int(num_mean_text)
            except ValueError as error:
                raise MalformedDataError(
                    'invalid meaning count for {!r}'.format(entry),
                    path=self.data_path,
                    offset=offset_into_dat,
                ) from error

            # get each meaning
            for _ in range(num_mean):
                meaning_line = dat_f.readline()
                if meaning_line == '':
                    raise MalformedDataError(
                        'entry {!r} declares more meanings than remain in the data file'.format(
                            entry
                        ),
                        path=self.data_path,
                        offset=offset_into_dat,
                    )
                mean = meaning_line.rstrip('\r\n').split('|')
                if len(mean) < 2:
                    raise MalformedDataError(
                        'entry {!r} contains an invalid meaning'.format(entry),
                        path=self.data_path,
                        offset=offset_into_dat,
                    )
                meanings += (Mean(mean[0], mean[1], tuple(mean[2:])),)

        return ThesaurusEntry(word, meanings)

    def load_index_from_dat(self, dat_path: PathInput) -> Dict[str, int]:
        '''Returns a dictionary of pairs { entry: byte_offset_into_data_file }
        from the thesaurus data file
        '''
        _, _, entries = self._scan_data_entries(dat_path)
        return {self.normalize_word(entry): offset for entry, offset in entries}

    def _scan_data_entries(
        self, dat_path: PathInput
    ) -> Tuple[bytes, bytes, list[Tuple[str, int]]]:
        '''Return the declaration, newline, and exact binary offsets in `.dat`.'''
        resolved_path = Path(abspath(Path(dat_path).expanduser()))
        entries = []
        with resolved_path.open('rb') as dat_f:
            declaration_line = dat_f.readline()
            if declaration_line.endswith(b'\r\n'):
                line_ending = b'\r\n'
            else:
                line_ending = b'\n'
            declaration = declaration_line.rstrip(b'\r\n')
            line_number = 1
            malformed_lines = []
            while True:
                entry_byte_offset = dat_f.tell()
                raw_line = dat_f.readline()
                if raw_line == b'':
                    # the end of the file has been reached
                    break
                line_number += 1
                try:
                    line = raw_line.decode(self.dat_encoding)
                except UnicodeError as error:
                    raise MalformedDataError(
                        'cannot decode data line {} in {!r}'.format(line_number, str(resolved_path)),
                        path=resolved_path,
                        line_number=line_number,
                    ) from error
                entry, separator, num_mean_text = line.rstrip('\r\n').rpartition('|')
                try:
                    num_mean = int(num_mean_text)
                except ValueError:
                    num_mean = -1
                if not separator or not entry or num_mean < 0:
                    malformed_lines.append(line_number)
                    continue
                entries.append((entry, entry_byte_offset))
                for _ in range(num_mean):
                    if dat_f.readline() == b'':
                        raise MalformedDataError(
                            'entry {!r} declares more meanings than remain in {!r}'.format(
                                entry, str(resolved_path)
                            ),
                            path=resolved_path,
                            line_number=line_number,
                        )
                    line_number += 1
            if malformed_lines:
                warnings.warn(
                    'ignored malformed data line(s) {} while rebuilding {!r}'.format(
                        ', '.join(map(str, malformed_lines)), str(resolved_path)
                    ),
                    PyThesIndexWarning,
                    stacklevel=2,
                )
        return declaration, line_ending, entries

    def regenerate_index(
        self, destination: Optional[PathInput] = None, *, overwrite: bool = False
    ) -> Path:
        '''Generate and atomically publish an index from the source `.dat`.

        Args:
            destination: Optional output path. Defaults to the `.idx` path next
                to the loaded `.dat` file.
            overwrite: Existing files are protected unless this is explicitly
                set to ``True``.

        Returns:
            The absolute :class:`pathlib.Path` of the generated index.
        '''
        destination = Path(abspath(Path(
            destination if destination is not None else self.data_path.with_suffix('.idx')
        ).expanduser()))
        if destination.exists() and not overwrite:
            raise FileExistsError('refusing to overwrite existing index {!r}'.format(str(destination)))

        declaration, line_ending, entries = self._scan_data_entries(self.data_path)
        file_descriptor, temporary_name = tempfile.mkstemp(
            prefix='.{}.'.format(destination.name),
            suffix='.tmp',
            dir=str(destination.parent),
        )
        try:
            with os.fdopen(file_descriptor, 'wb') as index_file:
                index_file.write(declaration + line_ending)
                index_file.write(str(len(entries)).encode('ascii') + line_ending)
                for entry, offset in entries:
                    index_file.write(entry.encode(self.dat_encoding))
                    index_file.write(b'|' + str(offset).encode('ascii') + line_ending)
                index_file.flush()
                os.fsync(index_file.fileno())

            generated_index = self.load_index(temporary_name)
            self.validate_index(generated_index)
            if overwrite:
                os.replace(temporary_name, destination)
            else:
                # A hard link publishes the validated temporary file only if
                # the destination does not already exist. Unlike a separate
                # existence check followed by replace, this is race-free.
                os.link(temporary_name, destination)
                os.unlink(temporary_name)
        except BaseException:
            try:
                os.unlink(temporary_name)
            except FileNotFoundError:
                pass
            raise

        self.idx_path = str(destination)
        self.index_path = destination
        self.index = generated_index
        self.clear_cache()
        return destination

    def load_index(self, idx_path: PathInput) -> Dict[str, int]:
        '''Returns the thesaurus index file content as a dictionary of pairs
        { entry: byte_offset_into_data_file }

        Thesaurus index is a text file with the following lines content:
            Line 1: a string describes the encoding subsequently used;
            Line 2: a count of the total number of entries in the thesaurus.

            All of the remaining lines are of the form:
                entry|byte_offset_into_data_file_where_entry_is_found
        '''
        word_idx = {}
        idx_codec = self.get_encoding(idx_path)
        with open(idx_path, 'r', encoding=idx_codec) as idx_f:
            idx_f.readline()  # skip first line (file encoding)
            count_line = idx_f.readline()
            try:
                idx_size = int(count_line)
            except ValueError as error:
                raise MalformedIndexError(
                    'missing or invalid entry count on line 2 in {!r}'.format(str(idx_path)),
                    path=idx_path,
                    line_number=2,
                ) from error
            cnt = 0  # now parse the remaining lines of the index
            malformed_lines = []
            for line_number, line in enumerate(idx_f, start=3):
                word, separator, offset = line.rstrip('\r\n').rpartition('|')
                if not separator or not word or not offset:
                    malformed_lines.append(line_number)
                    continue
                try:
                    word_idx[self.normalize_word(word)] = int(offset)
                except ValueError as error:
                    raise MalformedIndexError(
                        'invalid byte offset on line {} in {!r}'.format(
                            line_number, str(idx_path)
                        ),
                        path=idx_path,
                        line_number=line_number,
                    ) from error
                cnt += 1
            if idx_size != cnt:
                raise IndexLineCountError(
                    'index declares {} entries but contains {} in {!r}'.format(
                        idx_size, cnt, str(idx_path)
                    ),
                    path=idx_path,
                )
            if malformed_lines:
                warnings.warn(
                    'ignored malformed index line(s) {} in {!r}'.format(
                        ', '.join(map(str, malformed_lines)), idx_path
                    ),
                    PyThesIndexWarning,
                    stacklevel=2,
                )
        return word_idx

    def validate_index(self, word_idx: Dict[str, int]) -> None:
        '''Verify that every index offset points to its named data entry.

        External indexes can remain syntactically valid after their data file
        has changed. Validation detects those stale byte offsets before a
        lookup can return the wrong entry or fail unexpectedly.
        '''
        with self.data_path.open('r', encoding=self.dat_encoding) as dat_f:
            for word, offset in word_idx.items():
                try:
                    dat_f.seek(offset)
                    line = dat_f.readline().rstrip('\r\n')
                except (OSError, UnicodeError, ValueError) as error:
                    raise LookupMismatchError(
                        'invalid byte offset {} for {!r}'.format(offset, word),
                        path=self.data_path,
                        offset=offset,
                    ) from error

                entry, separator, num_mean = line.rpartition('|')
                try:
                    valid_count = int(num_mean) >= 0
                except ValueError:
                    valid_count = False
                if not separator or self.normalize_word(entry) != word or not valid_count:
                    raise LookupMismatchError(
                        'index entry {!r} at byte offset {} points to {!r}'.format(
                            word, offset, entry
                        ),
                        path=self.data_path,
                        offset=offset,
                    )

    def get_encoding(self, thesaurus_file: PathInput) -> str:
        '''Returns first line of thesaurus_file as encoding type.

        thesaurus_file is a text file where line 1 describes the encoding used.
        This function opens the source text file in encoding-agnostic mode,
        that is binary, to get the ASCII string revealing the encoding type
        that will be later used to re-open the thesaurus_file in text mode.
        '''
        with open(thesaurus_file, 'rb') as f:
            # convert first binary line to string, removing trailing newline
            # UTF-8's optional BOM is common in LibreOffice dictionaries.  It
            # prefixes the ASCII-compatible encoding declaration, not the
            # thesaurus content itself.
            encoding_type = f.readline().decode('utf-8-sig').strip()
        return encoding_type


if __name__ == "__main__":
    # TEST BENCH: check integrity of thesaurus data files
    # checking thesaurus data entry for each word in the index
    dictionaries = (
        '../dictionaries/en_US/th_en_US_v2',
        '../dictionaries/it_IT/th_it_IT_v2',
        '../dictionaries/ca_ES/dictionaries/th_ca_ES_v3'
    )
    for thesaurus in dictionaries:
        th = PyThes(thesaurus)
        print('Data file: {}'.format(th.dat_path))
        print('Index file: {}'.format(th.idx_path))
        print('Searching {} words...'.format(len(th.index)))
        for word in th.getIndex():
            th.lookup(word)
    print('Done!')
