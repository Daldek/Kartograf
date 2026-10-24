"""``outputSchema`` of every MCP tool (AGI-5.5), generated.

The schema is ``kartograf-result/1``: ``schemas/nogat/result-1.schema.json``
made self-contained by ``scripts/generate_output_schema.py``; do not edit.
"""

from typing import Any, Final

OUTPUT_SCHEMA: Final[dict[str, Any]] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "kartograf-result/1",
    "description": "Result envelope of every command (AGI-4.2). Unknown fields are "
    "allowed: adding optional fields keeps the version (AGI-4.1).",
    "type": "object",
    "required": ["schema", "tool", "version", "command", "check", "status", "result"],
    "properties": {
        "schema": {"type": "string", "pattern": "^[a-z][a-z0-9]*-result/1$"},
        "tool": {"type": "string", "pattern": "^[a-z][a-z0-9]*$"},
        "version": {"type": "string", "minLength": 1},
        "command": {"$ref": "#/$defs/command_name"},
        "check": {
            "type": "boolean",
            "description": "true when the run was a plan without effects",
        },
        "status": {"enum": ["ok", "partial", "failed", "cancelled"]},
        "result": {
            "description": "Domain document, a list of them, or "
            "null when nothing was produced",
            "oneOf": [
                {"$ref": "#/$defs/document"},
                {"type": "array", "items": {"$ref": "#/$defs/document"}},
                {"type": "null"},
            ],
        },
        "items": {"type": "array", "items": {"$ref": "#/$defs/item"}},
        "notices": {"type": "array", "items": {"$ref": "#/$defs/notice"}},
        "page": {"$ref": "#/$defs/page"},
    },
    "allOf": [
        {
            "if": {
                "properties": {"status": {"const": "partial"}},
                "required": ["status"],
            },
            "then": {
                "required": ["items"],
                "properties": {
                    "items": {
                        "allOf": [
                            {"contains": {"properties": {"status": {"const": "ok"}}}},
                            {
                                "contains": {
                                    "properties": {"status": {"const": "failed"}}
                                }
                            },
                        ]
                    }
                },
            },
        },
        {
            "if": {
                "properties": {"status": {"const": "failed"}},
                "required": ["status"],
            },
            "then": {
                "required": ["items"],
                "properties": {
                    "items": {
                        "minItems": 1,
                        "not": {
                            "contains": {"properties": {"status": {"const": "ok"}}}
                        },
                    }
                },
            },
        },
    ],
    "$defs": {
        "document": {
            "type": "object",
            "required": ["schema"],
            "properties": {
                "schema": {
                    "type": "string",
                    "pattern": "^[a-z][a-z0-9]*-[a-z0-9-]+/[1-9][0-9]*$",
                }
            },
        },
        "item": {
            "description": "Outcome of one unit of a batch",
            "type": "object",
            "required": ["id", "status"],
            "properties": {
                "id": {"type": ["string", "integer"]},
                "status": {"enum": ["ok", "failed"]},
                "code": {"$ref": "#/$defs/code"},
                "reason": {"$ref": "#/$defs/reason"},
                "message": {"type": "string"},
            },
            "if": {"properties": {"status": {"const": "failed"}}},
            "then": {"required": ["code"]},
        },
        "notice": {
            "type": "object",
            "required": ["level", "code", "message"],
            "properties": {
                "level": {"enum": ["info", "warning"]},
                "code": {"type": "string", "pattern": "^[a-z][a-z0-9_]*$"},
                "message": {"type": "string"},
            },
        },
        "page": {
            "type": "object",
            "required": ["truncated"],
            "properties": {
                "total": {"type": "integer", "minimum": 0},
                "next_cursor": {"type": ["string", "null"]},
                "truncated": {
                    "type": "boolean",
                    "description": "true when more results exist than this page holds",
                },
            },
            "if": {"properties": {"truncated": {"const": True}}},
            "then": {
                "required": ["next_cursor"],
                "properties": {"next_cursor": {"type": "string"}},
            },
        },
        "command_name": {
            "description": "`<group> <verb>` as typed in the CLI",
            "type": "string",
            "pattern": "^[a-z][a-z0-9-]* [a-z][a-z0-9-]*$",
        },
        "code": {
            "enum": [
                "internal_error",
                "validation_error",
                "not_found",
                "conflict",
                "source_unavailable",
                "missing_dependency",
                "data_error",
                "store_unavailable",
                "io_error",
                "forbidden",
                "calculation_error",
                "no_data",
                "unsupported",
                "cancelled",
                "terminated",
                "unauthorized",
                "method_not_allowed",
                "rate_limited",
            ]
        },
        "reason": {"type": "string", "pattern": "^[a-z][a-z0-9_]*$"},
    },
}
