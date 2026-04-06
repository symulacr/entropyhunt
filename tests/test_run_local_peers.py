from __future__ import annotations

from pathlib import Path

from scripts import run_local_peers


class _FakeProcess:
    def __init__(self, *, interrupt_on_wait: bool = False) -> None:
        self.interrupt_on_wait = interrupt_on_wait
        self.returncode: int | None = None
        self.terminated = False
        self.killed = False

    def wait(self, timeout: float | None = None) -> int:
        if self.interrupt_on_wait and self.returncode is None:
            raise KeyboardInterrupt
        self.returncode = 0 if self.returncode is None else self.returncode
        return self.returncode

    def poll(self) -> int | None:
        return self.returncode

    def terminate(self) -> None:
        self.terminated = True
        self.returncode = 130

    def kill(self) -> None:
        self.killed = True
        self.returncode = 130


def test_launch_processes_returns_130_and_terminates_children_on_interrupt(monkeypatch) -> None:
    first = _FakeProcess(interrupt_on_wait=True)
    second = _FakeProcess()
    processes = iter([first, second])

    monkeypatch.setattr(
        run_local_peers.subprocess,
        "Popen",
        lambda command, cwd: next(processes),
    )

    exit_code = run_local_peers.launch_processes([["python3", "main.py"], ["python3", "main.py"]], cwd=Path("."))

    assert exit_code == 130
    assert first.terminated is True
    assert second.terminated is True
    assert first.killed is False
    assert second.killed is False
