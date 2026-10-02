# SPDX-License-Identifier: GPL-3.0-or-later
"""The intake bundle envelope, ``envelope.json`` (DESIGN.md §5.2).

An adapter writes one envelope per bundle. The core stores it verbatim in
``registry/intake/YYYY/<intake_id>.json`` and never edits it afterwards.
"""

from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import (
    AfterValidator,
    Field,
    StringConstraints,
    model_validator,
)

from hledger_tab.contracts.primitives import (
    ContractModel,
    NonEmptyStr,
    Sha256,
    Timestamp,
    UUIDv7,
)


class Channel(StrEnum):
    """How a bundle arrived (§5.1)."""

    SCANNER = "scanner"
    MAILDIR = "maildir"
    AGENT = "agent"
    MANUAL = "manual"


class FileRole(StrEnum):
    """What a payload file in a bundle is.

    ``container``: holds further documents that the core extracts, e.g. an
    ``.eml`` with attachments. ``document``: is itself a document source,
    e.g. a scanned PDF or a photo.
    """

    CONTAINER = "container"
    DOCUMENT = "document"


RESERVED_FILE_NAMES = frozenset({".", "..", "envelope.json"})


def _not_reserved(name: str) -> str:
    if name in RESERVED_FILE_NAMES:
        raise ValueError(f"{name!r} is not allowed as a payload file name")
    return name


type FileName = Annotated[
    str,
    StringConstraints(pattern=r"^[^/\x00]+$"),
    AfterValidator(_not_reserved),
]
"""A plain file name inside the bundle directory: no ``/``, no NUL, not
``.``/``..``, and not ``envelope.json`` itself."""

type AdapterId = Annotated[str, StringConstraints(pattern=r"^[^@\s]+@[^@\s]+$")]
"""``<adapter name>@<version>``, e.g. ``scanner-sftp@0.1.0``."""


class EnvelopeFile(ContractModel):
    """One payload file in the bundle, exactly as received."""

    name: FileName
    sha256: Sha256
    role: FileRole


class Envelope(ContractModel):
    """``envelope.json`` of an intake bundle (§5.2).

    ``source_ref`` holds adapter-specific references (``message_id``,
    ``mailbox``, ``scan_profile``, …) as a flat string mapping. It is kept
    open on purpose: each adapter defines its own keys, and the envelope is
    stored verbatim, so nothing in it is dropped.
    """

    intake_id: UUIDv7
    schema_: Literal["envelope/1"] = Field(alias="schema")
    channel: Channel
    adapter: AdapterId
    received_at: Timestamp
    source_ref: dict[NonEmptyStr, str]
    from_: str | None = Field(default=None, alias="from")
    subject: str | None = None
    files: list[EnvelopeFile] = Field(min_length=1)

    @model_validator(mode="after")
    def _file_names_unique(self) -> Self:
        names = [f.name for f in self.files]
        duplicates = sorted({n for n in names if names.count(n) > 1})
        if duplicates:
            raise ValueError(f"duplicate file names in files: {duplicates}")
        return self
