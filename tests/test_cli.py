"""Setup and doctor — the commands people meet before anything works."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from recall import cli, discovery


@pytest.fixture
def obsidian_vault(tmp_path: Path) -> Path:
    vault = tmp_path / "MyVault"
    (vault / ".obsidian").mkdir(parents=True)
    return vault


class TestDiscovery:
    def _registry(self, tmp_path: Path, vaults: list[Path]) -> Path:
        path = tmp_path / "obsidian.json"
        path.write_text(
            json.dumps(
                {
                    "vaults": {
                        f"id{index}": {"path": str(vault), "ts": index}
                        for index, vault in enumerate(vaults)
                    }
                }
            ),
            encoding="utf-8",
        )
        return path

    def test_registered_vaults_are_returned_most_recent_first(
        self, tmp_path: Path, obsidian_vault: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        older = tmp_path / "Older"
        older.mkdir()
        registry = self._registry(tmp_path, [older, obsidian_vault])
        monkeypatch.setattr(discovery, "registry_path", lambda: registry)

        assert discovery.registered_vaults() == [obsidian_vault, older]

    def test_a_missing_registry_is_not_an_error(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Obsidian may not be installed; setup still has to work."""
        monkeypatch.setattr(discovery, "registry_path", lambda: tmp_path / "absent.json")
        assert discovery.registered_vaults() == []

    def test_a_corrupt_registry_is_not_an_error(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        broken = tmp_path / "obsidian.json"
        broken.write_text("{not json", encoding="utf-8")
        monkeypatch.setattr(discovery, "registry_path", lambda: broken)
        assert discovery.registered_vaults() == []

    def test_vaults_that_no_longer_exist_are_dropped(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        registry = self._registry(tmp_path, [tmp_path / "deleted"])
        monkeypatch.setattr(discovery, "registry_path", lambda: registry)
        assert discovery.registered_vaults() == []

    def test_an_obsidian_folder_identifies_a_vault(
        self, obsidian_vault: Path, tmp_path: Path
    ) -> None:
        assert discovery.looks_like_a_vault(obsidian_vault)
        assert not discovery.looks_like_a_vault(tmp_path)


class TestSetup:
    def test_it_writes_a_config_the_server_can_read(
        self, obsidian_vault: Path, tmp_path: Path
    ) -> None:
        target = tmp_path / "out" / ".env"
        code = cli.main(
            ["setup", "--vault", str(obsidian_vault), "--scope", "vault", "--output", str(target)]
        )

        assert code == 0
        written = target.read_text(encoding="utf-8")
        assert f"RECALL_VAULT_PATH={obsidian_vault.resolve()}" in written
        assert "RECALL_SEARCH_SCOPE=vault" in written

    def test_it_refuses_to_clobber_an_existing_config(
        self, obsidian_vault: Path, tmp_path: Path
    ) -> None:
        target = tmp_path / ".env"
        target.write_text("RECALL_VAULT_PATH=/somewhere/else\n", encoding="utf-8")

        code = cli.main(
            ["setup", "--vault", str(obsidian_vault), "--scope", "recall", "--output", str(target)]
        )

        assert code == 1
        assert "somewhere/else" in target.read_text(encoding="utf-8")

    def test_force_overwrites(self, obsidian_vault: Path, tmp_path: Path) -> None:
        target = tmp_path / ".env"
        target.write_text("RECALL_VAULT_PATH=/somewhere/else\n", encoding="utf-8")

        code = cli.main(
            [
                "setup",
                "--vault",
                str(obsidian_vault),
                "--scope",
                "recall",
                "--output",
                str(target),
                "--force",
            ]
        )

        assert code == 0
        assert "somewhere/else" not in target.read_text(encoding="utf-8")

    def test_a_path_that_is_not_a_directory_is_rejected(self, tmp_path: Path) -> None:
        file_not_folder = tmp_path / "notes.md"
        file_not_folder.write_text("", encoding="utf-8")

        assert cli.main(["setup", "--vault", str(file_not_folder), "--scope", "recall"]) == 1

    def test_setup_writes_nothing_to_stdout(
        self, obsidian_vault: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """The same entry point serves MCP; stdout must stay clean throughout."""
        cli.main(
            [
                "setup",
                "--vault",
                str(obsidian_vault),
                "--scope",
                "vault",
                "--output",
                str(tmp_path / ".env"),
            ]
        )
        assert capsys.readouterr().out == ""


class TestDoctor:
    def test_it_fails_clearly_when_nothing_is_configured(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        monkeypatch.delenv("RECALL_VAULT_PATH", raising=False)
        monkeypatch.chdir(tmp_path)

        assert cli.main(["doctor"]) == 1
        assert "recall setup" in capsys.readouterr().err

    def test_it_reports_a_healthy_vault(
        self,
        obsidian_vault: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        monkeypatch.setenv("RECALL_VAULT_PATH", str(obsidian_vault))

        assert cli.main(["doctor"]) == 0
        err = capsys.readouterr().err
        assert "writable   yes" in err
        assert "Everything checks out" in err

    def test_it_fails_when_the_vault_is_gone(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        monkeypatch.setenv("RECALL_VAULT_PATH", str(tmp_path / "deleted"))

        assert cli.main(["doctor"]) == 1
        assert "FAIL" in capsys.readouterr().err

    def test_doctor_writes_nothing_to_stdout(
        self,
        obsidian_vault: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        monkeypatch.setenv("RECALL_VAULT_PATH", str(obsidian_vault))
        cli.main(["doctor"])
        assert capsys.readouterr().out == ""


def test_the_parser_exposes_every_command() -> None:
    parser = cli.build_parser()
    actions = [a for a in parser._actions if hasattr(a, "choices") and a.choices]
    commands = set(next(a.choices for a in actions if isinstance(a.choices, dict)))
    assert commands == {"serve", "setup", "doctor"}


def test_no_arguments_defaults_to_serving(monkeypatch: pytest.MonkeyPatch) -> None:
    """An assistant launches `recall` with no arguments; it must not print help."""
    served = False

    def fake_serve(_: object) -> int:
        nonlocal served
        served = True
        return 0

    monkeypatch.setattr(cli, "command_serve", fake_serve)
    assert cli.main([]) == 0
    assert served


class TestInteractiveChoice:
    """The prompts a first-time user actually meets."""

    def test_choosing_a_vault_by_number(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        first, second = tmp_path / "One", tmp_path / "Two"
        for path in (first, second):
            (path / ".obsidian").mkdir(parents=True)
        monkeypatch.setattr("builtins.input", lambda _="": "2")

        assert cli._choose_vault([first, second]) == second

    def test_pressing_enter_takes_the_most_recent_vault(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        first, second = tmp_path / "One", tmp_path / "Two"
        monkeypatch.setattr("builtins.input", lambda _="": "")

        assert cli._choose_vault([first, second]) == first

    def test_choosing_somewhere_else_prompts_for_a_path(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        elsewhere = tmp_path / "Elsewhere"
        answers = iter(["2", str(elsewhere)])
        monkeypatch.setattr("builtins.input", lambda _="": next(answers))

        assert cli._choose_vault([tmp_path / "One"]) == elsewhere.resolve()

    def test_an_out_of_range_choice_gives_up_rather_than_guessing(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("builtins.input", lambda _="": "99")
        assert cli._choose_vault([tmp_path / "One"]) is None

    def test_nonsense_input_gives_up(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("builtins.input", lambda _="": "banana")
        assert cli._choose_vault([tmp_path / "One"]) is None

    def test_with_no_candidates_it_asks_outright(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("builtins.input", lambda _="": str(tmp_path / "Typed"))
        assert cli._choose_vault([]) == (tmp_path / "Typed").resolve()

    def test_an_empty_answer_with_no_candidates_chooses_nothing(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("builtins.input", lambda _="": "")
        assert cli._choose_vault([]) is None

    @pytest.mark.parametrize(
        ("answer", "expected"),
        [("1", "vault"), ("2", "recall"), ("", "vault"), ("anything", "vault")],
    )
    def test_scope_question(
        self, answer: str, expected: str, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Only an explicit '2' opts out of vault scope."""
        monkeypatch.setattr("builtins.input", lambda _="": answer)
        assert cli._choose_scope() == expected

    def test_setup_stops_when_no_vault_is_chosen(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.setattr(discovery, "discover", list)
        monkeypatch.setattr("builtins.input", lambda _="": "")
        monkeypatch.chdir(tmp_path)

        assert cli.main(["setup"]) == 1
        assert not (tmp_path / ".env").exists()

    def test_setup_reports_a_write_failure_with_the_values_to_set_by_hand(
        self,
        obsidian_vault: Path,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        def refuse(*_: object, **__: object) -> None:
            raise OSError(13, "Permission denied")

        monkeypatch.setattr(Path, "write_text", refuse)
        code = cli.main(
            [
                "setup",
                "--vault",
                str(obsidian_vault),
                "--scope",
                "vault",
                "--output",
                str(tmp_path / ".env"),
            ]
        )

        assert code == 1
        err = capsys.readouterr().err
        assert "RECALL_VAULT_PATH=" in err, "must tell the user what to set manually"


class TestNearbySearch:
    def test_vaults_are_found_in_the_usual_places(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        (tmp_path / "Documents" / "Notes" / ".obsidian").mkdir(parents=True)
        monkeypatch.setattr(Path, "home", classmethod(lambda _: tmp_path))

        assert tmp_path / "Documents" / "Notes" in discovery.search_nearby()

    def test_a_directory_without_obsidian_is_not_a_vault(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        (tmp_path / "Documents" / "Plain").mkdir(parents=True)
        monkeypatch.setattr(Path, "home", classmethod(lambda _: tmp_path))

        assert discovery.search_nearby() == []

    def test_discover_merges_both_sources_without_duplicates(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        shared = tmp_path / "Documents" / "Shared"
        (shared / ".obsidian").mkdir(parents=True)
        monkeypatch.setattr(Path, "home", classmethod(lambda _: tmp_path))
        monkeypatch.setattr(discovery, "registered_vaults", lambda: [shared])

        assert discovery.discover() == [shared]

    def test_discover_works_with_no_registry_at_all(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(Path, "home", classmethod(lambda _: tmp_path))
        monkeypatch.setattr(discovery, "registered_vaults", list)

        assert discovery.discover() == []
