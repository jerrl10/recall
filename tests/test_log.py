"""Logging must be informative, and must never touch stdout."""

from __future__ import annotations

import logging
from typing import Any

import pytest

from recall import log


@pytest.fixture(autouse=True)
def _reset() -> Any:
    yield
    logging.getLogger(log.LOGGER_NAME).handlers.clear()


def test_records_go_to_stderr_only(capsys: pytest.CaptureFixture[str]) -> None:
    """stdout carries the MCP protocol; a single byte on it breaks a session."""
    log.configure("INFO")
    log.event(logging.INFO, "something happened", note_id="abc")

    captured = capsys.readouterr()
    assert captured.out == ""
    assert "something happened" in captured.err


def test_fields_are_rendered_as_key_values(capsys: pytest.CaptureFixture[str]) -> None:
    log.configure("INFO")
    log.event(logging.INFO, "captured", kind="concept", count=3)

    err = capsys.readouterr().err
    assert "kind=concept" in err
    assert "count=3" in err


def test_values_containing_spaces_are_quoted(capsys: pytest.CaptureFixture[str]) -> None:
    log.configure("INFO")
    log.event(logging.INFO, "refused", reason="a similar note exists")

    assert 'reason="a similar note exists"' in capsys.readouterr().err


def test_configuring_twice_does_not_duplicate_output(
    capsys: pytest.CaptureFixture[str],
) -> None:
    log.configure("INFO")
    log.configure("INFO")
    log.event(logging.INFO, "once")

    assert capsys.readouterr().err.count("once") == 1


def test_the_level_is_respected(capsys: pytest.CaptureFixture[str]) -> None:
    log.configure("WARNING")
    log.event(logging.INFO, "quiet")
    log.event(logging.WARNING, "loud")

    err = capsys.readouterr().err
    assert "quiet" not in err
    assert "loud" in err


def test_an_unknown_level_falls_back_to_info(capsys: pytest.CaptureFixture[str]) -> None:
    """A typo in RECALL_LOG_LEVEL must not silence the server."""
    log.configure("VERBOSE")
    log.event(logging.INFO, "still logged")

    assert "still logged" in capsys.readouterr().err


def test_records_do_not_propagate_to_the_root_logger() -> None:
    """A root handler could be pointed at stdout by the embedding process."""
    log.configure("INFO")
    assert logging.getLogger(log.LOGGER_NAME).propagate is False


class TestOperation:
    def test_a_successful_operation_reports_its_duration(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        log.configure("INFO")
        with log.operation("note_capture", kind="concept") as record:
            record["outcome"] = "ok"

        err = capsys.readouterr().err
        assert "note_capture" in err
        assert "kind=concept" in err
        assert "outcome=ok" in err
        assert "duration_ms=" in err

    def test_an_exception_is_logged_and_re_raised(self, capsys: pytest.CaptureFixture[str]) -> None:
        log.configure("INFO")
        with pytest.raises(ValueError), log.operation("note_capture"):
            raise ValueError("boom")

        err = capsys.readouterr().err
        assert "outcome=exception" in err
        assert "error=ValueError" in err


def test_tool_calls_are_logged_with_their_outcome(
    call: Any, capsys: pytest.CaptureFixture[str]
) -> None:
    """The wrapper must survive MCP's schema generation and still log."""
    import asyncio

    log.configure("INFO")
    asyncio.run(call("note_capture", title="Queues", kind="concept", summary="s"))
    asyncio.run(call("note_read", title="Missing"))

    err = capsys.readouterr().err
    assert "note_capture" in err and "outcome=ok" in err
    assert "note_read" in err and "outcome=refused" in err


def test_note_content_is_never_logged(call: Any, capsys: pytest.CaptureFixture[str]) -> None:
    """A vault holds the user's own notes; a log is easier to leak from."""
    import asyncio

    log.configure("DEBUG")
    asyncio.run(
        call(
            "note_capture",
            title="Secret project codename",
            kind="concept",
            summary="Confidential detail that must not appear in logs.",
            body="More confidential detail.",
        )
    )

    err = capsys.readouterr().err
    assert "Confidential detail" not in err
    assert "More confidential detail" not in err
