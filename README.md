# Tabularius

Document intake, review and evidence archive for plain-text accounting.
Python package and [hledger](https://hledger.org) add-on: **`hledger-tab`**.

> **Status: design phase.** Nothing here runs yet. [DESIGN.md](DESIGN.md) is the
> current plan; this README describes what Tabularius is meant to do, not what it
> does today.

## What it is

Bills, receipts and letters arrive on paper and by email. Tabularius is meant to
take each one through the same path:

1. **Capture**: from a document scanner, an email folder, or a manual drop.
2. **Understand**: OCR, split into documents, classify, extract fields
   (amount, due date, OCR reference, …).
3. **Review**: a keyboard-driven terminal UI where a person confirms or corrects
   every value.
4. **Act**: record a payable in hledger, submit to an accountant, or file it.
5. **Keep**: store the original write-once with hashes, an archival PDF/A copy,
   and an audit history, so the paper can be shredded once the archive is
   verifiably backed up.

It is **content-first**: the main record is what a document says and what has to
be done about it. The file is kept as evidence.

## How it relates to hledger

hledger owns money; Tabularius owns documents. The two are linked through plain
journal syntax, so the journal stays valid without the add-on:

```journal
2026-10-02 (V2026-0042) Telia | faktura 88412  ; doc:0199a1c3-…, due:2026-10-30
    expenses:phone                     449.00 SEK
    liabilities:payable:telia
```

- The transaction code is the verification number.
- The `doc:<uuid>` tag points to a document in the archive.
- Generated entries go to their own include file. Hand-written journal files
  are never modified without explicit confirmation.

Installed on `PATH`, the `hledger-tab` executable becomes the subcommand
`hledger tab`. Planned commands:

| Command | Purpose |
|---|---|
| `hledger tab check` | Every `doc:` tag resolves and every hash matches; for pre-commit/CI |
| `hledger tab unlinked` | Documents about money that have no transaction |
| `hledger tab show QUERY` | Open the documents behind matching transactions |
| `hledger tab attach TXN DOC` | Link a document to an existing transaction |

beancount has a `document` directive and Fava shows the linked files; hledger
has no equivalent, and this project aims to fill that gap.

## Principles

The full list, with reasoning, is in [DESIGN.md §2](DESIGN.md#2-invariants).
In short:

- **Originals are write-once.** Copy, verify the hash, then remove the inbox copy.
- **Nothing is silently lost.** Unknown formats and failed parses go to quarantine.
- **Readable without the tool.** The archive is plain files and plain text, with a
  README in each collection.
- **Collections never mix.** For example, personal papers and a club's treasury
  get separate storage, keys and exports.
- **No hard-coded document types.** Types and per-sender templates are YAML
  profiles; the review UI renders fields by type, not by name.
- **Shred only when proven safe.** Only after review *and* after the original's
  hash is confirmed in a replicated backup.

## Planned requirements

Linux only. Not final; see [DESIGN.md §14](DESIGN.md#14-tech-stack).

- Python 3.13, [uv](https://docs.astral.sh/uv/)
- hledger
- ocrmypdf, Tesseract (`swe`, `eng`), qpdf, veraPDF
- Optional: a local LLM through an OpenAI-compatible or Ollama endpoint, used
  only when cheaper methods (identifiers, templates, a local classifier) are
  uncertain
- Recommended: ZFS with native encryption for the archive and its backups

## Roadmap

| Milestone | Scope |
|---|---|
| M0 | Project skeleton, data contracts, invariant test stubs |
| M1 | Scanner → write-once archive → PDF/A + OCR → index |
| M2 | Review TUI v0 |
| M3 | Document types, templates, field extraction, validators |
| M4 | hledger integration (`docs.journal`, `check`, payment matching) |
| M5 | Email intake |
| M6 | Submission to an accountant, BagIt export |
| M7 | Backup verification, shred-OK, retention |

Details and open questions are in [DESIGN.md](DESIGN.md).

## Name

A *tabularius* was a Roman record keeper or accountant. The PyPI name
`tabularius` belongs to an unrelated project, so the package is `hledger-tab`
and the import name is `hledger_tab`.

## Licence

[GNU General Public License v3.0](LICENSE).
