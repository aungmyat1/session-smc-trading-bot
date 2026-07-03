import subprocess
import sys


def test_cli_self_test_passes() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "replay.replay_cli", "self-test"],
        check=False, capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    assert "self-test passed" in result.stdout
