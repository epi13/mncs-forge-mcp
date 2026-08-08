"""Startup storage and stranded-verifier execution recovery orchestration."""

from __future__ import annotations

from ..errors import ForgeError
from ..ports import RecordCommitter, RecordReader
from ..records import RecordType, VerifierActionRecord, VerifierResultRecord, new_record
from ..state_machine import ForgeStateMachine
from ..verifier_support import recovered_terminal_unknown_result
from .support import now


class RecoveryService:
    def __init__(self, *, records: RecordReader, record_store: RecordCommitter) -> None:
        self.records = records
        self.record_store = record_store

    def recover(self, *, recover_storage: bool) -> None:
        if recover_storage:
            self.record_store.recover()
        self._recover_stranded_verifier_actions()

    def _recover_stranded_verifier_actions(self) -> None:
        actions = self.records.records("verifier_action")
        terminal_action_ids = {
            str(entry.payload["action_id"]) for entry in self.records.records("verifier_result")
        }
        for entry in actions:
            action = entry.payload
            if not isinstance(action, VerifierActionRecord):
                raise ForgeError("RECOVERY_ACTION_MALFORMED", "verifier action has wrong type")
            action_id = str(action["action_id"])
            if action_id in terminal_action_ids:
                continue
            try:
                with self.record_store.action_execution(action_id, timeout=0):
                    current_results = self.records.records("verifier_result")
                    ForgeStateMachine.authorize_terminal_result_for_recorded_action(
                        action,
                        current_results,
                        action_id=action_id,
                        candidate_id=str(action["candidate_identity"]),
                        freeze_id=(
                            str(action["freeze_identity"])
                            if action["freeze_identity"] is not None
                            else None
                        ),
                        mode=str(action["mode"]),
                    )
                    result = new_record(
                        RecordType.VERIFIER_RESULT,
                        recovered_terminal_unknown_result(action=action, recorded_at=now()),
                    )
                    if not isinstance(result, VerifierResultRecord):
                        raise ForgeError(
                            "RECOVERY_ACTION_MALFORMED",
                            "recovered verifier result has wrong type",
                        )
                    self.record_store.commit("verifier-results", "verifier_result", result)
                    terminal_action_ids.add(action_id)
            except ForgeError as exc:
                if exc.code == "ACTION_EXECUTION_BUSY":
                    continue
                raise
