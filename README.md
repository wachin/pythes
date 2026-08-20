Hunspell Thesaurus Support in Python
===================================
[Hunspell](http://hunspell.github.io/) is the spell checker of LibreOffice,
OpenOffice, Mozilla Firefox 3 & Thunderbird, Google Chrome,
and it is also used by proprietary software packages, like macOS, InDesign,
memoQ, Opera and SDL Trados.

**PyThes** is a Python class providing methods to search Hunspell thesaurus
for words and related information on part of speech, meanings and synonyms.

**PyThes-cli** is simple example script that looks up a word and returns
its meaning and synonyms.

Hunspell thesaurus consists of a `.dat` structured text data file
and an optional `.idx` index file.
You can find their description in the `data_layout.txt` file.

The root name of LibreOffice / OpenOffice thesaurus files is prefixed by `th_`
following Language and Country Code, more an optional suffix, e.g.:
```
th_en_US_v2.dat th_en_US_v2.idx
th_it_IT_v2.dat th_it_IT_v2.idx
```

Using the example script to look up an italian word, open a command line window
and enter only the thesaurus root name (without extensions) as follows: 
```
python pythes-cli.py directory-path-to/th_it_IT_v2 lookup-word
```
The script will open the `th_it_IT_v2.dat` and `th_it_IT_v2.idx` files
in the directory path.


Index validation and recovery
-----------------------------

PyThes treats the `.dat` file as the thesaurus source of truth. The `.idx`
file is optional and is never modified. When an external index is present,
PyThes validates its declared entry count and verifies that every byte offset
points to the named data entry.

If the index is missing, truncated, malformed, or stale, PyThes reconstructs
it in memory from the `.dat` file. Recoverable corruption is reported with
`PyThesIndexWarning`; applications may log or display that diagnostic without
losing access to valid thesaurus entries. UTF-8 BOMs, LF, CRLF, and declared
legacy encodings remain supported without converting the source files.

Applications and validation tools may explicitly persist a reconstructed
index:

```python
from pythes import PyThes

thesaurus = PyThes("/path/to/th_es_v2.dat")
generated_path = thesaurus.regenerate_index()
```

The method writes atomically and returns an absolute `pathlib.Path`. Existing
indexes are protected with `FileExistsError`. Replacing one requires an
explicit request:

```python
thesaurus.regenerate_index(overwrite=True)
```

An alternate destination can be supplied as the first argument. The generated
index preserves the data file's encoding declaration, optional BOM, and LF or
CRLF convention. It is reloaded and checked against the `.dat` file before it
replaces the destination.


Unicode lookup and bounded caching
----------------------------------

Index keys and lookup words use Unicode NFC normalization after lowercasing.
This means canonically equivalent input, such as `á` and `a` followed by a
combining acute accent, resolves to the same thesaurus entry. Meaning and
synonym text remains as supplied by the source dictionary.

Each `PyThes` instance has a thread-safe LRU cache limited to 256 entries by
default. Both successful lookups and missing words are cached. The limit is
configurable and never grows without bound:

```python
thesaurus = PyThes("/path/to/th_es_v2.dat", cache_size=512)
thesaurus_without_cache = PyThes("/path/to/th_es_v2.dat", cache_size=0)
```

Use `thesaurus.clear_cache()` when an application needs explicit invalidation.
Successfully regenerating an index also clears the cache automatically.


Stable public primitives
------------------------

The maintained fork accepts strings and `os.PathLike` objects. New code can
use the typed path attributes:

```python
thesaurus.data_path   # pathlib.Path
thesaurus.index_path  # pathlib.Path | None
```

The legacy `dat_path` and `idx_path` string attributes remain available.
Lookup returns an immutable `ThesaurusEntry` containing immutable
`ThesaurusMeaning` records. They preserve the original tuple field names and
unpacking behavior while adding descriptive aliases:

```python
result = thesaurus.lookup("árbol")
for meaning in result.meanings:
    print(meaning.part_of_speech, meaning.meaning, meaning.synonyms)
```

Data and index failures derive from `PyThesError` and use the public classes
`IndexLineCountError`, `LookupMismatchError`, `MalformedIndexError`, and
`MalformedDataError`. Errors expose applicable `path`, `line_number`, and
`offset` context. Original names such as `ExcLookupMissmatch` remain aliases
for source compatibility.


How to get Hunspell thesaurus files
-----------------------------------
Thesaurus files are bundled in LibreOffice / OpenOffice Language Packs
together spellchecking and hyphenation dictionaries used for stemming
and morphological generation.

Goto to [Document Foundation Language/Support](https://wiki.documentfoundation.org/Language_support_of_LibreOffice)
and search for you language.

Language bundles are deployed as a single `.oxt` compressed file.

You can use an archive manager like 7-Zip to open the bundle and extract
the thesaurus file `.dat` and `.idx`.

If your archive manager doesn't recognize `.oxt` file, then rename it as `.zip`
and there you have it.

In the following web pages you can find the `.dat` files only:
- https://cgit.freedesktop.org/libreoffice/dictionaries/tree/
- https://github.com/LibreOffice/dictionaries


Other dictionaries
------------------
words (Unix) words is a standard file on Unix and Unix-like operating systems,
and is simply a newline-delimited list of dictionary english words.

The words file is usually stored in `/usr/share/dict/words` or `/usr/dict/words`.


Credits
-------
**PyThes** is a Python port of **C++ MyThes** class, whose project page is:
- https://github.com/hunspell/mythes


Disclaimer
----------
The author of this software is not affiliated, associated, authorized,
endorsed by, or in any way officially connected with any of the companies,
organizations and individuals mentioned above.

None of them can be hold liable for any damages arising out of the use
of this software.


MIT License
-----------
Copyright (c) 2019 Corrado Ubezio

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
