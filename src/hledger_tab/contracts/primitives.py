# SPDX-License-Identifier: GPL-3.0-or-later
"""Primitive types shared by all contracts.

Everything here is a plain type alias or a small model; no behaviour beyond
validation. See DESIGN.md §7.1 (identity), §8.1 and §12.3 (retention),
§8.5 (money).
"""

from decimal import Decimal
from typing import Annotated, Any, Literal

from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
)
from pydantic.types import UUID7

from hledger_tab.core.retention import RETENTION_YEARS_PATTERN, SHARD_PATTERN


class ContractModel(BaseModel):
    """Base class of every contract model.

    ``extra="forbid"``: an unknown key is a validation error, never silently
    dropped (DESIGN.md §2, invariant 5). Pydantic's default (``"ignore"``)
    would discard it. Unknown *data* is representable only explicitly, as a
    field record of type ``unknown`` (§8.5).

    ``serialize_by_alias=True``: fields whose wire name is a Python keyword or
    clashes with ``BaseModel`` (``from``, ``schema``) dump under the wire name.
    """

    model_config = ConfigDict(extra="forbid", serialize_by_alias=True)


# --- Identity (§7.1) --------------------------------------------------------

type Sha256 = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
"""A sha256 digest: exactly 64 lowercase hexadecimal characters."""

type UUIDv7 = UUID7
"""A UUID of version 7 (RFC 9562 variant). Validation only; generating them
is not the contracts' job."""

type TxnCode = Annotated[str, StringConstraints(pattern=r"^[^\s()]+$")]
"""An hledger transaction code (verification number), e.g. ``V2026-0042``
(§10.1). No whitespace or parentheses, since hledger writes it as ``(code)``."""


# --- Names and references -----------------------------------------------------

type NonEmptyStr = Annotated[str, StringConstraints(min_length=1)]

type Actor = Annotated[str, StringConstraints(pattern=r"^\S+$")]
"""Who did something, e.g. ``andreas`` or ``core``. One word."""

type FieldKey = Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9_]*$")]
"""A field name, e.g. ``amount_due`` (§8.1, §8.5)."""

type ProfileId = Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9_-]*$")]
"""The id of a type or template, e.g. ``invoice``, ``example-invoice``."""

type ProfileRef = Annotated[
    str, StringConstraints(pattern=r"^[a-z][a-z0-9_-]*@[1-9][0-9]*$")
]
"""A versioned reference to a type or template, e.g. ``invoice@2`` (§8.2)."""

type ShardName = Annotated[str, StringConstraints(pattern=SHARD_PATTERN)]
"""A shard: its expiry year as four digits, e.g. ``"2036"``, or ``"open"``
(§7.2, §12.3)."""


# --- Retention (§8.1, §12.3) --------------------------------------------------

type RetentionYears = Annotated[str, StringConstraints(pattern=RETENTION_YEARS_PATTERN)]
"""A whole-year ISO 8601 duration ``P<n>Y`` with n >= 1, e.g. ``P10Y``."""

type Retention = Literal["open"] | RetentionYears
"""How long a type's documents are kept: ``P<n>Y`` or ``"open"``."""


# --- Money (§8.5) -------------------------------------------------------------


def _reject_float(value: Any) -> Any:
    """Refuse binary floats before pydantic converts them to ``Decimal``.

    Pydantic would accept ``449.1`` and convert it, and a JSON number reaches
    a ``Decimal`` field through a Python float, which loses digits beyond
    about 17 significant figures. Amounts must therefore be written as
    strings (``"449.10"``), integers or ``Decimal`` objects.
    """
    if isinstance(value, float):
        raise ValueError(
            'floats are not accepted for decimal values; write a string, e.g. "449.10"'
        )
    return value


type DecimalValue = Annotated[
    Decimal, BeforeValidator(_reject_float), Field(allow_inf_nan=False)
]
"""A finite decimal number that never passed through a float."""

type Currency = Annotated[str, StringConstraints(pattern=r"^[A-Z]{3}$")]
"""An ISO 4217 style currency code: three uppercase letters, e.g. ``SEK``.
Membership of the actual ISO 4217 list is a validator's job (§8.5)."""


class Money(ContractModel):
    """An amount of money (§8.5). ``amount`` is a ``Decimal``, never a float."""

    amount: DecimalValue
    currency: Currency


# --- Payload reference (§7.3) ------------------------------------------------


class PayloadRef(ContractModel):
    """Stands in for a sensitive value stored in ``payload/<doc_uuid>.json``.

    Written as ``{payload: true}`` in place of the value (§7.3). Only the
    boolean ``true`` is accepted: ``1`` or ``"true"`` are rejected, so that a
    raw ``unknown`` value is never mistaken for a payload reference.
    """

    payload: Literal[True]

    @field_validator("payload", mode="before")
    @classmethod
    def _exactly_true(cls, value: Any) -> Any:
        if value is not True:
            raise ValueError("payload must be the boolean true")
        return value
