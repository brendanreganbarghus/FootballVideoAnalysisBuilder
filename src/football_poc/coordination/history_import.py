from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from football_poc.artifact_store import discover_artifact_root
from football_poc.coordination.models import (
    HistoricalImportOutcome,
    HistoricalImportSource,
)

_CHECKSUM_LINE = re.compile(r"^([0-9a-fA-F]{64})\s+[* ]?(.+?)\s*$")
_EVENT_KEY = re.compile(r"^(?P<stream>[CEM])(?P<number>[1-9][0-9]*)$")
_STATE_SUFFIX = "-review-state.json"
_WORKFLOWS = {
    "event-review-state-innovation": (
        "innovation_day_bac",
        "football-event-review",
    ),
    "event-review-state-live": (
        "live_iteration_25",
        "football-event-review-live",
    ),
}
_WORKFLOW_IDS = frozenset(item[0] for item in _WORKFLOWS.values())


class HistoricalImportError(RuntimeError):
    pass


@dataclass(frozen=True)
class HistoricalImportReport:
    source_root: str
    mode: str
    outcomes: tuple[HistoricalImportOutcome, ...]

    @property
    def counts(self) -> Mapping[str, int]:
        counts = Counter(outcome.status for outcome in self.outcomes)
        return {
            name: counts.get(name, 0)
            for name in ("inserted", "unchanged", "conflicting", "rejected")
        }

    @property
    def succeeded(self) -> bool:
        return not self.counts["conflicting"] and not self.counts["rejected"]

    def to_dict(self) -> Mapping[str, Any]:
        return {
            "source_root": self.source_root,
            "mode": self.mode,
            "succeeded": self.succeeded,
            "counts": dict(self.counts),
            "outcomes": [asdict(item) for item in self.outcomes],
        }


def canonical_json_hash(value: Mapping[str, Any]) -> str:
    encoded = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _payload(value: Any, **identity: Any) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return {**value, **identity}
    return {"value": value, **identity}


def _explicit_event_key(value: Any, stream: str) -> str | None:
    if not isinstance(value, Mapping):
        return None
    for field in (
        "event_key",
        "eventKey",
        "proposal_key",
        "proposalKey",
        "id",
    ):
        candidate = value.get(field)
        if not isinstance(candidate, str):
            continue
        match = _EVENT_KEY.fullmatch(candidate)
        if match and match.group("stream") == stream:
            return candidate
    return None


def derive_history_records(
    state: Mapping[str, Any],
) -> tuple[Mapping[str, Any], ...]:
    """Derive only records explicitly represented by the saved state."""

    records: list[Mapping[str, Any]] = []
    proposals = state.get("additionalProposals")
    if isinstance(proposals, list):
        for proposal in proposals:
            event_key = _explicit_event_key(proposal, "C")
            if event_key is None:
                continue
            records.append(
                {
                    "stream": "C",
                    "payload": _payload(
                        proposal, event_key=event_key, imported=True
                    ),
                }
            )
    snapshots = [
        item
        for item in (state.get("engineBefore"), state.get("engineAfter"))
        if isinstance(item, Mapping)
    ]
    predictions = next(
        (
            item.get("predictions")
            for item in reversed(snapshots)
            if isinstance(item.get("predictions"), list)
        ),
        (),
    )
    for event in predictions:
        event_key = _explicit_event_key(event, "E")
        if event_key is None:
            continue
        records.append(
            {
                "stream": "E",
                "payload": _payload(
                    event, event_key=event_key, imported=True
                ),
            }
        )
    decisions = state.get("decisions")
    if isinstance(decisions, Mapping):
        for key in sorted(decisions, key=str):
            decision = decisions[key]
            proposal_key = _explicit_event_key(decision, "C")
            if proposal_key is None:
                source_key = str(key)
                proposal_key = (
                    f"decision-index:{source_key}"
                    if source_key.isdigit()
                    else source_key
                )
            records.append(
                {
                    "stream": "decision",
                    "payload": _payload(
                        decision,
                        proposal_key=proposal_key,
                        type=(
                            str(decision.get("status", "decision"))
                            if isinstance(decision, Mapping)
                            else "decision"
                        ),
                        imported=True,
                    ),
                }
            )
    conversation = state.get("conversation")
    if isinstance(conversation, list):
        for message in conversation:
            records.append(
                {
                    "stream": "activity",
                    "payload": _payload(
                        message, type="conversation", imported=True
                    ),
                }
            )
    reviews = state.get("engineEventReviews")
    if isinstance(reviews, Mapping):
        for key in sorted(reviews):
            review = reviews[key]
            records.append(
                {
                    "stream": "verdict",
                    "payload": _payload(
                        review,
                        event_key=str(key),
                        type=(
                            str(review.get("status", "reviewed"))
                            if isinstance(review, Mapping)
                            else "reviewed"
                        ),
                        imported=True,
                    ),
                }
            )
    return validate_history_records(records)


