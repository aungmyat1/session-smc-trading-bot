import json
from datetime import datetime, timezone

import pytest

from replay.replay_events import ReplayEvent, ReplayEventType
from replay.replay_journal import ReplayJournal


def test_journal_writes_jsonl_and_summary(tmp_path) -> None:
    journal = ReplayJournal(tmp_path, "run-1")
    journal.append(ReplayEvent("run-1", ReplayEventType.REPLAY_STARTED, datetime(2024, 1, 1, tzinfo=timezone.utc), {}, 0))
    journal.write_summary({"status": "pass"})
    event = json.loads(journal.events_path.read_text(encoding="utf-8"))
    assert event["event_type"] == "replay_started"
    assert json.loads(journal.summary_path.read_text(encoding="utf-8"))["status"] == "pass"

    with pytest.raises(FileExistsError):
        ReplayJournal(tmp_path, "run-1")
