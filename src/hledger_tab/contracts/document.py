# SPDX-License-Identifier: GPL-3.0-or-later
"""The document sidecar, ``docs/<doc_uuid>.yaml`` (DESIGN.md §7.3).

One sidecar per logical document. In a shard it is the only registry file
that changes; every change is a git commit by the core (§7.3).

Keys that the §7.3 example shows are required keys here, even where the
value may be ``null`` (``classification``, ``issued``, ``expires``,
``hold``, ``payload_sha256``): a missing key is an error, an explicit
``null`` is not. Only ``container`` is optional, as in the example.
"""

from enum import StrEnum
from typing import Literal, Self

from pydantic import Field, StrictBool, model_validator

from hledger_tab.contracts.events import Event
from hledger_tab.contracts.field import FieldRecord, is_sensitive
from hledger_tab.contracts.primitives import (
    Actor,
    Confidence,
    ContractModel,
    IsoDate,
    NonEmptyStr,
    PayloadRef,
    PositiveStrictInt,
    ProfileRef,
    Sha256,
    ShardName,
    TxnCode,
    UUIDv7,
)
from hledger_tab.core.retention import is_end_of_year, shard_for

# --- Sources (§6.2, §7.1) ---------------------------------------------------


class ContainerKind(StrEnum):
    """What kind of file the document was extracted from."""

    EMAIL = "email"


class Container(ContractModel):
    """The file the document's original was extracted from, e.g. an email."""

    sha256: Sha256
    kind: ContainerKind


class VeraPdfResult(StrEnum):
    """veraPDF verdict (§6.1, §6.2)."""

    PASS = "pass"
    FAIL = "fail"


type MimeType = NonEmptyStr


class OriginalSource(ContractModel):
    """The untouched original and what analysis found out about it (§6.1).

    ``pages``: the pages of the original that make up this document, in
    document order (one file can hold several documents, §7.1). ``claimed``:
    the format the file claims, e.g. ``PDF/A-1b``; ``verapdf``: whether that
    claim was verified. ``dpi`` applies to scans.
    """

    sha256: Sha256
    mime: MimeType
    pages: list[PositiveStrictInt] = Field(min_length=1)
    claimed: NonEmptyStr | None = None
    verapdf: VeraPdfResult | None = None
    born_digital: StrictBool | None = None
    dpi: PositiveStrictInt | None = None

    @model_validator(mode="after")
    def _pages_unique(self) -> Self:
        if len(set(self.pages)) != len(self.pages):
            raise ValueError("pages must not repeat")
        return self


class ArchiveSource(ContractModel):
    """The archive rendition (§6.2), with the tools that produced it."""

    sha256: Sha256
    format: NonEmptyStr
    verapdf: VeraPdfResult
    tools: dict[NonEmptyStr, str]


class BlobRef(ContractModel):
    """A derived blob identified by hash only (OCR text, hOCR)."""

    sha256: Sha256


class Sources(ContractModel):
    """All blobs of the document. Only ``original`` exists from the start;
    the others appear as the pipeline runs (§6)."""

    original: OriginalSource
    archive: ArchiveSource | None = None
    text: BlobRef | None = None
    hocr: BlobRef | None = None


# --- Classification (§6.5) --------------------------------------------------


class ClassificationMethod(StrEnum):
    IDENTIFIER = "identifier"
    CLASSIFIER = "classifier"
    LLM = "llm"
    MANUAL = "manual"


class Classification(ContractModel):
    """The document's type, how it was decided and how sure (§6.5)."""

    type: ProfileRef
    template: ProfileRef | None = None
    method: ClassificationMethod
    confidence: Confidence


# --- Status, hold, links -----------------------------------------------------


class Status(StrEnum):
    """Where the document is in its life (§7.3)."""

    RECEIVED = "received"
    NEEDS_REVIEW = "needs_review"
    CONFIRMED = "confirmed"
    FILED = "filed"
    QUARANTINED = "quarantined"


ASSIGNED_STATUSES: frozenset[Status] = frozenset({Status.CONFIRMED, Status.FILED})
"""Statuses of a document that has been assigned to a shard.

Assignment happens at confirm (§7.2): the issue date is confirmed in review,
so expiry, and with it the shard, is final (§12.3). Before that the
document lives in ``staging/`` and has no shard."""


