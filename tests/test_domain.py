from recall_core.domain.models import Memory, MemoryKind


def test_memory_defaults_to_active() -> None:
    memory = Memory(
        kind=MemoryKind.CONCEPT,
        title="Azure Storage Queue",
        summary="Queueing service.",
        content="Durable engineering knowledge.",
    )

    assert memory.status.value == "active"
    assert memory.title == "Azure Storage Queue"
