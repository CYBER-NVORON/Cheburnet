from __future__ import annotations

import sys

from cheburnet.app.core.process import run_command


def test_run_command_captures_stdout() -> None:
    result = run_command([sys.executable, "-c", "print('ok')"], timeout=5)

    assert result.ok
    assert result.stdout.strip() == "ok"
