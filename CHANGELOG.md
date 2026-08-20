# Changelog

## Unreleased

- Accept a UTF-8 BOM before the encoding declaration used by LibreOffice
  thesaurus files.
- Detect malformed external indexes and safely rebuild the index in memory
  from the original `.dat` file, without modifying dictionary files.
- Add regression coverage for UTF-8, ISO-8859-1, ISO-8859-2, byte offsets,
  BOMs, and malformed indexes.
