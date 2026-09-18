from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping

from football_poc.coordination.repository import (
    LEASE_EXPIRY_SECONDS,
    LEASE_HEARTBEAT_SECONDS,
)

_CONFIG_SETTINGS = {
    "deployment_id",
    "authority_id",
    "authority_epoch",
    "machine_id_path",
    "connect_timeout_seconds",
    "lease_heartbeat_seconds",
    "lease_expiry_seconds",
}
_DOCUMENTED_CONFIG_KEYS = {
    "mode",
    "authority_id",
    "authority_label",
    "database_url_env",
    "deployment_id",
    "authority_epoch",
    "retired_authority_ids",
    "lease",
    "artifact_providers",
    "machine_id_path",
    "connect_timeout_seconds",
}
LEASE_IDLE_WARNING_SECONDS = 18 * 60
LEASE_IDLE_RELEASE_SECONDS = 20 * 60


@dataclass(frozen=True)
class CoordinationConfig:
    database_url: str | None
    database_url_env: str = "FOOTBALL_DATABASE_URL"
    mode: str = "postgresql"
    deployment_id: str = "local"
    authority_id: str = "local"
    authority_label: str | None = None
    authority_epoch: int = 1
    retired_authority_ids: tuple[str, ...] = ()
    artifact_providers: Mapping[str, Mapping[str, str]] = field(
        default_factory=dict
    )
    lease_idle_warning_seconds: int = LEASE_IDLE_WARNING_SECONDS
    lease_idle_release_seconds: int = LEASE_IDLE_RELEASE_SECONDS
    machine_id_path: Path | None = None
    connect_timeout_seconds: int = 5

    @classmethod
    def from_environment(
        cls, environment: Mapping[str, str] | None = None
    ) -> "CoordinationConfig":
        values = os.environ if environment is None else environment
        config_path = values.get(
            "FOOTBALL_COORDINATION_CONFIG", ""
        ).strip()
        if config_path:
            return cls._from_json_file(Path(config_path).expanduser(), values)
        raw_url = values.get("FOOTBALL_DATABASE_URL", "").strip()
        machine_path = values.get("FOOTBALL_MACHINE_ID_PATH", "").strip()
        timeout = _positive_int(
            values.get("FOOTBALL_DATABASE_CONNECT_TIMEOUT", "5"),
            "FOOTBALL_DATABASE_CONNECT_TIMEOUT",
        )
        epoch = _positive_int(
            values.get("FOOTBALL_AUTHORITY_EPOCH", "1"),
            "FOOTBALL_AUTHORITY_EPOCH",
        )
        return cls(
            database_url=raw_url or None,
            database_url_env="FOOTBALL_DATABASE_URL",
            deployment_id=values.get(
                "FOOTBALL_DEPLOYMENT_ID", "local"
            ).strip()
            or "local",
            authority_id=values.get(
                "FOOTBALL_AUTHORITY_ID", "local"
            ).strip()
            or "local",
            authority_epoch=epoch,
            machine_id_path=Path(machine_path).expanduser()
            if machine_path
            else None,
            connect_timeout_seconds=timeout,
        )

    @classmethod
    def _from_json_file(
        cls, path: Path, environment: Mapping[str, str]
    ) -> "CoordinationConfig":
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise ValueError(
                f"Cannot read FOOTBALL_COORDINATION_CONFIG: {path}"
            ) from error
        if not isinstance(document, dict):
            raise ValueError("Coordination config must be a JSON object")
        if "settings" in document:
            return cls._from_legacy_settings(document, environment)
        unknown = set(document) - _DOCUMENTED_CONFIG_KEYS
        if unknown:
            raise ValueError(
                "Unsupported coordination config keys: "
                + ", ".join(sorted(unknown))
            )
        mode = document.get("mode")
        if mode != "postgresql":
            raise ValueError("Coordination config mode must be 'postgresql'")
        secret_name = document.get("database_url_env")
        if not isinstance(secret_name, str) or not secret_name.strip():
            raise ValueError(
                "Coordination config requires database_url_env"
            )
        secret_name = secret_name.strip()
        raw_url = environment.get(secret_name, "").strip()
        if not raw_url:
            raise ValueError(
                f"Database URL environment variable {secret_name} is missing"
            )
        authority_id = _required_string(document, "authority_id")
        lease = document.get("lease")
        if not isinstance(lease, dict):
            raise ValueError("Coordination config lease must be an object")
        _validate_documented_lease(lease)
        machine_path = document.get("machine_id_path")
        if machine_path is not None and not isinstance(machine_path, str):
            raise ValueError("machine_id_path must be a string")
        authority_label = document.get("authority_label")
        if authority_label is not None and (
            not isinstance(authority_label, str)
            or not authority_label.strip()
        ):
            raise ValueError("authority_label must be a non-empty string")
        retired_authority_ids = _retired_authorities(document)
        if authority_id in retired_authority_ids:
            raise ValueError("Active authority_id cannot also be retired")
        return cls(
            database_url=raw_url,
            database_url_env=secret_name,
            mode=mode,
            deployment_id=_string_setting(
                document, "deployment_id", authority_id
            ),
            authority_id=authority_id,
            authority_label=authority_label.strip()
            if authority_label
            else None,
            authority_epoch=_setting_positive_int(
                document, "authority_epoch", 1
            ),
            retired_authority_ids=retired_authority_ids,
            artifact_providers=_artifact_providers(document),
            lease_idle_warning_seconds=LEASE_IDLE_WARNING_SECONDS,
            lease_idle_release_seconds=LEASE_IDLE_RELEASE_SECONDS,
            machine_id_path=Path(machine_path).expanduser()
            if machine_path
            else None,
            connect_timeout_seconds=_setting_positive_int(
                document, "connect_timeout_seconds", 5
            ),
        )

    @classmethod
    def _from_legacy_settings(
        cls,
        document: Mapping[str, object],
        environment: Mapping[str, str],
    ) -> "CoordinationConfig":
        unknown = set(document) - {"database_url_env", "settings"}
        if unknown:
            raise ValueError(
                "Unsupported coordination config keys: "
                + ", ".join(sorted(unknown))
            )
        secret_name, raw_url = _database_secret(document, environment)
        settings = document.get("settings", {})
        if not isinstance(settings, dict):
            raise ValueError("Coordination config settings must be an object")
        unsupported = set(settings) - _CONFIG_SETTINGS
        if unsupported:
            raise ValueError(
                "Unsupported coordination settings: "
                + ", ".join(sorted(unsupported))
            )
        _validate_lease_contract(settings)
        machine_path = settings.get("machine_id_path")
        if machine_path is not None and not isinstance(machine_path, str):
            raise ValueError("machine_id_path must be a string")
        return cls(
            database_url=raw_url,
            database_url_env=secret_name,
            deployment_id=_string_setting(
                settings, "deployment_id", "local"
            ),
            authority_id=_string_setting(
                settings, "authority_id", "local"
            ),
            authority_epoch=_setting_positive_int(
                settings, "authority_epoch", 1
            ),
            machine_id_path=Path(machine_path).expanduser()
            if machine_path
            else None,
            connect_timeout_seconds=_setting_positive_int(
                settings, "connect_timeout_seconds", 5
            ),
        )


