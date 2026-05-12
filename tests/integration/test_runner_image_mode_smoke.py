from __future__ import annotations

from pathlib import Path

from testo_core.command_builders import BuiltCommand
from testo_core.runners import _run_in_ephemeral_container_streaming


def test_runner_image_prebuilt_mode_skips_runtime_pip_install(monkeypatch, tmp_path: Path) -> None:  # noqa: ANN001
    class _FakeContainer:
        status = "exited"

        def logs(self, stream=True, follow=True):  # noqa: ANN001, FBT002
            del stream, follow
            if False:  # pragma: no cover - preserve generator shape
                yield b""
            return iter(())

        def reload(self) -> None:
            self.status = "exited"

        def wait(self):  # noqa: ANN201
            return {"StatusCode": 0}

        def remove(self, force=False):  # noqa: ANN001, FBT002
            del force

    class _FakeContainers:
        def __init__(self) -> None:
            self.last_call: dict[str, object] | None = None

        def run(self, image, **kwargs):  # noqa: ANN001, ANN201
            self.last_call = {"image": image, **kwargs}
            return _FakeContainer()

    fake_containers = _FakeContainers()
    fake_client = type("FakeDockerClient", (), {"containers": fake_containers})()
    monkeypatch.setattr("testo_core.runners._docker_client", lambda: fake_client)

    emitted: list[tuple[str, str]] = []
    cmd = BuiltCommand(
        argv=["pytest", "-q"],
        cwd=tmp_path,
        env={
            "UQO_RUNNER_IMAGE": "docker.io/acme/uqo-runner:v1",
            "UQO_RUNNER_PREBUILT": "true",
        },
    )
    rc, _started_at, _finished_at = _run_in_ephemeral_container_streaming(
        run_id="smoke-prebuilt",
        cmd=cmd,
        cfg_timeout_s=10.0,
        cfg_heartbeat_s=0.0,
        emit=lambda stream, line: emitted.append((stream, line)),
        log_path=tmp_path / "logs" / "runner-image.log",
    )

    assert rc == 0
    assert fake_containers.last_call is not None
    assert fake_containers.last_call["image"] == "docker.io/acme/uqo-runner:v1"
    shell_cmd = fake_containers.last_call["command"][2]
    assert "pip install --no-cache-dir -r" not in shell_cmd
    assert any("prebuilt=true" in line for stream, line in emitted if stream == "meta")
