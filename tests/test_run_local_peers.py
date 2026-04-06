from __future__ import annotations

import json
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


def test_launch_processes_returns_highest_child_exit_code(monkeypatch) -> None:
    first = _FakeProcess()
    first.returncode = 0
    second = _FakeProcess()
    second.returncode = 2
    processes = iter([first, second])

    monkeypatch.setattr(
        run_local_peers.subprocess,
        "Popen",
        lambda command, cwd: next(processes),
    )

    exit_code = run_local_peers.launch_processes([["python3", "main.py"], ["python3", "main.py"]], cwd=Path("."))

    assert exit_code == 2


def test_synthesize_proofs_marks_runtime_and_derived_event_provenance(tmp_path: Path) -> None:
    proofs_path = tmp_path / "proofs.jsonl"
    proofs_path.write_text(
        json.dumps(
            {
                "t": 3,
                "type": "bft_result",
                "contest_id": "contest-1",
                "round_id": 1,
                "cell": [1, 2],
                "assignments": [{"drone_id": "drone_1"}, {"drone_id": "drone_2"}],
            }
        )
        + "\n"
    )
    (tmp_path / "drone_1.json").write_text(
        json.dumps(
            {
                "events": [
                    {"t": 4, "type": "failure", "message": "drone_2 dropped off-mesh"},
                ]
            }
        )
    )

    run_local_peers._synthesize_proofs_from_outputs(tmp_path, proofs_path)

    events = [json.loads(line) for line in proofs_path.read_text().splitlines()]
    bft_result = next(event for event in events if event["type"] == "bft_result")
    auction = next(event for event in events if event["type"] == "auction")
    failure = next(event for event in events if event["type"] == "failure")

    assert bft_result["source"] == "runtime"
    assert auction["source"] == "derived"
    assert auction["derived_from"] == "bft_result"
    assert failure["source"] == "snapshot"
