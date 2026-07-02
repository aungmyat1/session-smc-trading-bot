from shared.models.records import EvidenceRecord as SharedEvidenceRecord
from shared.serialization.json_files import now_iso as shared_now_iso
from shared.strategy_api.signal import Signal as SharedSignal
from svos.shared.models import EvidenceRecord as LegacyEvidenceRecord
from svos.shared.support import now_iso as legacy_now_iso
from core.signal import Signal as LegacySignal


def test_signal_reexport_identity() -> None:
    assert LegacySignal is SharedSignal


def test_svos_models_reexport_identity() -> None:
    assert LegacyEvidenceRecord is SharedEvidenceRecord


def test_svos_support_reexport_identity() -> None:
    assert legacy_now_iso is shared_now_iso