def _positive_int(value: str, variable: str) -> int:
    try:
        parsed = int(value)
    except ValueError as error:
        raise ValueError(f"{variable} must be a positive integer") from error
    if parsed < 1:
        raise ValueError(f"{variable} must be a positive integer")
    return parsed


def _setting_positive_int(
    settings: Mapping[str, object], name: str, default: int
) -> int:
    value = settings.get(name, default)
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"{name} must be a positive integer")
    return value


def _string_setting(
    settings: Mapping[str, object], name: str, default: str
) -> str:
    value = settings.get(name, default)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value.strip()


def _validate_lease_contract(settings: Mapping[str, object]) -> None:
    heartbeat = settings.get(
        "lease_heartbeat_seconds", LEASE_HEARTBEAT_SECONDS
    )
    expiry = settings.get("lease_expiry_seconds", LEASE_EXPIRY_SECONDS)
    if heartbeat != LEASE_HEARTBEAT_SECONDS:
        raise ValueError(
            "lease_heartbeat_seconds must match the fixed repository "
            f"contract ({LEASE_HEARTBEAT_SECONDS})"
        )
    if expiry != LEASE_EXPIRY_SECONDS:
        raise ValueError(
            "lease_expiry_seconds must match the fixed repository "
            f"contract ({LEASE_EXPIRY_SECONDS})"
        )


def _database_secret(
    document: Mapping[str, object],
    environment: Mapping[str, str],
) -> tuple[str, str]:
    secret_name = document.get("database_url_env")
    if not isinstance(secret_name, str) or not secret_name.strip():
        raise ValueError("Coordination config requires database_url_env")
    secret_name = secret_name.strip()
    raw_url = environment.get(secret_name, "").strip()
    if not raw_url:
        raise ValueError(
            f"Database URL environment variable {secret_name} is missing"
        )
    return secret_name, raw_url


def _required_string(
    document: Mapping[str, object], name: str
) -> str:
    value = document.get(name)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Coordination config requires {name}")
    return value.strip()


def _validate_documented_lease(lease: Mapping[str, object]) -> None:
    expected = {
        "heartbeat_seconds": LEASE_HEARTBEAT_SECONDS,
        "expiry_seconds": LEASE_EXPIRY_SECONDS,
        "idle_warning_seconds": LEASE_IDLE_WARNING_SECONDS,
        "idle_release_seconds": LEASE_IDLE_RELEASE_SECONDS,
    }
    unknown = set(lease) - set(expected)
    if unknown:
        raise ValueError(
            "Unsupported lease settings: " + ", ".join(sorted(unknown))
        )
    for name, expected_value in expected.items():
        if lease.get(name) != expected_value:
            raise ValueError(
                f"lease.{name} must match the fixed repository contract "
                f"({expected_value})"
            )


def _retired_authorities(
    document: Mapping[str, object],
) -> tuple[str, ...]:
    values = document.get("retired_authority_ids", [])
    if not isinstance(values, list) or any(
        not isinstance(value, str) or not value.strip() for value in values
    ):
        raise ValueError(
            "retired_authority_ids must be an array of non-empty strings"
        )
    return tuple(value.strip() for value in values)


def _artifact_providers(
    document: Mapping[str, object],
) -> Mapping[str, Mapping[str, str]]:
    providers = document.get("artifact_providers", {})
    if not isinstance(providers, dict):
        raise ValueError("artifact_providers must be an object")
    validated: dict[str, Mapping[str, str]] = {}
    for provider_id, metadata in providers.items():
        if not isinstance(provider_id, str) or not provider_id.strip():
            raise ValueError("Artifact provider IDs must be non-empty strings")
        if not isinstance(metadata, dict):
            raise ValueError("Artifact provider metadata must be an object")
        if any(
            not isinstance(key, str) or not isinstance(value, str)
            for key, value in metadata.items()
        ):
            raise ValueError("Artifact provider metadata must contain strings")
        root_env = metadata.get("root_env", "").strip()
        if not root_env:
            raise ValueError(
                f"Artifact provider {provider_id} requires root_env"
            )
        validated[provider_id.strip()] = dict(metadata)
    return validated
