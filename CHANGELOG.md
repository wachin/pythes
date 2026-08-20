# Changelog

## Unreleased

- Accept a UTF-8 BOM before the encoding declaration used by LibreOffice
  thesaurus files.
- Detect malformed external indexes and safely rebuild the index in memory
  from the original `.dat` file, without modifying dictionary files.
- Add regression coverage for UTF-8, ISO-8859-1, ISO-8859-2, byte offsets,
  BOMs, and malformed indexes.
- Validate every external index offset against its named `.dat` entry and
  rebuild stale or truncated indexes safely in memory.
- Support index reconstruction from CRLF data and skip isolated malformed data
  headers with a visible warning while preserving valid entries.
- Add explicit, atomic `.idx` regeneration with exact binary offsets,
  source-format preservation, validation before publication, and overwrite
  protection by default.
- Normalize index and query words to NFC so canonically equivalent Unicode
  spellings resolve to the same entry.
- Add a configurable, thread-safe LRU lookup cache with a fixed upper bound,
  negative-result caching, explicit clearing, and regeneration invalidation.
- Add typed `Path` attributes, typed immutable result records, and a public
  structured exception hierarchy while retaining legacy attributes, tuple
  behavior, and exception aliases.
- Translate malformed entry headers and truncated meanings into contextual
  `MalformedDataError` instances instead of leaking parser exceptions.
- Declare Python 3.10 as the minimum supported version for the maintained fork.
