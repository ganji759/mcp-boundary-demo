"""
Registry-wide boundary test.

This test does not hard-code tool names. It asks the server for every
registered tool, calls each one, and checks the result for private
data. A tool added later is checked the same way, with no change to
this file.

The test fails closed. A tool it cannot call is a tool it did not
check, so that counts as a failure, not a skip.

Run:
    python test_boundary_registry.py
    DEMO_INTRODUCE_LEAK=1 python test_boundary_registry.py    (see it fail)
"""
from __future__ import annotations

import asyncio
import json
import sys

from mcp_boundary_server import (
    ALLOWED_FIELDS,
    DENYLISTED_SOURCES,
    PRIVATE_NOTES,
    PUBLIC_NOTES,
    _store,
    build_app,
)

# Canaries: exact private values. Any of these in a tool result is a leak.
CANARIES = []
for _note in PRIVATE_NOTES:
    CANARIES.append(_note["title"])
    CANARIES.append(_note["body"])
    CANARIES.append(_note["auth_token"])

# Restricted fields: on the records, but not on the allow-list.
RESTRICTED_FIELDS = sorted(
    {field for note in PUBLIC_NOTES + PRIVATE_NOTES for field in note} - set(ALLOWED_FIELDS)
)

SAMPLE_ID = PUBLIC_NOTES[0]["id"]
_SAMPLE_BY_TYPE = {"integer": 10, "number": 10.0, "boolean": True, "array": [], "object": {}}


def _flatten_to_text(result: object) -> str:
    """Turn any tool result shape into one text blob to scan."""
    parts: list[str] = []

    def walk(value: object) -> None:
        if hasattr(value, "text"):
            parts.append(value.text)
        elif isinstance(value, (list, tuple)):
            for item in value:
                walk(item)
        elif isinstance(value, dict):
            parts.append(json.dumps(value, default=str))
        elif value is not None:
            parts.append(str(value))

    walk(result)
    return "\n".join(parts)


def _args_from_schema(schema: dict) -> dict:
    """Build arguments a well-behaved tool accepts, from its input schema alone.

    A tool that needs one specific input can name it as an example in its
    schema. The test uses that example. It never names a tool.
    """
    args = {}
    properties = schema.get("properties", {})
    for field in schema.get("required", []):
        spec = properties.get(field, {})
        if spec.get("examples"):
            args[field] = spec["examples"][0]
            continue
        kind = spec.get("type", "string")
        if kind == "string":
            args[field] = SAMPLE_ID if "id" in field.lower() else "demo"
        else:
            args[field] = _SAMPLE_BY_TYPE.get(kind, "demo")
    return args


def check_direct_access_is_blocked() -> list[str]:
    """Part 1: the accessor must refuse the denylisted source, always."""
    problems = []
    for source in DENYLISTED_SOURCES:
        try:
            _store(source)
            problems.append(f"_store('{source}') did not raise - boundary is not enforced")
        except PermissionError:
            pass
    return problems


async def check_every_registered_tool() -> list[str]:
    """Part 2: no registered tool may return a canary or a restricted field."""
    app = build_app()
    tools = await app.list_tools()
    print(f"Registered tools: {[t.name for t in tools]}")

    problems: list[str] = []

    for tool in tools:
        args = _args_from_schema(tool.inputSchema)
        try:
            result = await app.call_tool(tool.name, args)
        except Exception as exc:  # a tool the test cannot call is a tool it did not check
            print(f"  {tool.name}({args}) -> could not call ({type(exc).__name__})")
            problems.append(f"{tool.name}({args}) could not be called, so it was not checked")
            continue

        blob = _flatten_to_text(result)

        hit = next((c for c in CANARIES if c in blob), None)
        field = next((f for f in RESTRICTED_FIELDS if f'"{f}"' in blob), None)
        status = "LEAK" if hit or field else "clean"
        print(f"  {tool.name}({args}) -> {status}")
        if hit:
            problems.append(f"{tool.name}({args}) returned private data: {hit!r}")
        elif field:
            problems.append(f"{tool.name}({args}) returned a restricted field: {field!r}")

    return problems


async def main() -> int:
    problems = check_direct_access_is_blocked()
    problems += await check_every_registered_tool()

    if problems:
        print("\nFAIL - boundary violated:")
        for p in problems:
            print(f"  - {p}")
        return 1

    print("\nPASS - no registered tool exposed private data.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
