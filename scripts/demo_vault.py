#!/usr/bin/env python3
"""Seed a vault with a realistic set of interlinked notes.

For screenshots, demos, and trying the search out with something in it. Notes
are written through the normal capture path, so what appears is exactly what a
real session produces — not hand-written Markdown that happens to look right.

Usage:
    python scripts/demo_vault.py /tmp/demo-vault
    python scripts/demo_vault.py /tmp/demo-vault --open
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from recall.config import Settings
from recall.models import Note, NoteKind
from recall.vault import Vault

NOTES: list[dict[str, object]] = [
    {
        "title": "Azure Storage Queue visibility timeout",
        "kind": NoteKind.CONCEPT,
        "summary": (
            "A dequeued message is hidden from other consumers for a set window, "
            "not deleted — if you never delete it, it comes back."
        ),
        "body": """## How it works

`GetMessages` returns a message and starts a timer, defaulting to 30 seconds and
capped at 7 days. Until that timer expires the message is invisible to other
consumers, but it still exists. Deleting it requires the pop receipt returned
alongside it; that receipt is invalidated by every subsequent dequeue.

## Why it matters

This is what makes the queue at-least-once rather than at-most-once. A consumer
that crashes mid-work never deletes the message, so it reappears and someone
else picks it up. Nothing is lost, but nothing is exactly-once either.

## Gotchas

A consumer slower than the visibility timeout will have its work duplicated
while it is still running, and its delete will then fail with a stale receipt.
Either extend the timeout with `UpdateMessage` as you work, or make the handler
idempotent. The second is usually the better answer.""",
        "tags": ["azure", "queue", "distributed-systems"],
        "projects": ["order-pipeline"],
        "related": ["Idempotency keys", "Retry policy"],
    },
    {
        "title": "Idempotency keys",
        "kind": NoteKind.CONCEPT,
        "summary": (
            "A caller-supplied key that lets a server recognise a retry and return "
            "the original result instead of doing the work twice."
        ),
        "body": """## How it works

The client generates a key per logical operation — not per HTTP attempt — and
sends it on every retry. The server records the key with the result of the first
completed attempt. A second request carrying the same key returns that stored
result without re-executing.

## Why it matters

Every at-least-once delivery system eventually delivers twice. Idempotency moves
the correctness burden from "never deliver twice" (impossible) to "make the
second delivery harmless" (achievable).

## Gotchas

The key must be stored in the same transaction as the effect, or a crash between
the two reintroduces the duplicate you were preventing. Keys also need an expiry
policy; unbounded retention turns into an unbounded table.""",
        "tags": ["distributed-systems", "reliability"],
        "projects": ["order-pipeline"],
        "related": ["Azure Storage Queue visibility timeout"],
    },
    {
        "title": "Retry policy",
        "kind": NoteKind.DECISION,
        "summary": (
            "Exponential backoff with full jitter, capped at five attempts, and "
            "only for genuinely transient failures."
        ),
        "body": """## Context

The order pipeline calls three downstream services, all of which fail
occasionally under load. Naive immediate retries were amplifying those failures
into outages: every client retried in lockstep and the recovering service was
knocked over again.

## Decision

Exponential backoff starting at 100 ms, with full jitter, capped at five
attempts. Retry only on timeouts, connection errors, and 5xx. Never retry a 4xx.

## Consequences

Tail latency rises for requests that do retry — a fifth attempt can land four
seconds in. That is acceptable here because the pipeline is asynchronous. It
would not be for an interactive path, which should fail faster and surface the
error.

## Alternatives considered

Fixed-interval retry is simpler but produces the thundering herd we were trying
to escape. A circuit breaker alone stops the herd but gives up on requests that
a single retry would have saved; the two work better together than either
alone.""",
        "tags": ["resilience", "retries", "distributed-systems"],
        "projects": ["order-pipeline"],
        "related": ["Idempotency keys", "Thundering herd after a deploy"],
    },
    {
        "title": "Thundering herd after a deploy",
        "kind": NoteKind.LESSON,
        "summary": (
            "Every pod restarting at once refilled an empty cache simultaneously "
            "and took down the database that the cache existed to protect."
        ),
        "body": """## What happened

A routine rolling deploy at 14:20 was followed four minutes later by database
CPU at 100% and API latency above 30 seconds. The deploy itself was clean; the
outage began as the new pods became ready.

## Root cause

The in-process cache is empty on start. Forty pods came up inside a two-minute
window, each took the same cold path, and all of them queried the same handful
of hot rows at once. The database saw roughly forty times its normal read load
for those keys. The cache was protecting the database, and replacing the cache
removed the protection at exactly the moment load resumed.

## Fix

Request coalescing in front of the cache: concurrent misses for one key wait on
a single in-flight fetch rather than each issuing their own query. Deploy
surge was also reduced so pods warm in smaller batches.

