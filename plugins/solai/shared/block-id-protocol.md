# Block id protocol

Mint-or-reuse, run before emitting any wikilink of the form `[[file#^id]]`.

## Format

Lowercase hex, six characters: `^[0-9a-f]{6}`. Never sequential numbers: two people
citing the same document on the same day both reach for `^001`.

## Protocol

1. Open the target file once per run and build a map of paragraph to existing block id.
2. For the paragraph being cited, reuse the id if it has one.
3. Otherwise mint a fresh six-hex id, check it against the map for collision, and append
   it to the end of that paragraph after a single space.
4. Return the bare wikilink. The caller decides how to present it.

## Why lazily

Most paragraphs are never cited. Stamping every one produces a document full of noise
protecting against a citation that never comes.
