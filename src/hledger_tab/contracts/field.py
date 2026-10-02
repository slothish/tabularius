# SPDX-License-Identifier: GPL-3.0-or-later
"""Field records: self-describing extracted values (DESIGN.md §8.5).

The extractor always emits field records, and the TUI renders them by
``type`` alone, never by field name. ``FieldRecord`` is a union
discriminated on ``type``; there is one model per row of the §8.5 table.

A record's ``value`` is one of:

- the value itself, in the shape its type defines;
- ``{payload: true}`` (``PayloadRef``): the value is sensitive and stored in
  the shard's ``payload/<doc_uuid>.json`` instead (§7.3);
- ``null``: no value was found (e.g. a required field the extractor missed).
"""

from collections.abc import Set
from enum import StrEnum
from typing import Annotated, Final, Literal, Self

from pydantic import Field, JsonValue, StrictBool, model_validator

from hledger_tab.contracts.primitives import (
    Confidence,
    ContractModel,
    DecimalValue,
    FieldKey,
    IsoDate,
    Money,
    NonEmptyStr,
    NonNegativeStrictInt,
    PayloadRef,
    PositiveStrictInt,
)

# --- Vocabulary -------------------------------------------------------------


class FieldType(StrEnum):
    """The type vocabulary of §8.5. Also used by type profiles (§8.1)."""

    TEXT = "text"
    LONGTEXT = "longtext"
    NUMBER = "number"
    MONEY = "money"
    DATE = "date"
    ENUM = "enum"
    BOOL = "bool"
    IDENTIFIER = "identifier"
    PARTY = "party"
    TABLE = "table"
    UNKNOWN = "unknown"


class IdentifierKind(StrEnum):
    """Kinds of ``identifier`` values (§8.5). Each kind has its own validator."""

    OCR = "ocr"
    BANKGIRO = "bankgiro"
    PLUSGIRO = "plusgiro"
    ORGNR = "orgnr"
    PERSONNUMMER = "personnummer"
    IBAN = "iban"
    VAT = "vat"
    INVOICE_NO = "invoice_no"


SENSITIVE_IDENTIFIER_KINDS: Final = frozenset({IdentifierKind.PERSONNUMMER})
"""Identifier kinds that are sensitive wherever they occur (§7.3, §7.6).
No profile can unmark them."""


class Origin(StrEnum):
    """Whether a field was asked for by the type profile or found besides it
    (§6.6, §8.3)."""

    PROFILE = "profile"
    DISCOVERED = "discovered"


class ExtractionMethod(StrEnum):
    """How a value was obtained."""

    TEMPLATE = "template"
    REGEX = "regex"
    LLM = "llm"
    MANUAL = "manual"


# --- Common attributes ------------------------------------------------------


class SourceLocation(ContractModel):
    """Where a value was found.

    ``page`` is 1-based. ``bbox`` is ``[x0, y0, x1, y1]`` in the pixel
    coordinates of the page's hOCR (§6.3), with ``x0 <= x1`` and ``y0 <= y1``.
    Both are absent for values that do not come from a page (e.g. manual).
    """

    page: PositiveStrictInt | None = None
    bbox: (
        tuple[
            NonNegativeStrictInt,
            NonNegativeStrictInt,
            NonNegativeStrictInt,
            NonNegativeStrictInt,
        ]
        | None
    ) = None
    method: ExtractionMethod

    @model_validator(mode="after")
    def _bbox_ordered(self) -> Self:
        if self.bbox is not None:
            x0, y0, x1, y1 = self.bbox
            if x0 > x1 or y0 > y1:
                raise ValueError("bbox must be [x0, y0, x1, y1] with x0<=x1, y0<=y1")
        return self


class ValidationResult(ContractModel):
    """Outcome of the validators run on the value (§6.6)."""

    ok: StrictBool
    message: str | None = None


class _FieldRecordBase(ContractModel):
    """Attributes common to every field record (§8.5)."""

    key: FieldKey
    label: NonEmptyStr | None = None
    confidence: Confidence | None = None
    source: SourceLocation | None = None
    validation: ValidationResult | None = None
    required: StrictBool = False
    origin: Origin
    confirmed: StrictBool = False


# --- Value shapes -----------------------------------------------------------


class Party(ContractModel):
    """A counterparty: ``{name, orgnr?, address?}`` (§8.5)."""

    name: NonEmptyStr
    orgnr: NonEmptyStr | None = None
    address: NonEmptyStr | None = None


