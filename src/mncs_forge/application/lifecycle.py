"""Construct one lifecycle projection from verified history and current observations."""

from __future__ import annotations

from collections.abc import Mapping

from ..ports import ProjectObserver, RecordReader, record_by_id
from ..records import ForgeRecord, LedgerEntry
from ..state_machine import ForgeStateMachine


class LifecycleContext:
    """Shared application collaborator; transition policy remains in `ForgeStateMachine`."""

    def __init__(
        self,
        *,
        mode: str,
        records: RecordReader,
        observer: ProjectObserver,
    ) -> None:
        self.mode = mode
        self.records = records
        self.observer = observer

    def machine(
        self,
        *,
        observe_epoch_authority: bool = True,
        observe_freeze_bindings: bool = True,
        observe_policy: bool = True,
        history_kinds: frozenset[str] | None = None,
    ) -> ForgeStateMachine:
        policy_identity, required_evidence, policy_error = (
            self.observer.selection_evidence_policy() if observe_policy else ("", (), None)
        )
        environment_keys, environment_identities, policy_identities = (
            self.observer.evidence_envelopes() if observe_policy else ({}, {}, {})
        )
        current_candidate_identity = self.observer.current_candidate_identity()
        history = (
            self.records.records_for(history_kinds)
            if history_kinds is not None
            else self.records.records()
        )
        current_freeze = next(
            (entry.payload for entry in reversed(history) if entry.kind == "freeze"), None
        )
        return ForgeStateMachine(
            mode=self.mode,
            history=history,
            current_candidate_identity=current_candidate_identity,
            current_authority_identities=(
                self.observer.current_authority_identities() if observe_epoch_authority else {}
            ),
            current_freeze_bindings=(
                self.observer.current_freeze_bindings(
                    current_candidate_identity,
                    current_freeze if isinstance(current_freeze, Mapping) else None,
                )
                if observe_freeze_bindings
                else {}
            ),
            selection_policy_identity=policy_identity,
            required_evidence=required_evidence,
            selection_policy_error=policy_error,
            evidence_environment_keys=environment_keys,
            evidence_environment_identities=environment_identities,
            evidence_policy_identities=policy_identities,
        )

    def record_by_id(self, kind: str, identity: str, key: str) -> ForgeRecord:
        return record_by_id(self.records, kind, identity, key)

    def records_of(self, kind: str) -> list[LedgerEntry]:
        return self.records.records(kind)

    def verify_freeze(self, freeze: Mapping[str, object]) -> None:
        from ..errors import ForgeError

        current, _ = self.machine(observe_epoch_authority=False).authorize_evaluator_entry()
        if current["freeze_id"] != freeze.get("freeze_id"):
            raise ForgeError("FREEZE_SUPERSEDED", "freeze is not the current lifecycle freeze")
