# SPDX-License-Identifier: GPL-3.0-or-later
"""Document events: the ``events`` list of a sidecar (DESIGN.md §7.3).

``Event`` is a union discriminated on ``type``. Every event has a
timezone-aware ``at``. Events are appended, never edited; git history of the
sidecar is the audit log (§7.3).
"""

from typing import Annotated, Literal, Self

from pydantic import Field, model_validator

from hledger_tab.contracts.envelope import Channel
from hledger_tab.contracts.primitives import (
    Actor,
    ContractModel,
    NonEmptyStr,
    Sha256,
    ShardName,
    Timestamp,
    TxnCode,
)


class _EventBase(ContractModel):
    at: Timestamp


class ReceivedEvent(_EventBase):
    """The document arrived through ``via`` (§5.1)."""

    type: Literal["received"]
    via: Channel


class ConfirmedEvent(_EventBase):
    """A person confirmed the document in review (§9.3)."""

    type: Literal["confirmed"]
    by: Actor


class PayableRecordedEvent(_EventBase):
    """A payable was written to ``docs.journal`` as transaction ``txn`` (§10.1)."""

    type: Literal["payable_recorded"]
    txn: TxnCode


class BackupConfirmation(ContractModel):
    """One answer line of the backup verifier, ``<sha256> <backup ref>``
    (§12.2): the blob ``sha256`` is held in the backup ``backup``."""

    sha256: Sha256
    backup: NonEmptyStr


class ShredOkEvent(_EventBase):
    """The backup verifier confirmed the document's originals are held off
    this machine (§2 invariant 7, §12.2).

    ``backups`` has one entry per original blob the document references:
    the original file and, if any, its container (e.g. the ``.eml``).
    shred_ok is only set when every one of them is confirmed.
    """

    type: Literal["shred_ok"]
    backups: list[BackupConfirmation] = Field(min_length=1)

    @model_validator(mode="after")
    def _one_entry_per_blob(self) -> Self:
        hashes = [b.sha256 for b in self.backups]
        if len(set(hashes)) != len(hashes):
            raise ValueError("backups must not list a sha256 twice")
        return self


class MovedEvent(_EventBase):
    """The confirmed document was moved between shards, e.g. after its issue
    date or type was corrected (§7.2), or to ``open`` because of a hold
    (§12.4). Recorded in both shards."""

    type: Literal["moved"]
    from_shard: ShardName
    to_shard: ShardName
    by: Actor
    reason: NonEmptyStr | None = None

    @model_validator(mode="after")
    def _shards_differ(self) -> Self:
        if self.from_shard == self.to_shard:
            raise ValueError("a move must change the shard")
        return self


class HoldSetEvent(_EventBase):
    """A legal hold was placed on the document (§12.4)."""

    type: Literal["hold_set"]
    by: Actor
    reason: NonEmptyStr


class HoldReleasedEvent(_EventBase):
    """The legal hold was lifted (§12.4)."""

    type: Literal["hold_released"]
    by: Actor
    reason: NonEmptyStr | None = None


class QuarantinedEvent(_EventBase):
    """Processing failed and the document went to quarantine (§2 invariant 5,
    §6.1)."""

    type: Literal["quarantined"]
    reason: NonEmptyStr


type Event = Annotated[
    ReceivedEvent
    | ConfirmedEvent
    | PayableRecordedEvent
    | ShredOkEvent
    | MovedEvent
    | HoldSetEvent
    | HoldReleasedEvent
    | QuarantinedEvent,
    Field(discriminator="type"),
]
"""Any document event, selected by its ``type`` key."""
