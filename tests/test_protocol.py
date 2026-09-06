"""End-to-end MCP protocol tests.

Every other test calls the tool functions in-process. These launch `recall` as
a real subprocess and drive it over stdio with the official MCP client — the
same handshake Claude Code, Codex, and OpenCode each perform.

This is what makes the multi-provider claim testable without any provider
installed: MCP is the contract, so a server that satisfies a compliant client
satisfies all of them. It cannot prove a given client's *configuration* is
right — that is what the installer tests cover — but it does prove the server
speaks the protocol.
"""

from __future__ import annotations

import json
import os
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

pytestmark = pytest.mark.protocol

REPO = Path(__file__).resolve().parent.parent


@asynccontextmanager
async def connect(vault: Path) -> AsyncIterator[ClientSession]:
    """Launch the server as a subprocess and complete the MCP handshake."""
    parameters = StdioServerParameters(
        command=sys.executable,
        args=["-c", "from recall.server import main; main()"],
        env={
            **os.environ,
            "RECALL_VAULT_PATH": str(vault),
            "PYTHONPATH": str(REPO / "src"),
        },
    )
    async with (
        stdio_client(parameters) as (read, write),
        ClientSession(read, write) as session,
    ):
        await session.initialize()
        yield session


def payload(result: object) -> dict[str, object]:
    """Pull the structured result out of a CallToolResult."""
    structured = getattr(result, "structured_content", None)
    if structured is not None:
        return dict(structured)
    content = getattr(result, "content", [])
    return dict(json.loads(content[0].text))


async def test_the_server_completes_a_handshake_and_advertises_itself(
    vault_path: Path,
) -> None:
    async with connect(vault_path) as session:
        info = session.initialize_result
        assert info is not None, "handshake did not complete"

        assert info.server_info.name == "recall"
        assert info.instructions is not None
        assert "note_search" in info.instructions


async def test_tools_are_discoverable_with_usable_schemas(vault_path: Path) -> None:
    async with connect(vault_path) as session:
        tools = {tool.name: tool for tool in (await session.list_tools()).tools}

        assert set(tools) == {
            "note_capture",
            "note_search",
            "note_read",
            "note_context",
            "note_archive",
            "vault_health",
        }

        capture = tools["note_capture"]
        assert capture.description and "concept" in capture.description
        properties = capture.input_schema["properties"]
        assert {"title", "kind", "summary"} <= set(properties)
        assert capture.input_schema["required"] == ["title", "kind", "summary"]


async def test_the_full_capture_and_recall_loop_over_the_wire(vault_path: Path) -> None:
    """The journey a real client makes: health, capture, search, read, context."""
    async with connect(vault_path) as session:
        health = payload(await session.call_tool("vault_health", {}))
        assert health["ok"] is True

        created = payload(
            await session.call_tool(
                "note_capture",
                {
                    "title": "Visibility timeout",
                    "kind": "concept",
                    "summary": "A dequeued message is hidden, not deleted.",
                    "body": "## How it works\n\nDelete it explicitly or it reappears.",
                    "tags": ["azure", "queue"],
                },
            )
        )
        assert created["ok"] is True
        assert created["wiki_link"] == "[[Visibility timeout]]"

        found = payload(await session.call_tool("note_search", {"query": "visibility timeout"}))
        assert found["count"] == 1

        read = payload(await session.call_tool("note_read", {"title": "Visibility timeout"}))
        assert "dequeued message" in str(read["content"])

        context = payload(await session.call_tool("note_context", {"query": "visibility"}))
        assert "title:" not in str(context["context"]), "frontmatter must not reach the model"


async def test_a_tool_error_arrives_as_data_not_a_transport_failure(
    vault_path: Path,
) -> None:
    """A client must be able to read the reason and retry, not just see a crash."""
    async with connect(vault_path) as session:
        result = await session.call_tool(
            "note_capture", {"title": "  ", "kind": "concept", "summary": "s"}
        )

        assert result.is_error is False, "invalid input is a result, not a protocol error"
        body = payload(result)
        assert body["ok"] is False
        assert body["invalid_fields"][0]["field"] == "title"  # type: ignore[index]


async def test_nothing_pollutes_stdout(vault_path: Path) -> None:
    """stdout carries the protocol. A stray print corrupts every message.

    If the server wrote to stdout, the handshake above would already have
    failed — this asserts the quieter case, that a full working session still
    leaves the stream clean enough for a second call to succeed.
    """
    async with connect(vault_path) as session:
        for index in range(3):
            result = payload(
                await session.call_tool(
                    "note_capture",
                    {"title": f"Note {index}", "kind": "concept", "summary": "s"},
                )
            )
            assert result["ok"] is True

        assert payload(await session.call_tool("vault_health", {}))["note_counts"] == {
            "concept": 3,
            "decision": 0,
            "lesson": 0,
            "question": 0,
            "project": 0,
            "daily": 1,
            "archived": 0,
        }
