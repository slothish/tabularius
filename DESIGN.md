# Tabularius — Design

> Document intake, review and evidence archive for plain-text accounting.
> Python package and hledger add-on: **`hledger-tab`**.

Status: draft v0.2 · 2026-10-02 · Author: Andreas

---

## 1. Purpose

Paper and email documents arrive, get captured once, are understood (classified,
fields extracted), reviewed by a human, acted upon (recorded in hledger, filed), and
kept as verifiable evidence for as long as required. The paper is then shredded.

Tabularius is **content-first**: the source of truth is *what a document says and
what has to be done about it*. The file itself is kept only as evidence.

It sits next to hledger, not inside it: hledger owns money, Tabularius owns
documents. They are linked by tags in the journal (`doc:<uuid>`) and by the
transaction code field (verification number).

### 1.1 In scope

- Intake from a document scanner (Brother ADS-1800W), email (IMAP, e.g. Fastmail),
  and manual/agent drops.
- Format analysis and normalisation to an archival rendition (PDF/A-2b).
- OCR, document splitting, identification, field extraction.
- Generic, profile-driven extraction — no document type is hard-coded.
- Keyboard-driven review in a TUI.
- Actions: payables in hledger, filing.
- Evidence integrity: write-once originals, hashes, event history, verified backups.
- Export as BagIt packages for handover.

### 1.2 Non-goals (for now)

- Web UI, multi-user, mobile app. (The core API must not prevent adding one later.)
- More than one entity per archive. One archive serves one person, household or
  business; another entity runs its own instance (§4, §11).
- Paying bills.
- Windows/macOS support.
- Hard-coded country-specific rules in the core. Swedish specifics live in
  profiles and validators.

---

## 2. Invariants

These are the rules that must never be broken. Every one of them has tests.

1. **Originals are write-once.** Once stored, an original is never modified or
   overwritten. It is copied, its hash verified, and only then is the source copy
   removed (inbox → staging → shard). Never move-then-verify.
2. **Single writer.** Only the core service writes to the archive. The TUI, CLI
   and agent go through the core API. Users have no write access to archive files.
3. **Intake is idempotent.** The same file or email ingested twice yields one
   original and the same documents.
4. **Never modify hand-written journal files.** Generated hledger entries go to a
   dedicated include file. Adding a `doc:` tag to an existing transaction requires
   explicit confirmation in the TUI.
5. **Nothing is lost.** Unknown formats, failed parses and unrecognised fields go
   to quarantine or are kept as raw data — never silently dropped.
6. **Readable without the tool.** The archive is plain files and plain text. A
   person with no copy of Tabularius can understand it from the files and the
   README at the archive root.
7. **Shred only when proven safe.** "Shred OK" means: confirmed in review *and*
   the configured backup verifier confirms the original's hash is held in a backup
   off this machine (§12.2). No verifier, no shred OK.
8. **Deletion is explicit, coarse and logged.** Data leaves the archive only by
   deleting a whole expired shard or by an explicit early deletion of one
   document, each confirmed in the TUI and recorded in the deletion ledger
   (§12.4). History is never rewritten as part of normal operation.

---

## 3. Architecture

```
 scanner (SFTP) ─┐
 mbsync/Maildir ─┼─► adapters ─► inbox/ready/<bundle> ─► core service ─► store/  (blobs)
 agent / manual ─┘                                          │        ─► registry/ (git, text)
                                                            │        ─► index.sqlite (cache)
                                                            │        ─► docs.journal (hledger)
                                       Unix socket API ◄────┘
                                        ▲      ▲      ▲
                                       TUI    CLI   agent (read-only)
```

- **Adapters** are small and dumb. Their only job is to turn something that
  arrived into an intake bundle and place it in the inbox atomically.
- **Core service** (systemd unit, its own user) does everything else: analysis,
  normalisation, OCR, splitting, identification, extraction, persistence, events,
  hledger generation, submission, export.
- **API**: local Unix socket. The TUI may run on the laptop and reach the socket
  through SSH forwarding. Every TUI action exists as an API call and a CLI command.
