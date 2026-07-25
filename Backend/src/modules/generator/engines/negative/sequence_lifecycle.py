from __future__ import annotations

from enum import Enum


class SequenceType(str, Enum):
    CREATE_THEN_GET = "CREATE_THEN_GET"
    CREATE_THEN_DELETE_THEN_GET = "CREATE_THEN_DELETE_THEN_GET"
    CREATE_DUPLICATE = "CREATE_DUPLICATE"


LIFECYCLE_RULES: dict[str, dict[str, list[int | list[int]]]] = {
    SequenceType.CREATE_THEN_GET.value: {
        "step_validations": [201, 200],
    },
    SequenceType.CREATE_THEN_DELETE_THEN_GET.value: {
        "step_validations": [201, [200, 204], 404],
    },
    SequenceType.CREATE_DUPLICATE.value: {
        "step_validations": [201, 409],
    },
}


def normalize_sequence_type(value: str | SequenceType | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, SequenceType):
        return value.value
    candidate = str(value).strip().upper()
    return candidate if candidate in LIFECYCLE_RULES else None


def get_lifecycle_rule(sequence_type: str | SequenceType | None) -> dict[str, list[int | list[int]]] | None:
    normalized = normalize_sequence_type(sequence_type)
    if normalized is None:
        return None
    return LIFECYCLE_RULES[normalized]
