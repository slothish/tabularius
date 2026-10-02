# SPDX-License-Identifier: GPL-3.0-or-later
"""Primitive types shared by all contracts.

Everything here is a plain type alias or a small model; no behaviour beyond
validation. See DESIGN.md §7.1 (identity), §8.1 and §12.3 (retention),
§8.5 (money).
"""

import re
from datetime import date
from decimal import Decimal
from typing import Annotated, Any, Final, Literal
from uuid import UUID

from pydantic import (
    AwareDatetime,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    Strict,
    StringConstraints,
    WithJsonSchema,
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

UUID7_PATTERN: Final = (
    r"^[0-9a-f]{8}-[0-9a-f]{4}-7[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
)
"""The canonical text form of a UUIDv7: lowercase, hyphenated, version 7,
RFC 9562 variant."""


def _canonical_uuid7(value: Any) -> Any:
    """Accept a ``UUID`` object or the canonical text form only.

    Pydantic's UUID parsing also takes uppercase, ``{...}``, ``urn:uuid:``
    and unhyphenated forms; identifiers are compared and used as file
    names as text, so only one spelling is allowed.
    """
    if isinstance(value, UUID):
        return value
    if isinstance(value, str) and re.fullmatch(UUID7_PATTERN, value):
        return value
    raise ValueError("must be a UUIDv7 in canonical form (lowercase, hyphenated)")


type UUIDv7 = Annotated[
    UUID7,
    BeforeValidator(_canonical_uuid7),
    WithJsonSchema({"type": "string", "format": "uuid", "pattern": UUID7_PATTERN}),
]
"""A UUID of version 7 (RFC 9562 variant) in canonical form. Validation
only; generating them is not the contracts' job."""

type TxnCode = Annotated[str, StringConstraints(pattern=r"^[^\s()]+$")]
"""An hledger transaction code (verification number), e.g. ``V2026-0042``
(§10.1). No whitespace or parentheses, since hledger writes it as ``(code)``."""


# --- Numbers, dates and timestamps -------------------------------------------
#
# Pydantic's default ("lax") mode turns ``true``, ``"2"`` and ``2.0`` into
# the int 2, and an int or a numeric string into a date (as a Unix
# timestamp). These types refuse such conversions.

type PositiveStrictInt = Annotated[int, Strict(), Field(gt=0)]
"""An int > 0; no bool, string or float input."""

type NonNegativeStrictInt = Annotated[int, Strict(), Field(ge=0)]
"""An int >= 0; no bool, string or float input."""

type Confidence = Annotated[float, Strict(), Field(ge=0.0, le=1.0)]
"""A confidence between 0 and 1. A float, or an int (0 or 1); no bool or
string input."""


def _reject_non_iso_dates(value: Any) -> Any:
    """Refuse numbers and timestamps for dates and datetimes.

    A string must start with a four-digit year and ``-`` (ISO 8601); pydantic
    then parses it. ``date``/``datetime`` objects pass unchanged.
    """
    if isinstance(value, int | float):  # includes bool
        raise ValueError("must be an ISO 8601 date or timestamp, not a number")
    if isinstance(value, str) and not re.match(r"[0-9]{4}-", value):
        raise ValueError("must be an ISO 8601 date or timestamp (YYYY-MM-DD...)")
    return value


type IsoDate = Annotated[date, BeforeValidator(_reject_non_iso_dates)]
"""A calendar date, written ``YYYY-MM-DD``."""

type Timestamp = Annotated[AwareDatetime, BeforeValidator(_reject_non_iso_dates)]
"""A timezone-aware ISO 8601 timestamp, e.g. ``2026-10-02T08:14:03Z``."""


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


DECIMAL_PATTERN: Final = r"^-?(0|[1-9][0-9]*)(\.[0-9]+)?$"
"""A plain decimal number as text: optional minus, no leading zeros, no
exponent, no spaces or underscores, e.g. ``"449.00"``."""


def _decimal_input(value: Any) -> Any:
    """Accept an int or a string matching ``DECIMAL_PATTERN`` (and, from
    Python code, a ``Decimal``); refuse everything else.

    Floats are refused because a JSON number with a fraction reaches the
    validator as a binary float, which cannot hold most decimal amounts
    exactly. Write ``"449.10"``, not ``449.10``.
    """
    if isinstance(value, bool):
        raise ValueError("must be a decimal number, not a boolean")
    if isinstance(value, int | Decimal):
        return value
    if isinstance(value, str) and re.fullmatch(DECIMAL_PATTERN, value):
        return value
    if isinstance(value, float):
        raise ValueError(
            'floats are not accepted for decimal values; write a string, e.g. "449.10"'
        )
    raise ValueError('must be an integer or a decimal string such as "449.10"')


type DecimalValue = Annotated[
    Decimal,
    BeforeValidator(_decimal_input),
    Field(allow_inf_nan=False),
    WithJsonSchema(
        {"anyOf": [{"type": "integer"}, {"type": "string", "pattern": DECIMAL_PATTERN}]}
    ),
]
"""A finite decimal number that never passed through a float. On the wire:
an integer, or a string matching ``DECIMAL_PATTERN``."""

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
