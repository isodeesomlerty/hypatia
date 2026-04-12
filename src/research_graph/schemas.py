from __future__ import annotations

from jsonschema import Draft202012Validator

PAPER_METADATA_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "authors": {
            "type": "array",
            "items": {"type": "string"},
        },
        "year": {"type": ["integer", "null"]},
    },
    "required": ["title", "authors", "year"],
    "additionalProperties": False,
}

CLAIM_PROPERTIES = {
    "claim_id": {"type": "string"},
    "claim": {"type": "string"},
    "claim_type": {
        "type": "string",
        "enum": [
            "causal",
            "correlational",
            "descriptive",
            "theoretical",
            "predictive",
            "policy_recommendation",
        ],
    },
    "evidence_type": {
        "type": "string",
        "enum": [
            "RCT",
            "natural_experiment",
            "quasi_experimental",
            "observational",
            "meta_analysis",
            "systematic_review",
            "computational_simulation",
            "survey",
            "case_study",
            "theoretical_model",
            "qualitative",
            "other",
        ],
    },
    "evidence_strength": {
        "type": "string",
        "enum": ["strong", "moderate", "weak"],
    },
    "evidence_reasoning": {"type": "string"},
    "key_variables": {
        "type": "array",
        "items": {"type": "string"},
    },
    "context": {"type": "string"},
}

CLAIM_REQUIRED_FIELDS = [
    "claim_id",
    "claim",
    "claim_type",
    "evidence_type",
    "evidence_strength",
    "evidence_reasoning",
    "key_variables",
    "context",
]

CLAIM_ANALYSIS_ITEM_SCHEMA = {
    "type": "object",
    "properties": {
        key: value
        for key, value in CLAIM_PROPERTIES.items()
        if key != "claim_id"
    },
    "required": [field for field in CLAIM_REQUIRED_FIELDS if field != "claim_id"],
    "additionalProperties": False,
}

HEALTH_CHECK_ITEM_SCHEMA = {
    "type": "object",
    "properties": {
        "check": {"type": "string"},
        "status": {
            "type": "string",
            "enum": ["pass", "warn", "fail"],
        },
        "detail": {"type": "string"},
    },
    "required": ["check", "status", "detail"],
    "additionalProperties": False,
}

HEALTH_SUMMARY_SCHEMA = {
    "type": "object",
    "properties": {
        "overall_score": {
            "type": "string",
            "enum": ["healthy", "caution", "concern"],
        },
        "checks": {
            "type": "array",
            "items": HEALTH_CHECK_ITEM_SCHEMA,
        },
    },
    "required": ["overall_score", "checks"],
    "additionalProperties": False,
}

CLAIM_SCHEMA = {
    "type": "object",
    "properties": {
        "paper_metadata": PAPER_METADATA_SCHEMA,
        "claims": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": CLAIM_PROPERTIES,
                "required": CLAIM_REQUIRED_FIELDS,
                "additionalProperties": False,
            },
        },
    },
    "required": ["paper_metadata", "claims"],
    "additionalProperties": False,
}

HEALTH_SCHEMA = {
    "type": "object",
    "properties": {
        "paper_id": {"type": "string"},
        **HEALTH_SUMMARY_SCHEMA["properties"],
    },
    "required": ["paper_id", *HEALTH_SUMMARY_SCHEMA["required"]],
    "additionalProperties": False,
}

PAPER_ANALYSIS_SCHEMA = {
    "type": "object",
    "properties": {
        "paper_metadata": PAPER_METADATA_SCHEMA,
        "claims": {
            "type": "array",
            "items": CLAIM_ANALYSIS_ITEM_SCHEMA,
        },
        "health_assessment": HEALTH_SUMMARY_SCHEMA,
    },
    "required": ["paper_metadata", "claims", "health_assessment"],
    "additionalProperties": False,
}

RELATIONSHIP_ITEM_SCHEMA = {
    "type": "object",
    "properties": {
        "source_claim_id": {"type": "string"},
        "target_claim_id": {"type": "string"},
        "relationship": {
            "type": "string",
            "enum": [
                "contradicts",
                "supports",
                "extends",
                "qualifies",
                "uses_same_method",
                "uses_same_data",
            ],
        },
        "relationship_strength": {
            "type": "string",
            "enum": ["direct", "partial", "implicit"],
        },
        "explanation": {"type": "string"},
        "methodological_note": {"type": "string"},
    },
    "required": [
        "source_claim_id",
        "target_claim_id",
        "relationship",
        "relationship_strength",
        "explanation",
        "methodological_note",
    ],
    "additionalProperties": False,
}

RELATIONSHIP_SCHEMA = {
    "type": "object",
    "properties": {
        "relationships": {
            "type": "array",
            "items": RELATIONSHIP_ITEM_SCHEMA,
        }
    },
    "required": ["relationships"],
    "additionalProperties": False,
}

SEARCH_SCHEMA = {
    "type": "object",
    "properties": {
        "matching_claim_ids": {
            "type": "array",
            "items": {"type": "string"},
        },
        "summary": {"type": "string"},
    },
    "required": ["matching_claim_ids", "summary"],
    "additionalProperties": False,
}

_VALIDATORS = {
    "claims": Draft202012Validator(CLAIM_SCHEMA),
    "health": Draft202012Validator(HEALTH_SCHEMA),
    "paper_analysis": Draft202012Validator(PAPER_ANALYSIS_SCHEMA),
    "relationships": Draft202012Validator(RELATIONSHIP_SCHEMA),
    "relationship_item": Draft202012Validator(RELATIONSHIP_ITEM_SCHEMA),
    "search": Draft202012Validator(SEARCH_SCHEMA),
}


def validate_payload(kind: str, payload: dict) -> None:
    validator = _VALIDATORS[kind]
    errors = sorted(validator.iter_errors(payload), key=lambda item: item.path)
    if not errors:
        return

    joined = "; ".join(error.message for error in errors[:5])
    raise ValueError(f"Schema validation failed for {kind}: {joined}")
