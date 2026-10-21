"""Automatisk säkerhetskopiering av databasen."""

from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional


class BackupManager:
    """Hanterar automatiska säkerhetskopior av SQLite-databasen."""

    MAX_BACKUPS = 10

    def __init__(self, db_path: Path, backup_dir: Optional[Path] = None) -> None:
        """
        Initierar backup-hanteraren.

        Args:
            db_path: Sökväg till databasfilen.
            backup_dir: Mapp för backups (standard: data/backups).
        """
        self.db_path = db_path
        self.backup_dir = backup_dir or db_path.parent / "backups"
        self.backup_dir.mkdir(parents=True, exist_ok=True)

    def create_backup(self) -> Path:
        """
        Skapar en tidsstämplad säkerhetskopia.

        Returns:
            Sökväg till backup-filen.

        Raises:
            FileNotFoundError: Om databasfilen saknas.
            OSError: Om kopiering misslyckas.
        """
        if not self.db_path.exists():
            raise FileNotFoundError(f"Databasen hittades inte: {self.db_path}")

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = self.backup_dir / f"finans_backup_{timestamp}.db"
        shutil.copy2(self.db_path, backup_path)
        self._cleanup_old_backups()
        return backup_path

    def _cleanup_old_backups(self) -> None:
        """Behåller endast de senaste MAX_BACKUPS kopiorna."""
        backups = sorted(
            self.backup_dir.glob("finans_backup_*.db"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        for old_backup in backups[self.MAX_BACKUPS :]:
            old_backup.unlink(missing_ok=True)

    def list_backups(self) -> list[Path]:
        """Returnerar alla tillgängliga backups, nyast först."""
        return sorted(
            self.backup_dir.glob("finans_backup_*.db"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
