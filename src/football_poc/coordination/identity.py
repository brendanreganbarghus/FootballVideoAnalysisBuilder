from __future__ import annotations

import getpass
import json
import os
import socket
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping


class IdentityError(RuntimeError):
    pass


@dataclass(frozen=True)
class MachineIdentity:
    machine_id: str
    domain: str
    username: str
    hostname: str
    ip_address: str | None

    @property
    def developer_id(self) -> str:
        principal = (
            f"{self.domain}\\{self.username}"
            if self.domain
            else self.username
        )
        return principal.casefold()


def default_machine_id_path(
    environment: Mapping[str, str] | None = None,
) -> Path:
    values = os.environ if environment is None else environment
    configured = values.get("FOOTBALL_MACHINE_ID_PATH", "").strip()
    if configured:
        return Path(configured).expanduser()
    local_app_data = values.get("LOCALAPPDATA", "").strip()
    if local_app_data:
        return Path(local_app_data) / "FootballVideoPOC" / "machine.json"
    return Path.home() / ".football-video-poc" / "machine.json"


def load_or_create_machine_identity(
    path: Path | None = None,
    *,
    environment: Mapping[str, str] | None = None,
) -> MachineIdentity:
    values = os.environ if environment is None else environment
    identity_path = path or default_machine_id_path(values)
    machine_id = _load_or_create_id(identity_path)
    hostname = socket.gethostname()
    username = values.get("USERNAME", "").strip() or getpass.getuser()
    domain = values.get("USERDOMAIN", "").strip()
    return MachineIdentity(
        machine_id=machine_id,
        domain=domain,
        username=username,
        hostname=hostname,
        ip_address=_best_effort_ip(hostname),
    )


def _load_or_create_id(path: Path) -> str:
    if path.exists():
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            return str(uuid.UUID(str(payload["machine_id"])))
        except (
            OSError,
            ValueError,
            KeyError,
            TypeError,
            json.JSONDecodeError,
        ) as error:
            raise IdentityError(f"Invalid machine identity file: {path}") from error

    path.parent.mkdir(parents=True, exist_ok=True)
    machine_id = str(uuid.uuid4())
    payload = json.dumps({"machine_id": machine_id}, indent=2) + "\n"
    try:
        with path.open("x", encoding="utf-8") as output:
            output.write(payload)
    except FileExistsError:
        return _load_or_create_id(path)
    except OSError as error:
        raise IdentityError(f"Cannot persist machine identity: {path}") from error
    return machine_id


def _best_effort_ip(hostname: str) -> str | None:
    try:
        return socket.gethostbyname(hostname)
    except OSError:
        return None
