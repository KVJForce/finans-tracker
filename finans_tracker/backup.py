"""Automatic backup of the database."""

from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional


class BackupManager:
    """Manages automatic backups of the SQLite database."""

    MAX_BACKUPS = 10

    def __init__(self, db_path: Path, backup_dir: Optional[Path] = None) -> None:
        """
        Initializes the backup manager.

        Args:
            db_path: Path to the database file.
            backup_dir: Directory for backups (default: data/backups).
        """
        self.db_path = db_path
        self.backup_dir = backup_dir or db_path.parent / "backups"
        self.backup_dir.mkdir(parents=True, exist_ok=True)

    def create_backup(self) -> Path:
        """
        Creates a timestamped backup.

        Returns:
            Path to the backup file.

        Raises:
            FileNotFoundError: If the database file is missing.
            OSError: If copying fails.
        """
        if not self.db_path.exists():
            raise FileNotFoundError(f"Database not found: {self.db_path}")

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = self.backup_dir / f"finans_backup_{timestamp}.db"
        shutil.copy2(self.db_path, backup_path)
        self._cleanup_old_backups()
        return backup_path

    def _cleanup_old_backups(self) -> None:
        """Keeps only the most recent MAX_BACKUPS copies."""
        backups = sorted(
            self.backup_dir.glob("finans_backup_*.db"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        for old_backup in backups[self.MAX_BACKUPS :]:
            old_backup.unlink(missing_ok=True)

    def list_backups(self) -> list[Path]:
        """Returns all available backups, newest first."""
        return sorted(
            self.backup_dir.glob("finans_backup_*.db"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
