# SPDX-License-Identifier: GPL-3.0-or-later
"""Profiles: document types and sender templates (DESIGN.md §8.1, §8.2).

A *type profile* says what a document contains (``profiles/types/<id>.yaml``);
a *template* says how to find those fields for one sender
(``profiles/templates/<id>.yaml``). Profiles are validated at load and
invalid ones fail loudly (§8.4).
"""

import re
from enum import StrEnum
from typing import Literal, Self

from pydantic import Field, PositiveInt, StrictBool, field_validator, model_validator

from hledger_tab.contracts.field import FieldType, IdentifierKind, Party
from hledger_tab.contracts.primitives import (
    ContractModel,
    FieldKey,
    NonEmptyStr,
    ProfileId,
    ProfileRef,
    Retention,
)

# --- Type profile (§8.1) ----------------------------------------------------


class FieldRole(StrEnum):
    """A special meaning a field has for the core.

    ``issued``: the issue date, which drives expiry (§8.1, §12.3).
    """

    ISSUED = "issued"


class FieldDefinition(ContractModel):
    """One field a type asks for (§8.1).

    ``description`` explains the field to the LLM extractor, which works from
    "the type's field descriptions" (§6.6).

    Checks: ``kind`` is given iff ``type`` is ``identifier``; ``options`` is
    given iff ``type`` is ``enum``, non-empty and without repeats.
    """

    type: FieldType
    required: StrictBool = False
    label: NonEmptyStr | None = None
    description: NonEmptyStr | None = None
    kind: IdentifierKind | None = None
    role: FieldRole | None = None
    sensitive: StrictBool = False
    options: list[NonEmptyStr] | None = None

    @model_validator(mode="after")
    def _kind_iff_identifier(self) -> Self:
        is_identifier = self.type is FieldType.IDENTIFIER
        if is_identifier and self.kind is None:
            raise ValueError("an identifier field needs a kind")
        if not is_identifier and self.kind is not None:
            raise ValueError(
                f"kind is only allowed on identifier fields, not {self.type}"
            )
        return self

    @model_validator(mode="after")
    def _options_iff_enum(self) -> Self:
        is_enum = self.type is FieldType.ENUM
        if is_enum and not self.options:
            raise ValueError("an enum field needs a non-empty list of options")
        if not is_enum and self.options is not None:
            raise ValueError(
                f"options are only allowed on enum fields, not {self.type}"
            )
        if self.options is not None and len(set(self.options)) != len(self.options):
            raise ValueError("options must not repeat")
        return self


class HledgerAction(StrEnum):
    """What to record in hledger when a document of the type is confirmed
    (§10.1)."""

    PAYABLE = "payable"


class OnConfirm(ContractModel):
    """Actions run on confirm. Absent or ``null`` means: none."""

    hledger: HledgerAction | None = None


PARTY_ATTRIBUTES: frozenset[str] = frozenset(Party.model_fields)
"""Sub-keys a uniqueness path may use on a ``party`` field."""


class TypeProfile(ContractModel):
    """A document type (§8.1).

    ``uniqueness``: field paths that together identify a document for
    duplicate detection (§5.3), e.g. ``correspondent.orgnr``. A path is a
    field key, or ``<party field>.<name|orgnr|address>``.

    ``retention``: ``P<n>Y`` or ``open`` (§8.1, §12.3).

    Checks: exactly one field has ``role: issued``, and it is of type
    ``date``; every uniqueness path refers to a defined field.
    """

    schema_: Literal["type/1"] = Field(alias="schema")
    id: ProfileId
    version: PositiveInt
    description: NonEmptyStr
    fields: dict[FieldKey, FieldDefinition] = Field(min_length=1)
    uniqueness: list[NonEmptyStr] = Field(default_factory=list[str])
    retention: Retention
    on_confirm: OnConfirm = Field(default_factory=OnConfirm)

    @model_validator(mode="after")
    def _exactly_one_issued_date(self) -> Self:
        issued = [key for key, f in self.fields.items() if f.role is FieldRole.ISSUED]
        if len(issued) != 1:
            raise ValueError(
                f"exactly one field must have role: issued, found {len(issued)}"
                + (f" ({', '.join(issued)})" if issued else "")
            )
        definition = self.fields[issued[0]]
        if definition.type is not FieldType.DATE:
            raise ValueError(
                f"the role: issued field {issued[0]!r} must be of type date, "
                f"not {definition.type}"
            )
        return self

    @model_validator(mode="after")
    def _uniqueness_paths_exist(self) -> Self:
        for path in self.uniqueness:
            key, _, attribute = path.partition(".")
            definition = self.fields.get(key)
            if definition is None:
                raise ValueError(f"uniqueness path {path!r}: no field {key!r}")
            if attribute and (
                definition.type is not FieldType.PARTY
                or attribute not in PARTY_ATTRIBUTES
            ):
                raise ValueError(
                    f"uniqueness path {path!r}: only party fields have sub-keys "
                    f"({', '.join(sorted(PARTY_ATTRIBUTES))})"
                )
        return self

    @property
    def issued_field(self) -> str:
        """The key of the ``role: issued`` field (exists by validation)."""
        return next(k for k, f in self.fields.items() if f.role is FieldRole.ISSUED)

    @property
    def sensitive_keys(self) -> frozenset[str]:
        """Keys of fields marked ``sensitive: true``; for ``is_sensitive``."""
        return frozenset(k for k, f in self.fields.items() if f.sensitive)


# --- Template (§8.2) --------------------------------------------------------


class TemplateStatus(StrEnum):
    """Lifecycle of a template (§8.3)."""

    CANDIDATE = "candidate"
    ACTIVE = "active"
    RETIRED = "retired"


class TemplateMatch(ContractModel):
    """When a template applies to a document (§8.2).

    ``identifiers``: hard identifiers that must be present, by kind, e.g.
    ``{orgnr: "556000-0000"}``. ``keywords_all``: strings that must all
    occur in the text. At least one criterion is required, so that a
    template never matches every document.
    """

    identifiers: dict[IdentifierKind, NonEmptyStr] = Field(
        default_factory=dict[IdentifierKind, str]
    )
    keywords_all: list[NonEmptyStr] = Field(default_factory=list[str])

    @model_validator(mode="after")
    def _has_a_criterion(self) -> Self:
        if not self.identifiers and not self.keywords_all:
            raise ValueError("match needs at least one identifier or keyword")
        return self


class ExtractRule(ContractModel):
    """Find a value: the text after ``anchor`` that matches ``pattern`` (§8.2).

    ``pattern`` must compile as a Python regular expression (``re``) and
    have exactly one capturing group: the group is the value.
    """

    anchor: NonEmptyStr
    pattern: NonEmptyStr

    @field_validator("pattern")
    @classmethod
    def _pattern_compiles_with_one_group(cls, pattern: str) -> str:
        try:
            compiled = re.compile(pattern)
        except re.error as error:
            raise ValueError(
                f"pattern is not a valid regular expression: {error}"
            ) from None
        if compiled.groups != 1:
            raise ValueError(
                "pattern must have exactly one capturing group, "
                f"found {compiled.groups}"
            )
        return pattern


class Template(ContractModel):
    """A sender-specific template (§8.2). ``type`` names the type profile it
    fills, with version, e.g. ``invoice@2``."""

    schema_: Literal["template/1"] = Field(alias="schema")
    id: ProfileId
    version: PositiveInt
    type: ProfileRef
    status: TemplateStatus
    match: TemplateMatch
    extract: dict[FieldKey, ExtractRule] = Field(min_length=1)