def validate_history_records(
    records: Iterable[Mapping[str, Any]],
) -> tuple[Mapping[str, Any], ...]:
    validated: list[Mapping[str, Any]] = []
    for record in records:
        stream = record.get("stream")
        payload = record.get("payload")
        if stream not in {
            "C",
            "E",
            "M",
            "activity",
            "decision",
            "verdict",
        }:
            raise HistoricalImportError(
                f"Unsupported derived history stream: {stream}"
            )
        if not isinstance(payload, Mapping):
            raise HistoricalImportError(
                f"Derived {stream} history payload must be an object"
            )
        if stream in {"C", "E", "M"}:
            event_key = payload.get("event_key")
            match = (
                _EVENT_KEY.fullmatch(event_key)
                if isinstance(event_key, str)
                else None
            )
            if match is None or match.group("stream") != stream:
                raise HistoricalImportError(
                    f"Derived {stream} history requires an explicit "
                    "matching event_key"
                )
        if stream == "decision" and not isinstance(
            payload.get("proposal_key"), str
        ):
            raise HistoricalImportError(
                "Derived decision history requires an explicit proposal_key"
            )
        if stream == "verdict" and not isinstance(
            payload.get("event_key"), str
        ):
            raise HistoricalImportError(
                "Derived verdict history requires an explicit event_key"
            )
        validated.append(record)
    return tuple(validated)