class Hold(ContractModel):
    """A legal hold (§12.4): blocks deletion of the document's shard."""

    reason: NonEmptyStr
    since: IsoDate
    by: Actor


class Links(ContractModel):
    """Links to other systems. ``hledger``: transaction codes (§10.1)."""

    hledger: list[TxnCode] = Field(default_factory=list[TxnCode])


# --- The sidecar --------------------------------------------------------------


class Document(ContractModel):
    """A document sidecar (§7.3).

    Model-level checks:

    - ``expires``, if set, is a 31 December (§8.1: expiry is always the end
      of a calendar year).
    - ``expires``, if set together with ``issued``, is in a later year
      (retention is at least one year, §8.1).
    - Shard assignment (§7.2): a confirmed or filed document has ``issued``
      and ``shard`` set; a document in staging (received, needs_review,
      quarantined) has ``shard: null``. ``expires`` may already be filled
      provisionally in staging.
    - A set ``shard`` is the year of ``expires``, or ``"open"`` iff
      ``expires`` is null (§7.2, §12.3).
    - Field keys are unique.
    - Built-in sensitive values (``identifier`` of kind ``personnummer``)
      are never stored inline: their value is ``{payload: true}`` or null
      (§7.3). Fields that a *profile* marks sensitive are checked where the
      profile is known, not here.
    - A payload reference requires ``payload_sha256``.
    """

    id: UUIDv7
    schema_: Literal["document/1"] = Field(alias="schema")
    intake: UUIDv7
    container: Container | None = None
    source: Sources
    classification: Classification | None
    fields: list[FieldRecord]
    status: Status
    issued: IsoDate | None
    expires: IsoDate | None
    shard: ShardName | None
    hold: Hold | None
    payload_sha256: Sha256 | None
    events: list[Event]
    links: Links

    @model_validator(mode="after")
    def _expires_is_end_of_year(self) -> Self:
        if self.expires is not None and not is_end_of_year(self.expires):
            raise ValueError(f"expires must be a 31 December, got {self.expires}")
        return self

    @model_validator(mode="after")
    def _expires_after_issue_year(self) -> Self:
        if (
            self.issued is not None
            and self.expires is not None
            and self.expires.year <= self.issued.year
        ):
            raise ValueError(
                f"expires {self.expires} must be in a later year than "
                f"issued {self.issued}"
            )
        return self

    @model_validator(mode="after")
    def _shard_set_iff_assigned(self) -> Self:
        if self.status in ASSIGNED_STATUSES:
            if self.issued is None:
                raise ValueError(f"issued must be set when status is {self.status}")
            if self.shard is None:
                raise ValueError(f"shard must be set when status is {self.status}")
        elif self.shard is not None:
            raise ValueError(
                f"shard must be null in staging (status {self.status}), "
                f"got {self.shard!r}"
            )
        return self

    @model_validator(mode="after")
    def _shard_matches_expires(self) -> Self:
        if self.shard is None:
            return self
        expected = shard_for(self.expires)
        if self.shard != expected:
            raise ValueError(
                f"shard {self.shard!r} does not match expires {self.expires}; "
                f"expected {expected!r}"
            )
        return self

    @model_validator(mode="after")
    def _field_keys_unique(self) -> Self:
        keys = [f.key for f in self.fields]
        duplicates = sorted({k for k in keys if keys.count(k) > 1})
        if duplicates:
            raise ValueError(f"duplicate field keys: {duplicates}")
        return self

    @model_validator(mode="after")
    def _builtin_sensitive_not_inline(self) -> Self:
        for record in self.fields:
            inline = record.value is not None and not isinstance(
                record.value, PayloadRef
            )
            if inline and is_sensitive(record):
                raise ValueError(
                    f"field {record.key!r} is sensitive; its value must be "
                    "{payload: true}, not stored in the sidecar"
                )
        return self

    @model_validator(mode="after")
    def _payload_ref_has_payload(self) -> Self:
        uses_payload = any(isinstance(f.value, PayloadRef) for f in self.fields)
        if uses_payload and self.payload_sha256 is None:
            raise ValueError("a field refers to the payload but payload_sha256 is null")
        return self
