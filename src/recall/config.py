"""Runtime configuration, resolved once at startup."""

from __future__ import annotations

from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuration for a Recall server instance.

    Every value can be supplied as an environment variable prefixed with
    ``RECALL_`` or placed in a local ``.env`` file.
    """

    model_config = SettingsConfigDict(
        env_prefix="RECALL_",
        env_file=".env",
        extra="ignore",
    )

    vault_path: Path = Field(
        description="Absolute path to the Obsidian vault directory.",
    )
    root: str = Field(
        default="Recall",
        description="Folder inside the vault that Recall owns.",
    )
    daily_folder: str = Field(
        default="Daily",
        description="Subfolder holding dated capture logs.",
    )
    max_search_results: int = Field(default=10, ge=1, le=100)
    excerpt_chars: int = Field(default=320, ge=80, le=2000)

    @field_validator("vault_path")
    @classmethod
    def _expand(cls, value: Path) -> Path:
        return value.expanduser().resolve()

    @field_validator("root", "daily_folder")
    @classmethod
    def _clean_folder(cls, value: str) -> str:
        cleaned = value.strip().strip("/")
        if not cleaned or ".." in Path(cleaned).parts:
            raise ValueError(f"invalid folder name: {value!r}")
        return cleaned

    @property
    def root_path(self) -> Path:
        """Absolute path to the folder Recall writes into."""
        return self.vault_path / self.root

    @property
    def daily_path(self) -> Path:
        """Absolute path to the daily-log folder."""
        return self.root_path / self.daily_folder

    def validate_vault(self) -> None:
        """Fail fast on a misconfigured vault.

        Recall creates its own folder inside an existing vault; it never
        creates the vault itself, because doing so silently would scatter
        notes into a directory the user did not mean to use.
        """
        if not self.vault_path.exists():
            raise ValueError(
                f"vault path does not exist: {self.vault_path}. "
                "Set RECALL_VAULT_PATH to an existing Obsidian vault."
            )
        if not self.vault_path.is_dir():
            raise ValueError(f"vault path is not a directory: {self.vault_path}")
        self.root_path.mkdir(parents=True, exist_ok=True)


def load_settings() -> Settings:
    """Load and validate settings, creating the Recall folder if needed."""
    settings = Settings()  # type: ignore[call-arg]  # values come from env
    settings.validate_vault()
    return settings