- **Agent** gets a read-only token: query, search, list due items. No mutations.
  It may also act as a producer by writing a bundle with `channel: agent`, which
  goes through review like everything else.

---

## 4. Scope: one entity

One archive holds the documents of one entity: a person, a household or a small
business. There is no separation of owners inside an archive. A second entity
runs a second, independent instance with its own archive, keys and backups.

Earlier drafts had several *collections* (personal papers and a club's treasury)
in one archive. That is parked; see §11.

---

## 5. Intake

### 5.1 Channels

| Channel | Mechanism |
|---|---|
| Scanner | ADS-1800W scan profile → SFTP (preferred) or SMB, chrooted account, write-only to `inbox/scanner/` |
| Mail | Intake folder (e.g. Fastmail: Sieve rules + manual move/forward) → mbsync → Maildir |
| Agent / manual | writes a bundle directly |

Notes:
- The scanner is an untrusted device. Its credential can only write to its inbox
  directory: no read, no listing of the archive.
- Email becomes a document only when it is placed in an intake folder (rule or
  manual). Forward **as attachment** (`message/rfc822`) so the original headers
  survive.
- The ingestion path uses its own narrowly scoped mail credentials, never the
  agent's.

### 5.2 Intake bundle contract

Adapters write to `inbox/tmp/<intake_id>/`, then `rename()` to
`inbox/ready/<intake_id>/`. The core only ever sees complete bundles.

```
inbox/ready/<intake_id>/
  envelope.json
  <payload files>        # exactly as received: scan.pdf, original.eml, photo.heic …
```

```json
{
  "intake_id": "0199b2c4-…",
  "schema": "envelope/1",
  "channel": "scanner | maildir | agent | manual",
  "adapter": "scanner-sftp@0.1.0",
  "received_at": "2026-10-02T08:14:03Z",
  "source_ref": {"message_id": "<abc@example.se>", "mailbox": "Intake", "scan_profile": "default"},
  "from": "faktura@example.se",
  "subject": "Din faktura",
  "files": [{"name": "original.eml", "sha256": "…", "role": "container"}]
}
```

The envelope is stored verbatim in `registry/intake/YYYY/<intake_id>.json` and is
never edited afterwards.

### 5.3 Deduplication

- Blob level: sha256 (automatic, store is content-addressed).
- Email level: `Message-ID`.
- Business level: per profile uniqueness key, e.g. `(correspondent orgnr, invoice_no)`.
  A duplicate is flagged in review ("already received 2026-09-14"), never
  silently dropped.

---

## 6. Processing pipeline

```
bundle → analyse → store originals → normalise → OCR → split → identify → extract → review queue
```

### 6.1 Analysis (trust nothing)

- File type from content (libmagic), never from extension or sender claims.
- PDF structural check (`qpdf --check`). Broken → quarantine.
- Born-digital vs scanned: real text layer present? If yes, skip OCR.
- Scan quality: DPI (< 200 flagged), near-blank pages (marked, not deleted),
  skew, colour mode.
- Claimed PDF/A is verified with veraPDF, not trusted.

### 6.2 Normalisation

Every document gets an **archive rendition** in addition to the untouched original.

| Input | Archive rendition |
|---|---|
| Scanned PDF (scanner delivers PDF/A-1b) | PDF/A-2b with text layer (ocrmypdf, `-l swe+eng`, optimisation `-O1` lossless) |
| Born-digital PDF | PDF/A-2b, no rasterisation, no `--force-ocr` |
| Image (JPEG/HEIC/PNG) | deskew/crop → img2pdf → ocrmypdf → PDF/A-2b |
| Office files | LibreOffice headless → PDF/A-3 with original embedded |
| E-invoice XML | rendered PDF/A-3 with the XML embedded (the XML is the legal original) |
| Email body as document | HTML/text rendered → PDF/A-2b |

- Every rendition is validated with veraPDF. Failure → review queue.
- Tool names and versions are recorded with each rendition.
- All conversions run sandboxed (systemd hardening / bubblewrap: no network,
  only their working directory). Parsers of untrusted input are attack surface.

### 6.3 OCR

- Tesseract via ocrmypdf; languages `swe+eng`.
- Keep **hOCR** (word boxes) as a blob: field records point to a bounding box,
  and the TUI shows a zoomed crop of exactly where a value was found.

### 6.4 Splitting

One scan batch can contain several documents.

1. Barcode separator sheets (preferred; may also carry a type hint).
2. Blank-page / layout heuristics (suggested, never final without review).
3. Manual split/merge/reorder in the TUI.

### 6.5 Identification (cheap and certain first)

1. Separator barcode hint.
2. Known correspondent by hard identifier (orgnr, bankgiro, VAT number).
3. Local classifier trained on confirmed documents (TF-IDF + logistic regression).
4. LLM choosing among type descriptions (local model via an OpenAI-compatible or
   Ollama endpoint), only when the steps above are uncertain.

The method and confidence are stored with every classification.

### 6.6 Extraction

- Template (if one matches) → regex/anchor rules first.
- Type fields not covered → LLM with the type's field descriptions, constrained to
  the field-record JSON schema (structured output).
- Validators run on every value (check digits, date sanity, currency).
- Anything the LLM finds outside the profile is returned as
  `origin: "discovered"` (see §8.3).

---

## 7. Data model and storage

### 7.1 Identity

| Thing | Identifier |
|---|---|
| A file (exact bytes) | sha256 |
| A document (logical: "Telia invoice, September") | UUIDv7 (time-ordered) |
| An intake | UUIDv7 |
| A verification (hledger) | transaction code, e.g. `V2026-0042` |

One file can contain several documents; a document references
`{sha256, pages}`. A rescanned document gets a new source, same UUID.

### 7.2 Layout

The archive is split into **shards by expiry year** (§12.3): every document in a
shard expires on the same day, so a shard is deleted as one unit. Documents with
no fixed end (contracts, deeds) live in the `open` shard. Documents that are not
yet confirmed live in `staging/`, because their expiry is not final until review.

```
archive/
  README.md                       # how to read this archive without Tabularius
  staging/                        # unconfirmed documents; not git
    store/…                       # same layout as a shard store
    intake/<intake_id>.json
    docs/<doc_uuid>.yaml          # working sidecars
  shards/
    2036/                         # everything that expires 2036-12-31
      README.md
      store/                      # immutable, content-addressed, 0444, owned by core user
        9f/2c/9f2c…e1.eml
        41/aa/41aa…07.pdf         # original / extracted attachment
        c3/10/c310…9b.pdf         # PDF/A rendition
        77/e2/77e2…4d.txt         # OCR text
        5b/90/5b90…aa.hocr        # OCR word boxes
      payload/<doc_uuid>.json     # sensitive field values; not git (§7.3)
      registry/                   # git repository, plain text
        intake/<intake_id>.json   # envelopes, append-only
        docs/<doc_uuid>.yaml      # sidecars — the only files that change
    open/                         # no fixed expiry; same layout
  ledger/                         # git: deletion log, no personal data (§12.4)
  journal/docs.journal            # generated hledger entries
  profiles/                       # types + templates (git; shareable part separable)
  index.sqlite                    # rebuildable cache, outside git
```

- **Assignment happens at confirm.** On confirm the core copies the document's
  blobs, its intake envelope and its sidecar from staging into the target shard,
  verifies hashes, commits, and only then removes the staging copies. Events from
  before confirm are carried over in the sidecar's `events` list.
- **Each shard has its own store.** The same blob needed by two shards (one email
  with attachments that expire in different years) is copied into both. Some
  duplication buys deletion without reference counting across shards.
- **Moving a confirmed document** (issue date or type corrected later) is a copy
  into the new shard plus `git rm` in the old one. The old shard's history keeps
  the sidecar until that shard is deleted; the move is recorded in both.
- No human-readable filenames inside the archive. Readable names are produced
  only on export.

### 7.3 Document sidecar

```yaml
id: 0199a1c2-7b3e-7f10-9c41-2d8e5a6b0f11
schema: document/1
intake: 0199a1c0-…
container: {sha256: 9f2c…e1, kind: email}       # optional
source:
  original:  {sha256: 41aa…07, mime: application/pdf, pages: [1, 2],
              claimed: PDF/A-1b, verapdf: fail, born_digital: false, dpi: 300}
  archive:   {sha256: c310…9b, format: PDF/A-2b, verapdf: pass,
              tools: {ocrmypdf: "16.x", tesseract: "5.x", langs: swe+eng}}
  text:      {sha256: 77e2…4d}
  hocr:      {sha256: 5b90…aa}
classification:
  type: invoice@2
  template: example-invoice@3
  method: identifier            # identifier | classifier | llm | manual
  confidence: 1.0
fields:                         # list of field records, see §8
  - {key: amount_due, type: money, value: {amount: 12500.00, currency: SEK},
     confidence: 0.98, source: {page: 1, bbox: [412,1180,560,1210], method: template},
     validation: {ok: true}, origin: profile, confirmed: true}
  - {key: personnummer, type: identifier, kind: personnummer,
     value: {payload: true}, origin: discovered, confirmed: true}  # see below
status: confirmed               # received | needs_review | confirmed | filed | quarantined
issued: 2026-09-28              # issue date; drives expiry
expires: 2036-12-31             # 31 Dec of (issue year + retention); null = open shard
shard: "2036"
hold: null                      # or {reason: "tax audit", since: 2031-03-01, by: andreas}
payload_sha256: 3e7a…c1         # hash of payload/<id>.json (which includes a random salt)
events:
  - {at: 2026-10-02T09:12:00Z, type: received, via: scanner}
  - {at: 2026-10-02T19:40:00Z, type: confirmed, by: andreas}
  - {at: 2026-10-02T19:40:01Z, type: payable_recorded, txn: V2026-0042}
  - {at: 2026-10-03T03:10:00Z, type: shred_ok, backup: "…"}
links:
  hledger: [V2026-0042]         # transaction codes
```

Every change to a confirmed sidecar is a git commit by the core with a
structured message (document id, event type, actor). Git history is the audit
log, and it lives exactly as long as the shard.

**Sensitive values stay out of git.** A field marked `sensitive: true` in its type,
and any `identifier` of kind `personnummer` wherever it is found, has its value written to `payload/<doc_uuid>.json`
in the shard, not to the sidecar. The payload file contains a random salt, so the
hash recorded in the sidecar cannot be used to guess a low-entropy value. Payload
files are not content-addressed and not in git; deleting one leaves nothing
behind in history. Note that the same value is still in the scan, the OCR text
and the index: the smallest unit of early deletion is the whole document (§12.4).

### 7.4 Source of truth — decision

Default: **the registries (one git repository per shard, plain text) are the
source of truth; SQLite is a rebuildable index** (`tab index rebuild`).

Alternative considered: SQLite as truth with nightly plain-text export. Rejected
for now: git gives audit history and tool-independent readability for free.
Revisit if performance or concurrency becomes a problem. *(Open question §16.)*

### 7.5 Index (SQLite)

FTS5 over OCR text; tables for documents, fields, correspondents/identifiers,
items (payables/deadlines), review queue. Never backed up; always rebuildable.
After any deletion the affected rows are removed and the database is `VACUUM`ed,
so deleted text does not linger in free pages.

---

## 8. Profiles and field records

### 8.1 Types — *what* a document contains

`profiles/types/<id>.yaml`. Few, general, rarely changed.

```yaml
id: invoice
version: 2
description: "Request for payment from a supplier"   # used by the LLM classifier
fields:
  correspondent: {type: party,      required: true, label: "Avsändare"}
  invoice_no:    {type: identifier, kind: invoice_no, required: true}
  amount_due:    {type: money,      required: true, label: "Att betala"}
  issue_date:    {type: date,       required: true, label: "Fakturadatum", role: issued}
  due_date:      {type: date,       required: true, label: "Förfallodag"}
  ocr:           {type: identifier, kind: ocr}
  bankgiro:      {type: identifier, kind: bankgiro}
uniqueness: [correspondent.orgnr, invoice_no]
retention: P10Y                 # or "open"
on_confirm: {hledger: payable}
```

- Every type has exactly one date field with `role: issued`. If it cannot be
  found, the received date is proposed and flagged in review.
- `retention: P10Y` means `expires` = 31 December of (issue year + 10). Expiry
  is always the end of a calendar year; that is what makes year shards possible.
- `retention: open` puts the document in the `open` shard until an expiry is set
  by hand (e.g. when a contract ends).
- A field definition may carry `sensitive: true` (§7.3).

Starter set: `invoice`, `receipt`, `statement`, `letter`, `contract`, `notice`
(authorities), `other`. Split a type only when it needs different fields or
actions.

### 8.2 Templates — *how* to find fields for one sender

`profiles/templates/<id>.yaml`. Many, specific, mostly generated.

```yaml
id: example-invoice
version: 3
type: invoice@2
status: active                 # candidate | active | retired
match:
  identifiers: {orgnr: "556000-0000"}
  keywords_all: ["Faktura"]
extract:
  amount_due: {anchor: "Att betala",  pattern: '([\d\s]+,\d{2})'}
  due_date:   {anchor: "Förfallodag", pattern: '(\d{4}-\d{2}-\d{2})'}
  ocr:        {anchor: "OCR",         pattern: '(\d{6,25})'}
```

Prior art: `invoice2data` (YAML templates per issuer).

### 8.3 Lifecycle

```
generic (no type)  → user picks a type in review
type, no template  → LLM extracts the type's fields; user confirms
3rd confirmed doc from same sender → system drafts a candidate template
                     (anchors from text preceding confirmed values; hOCR positions)
candidate passes tests → active (regex first, LLM fallback)
```

Discovered fields (`origin: discovered`) appear in an "Also found" section in
review: accept, reject, or **promote** into the type.

### 8.4 Testing profiles

Every confirmed document is a test case (OCR text + confirmed values).

```
$ hledger-tab profile test example-invoice
  12 documents   amount_due 12/12   due_date 12/12   ocr 11/12
  ✗ 0199a3…  ocr: expected "4410287733", got "441028773"
```

- Any profile change is tested against all confirmed documents of that type.
- **Auto-accept is earned**: a template with ≥ N consecutive correct extractions
  per field may skip review for that field above a confidence threshold.
  Any miss revokes it.
- `profile lint`: profiles are validated with pydantic at load; invalid profiles
  fail loudly.

### 8.5 Field records and the type vocabulary

The extractor always emits **self-describing field records**; the TUI never knows
field names, only types.

```json
{"key": "amount_due", "label": "Att betala", "type": "money",
 "value": {"amount": 449.00, "currency": "SEK"}, "confidence": 0.93,
 "source": {"page": 1, "bbox": [412,1180,560,1210], "method": "regex"},
 "validation": {"ok": true}, "required": true, "origin": "profile"}
```

| Type | Value shape | Validators |
|---|---|---|
| `text`, `longtext` | string | |
| `number` | decimal | range |
| `money` | {amount, currency} | currency code, sign |
| `date` | ISO date | plausibility window |
| `enum` | string (options listed) | membership |
| `bool` | bool | |
| `identifier` | string + `kind` | per kind: `ocr` (Luhn), `bankgiro`, `plusgiro`, `orgnr`, `personnummer`*, `iban`, `vat`, `invoice_no` |
| `party` | {name, orgnr?, address?} | orgnr check |
| `table` | {columns, rows} | per column |
| `unknown` | raw JSON | none — preserved, never dropped |

\* Personal identity numbers are sensitive; store only where a profile requires
it, and mark the field `sensitive: true` so the value goes to a payload file (§7.3).

---

## 9. Review TUI

### 9.1 Stack

- Python, **Textual**.
- Page images via **textual-image** (Sixel; the user's terminal is **foot**, which
  supports Sixel, not the Kitty protocol). Known caveat: Sixel in Textual is not
  very performant — acceptable for static pages; **first spike**.
- Fallback: the TUI drives an external **imv** window via `imv-msg` (Wayland,
  tiled next to the TUI).
- Pages rendered with pypdfium2.

### 9.2 Form rendering

A widget factory keyed on field **type** (§8.5). All field widgets share a base:
value input, confidence colour, jump-to-crop, accept/edit/reject, provenance badge.
Unknown types render as raw JSON. No per-document-type UI code, ever.

### 9.3 Screens and actions

- **Queue**: sorted by due date and lowest confidence; filters per status and type.
- **Document**: page image | fields | OCR text toggle. Crop of the selected field's
  source box.
- **Actions**: confirm · edit field · change type (re-extract) ·
  split / merge / reorder / rotate / mark blank · accept/reject/promote discovered
  fields · link to hledger transaction · mark filed.
- **Search**: full text, correspondent, type, status, amount, date ranges.
- **Integrity**: verify hashes, backup status, shred-OK list.
- **Retention**: shards past expiry, documents on hold, early deletion of a
  single document. Deletion needs explicit confirmation (the only irreversible
  actions; they must feel like it).
- **Quarantine**: retry, convert, reject.
- **Export**: BagIt per year or selection.

Keyboard-first, vim-style bindings, command palette.

### 9.4 Later

A web front end against the same API if someone other than Andreas needs access
or for phone review. Note: `textual-serve` is not supported by textual-image, so
serving the TUI in a browser is not a shortcut.

---

## 10. hledger integration (`hledger-tab`)

### 10.1 Conventions

- **Transaction code = verification number** (`(V2026-0042)`).
- **Tag `doc:<uuid>`** links a transaction to a document. Plain comments → the
  journal stays valid without the add-on.
- Additional tags as useful: `due:`, `ocr:`.

```
; docs.journal — generated by hledger-tab, do not edit
2026-10-02 (V2026-0042) Telia | faktura 88412  ; doc:0199a1c3-…, due:2026-10-30
    expenses:phone                     449.00 SEK
    liabilities:payable:telia
```

Payment from the bank import is booked against `liabilities:payable:<x>`;
`hledger bal liabilities:payable` is the list of unpaid bills.

### 10.2 Add-on

An executable named `hledger-tab` on `PATH` becomes `hledger tab`.

| Command | Purpose |
|---|---|
| `hledger tab check [QUERY]` | Every `doc:` tag resolves; hashes match; rules like "every expense > 500 SEK has a document". `file:line` errors, non-zero exit. Usable in pre-commit/CI |
| `hledger tab unlinked` | Money-documents with no transaction |
| `hledger tab show QUERY` | Documents for matching transactions (opens TUI/viewer) |
| `hledger tab attach TXN DOC` | Add a `doc:` tag — via the core, with confirmation |

- **Never parse the journal ourselves.** Use `hledger print -O json` (transactions,
  codes, tags, source positions).
- Payment matching: amount + OCR reference → automatic; otherwise review.
- The existing hledger finance app's receipt pipeline is the first consumer.

---

## 11. Parked: organisations

An earlier draft also covered a sports club's treasury. It is parked; nothing is
built for it, but the core should not rule it out. Notes for when it comes back:

- Run it as a separate instance (§4), not as a section of a personal archive.
- It needs a submission action (send to an external accountant, record the
  `Message-ID` as an event), a duplicate guard against documents that arrived
  through other channels, statutory retention per financial year, GDPR handling
  of members' data, and a handover export to a successor (BagIt).

---

## 12. Storage, backup, retention and deletion

Tabularius does not prescribe how the archive is stored, encrypted or backed
up. This section says what it needs from the deployment and what it does itself.
§12.5 describes the author's setup as one example.

### 12.1 What Tabularius needs from storage

- A local POSIX filesystem with atomic `rename()` inside the inbox and inside the
  archive, and `fsync` that is honoured.
- The core owns the archive and sets `store/` files to `0444`.
- Recommended, not required: checksums with redundancy (to detect *and* repair
  corruption), encryption at rest, snapshots.

### 12.2 Backup and shred OK

Tabularius does not make backups. To set `shred_ok` it asks a configured
**backup verifier**: "which of these sha256 are held in a backup off this
machine, and where?" The answer is stored in the `shred_ok` event.

- Interface: an executable that reads sha256 values on stdin and prints
  `<sha256> <backup ref>` for each one it can confirm. Anything not printed is
  not confirmed.
- Reference verifier for ZFS: find a local snapshot that contains the file with
  the right hash, then check that a snapshot with the same `guid` exists on the
  backup target. This works with raw sends, where the target holds no keys and
  cannot read the file itself.
- No verifier configured → `shred_ok` is never set, and the TUI says why.

### 12.3 Retention

- `expires` = 31 December of (year of the issue date + the type's retention).
  The issue date is confirmed in review, so expiry is final at confirm.
- The document goes to the shard named after its expiry year, or to `open`.
- A shard may be deleted from 1 January of the year after its name.

### 12.4 Deletion

- **Shard deletion (normal case).** A yearly job lists shards past expiry. The
  TUI shows counts, types and holds. On confirmation the core removes the shard
  directory (store, payloads, registry with its history), removes the rows from
  the index and vacuums it.
- **Legal hold.** A document with `hold` set blocks deletion of its shard. The
  TUI offers to move held documents to `open`, so the rest of the shard can go.
- **Early deletion of one document** (no longer needed, or a request to erase).
  The core deletes the document's blobs and payload from the shard, `git rm`s
  its sidecar, and updates the index. The shard's git history keeps the
  sidecar's non-sensitive metadata until the shard itself is deleted; sensitive
  values were never in git (§7.3). Blobs still referenced by another document in
  the same shard are kept.
- **The `open` shard** never expires as a whole, so documents leaving it (moved
  to a year shard, or deleted) leave history behind. Rewriting its history with
  `git filter-repo` is the one sanctioned exception to invariant 8; it is a
  separate, explicit command and is itself logged.
- **Deletion ledger** (`ledger/`, git). One entry per deletion: what (shard name
  or document id), when, by whom, number of documents and blobs, the final
  commit of the deleted registry, and the configured `backup_max_age`. It holds
  no personal data, so it can be kept indefinitely. `hledger tab check` uses it to
  report a `doc:` tag as *deleted per retention* rather than *missing*.
- **Copies outside Tabularius.** Snapshots, backups and exports still hold
  deleted data until they age out. Tabularius cannot delete them. The operator
  declares `backup_max_age` (how long the oldest backup is kept); each ledger
  entry records the date after which no backup should hold the data any more.
  Exports (§9.3) are the user's own copies.

### 12.5 Example deployment (the author's)

Not a requirement; shown because the design was tested against it.

```
tank/archive            encryption=on, compression=zstd, dedup=off
├── inbox               SFTP/SMB target; no snapshots; emptied by ingest
├── docs                snapshots hourly/daily/monthly (sanoid)
└── index               SQLite cache; no snapshots
```

- Redundancy: mirror, or `copies=2` on a single disk. Monthly scrub.
- Optionally `chattr +i` on store files (verify OpenZFS support on the running
  version).
- sanoid/syncoid replication to a second machine, **pulled** from the backup
  side, raw sends (`zfs send -w`) so the target needs no keys.
- Monthly snapshots kept for 12 months on both sides, so `backup_max_age` is one
  year: a deleted shard is gone from every snapshot one year later.

---

## 13. Security

- Scanner: untrusted; write-only inbox account; SFTP chroot (key auth if supported).
- Mail ingestion: dedicated credentials scoped to intake folders; the password in
  secrets management, not in plain config.
- Core runs as its own user with systemd hardening.
- Converters/parsers sandboxed: no network, minimal filesystem.
- Agent: read-only API token.
- Encryption at rest is the deployment's job (example: ZFS native encryption,
  §12.5). Sensitive field values are kept out of git history (§7.3).
- PDF/A renditions strip JavaScript and active content; the TUI never opens
  originals directly (temporary read-only copies only).

---

## 14. Tech stack

| Area | Choice |
|---|---|
| Language | Python 3.13 |
| Project/deps | uv |
| Types | pyright (strict) |
| Lint/format | ruff |
| Tests | pytest |
| Contracts | pydantic v2 (envelope, field record, sidecar, events, type, template) |
| OCR / PDF | ocrmypdf, Tesseract (`swe`, `eng`), pypdfium2, qpdf, veraPDF, img2pdf, LibreOffice (headless) |
| Barcodes | zxing-cpp or pyzbar |
| Email | stdlib `email`/`mailbox`; mbsync for sync |
| Classifier | scikit-learn |
| LLM | OpenAI-compatible / Ollama endpoint, local model |
| TUI | Textual, textual-image |
| Export | bagit-python |
| Service | systemd units (core, adapters), Unix socket API |

**Contracts first.** The pydantic models in `hledger_tab/contracts/` are the most
important files in the project and are reviewed by hand. Implementation may be
generated; contracts may not change silently.

---

## 15. Repository layout

```
tabularius/
  DESIGN.md
  README.md
  pyproject.toml                 # name = "hledger-tab"
  src/hledger_tab/
    contracts/                   # pydantic models — the source of truth for shapes
      envelope.py  field.py  document.py  events.py  profile.py
    core/                        # ingest, pipeline, persistence, API server
    adapters/                    # scanner, maildir, outbox
    pipeline/                    # analyse, normalise, ocr, split, identify, extract
    profiles/                    # loader, lint, test runner, template drafting
    hledger/                     # print -O json reader, docs.journal writer, check
    tui/                         # Textual app, field widget factory
    cli.py                       # hledger-tab entry point
  profiles/
    types/                       # shareable
    templates/                   # local (gitignored or separate repo)
  tests/
    invariants/                  # §2 — must never be skipped
    fixtures/
  systemd/
```

Import name: `hledger_tab` (PyPI `tabularius` is taken by an unrelated package).

---

## 16. Open questions

1. Registry as truth (git) vs SQLite as truth — decided provisionally for git (§7.4).
2. Example deployment: mirror or single disk (`copies=2`)?
3. ADS-1800W: SFTP key authentication or password only? Which SMB version if SMB?
4. Does the scanner's PDF/A-1b pass veraPDF?
5. Sixel performance in foot with Textual (spike).
6. ~~Licence (EUPL-1.2 vs MIT).~~ Decided: GPL-3.0-or-later.
7. Phone photos and email attachments in v1, or scanner only?
8. Default retention for each starter type (`invoice`, `receipt`, … ), and which
   types default to `open`.

---

## 17. Milestones

**M0 — Skeleton (1–2 evenings)**
uv project, contracts (pydantic), invariant test suite stubs, `hledger-tab --version`.

**M1 — Scanner to archive**
Scanner SFTP adapter → bundle → analyse → write-once staging store → ocrmypdf
PDF/A-2b → staging sidecar → SQLite index. Invariant tests green.

**M2 — Review TUI v0**
Queue, page image (Sixel spike / imv fallback), generic fields, confirm (moves
the document into its shard, first git commit), split/merge.

**M3 — Profiles**
Types + LLM extraction with field records; validators (OCR, bankgiro, orgnr);
template drafting; `profile test`.

**M4 — hledger**
`docs.journal` generation for payables, `hledger tab check`, payment matching.

**M5 — Email intake**
mbsync + Maildir adapter, container/attachment model, dedup.

**M6 — Export**
BagIt export of a year or a selection, with readable file names.

**M7 — Integrity, retention and deletion**
Backup verifier interface (ZFS reference verifier), shred OK, legal hold, shard
deletion, early deletion, deletion ledger.

---

## 18. Prior art

- **Paperless-ngx** — document management; ingestion, OCR, auto-classification,
  workflows. Document-first; we are content-first.
- **beancount** `document` directive and Fava — documents linked to accounts.
  hledger has no equivalent; this project fills that gap.
- **invoice2data** — YAML templates per issuer.
- **BagIt (RFC 8493)** — packaging for handover/export.