class Table(ContractModel):
    """A table: ``{columns, rows}`` (§8.5).

    Cells are kept as the text that was read (or ``null`` for an empty
    cell); per-column validators interpret them. Every row has exactly one
    cell per column.
    """

    columns: list[NonEmptyStr] = Field(min_length=1)
    rows: list[list[str | None]]

    @model_validator(mode="after")
    def _rows_match_columns(self) -> Self:
        width = len(self.columns)
        for index, row in enumerate(self.rows):
            if len(row) != width:
                raise ValueError(f"row {index} has {len(row)} cells, expected {width}")
        return self


# --- One record model per type ----------------------------------------------
#
# Each ``value`` is ``PayloadRef | <shape> | None``, tried left to right, so
# ``{payload: true}`` is always read as a payload reference.


class TextField(_FieldRecordBase):
    """``text`` (one line) or ``longtext`` (free text): a string."""

    type: Literal["text", "longtext"]
    value: Annotated[PayloadRef | str | None, Field(union_mode="left_to_right")]


class NumberField(_FieldRecordBase):
    """``number``: a decimal."""

    type: Literal["number"]
    value: Annotated[
        PayloadRef | DecimalValue | None, Field(union_mode="left_to_right")
    ]


class MoneyField(_FieldRecordBase):
    """``money``: ``{amount, currency}``."""

    type: Literal["money"]
    value: Annotated[PayloadRef | Money | None, Field(union_mode="left_to_right")]


class DateField(_FieldRecordBase):
    """``date``: an ISO date."""

    type: Literal["date"]
    value: Annotated[PayloadRef | IsoDate | None, Field(union_mode="left_to_right")]


class EnumField(_FieldRecordBase):
    """``enum``: a string from ``options``.

    ``options`` travels with the record so the TUI can render the choice
    without knowing the profile. Membership is a validator's verdict
    (``validation``), not a schema error: a value outside the options must
    still be representable so that it can be reviewed.
    """

    type: Literal["enum"]
    options: list[NonEmptyStr] = Field(min_length=1)
    value: Annotated[PayloadRef | str | None, Field(union_mode="left_to_right")]


class BoolField(_FieldRecordBase):
    """``bool``: true or false."""

    type: Literal["bool"]
    value: Annotated[PayloadRef | StrictBool | None, Field(union_mode="left_to_right")]


class IdentifierField(_FieldRecordBase):
    """``identifier``: a string of a given ``kind``."""

    type: Literal["identifier"]
    kind: IdentifierKind
    value: Annotated[PayloadRef | str | None, Field(union_mode="left_to_right")]


class PartyField(_FieldRecordBase):
    """``party``: ``{name, orgnr?, address?}``."""

    type: Literal["party"]
    value: Annotated[PayloadRef | Party | None, Field(union_mode="left_to_right")]


class TableField(_FieldRecordBase):
    """``table``: ``{columns, rows}``."""

    type: Literal["table"]
    value: Annotated[PayloadRef | Table | None, Field(union_mode="left_to_right")]


class UnknownField(_FieldRecordBase):
    """``unknown``: raw JSON, preserved as found and never dropped (§2, inv. 5).

    ``null`` here means a JSON null was found or nothing was found; the two
    are not distinguished.
    """

    type: Literal["unknown"]
    value: Annotated[PayloadRef | JsonValue, Field(union_mode="left_to_right")]


type FieldRecord = Annotated[
    TextField
    | NumberField
    | MoneyField
    | DateField
    | EnumField
    | BoolField
    | IdentifierField
    | PartyField
    | TableField
    | UnknownField,
    Field(discriminator="type"),
]
"""A field record of any type, selected by its ``type`` key (§8.5)."""


def is_sensitive(
    record: FieldRecord, profile_sensitive: Set[str] = frozenset()
) -> bool:
    """Tell whether ``record``'s value must live in the payload file (§7.3).

    A record is sensitive if it is an ``identifier`` of a kind in
    ``SENSITIVE_IDENTIFIER_KINDS`` (wherever it was found, including
    discovered fields), or if its key is one the type profile marks
    ``sensitive: true``; pass those keys as ``profile_sensitive`` (see
    ``TypeProfile.sensitive_keys``). A profile can add sensitive fields but
    cannot unmark the built-in kinds (§7.6).
    """
    if (
        isinstance(record, IdentifierField)
        and record.kind in SENSITIVE_IDENTIFIER_KINDS
    ):
        return True
    return record.key in profile_sensitive
