"""Execute untrusted model code in a disposable, stateful Docker container.

The container boundary is the security control. Python import/AST filters are
not a sandbox. No model code or serialized Python objects are loaded by the host.
"""

from dataclasses import dataclass
import json
import math
import os
from pathlib import Path
import selectors
import shutil
import subprocess
import time
import uuid
import warnings


DEFAULT_IMAGE = "openrca-executor:local"
MAX_CODE_BYTES = 64 * 1024
MAX_REPLY_BYTES = 1024 * 1024
TELEMETRY_PATHS = (
    "Bank/telemetry",
    "Telecom/telemetry",
    "Market/cloudbed-1/telemetry",
    "Market/cloudbed-2/telemetry",
)


class SandboxError(RuntimeError):
    pass


class SandboxTerminatedError(SandboxError):
    """Fatal infrastructure failure: the current diagnosis cannot be retried."""


@dataclass(frozen=True)
class ExecutionResult:
    success: bool
    result: str = ""
    error: str = ""


class SandboxedKernel:
    """One container per control loop; variables persist between cells.

    Only the known telemetry directories are exposed. In particular the API
    config, source tree, home directory, query/record CSVs and Docker socket are
    never mounted. An unavailable or broken sandbox always fails closed.
    """

    def __init__(self, dataset_root=None, *, image=None, timeout=60, memory="8g"):
        if not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("Sandbox timeout must be finite and positive")
        self.timeout = timeout
        self._process = None
        self._container = None
        self._buffer = bytearray()
        self._closed = False
        self._paused = False
        self._docker = shutil.which("docker")
        if self._docker is None:
            raise SandboxError(
                "Docker is required for RCA-agent code execution. Build the "
                "sandbox image as documented in README.md; host execution is disabled."
            )
        dataset_root = Path(dataset_root or Path(__file__).resolve().parents[3] / "dataset").resolve()
        image = image or os.environ.get("OPENRCA_SANDBOX_IMAGE", DEFAULT_IMAGE)
        if not image or image.startswith("-"):
            raise SandboxError("Invalid sandbox image")
        name = "openrca-executor-" + uuid.uuid4().hex
        command = [
            self._docker, "create", "--name", name, "--rm", "--interactive",
            "--pull", "never", "--network", "none", "--read-only",
            "--user", "65534:65534", "--cap-drop", "ALL",
            "--security-opt", "no-new-privileges=true", "--pids-limit", "64",
            "--cpus", "2", "--memory", memory, "--memory-swap", memory,
            "--ulimit", "nofile=256:256", "--shm-size", "16m",
            "--log-driver", "none", "--no-healthcheck", "--init",
            "--tmpfs", "/tmp:rw,noexec,nosuid,nodev,size=64m,mode=1777",
            "--workdir", "/workspace", "--env", "HOME=/tmp",
            "--env", "IPYTHONDIR=/tmp/ipython", "--env", "MPLCONFIGDIR=/tmp/matplotlib",
            "--env", "OPENBLAS_NUM_THREADS=1", "--env", "OMP_NUM_THREADS=1",
            "--entrypoint", "python",
        ]
        for relative in TELEMETRY_PATHS:
            source = dataset_root / relative
            if not source.exists():
                continue
            source = source.resolve()
            if not source.is_dir() or not source.is_relative_to(dataset_root):
                raise SandboxError("Telemetry directory must remain inside the dataset root")
            if any(char in str(source) for char in (",", "\n", "\r")):
                raise SandboxError("Unsupported character in telemetry directory path")
            command.extend([
                "--mount",
                f"type=bind,source={source},target=/workspace/dataset/{relative},"
                "readonly,bind-propagation=rprivate,bind-recursive=disabled",
            ])
        command.extend([image, "-I", "-u", "/opt/openrca/worker.py"])
        self._container = name
        try:
            created = subprocess.run(
                command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                timeout=30, check=True,
            )
            container_id = created.stdout.decode("ascii").strip()
            if len(container_id) != 64 or any(c not in "0123456789abcdef" for c in container_id):
                raise SandboxError("Docker returned an invalid container ID")
            self._container = container_id
            self._process = subprocess.Popen(
                [self._docker, "start", "--attach", "--interactive", container_id],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT, bufsize=0,
            )
            os.set_blocking(self._process.stdin.fileno(), False)
            os.set_blocking(self._process.stdout.fileno(), False)
            deadline = time.monotonic() + 30
            if self._read_reply(deadline) != {"ready": True}:
                raise SandboxError("Invalid sandbox startup response")
            self._set_paused(True, deadline)
        except (OSError, subprocess.SubprocessError) as error:
            self.close()
            raise SandboxError(
                "Unable to start the Docker sandbox. Ensure Docker is running and "
                "the sandbox image has been built; host execution is disabled."
            ) from error
        except BaseException:
            self.close()
            raise

    def _read_reply(self, deadline):
        with selectors.DefaultSelector() as selector:
            selector.register(self._process.stdout, selectors.EVENT_READ)
            while True:
                if b"\n" in self._buffer:
                    line, _, rest = self._buffer.partition(b"\n")
                    self._buffer = bytearray(rest)
                    if len(line) > MAX_REPLY_BYTES:
                        raise SandboxError("Sandbox output limit exceeded")
                    try:
                        return json.loads(line)
                    except (ValueError, UnicodeError, RecursionError) as error:
                        raise SandboxError("Invalid sandbox response") from error
                remaining = deadline - time.monotonic()
                if remaining <= 0 or not selector.select(remaining):
                    raise SandboxError("Sandbox execution timed out")
                chunk = os.read(self._process.stdout.fileno(), 65536)
                if not chunk:
                    raise SandboxError("Sandbox exited without a response")
                self._buffer.extend(chunk)
                if len(self._buffer) > MAX_REPLY_BYTES:
                    raise SandboxError("Sandbox output limit exceeded")

    def _write_request(self, payload, deadline):
        with selectors.DefaultSelector() as selector:
            selector.register(self._process.stdin, selectors.EVENT_WRITE)
            pending = memoryview(payload)
            while pending:
                remaining = deadline - time.monotonic()
                if remaining <= 0 or not selector.select(remaining):
                    raise SandboxError("Sandbox execution timed out")
                written = os.write(self._process.stdin.fileno(), pending)
                pending = pending[written:]

    @property
    def closed(self):
        return self._closed

    def _set_paused(self, paused, deadline):
        if self._paused == paused:
            return
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise SandboxError("Sandbox execution timed out")
        # A JSON reply is untrusted output, not proof that code stopped running.
        # Docker's freezer suspends ALL container processes, including children.
        # The model has no Docker socket and cannot resume this container.
        subprocess.run(
            [self._docker, "pause" if paused else "unpause", self._container],
            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
            timeout=remaining, check=True,
        )
        if time.monotonic() >= deadline:
            raise SandboxError("Sandbox execution timed out")
        self._paused = paused

    def run_cell(self, code):
        if self._closed:
            raise SandboxTerminatedError("Sandbox is closed; host execution is disabled")
        if not isinstance(code, str) or len(code.encode("utf-8")) > MAX_CODE_BYTES:
            return ExecutionResult(False, error="Invalid or oversized Python cell")
        deadline = time.monotonic() + self.timeout
        try:
            self._set_paused(False, deadline)
            self._write_request((json.dumps({"code": code}) + "\n").encode("utf-8"), deadline)
            reply = self._read_reply(deadline)
            if (not isinstance(reply, dict) or set(reply) != {"success", "result", "error"}
                    or type(reply["success"]) is not bool
                    or not isinstance(reply["result"], str)
                    or not isinstance(reply["error"], str)):
                raise SandboxError("Invalid sandbox execution response")
            # Do not release execution supervision just because fd 1 contains
            # a valid JSON message. Even a forged reply must leave the entire
            # sandbox frozen before control returns to model/API calls.
            self._set_paused(True, deadline)
            return ExecutionResult(**reply)
        except TimeoutError:
            # Preserve an external diagnosis deadline instead of retrying it.
            self.close()
            raise
        except Exception as error:
            self.close()
            raise SandboxTerminatedError(f"Sandbox execution terminated: {error}") from error
        except BaseException:
            self.close()
            raise

    def close(self):
        if self._closed:
            return
        self._closed = True
        try:
            if self._container:
                # Killing only the CLI would leave the untrusted cell running.
                removed = subprocess.run(
                    [self._docker, "rm", "--force", self._container],
                    stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                    timeout=10, check=False,
                )
                # --rm may already have removed a worker that exited itself.
                if removed.returncode and b"No such container" not in removed.stderr:
                    warnings.warn(
                        f"Could not remove sandbox container {self._container}; check Docker connectivity",
                        RuntimeWarning,
                    )
        except (OSError, subprocess.SubprocessError):
            warnings.warn(
                f"Could not remove sandbox container {self._container}; check Docker connectivity",
                RuntimeWarning,
            )
        finally:
            if self._process:
                if self._process.poll() is None:
                    self._process.kill()
                self._process.wait(timeout=5)
                self._process.stdin.close()
                self._process.stdout.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