def _manifest_entries(root: Path) -> Mapping[str, str]:
    path = root / "00-governance" / "checksums.sha256"
    try:
        lines = path.read_text(encoding="utf-8-sig").splitlines()
    except OSError as error:
        raise HistoricalImportError(f"Cannot read checksum manifest: {path}") from error
    entries: dict[str, str] = {}
    for line_number, line in enumerate(lines, 1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        match = _CHECKSUM_LINE.fullmatch(stripped)
        if match is None:
            raise HistoricalImportError(
                f"Invalid checksum manifest line {line_number}"
            )
        logical_key = match.group(2).replace("\\", "/").removeprefix("./")
        if logical_key in entries:
            raise HistoricalImportError(
                f"Duplicate checksum entry: {logical_key}"
            )
        entries[logical_key] = match.group(1).lower()
    return entries


def _reject(
    provider: str,
    logical_key: str,
    digest: str,
    detail: str,
    workflow_id: str = "unknown",
    segment_id: str | None = None,
) -> HistoricalImportOutcome:
    return HistoricalImportOutcome(
        "rejected",
        workflow_id,
        provider,
        logical_key,
        digest,
        segment_id,
        {"reason": detail},
    )


def discover_review_sources(
    source_root: Path,
    *,
    provider: str = "xebia-shared",
) -> tuple[tuple[HistoricalImportSource, ...], tuple[HistoricalImportOutcome, ...]]:
    root = source_root.expanduser().resolve()
    manifest = _manifest_entries(root)
    sources: list[HistoricalImportSource] = []
    rejected: list[HistoricalImportOutcome] = []
    baseline = root / "30-shared-baselines"
    for directory, (workflow_id, canvas_id) in _WORKFLOWS.items():
        state_root = baseline / directory
        if not state_root.is_dir():
            continue
        for path in sorted(state_root.glob(f"*{_STATE_SUFFIX}")):
            resolved = path.resolve()
            if not resolved.is_relative_to(state_root.resolve()):
                rejected.append(
                    _reject(
                        provider,
                        path.name,
                        "0" * 64,
                        "review-state path escapes its workflow directory",
                        workflow_id,
                    )
                )
                continue
            logical_key = path.relative_to(root).as_posix()
            expected = manifest.get(logical_key)
            content = path.read_bytes()
            actual = hashlib.sha256(content).hexdigest()
            segment_id = path.name[: -len(_STATE_SUFFIX)]
            if expected is None:
                rejected.append(
                    _reject(
                        provider,
                        logical_key,
                        actual,
                        "file is absent from 00-governance/checksums.sha256",
                        workflow_id,
                        segment_id,
                    )
                )
                continue
            if actual != expected:
                rejected.append(
                    _reject(
                        provider,
                        logical_key,
                        actual,
                        f"checksum mismatch (expected {expected})",
                        workflow_id,
                        segment_id,
                    )
                )
                continue
            try:
                state = json.loads(content)
            except (UnicodeDecodeError, json.JSONDecodeError) as error:
                rejected.append(
                    _reject(
                        provider,
                        logical_key,
                        actual,
                        f"invalid JSON: {type(error).__name__}",
                        workflow_id,
                        segment_id,
                    )
                )
                continue
            if not isinstance(state, dict):
                rejected.append(
                    _reject(
                        provider,
                        logical_key,
                        actual,
                        "review state must be a JSON object",
                        workflow_id,
                        segment_id,
                    )
                )
                continue
            original_state = dict(state)
            mismatches = []
            canonicalized_fields = []
            if state.get("workflowId") in (None, ""):
                state["workflowId"] = workflow_id
                canonicalized_fields.append("workflowId")
            elif state.get("workflowId") != workflow_id:
                mismatches.append("workflowId")
            if state.get("canvasId") in (None, ""):
                state["canvasId"] = canvas_id
                canonicalized_fields.append("canvasId")
            elif state.get("canvasId") != canvas_id:
                mismatches.append("canvasId")
            if state.get("segment") != segment_id:
                mismatches.append("segment")
            if mismatches:
                rejected.append(
                    _reject(
                        provider,
                        logical_key,
                        actual,
                        "identity mismatch: " + ", ".join(mismatches),
                        workflow_id,
                        segment_id,
                    )
                )
                continue
            sources.append(
                HistoricalImportSource(
                    workflow_id,
                    provider,
                    logical_key,
                    actual,
                    segment_id,
                    state,
                    len(content),
                    original_state=original_state,
                    canonicalized_fields=tuple(canonicalized_fields),
                )
            )
    return tuple(sources), tuple(rejected)


def _discover_regression_outcomes(
    repository: Any,
    root: Path,
    provider: str,
    paths: Mapping[str, Path],
) -> tuple[HistoricalImportOutcome, ...]:
    manifest = _manifest_entries(root)
    results: list[HistoricalImportOutcome] = []
    for workflow_id, supplied_path in sorted(paths.items()):
        if workflow_id not in _WORKFLOW_IDS:
            results.append(
                _reject(
                    provider,
                    supplied_path.name,
                    "0" * 64,
                    "unknown regression workflow",
                    workflow_id,
                )
            )
            continue
        path = supplied_path.expanduser().resolve()
        logical_key = f"benchmarks/alfheim/{path.name}"
        try:
            content = path.read_bytes()
        except OSError as error:
            results.append(
                _reject(
                    provider,
                    logical_key,
                    "0" * 64,
                    f"cannot read regression registry: {type(error).__name__}",
                    workflow_id,
                )
            )
            continue
        digest = hashlib.sha256(content).hexdigest()
        try:
            relative = path.relative_to(root).as_posix()
        except ValueError:
            relative = None
        if relative is not None:
            logical_key = relative
            expected = manifest.get(relative)
            if expected is not None and expected != digest:
                results.append(
                    _reject(
                        provider,
                        logical_key,
                        digest,
                        f"checksum mismatch (expected {expected})",
                        workflow_id,
                    )
                )
                continue
        try:
            registry = json.loads(content)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            results.append(
                _reject(
                    provider,
                    logical_key,
                    digest,
                    f"invalid regression JSON: {type(error).__name__}",
                    workflow_id,
                )
            )
            continue
        if not isinstance(registry, (dict, list)):
            results.append(
                _reject(
                    provider,
                    logical_key,
                    digest,
                    "regression registry must be an object or array",
                    workflow_id,
                )
            )
            continue
        if (
            isinstance(registry, dict)
            and registry.get("workflow") != workflow_id
        ):
            results.append(
                _reject(
                    provider,
                    logical_key,
                    digest,
                    "regression registry workflow mismatch",
                    workflow_id,
                )
            )
            continue
        previous = repository.get_historical_import_outcome(
            workflow_id, provider, logical_key, digest
        )
        results.append(
            HistoricalImportOutcome(
                (
                    "unchanged"
                    if previous and previous.status == "inserted"
                    else "inserted"
                ),
                workflow_id,
                provider,
                logical_key,
                digest,
                None,
                {
                    "kind": "regression_registry",
                    "registry": registry,
                    "checksum_verified": relative in manifest if relative else False,
                    "source_size": len(content),
                    "state_sha256": hashlib.sha256(
                        json.dumps(
                            registry,
                            ensure_ascii=False,
                            sort_keys=True,
                            separators=(",", ":"),
                        ).encode("utf-8")
                    ).hexdigest(),
                },
            )
        )
    return tuple(results)


def reconcile_historical_review_state(
    repository: Any,
    source_root: Path,
    *,
    provider: str = "xebia-shared",
    apply: bool = False,
    regression_paths: Mapping[str, Path] | None = None,
) -> HistoricalImportReport:
    sources, rejected = discover_review_sources(source_root, provider=provider)
    regression = _discover_regression_outcomes(
        repository,
        source_root.expanduser().resolve(),
        provider,
        regression_paths or {},
    )
    preview = repository.import_historical_states(sources, apply=False)
    all_rejected = (
        *rejected,
        *(item for item in regression if item.status == "rejected"),
    )
    if apply and not all_rejected and not any(
        item.status == "conflicting" for item in preview
    ):
        outcomes = repository.import_historical_states(sources, apply=True)
        for item in regression:
            if item.status == "inserted":
                repository.record_historical_import_outcome(
                    item,
                    source_size=int(item.details["source_size"]),
                    state_sha256=str(item.details["state_sha256"]),
                )
    else:
        outcomes = preview
        if apply:
            for item in (*preview, *rejected, *regression):
                if item.status not in {"conflicting", "rejected"}:
                    continue
                if item.workflow_id in _WORKFLOW_IDS:
                    repository.record_historical_import_outcome(item)
    return HistoricalImportReport(
        str(source_root.expanduser().resolve()),
        "apply" if apply else "dry-run",
        tuple(
            sorted(
                (*outcomes, *rejected, *regression),
                key=lambda item: (item.workflow_id, item.logical_key),
            )
        ),
    )


def dry_run_import(
    repository: Any,
    source_root: Path,
    *,
    provider: str = "xebia-shared",
    regression_paths: Mapping[str, Path] | None = None,
) -> HistoricalImportReport:
    return reconcile_historical_review_state(
        repository,
        source_root,
        provider=provider,
        apply=False,
        regression_paths=regression_paths,
    )


def apply_import(
    repository: Any,
    source_root: Path,
    *,
    provider: str = "xebia-shared",
    regression_paths: Mapping[str, Path] | None = None,
) -> HistoricalImportReport:
    return reconcile_historical_review_state(
        repository,
        source_root,
        provider=provider,
        apply=True,
        regression_paths=regression_paths,
    )


def build_reconciliation_hook(
    source_root: Path,
    *,
    provider: str = "xebia-shared",
    regression_paths: Mapping[str, Path] | None = None,
):
    from football_poc.coordination.postgres import ReconciliationResult

    def reconcile(repository: Any) -> ReconciliationResult:
        report = apply_import(
            repository,
            source_root,
            provider=provider,
            regression_paths=regression_paths,
        )
        status = "completed" if report.succeeded else "conflict"
        return ReconciliationResult(
            status,
            (
                "Historical review state reconciled"
                if report.succeeded
                else "Historical review-state reconciliation blocked writes"
            ),
            report.to_dict(),
        )

    return reconcile


def _source_root(explicit: str | None) -> Path:
    if explicit:
        root = Path(explicit).expanduser().resolve()
    else:
        root = discover_artifact_root()
        if root is None:
            config_path = os.environ.get(
                "FOOTBALL_COORDINATION_CONFIG", ""
            ).strip()
            if config_path:
                try:
                    config = json.loads(
                        Path(config_path).expanduser().read_text(encoding="utf-8")
                    )
                    providers = config.get("artifact_providers", {})
                    provider = next(iter(providers.values()), {})
                    root_env = provider.get("root_env")
                    configured = os.environ.get(str(root_env), "").strip()
                    root = (
                        Path(configured).expanduser().resolve()
                        if configured
                        else None
                    )
                except (OSError, json.JSONDecodeError, AttributeError):
                    root = None
    if root is None or not root.is_dir():
        raise HistoricalImportError(
            "No artifact root; pass --source-root or set FOOTBALL_ARTIFACT_ROOT"
        )
    return root


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Reconcile checksummed historical football review state"
    )
    parser.add_argument("--source-root")
    parser.add_argument("--provider", default="xebia-shared")
    parser.add_argument("--innovation-regressions")
    parser.add_argument("--live-regressions")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    arguments = parser.parse_args(argv)
    try:
        from football_poc.coordination import create_coordination_repository

        root = _source_root(arguments.source_root)
        repository = create_coordination_repository()
        report = reconcile_historical_review_state(
            repository,
            root,
            provider=arguments.provider,
            apply=arguments.apply,
            regression_paths={
                workflow: Path(value)
                for workflow, value in (
                    ("innovation_day_bac", arguments.innovation_regressions),
                    ("live_iteration_25", arguments.live_regressions),
                )
                if value
            },
        )
        print(json.dumps(report.to_dict(), sort_keys=True))
        return 0 if report.succeeded else 2
    except Exception as error:
        print(
            json.dumps(
                {
                    "succeeded": False,
                    "error": f"{type(error).__name__}: {error}",
                },
                sort_keys=True,
            )
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
