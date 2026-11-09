# mcp-boundary-demo

Demo code for the talk "Server-Side Boundaries for MCP Tools and
Data", MCP Dev Summit Nairobi 2026, by Pacifique Mugisho.

The talk shows a boundary pattern from Hodari, my AI travel
assistant. This demo shows that the same pattern works outside
Hodari's own domain. It uses a small notes app instead of a
travel assistant. Two data sources exist: `public_notes` and
`private_notes`. No tool may ever read `private_notes`.

Three files:

- `mcp_boundary_server.py` — the MCP server. Implements the four-part
  pattern: one accessor, a fail-closed deny check, a field allow-list,
  and one hidden, off-by-default "leaky" tool for the proof below.
- `test_boundary_registry.py` — the registry-wide test. Reads every
  tool the server has registered, right now, and checks each one for
  a leak: a private value (a canary) or a restricted field name. It
  fails closed: a tool it cannot call counts as a failure, not a skip.
  Does not run over the network. Runs in-process.
- `mcp_boundary_client.py` — an agent-style client. Connects to a
  running server over real streamable HTTP and calls tools the same
  way an agent framework does.

## Setup

You need Python 3.10 or later.

```bash
git clone https://github.com/ganji759/mcp-boundary-demo.git
cd mcp-boundary-demo
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

This installs `mcp<2.0`, the same major version Hodari pins in
`agents/requirements.txt`.

## Step 1 — run the registry-wide test, clean

```bash
python test_boundary_registry.py
```

Expected output:

```
Registered tools: ['list_notes', 'get_note']
  list_notes({}) -> clean
  get_note({'note_id': 'n1'}) -> clean

PASS - no registered tool exposed private data.
```

Exit code 0.

## Step 2 — plant a leak, and watch the test catch it

```bash
DEMO_INTRODUCE_LEAK=1 python test_boundary_registry.py
```

This turns on `leaky_export`, a tool that skips the accessor and
returns raw private data. The test file did not change. It still
finds the leak, because it reads the tool registry at run time.

Expected output:

```
Registered tools: ['list_notes', 'get_note', 'leaky_export']
  list_notes({}) -> clean
  get_note({'note_id': 'n1'}) -> clean
  leaky_export({}) -> LEAK

FAIL - boundary violated:
  - leaky_export({}) returned private data: 'Salary talk'
```

Exit code 1. This is the proof that matters most: a tool nobody
wrote a test for yet is still caught, the moment it exists.

## Step 3 — run the real client against a real server

Open a second terminal. In the first terminal:

```bash
python mcp_boundary_server.py
```

In the second terminal:

```bash
source .venv/bin/activate
python mcp_boundary_client.py
```

Expected output: the client lists two tools, calls `list_notes` and
`get_note` and gets back public data, then calls a tool name that
does not exist (`get_private_note`) and gets a clean rejection —
`isError=True`, `"Unknown tool: get_private_note"`. There is no tool
by that name to call. That is the boundary, seen from the agent's
side of the wire.

Stop the server with `Ctrl+C` when done.

## What this does and does not prove

It proves the four-part pattern holds in a domain that has nothing to
do with Hodari, and that the registry-wide test catches a real,
previously-unknown leak with no changes to the test itself.

The test builds each tool's arguments from its input schema. It never
names a tool. If a tool needs one specific input to work, give that
input as an example in the tool's schema, and the test uses it. A tool
the test cannot call makes the run fail, so a new tool is never
skipped in silence.

It does not prove the pattern catches every kind of leak. In
particular, a tool that paraphrases or aggregates private data,
instead of returning it verbatim, would not trip the canary-string
check this demo uses. A leak that shows only for one specific input,
for example one private id, can also hide from the generated
arguments.

## License

MIT. See `LICENSE`.
