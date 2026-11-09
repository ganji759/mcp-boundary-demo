"""
MCP Boundary Pattern - demo server.

This server shows one pattern: use the MCP server itself to enforce
a hard privacy boundary. The boundary does not depend on the agent,
the prompt, or the model. It lives in the server code.

Domain: a small notes app. Two data sources exist:
  - public_notes  - safe. Tools may read this.
  - private_notes - never safe. No tool may read this, ever.

Four parts build the boundary:
  1. A single store accessor. Every tool must call it.
  2. A deny check inside the accessor, before any data loads.
  3. A field allow-list. Only named-safe fields leave the process.
  4. A registry-wide test (see test_boundary_registry.py). It checks
     every registered tool, not a fixed list of tool names.

Run this file to start the server:
    python mcp_boundary_server.py

Set DEMO_INTRODUCE_LEAK=1 to add one unsafe tool. Use this to prove
the test in test_boundary_registry.py catches a real leak:
    DEMO_INTRODUCE_LEAK=1 python test_boundary_registry.py
"""
from __future__ import annotations

import os

from mcp.server.fastmcp import FastMCP

# ── Data ──────────────────────────────────────────────────────────────────
# Real projects read these from a database. This demo uses two plain lists
# so the pattern is easy to read and needs no setup.

PUBLIC_NOTES = [
    {"id": "n1", "title": "Welcome", "body": "This note is public.",
     "owner_email": "alice@example.com"},
    {"id": "n2", "title": "Roadmap", "body": "Ship the boundary pattern.",
     "owner_email": "bob@example.com"},
]

PRIVATE_NOTES = [
    {"id": "p1", "title": "Salary talk", "body": "No agent may read this note.",
     "owner_email": "alice@example.com", "auth_token": "sk-secret-123"},
]

# ── The boundary ─────────────────────────────────────────────────────────

DENYLISTED_SOURCES = frozenset({"private_notes"})
ALLOWED_FIELDS = ("id", "title", "body")


def _store(name: str) -> list[dict]:
    """The single door to the data. Every tool must call this function.

    Raises PermissionError before any data loads, if the source is on
    the deny list. A tool that skips this function is a bug by design -
    the registry-wide test finds that bug.
    """
    if name in DENYLISTED_SOURCES:
        raise PermissionError(f"source '{name}' is denylisted; no tool may read it")
    if name == "public_notes":
        return PUBLIC_NOTES
    raise ValueError(f"unknown source '{name}'")


def _project(note: dict) -> dict:
    """Return only the allowed fields. New fields are safe by default.

    A field must be added to ALLOWED_FIELDS on purpose, before a tool
    can return it. This is an allow-list, not a block-list.
    """
    return {k: note[k] for k in ALLOWED_FIELDS if k in note}


# ── The server and its tools ────────────────────────────────────────────

DEMO_PORT = int(os.getenv("MCP_BOUNDARY_DEMO_PORT", "8811"))


def build_app() -> FastMCP:
    app = FastMCP("mcp-boundary-demo", port=DEMO_PORT)

    @app.tool()
    def list_notes() -> list[dict]:
        """List public notes. Each result has id, title, and body only."""
        return [_project(n) for n in _store("public_notes")]

    @app.tool()
    def get_note(note_id: str) -> dict:
        """Get one public note by id. Result has id, title, and body only."""
        for note in _store("public_notes"):
            if note["id"] == note_id:
                return _project(note)
        raise ValueError(f"no public note with id '{note_id}'")

    if os.getenv("DEMO_INTRODUCE_LEAK") == "1":
        # A tool that skips _store() and returns raw private data.
        # This is the bug the boundary is built to stop. It is off by
        # default. Turn it on to see test_boundary_registry.py catch it.
        @app.tool()
        def leaky_export() -> list[dict]:
            """Export notes for backup. (Demo bug: skips the boundary.)"""
            return PRIVATE_NOTES  # BUG: no _store() call, no _project() call

    return app


app = build_app()

if __name__ == "__main__":
    app.run(transport="streamable-http")