## How to avoid it

Treat cache warm-up as part of the deploy's load profile, not as something that
happens afterwards. Any cache that is load-bearing needs an answer for what
happens when it is empty and traffic is at its normal level.""",
        "tags": ["caching", "postgres", "incident", "resilience"],
        "projects": ["order-pipeline"],
        "related": ["Retry policy"],
    },
    {
        "title": "Postgres autovacuum on high-churn tables",
        "kind": NoteKind.CONCEPT,
        "summary": (
            "Autovacuum reclaims dead tuples, but its default threshold scales "
            "with table size, so large hot tables are vacuumed too rarely."
        ),
        "body": """## How it works

An update writes a new row version and marks the old one dead. Autovacuum
reclaims dead tuples once they exceed
`autovacuum_vacuum_threshold + autovacuum_vacuum_scale_factor * reltuples`,
which defaults to 50 rows plus 20% of the table.

## Why it matters

That 20% is proportional, so the bigger the table the longer it waits. A
hundred-million-row table accumulates twenty million dead tuples before
autovacuum considers it worth running. Index scans slow down long before that
point, and the eventual vacuum is enormous.

## Gotchas

Set `autovacuum_vacuum_scale_factor` per-table on high-churn tables — 0.01 or
lower — rather than globally. The global default is reasonable for small
tables and actively wrong for large ones.""",
        "tags": ["postgres", "performance", "databases"],
        "related": ["Thundering herd after a deploy"],
    },
    {
        "title": "Should retries be client-side or in the gateway?",
        "kind": NoteKind.QUESTION,
        "summary": (
            "Retry logic is duplicated across four services. Centralising it in "
            "the gateway is tempting but may hide which caller is amplifying load."
        ),
        "body": """## The question

Every service implements its own backoff. The code is near-identical and drifts.
Moving it into the gateway would deduplicate it — but the gateway cannot tell a
retryable business failure from a permanent one, and a single retry budget
shared across callers makes it hard to see who is causing amplification.

## What we know

The four implementations already differ in cap and jitter, so drift is real.
Two of the services call dependencies the gateway does not front, so gateway
retries would not cover them anyway.

## Next step

Measure how much of current retry volume actually flows through the gateway
before deciding. If it is most of it, centralise and keep per-caller budgets. If
not, a shared library is the smaller change.""",
        "tags": ["architecture", "retries", "open-question"],
        "projects": ["order-pipeline"],
        "related": ["Retry policy"],
    },
    {
        "title": "Order pipeline",
        "kind": NoteKind.PROJECT,
        "summary": (
            "Asynchronous order processing over Azure Storage Queues, with "
            "at-least-once delivery and idempotent handlers."
        ),
        "body": """## Overview

Orders arrive over HTTP, are validated, then enqueued for asynchronous
processing. Three downstream services handle payment, inventory, and
fulfilment. Delivery is at-least-once, so every handler must be idempotent.

## Current state

Payment and inventory are idempotent and in production. Fulfilment is not yet
— it currently relies on the visibility timeout being longer than its work,
which is the assumption that caused the duplicate-shipment incident.

## Open threads

Retry placement is unresolved. Fulfilment idempotency is the highest-priority
piece of work; until it lands, a slow fulfilment handler can ship twice.""",
        "tags": ["azure", "architecture"],
        "projects": ["order-pipeline"],
        "related": [
            "Azure Storage Queue visibility timeout",
            "Idempotency keys",
            "Retry policy",
        ],
    },
]


def seed(vault_path: Path) -> Path:
    settings = Settings(vault_path=vault_path)
    settings.validate_vault()
    vault = Vault(settings)

    results = []
    for fields in NOTES:
        note = Note.model_validate({**fields, "source": "claude-code"})
        result = vault.write_note(note)
        results.append(result)
        print(f"  {result.path.relative_to(vault_path)}")

    daily = vault.log_daily(results)
    print(f"  {daily.relative_to(vault_path)}")
    return settings.root_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed a demo Recall vault.")
    parser.add_argument("vault", type=Path, help="Directory to use as the vault.")
    parser.add_argument("--open", action="store_true", help="Reveal the folder afterwards (macOS).")
    args = parser.parse_args()

    vault_path = args.vault.expanduser().resolve()
    vault_path.mkdir(parents=True, exist_ok=True)

    print(f"Seeding {vault_path}")
    root = seed(vault_path)

    print(
        f"\n{len(NOTES)} notes written.\n\n"
        f"Open the vault in Obsidian:\n"
        f"  Open folder as vault → {vault_path}\n\n"
        "Worth looking at: the graph view (the notes interlink), a Decision note "
        "for its section structure, and the daily log."
    )
    if args.open and sys.platform == "darwin":
        subprocess.run(["open", str(root)], check=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
