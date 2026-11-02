"""Les réglages posés par `/setup` (docs/specs/reglages.md), serveur par serveur, dans un fichier JSON du dossier d'état. Ce
qui n'y est pas retombe sur la variable d'environnement : un service déjà réglé n'a rien à refaire.

Un fichier absent ou illisible ne vaut rien : le bot retombe sur ses variables. Il n'est jamais écrasé sans trace : un fichier
illisible est mis de côté. L'écriture passe par un fichier temporaire, et une écriture ratée ne change rien en mémoire.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

VERSION = 1
FROM_ENV = {"pvp_channel": "pvp_channel_id", "pvp_role": "pvp_role_id", "guide_category": "guide_category_id"}


class Settings:
    """Sans fichier (`path` absent), seules les variables comptent."""

    def __init__(self, conf, path: Path | None = None, log: logging.Logger | None = None):
        self.conf, self.path, self.log = conf, path, log
        self.servers: dict[int, dict[str, int]] = self._load() if path is not None else {}

    def _load(self) -> dict[int, dict[str, int]]:
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            if raw["version"] != VERSION:
                raise ValueError(f"version {raw['version']!r}")
            servers = {int(guild): dict(values) for guild, values in raw["servers"].items()}
            if not all(field in FROM_ENV and isinstance(value, int)
                       for values in servers.values() for field, value in values.items()):
                raise ValueError("réglage invalide")
            return servers
        except FileNotFoundError:
            return {}
        except (OSError, ValueError, KeyError, TypeError, AttributeError) as err:
            self._set_aside(err)
            return {}

    def _set_aside(self, err: Exception) -> None:
        aside = self.path.with_name(self.path.name + ".illisible")
        try:
            os.replace(self.path, aside)
        except OSError as other:
            aside = other
        self.log.warning("réglages illisibles (%s) : retour aux variables d'environnement ; fichier mis de côté : %s", err, aside)

    def _write(self, servers: dict[int, dict[str, int]]) -> None:
        if self.path is not None:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temp = self.path.with_name(self.path.name + ".tmp")
            raw = {"version": VERSION, "servers": {str(guild): values for guild, values in servers.items()}}
            temp.write_text(json.dumps(raw, indent=1), encoding="utf-8")
            os.replace(temp, self.path)
        self.servers = servers

    def _copy(self) -> dict[int, dict[str, int]]:
        return {guild: dict(values) for guild, values in self.servers.items()}

    def put(self, guild_id: int, field: str, value: int) -> None:
        """Lève OSError si le fichier ne peut pas être écrit : le réglage n'est alors pas appliqué non plus."""
        servers = self._copy()
        servers.setdefault(guild_id, {})[field] = value
        self._write(servers)

    def clear(self, guild_id: int, field: str) -> bool:
        """Vrai si la commande avait posé ce réglage. Lève OSError si le fichier ne peut pas être écrit."""
        servers = self._copy()
        if servers.get(guild_id, {}).pop(field, None) is None:
            return False
        self._write(servers)
        return True

    def stored(self, guild_id: int | None, field: str) -> int | None:
        return self.servers.get(guild_id, {}).get(field)

    def env(self, field: str) -> int | None:
        return getattr(self.conf, FROM_ENV[field], None)

    def get(self, guild_id: int | None, field: str) -> int | None:
        """La commande d'abord, puis la variable."""
        value = self.stored(guild_id, field)
        return value if value is not None else self.env(field)

    def origin(self, guild_id: int | None, field: str) -> str | None:
        if self.stored(guild_id, field) is not None:
            return "command"
        return "variable" if self.env(field) is not None else None

    def any_stored(self, field: str) -> bool:
        return any(field in values for values in self.servers.values())

    def count(self) -> int:
        return sum(len(values) for values in self.servers.values())
