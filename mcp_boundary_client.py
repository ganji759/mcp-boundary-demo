"""
MCP Boundary Pattern - demo client.

This script plays the part of an AI agent. It does not use a model.
It shows the tool-call loop an agent framework runs: connect, list
tools, call a tool, read the result. This is the same loop ADK,
LangGraph, or a raw MCP client library runs before an LLM ever picks
a tool name.

The server must run first, in another terminal:
    python mcp_boundary_server.py

Then run this script:
    python mcp_boundary_client.py
"""
from __future__ import annotations

import asyncio
import json
import os

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

PORT = int(os.getenv("MCP_BOUNDARY_DEMO_PORT", "8811"))
URL = f"http://127.0.0.1:{PORT}/mcp"


def _print_result(label: str, result) -> None:
    texts = [block.text for block in result.content if hasattr(block, "text")]
    print(f"{label}:")
    for text in texts:
        print(f"  {text}")
    print()


async def main() -> None:
    print(f"Connecting to {URL} ...\n")
    async with streamablehttp_client(URL) as (read, write, _get_session_id):
        async with ClientSession(read, write) as session:
            await session.initialize()

            tools = await session.list_tools()
            print(f"Tools this agent may call: {[t.name for t in tools.tools]}\n")

            listed = await session.call_tool("list_notes", {})
            _print_result("list_notes()", listed)

            note = await session.call_tool("get_note", {"note_id": "n1"})
            _print_result("get_note(note_id='n1')", note)

            # An agent, or a prompt-injected user message, might ask for
            # something outside the tool list. There is no tool name for
            # private notes - the boundary means there is nothing to call.
            blocked = await session.call_tool("get_private_note", {"note_id": "p1"})
            print("get_private_note(...) -> rejected, as expected:")
            print(f"  isError={blocked.isError}")
            for block in blocked.content:
                if hasattr(block, "text"):
                    print(f"  {block.text}")
            print()

    print("Done. The agent never had a tool that could reach a private note.")


if __name__ == "__main__":
    asyncio.run(main())
