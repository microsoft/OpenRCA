"""Security regressions; the model API is always mocked."""

import importlib
import json
import os
from pathlib import Path
import subprocess
import signal
import sys
import tempfile
import unittest
import time
from unittest import mock

from rca.baseline.rca_agent import sandbox

# Import the existing API router using a disposable, credential-free config.
with tempfile.TemporaryDirectory() as config_dir:
    config_path = Path(config_dir) / "config.json"
    config_path.write_text(json.dumps({"gemini3pro": {"api_key": "test-only"}}))
    with mock.patch.dict(os.environ, {"API_CONFIG_PATH": str(config_path)}):
        executor = importlib.import_module("rca.baseline.rca_agent.executor")
        controller = importlib.import_module("rca.baseline.rca_agent.controller")


class ExecutorTests(unittest.TestCase):
    def setUp(self):
        self.kernel = mock.create_autospec(sandbox.SandboxedKernel, instance=True)
        self.kernel.closed = False
        self.logger = mock.Mock()
        tokenizer = mock.Mock()
        tokenizer.encode.side_effect = lambda text: list(text)
        self.tokens = mock.patch.object(executor.tiktoken, "encoding_for_model", return_value=tokenizer)
        self.tokens.start()
        self.addCleanup(self.tokens.stop)

    def execute(self, responses):
        with mock.patch.object(executor, "get_chat_completion", side_effect=responses):
            return executor.execute_act("Analyze CSV", "schema", [], [], self.kernel, self.logger)

    def test_accepts_python_block_and_crlf(self):
        self.assertEqual(executor.extract_python(" \n```python\r\nx = 1\r\n```\n"), "x = 1")

    def test_rejects_bare_prose_multiple_blocks_and_ipython_escapes(self):
        for response in (
            "__import__('os').system('echo unsafe')",
            "Here is code:\n```python\n1\n```",
            "```python\n1\n```\nextra instructions",
            "```python\n1\n```\n```python\n2\n```",
            "```python\n!echo unsafe\n```",
            "```python\n%run /tmp/payload.py\n```",
            "```python\n\n```",
            "```python\n" + "x" * sandbox.MAX_CODE_BYTES + "\n```",
        ):
            with self.subTest(response=response[:80]), self.assertRaises((ValueError, SyntaxError)):
                executor.extract_python(response)

    def test_invalid_responses_never_reach_kernel_and_fail(self):
        result = self.execute(["__import__('os').system('echo unsafe')"] * 2)
        self.kernel.run_cell.assert_not_called()
        self.assertFalse(result[2])

    def test_rejects_in_process_kernel_before_model_request(self):
        with mock.patch.object(executor, "get_chat_completion") as api:
            with self.assertRaises(TypeError):
                executor.execute_act("q", "", [], [], mock.Mock(), self.logger)
            api.assert_not_called()

    def test_valid_fenced_code_goes_only_to_sandbox(self):
        self.kernel.run_cell.return_value = sandbox.ExecutionResult(True, "42")
        result = self.execute(["```python\nvalue = 42\nvalue\n```", "The value is 42"])
        self.kernel.run_cell.assert_called_once_with("value = 42\nvalue")
        self.assertTrue(result[2])
        self.assertIn("42", result[1])

    def test_retry_after_format_rejection(self):
        self.kernel.run_cell.return_value = sandbox.ExecutionResult(True, "2")
        result = self.execute(["1 + 1", "```python\n1 + 1\n```", "2"])
        self.kernel.run_cell.assert_called_once_with("1 + 1")
        self.assertTrue(result[2])

    def test_failed_cells_report_text_error_and_failure(self):
        self.kernel.run_cell.return_value = sandbox.ExecutionResult(False, error="read-only filesystem")
        result = self.execute(["```python\n1 / 0\n```"] * 2)
        self.assertFalse(result[2])

    def test_terminated_sandbox_is_not_retried(self):
        self.kernel.run_cell.side_effect = sandbox.SandboxTerminatedError("protocol failure")
        with mock.patch.object(executor, "get_chat_completion", return_value="```python\n1+1\n```") as api:
            with self.assertRaises(sandbox.SandboxTerminatedError):
                executor.execute_act("q", "", [], [], self.kernel, self.logger)
            self.assertEqual(api.call_count, 1)
            self.kernel.run_cell.assert_called_once()

    def test_closed_sandbox_rejected_before_model_request(self):
        self.kernel.closed = True
        with mock.patch.object(executor, "get_chat_completion") as api:
            with self.assertRaises(sandbox.SandboxTerminatedError):
                executor.execute_act("q", "", [], [], self.kernel, self.logger)
            api.assert_not_called()

    def test_python_error_can_still_be_corrected(self):
        self.kernel.run_cell.side_effect = [
            sandbox.ExecutionResult(False, error="ZeroDivisionError"),
            sandbox.ExecutionResult(True, "2"),
        ]
        result = self.execute(["```python\n1/0\n```", "```python\n1+1\n```", "2"])
        self.assertTrue(result[2])
        self.assertEqual(self.kernel.run_cell.call_count, 2)

    def test_controller_stops_after_fatal_sandbox_error(self):
        ap, bp = mock.Mock(rules="rules"), mock.Mock(schema="schema", cand="candidates")
        step = json.dumps({"analysis": "start", "instruction": "analyze", "completed": "False"})
        self.kernel.run_cell.side_effect = sandbox.SandboxTerminatedError("timed out")
        with mock.patch.object(controller, "get_chat_completion", return_value=step) as admin_api, \
                mock.patch.object(executor, "get_chat_completion", return_value="```python\n1+1\n```") as exec_api:
            result = controller._control_loop("q", "", ap, bp, self.logger, 25, 3, self.kernel)
        self.assertEqual(admin_api.call_count, 1)
        self.assertEqual(exec_api.call_count, 1)
        self.assertIn("terminated", result[0])
        self.assertEqual(result[1], [])

    def test_controller_with_closed_sandbox_makes_no_model_calls(self):
        self.kernel.closed = True
        ap, bp = mock.Mock(rules="rules"), mock.Mock(schema="schema", cand="candidates")
        with mock.patch.object(controller, "get_chat_completion") as admin_api:
            result = controller._control_loop("q", "", ap, bp, self.logger, 25, 3, self.kernel)
        admin_api.assert_not_called()
        self.assertIn("terminated", result[0])

    def test_external_deadline_propagates_through_executor_and_controller(self):
        self.kernel.run_cell.side_effect = TimeoutError("diagnosis deadline")
        ap, bp = mock.Mock(rules="rules"), mock.Mock(schema="schema", cand="candidates")
        step = json.dumps({"analysis": "start", "instruction": "analyze", "completed": "False"})
        with mock.patch.object(controller, "get_chat_completion", return_value=step), \
                mock.patch.object(executor, "get_chat_completion", return_value="```python\n1+1\n```") as api:
            with self.assertRaises(TimeoutError):
                controller._control_loop("q", "", ap, bp, self.logger, 25, 3, self.kernel)
            self.assertEqual(api.call_count, 1)

    def test_visualization_policy_handles_import_aliases(self):
        for code in ("import matplotlib as m", "from seaborn import heatmap", "import matplotlib.pyplot as plt"):
            with self.subTest(code=code), self.assertRaises(ValueError):
                executor.extract_python(f"```python\n{code}\n```")

    def test_control_loop_closes_sandbox_on_return_and_exception(self):
        for error in (None, TimeoutError("external deadline")):
            kernel = mock.MagicMock()
            with mock.patch.object(controller, "SandboxedKernel", return_value=kernel):
                with mock.patch.object(controller, "_control_loop", return_value="answer", side_effect=error):
                    if error:
                        with self.assertRaises(TimeoutError):
                            controller.control_loop("q", "", None, None, self.logger)
                    else:
                        self.assertEqual(controller.control_loop("q", "", None, None, self.logger), "answer")
            kernel.__exit__.assert_called_once()


class SandboxPolicyTests(unittest.TestCase):
    def test_missing_docker_fails_closed_without_starting_any_process(self):
        with mock.patch.object(sandbox.shutil, "which", return_value=None):
            with mock.patch.object(sandbox.subprocess, "Popen") as popen:
                with self.assertRaises(sandbox.SandboxError):
                    sandbox.SandboxedKernel()
                popen.assert_not_called()

    def test_daemon_or_image_failure_does_not_start_host_worker(self):
        with mock.patch.object(sandbox.shutil, "which", return_value="/usr/bin/docker"):
            with mock.patch.object(sandbox.subprocess, "run", side_effect=[
                subprocess.CalledProcessError(1, "docker"),
                subprocess.CompletedProcess([], 1, stderr=b"No such container"),
            ]):
                with mock.patch.object(sandbox.subprocess, "Popen") as popen:
                    with self.assertRaises(sandbox.SandboxError):
                        sandbox.SandboxedKernel()
                    popen.assert_not_called()

    def test_container_security_contract_and_minimal_mounts(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "Bank/telemetry").mkdir(parents=True)
            (root / "Bank/record.csv").write_text("secret groundtruth")
            (root / "config.json").write_text("secret key")
            created = subprocess.CompletedProcess([], 0, b"a" * 64 + b"\n", b"")
            with mock.patch.object(sandbox.shutil, "which", return_value="/usr/bin/docker"), \
                    mock.patch.object(sandbox.subprocess, "run", return_value=created) as run, \
                    mock.patch.object(sandbox.subprocess, "Popen") as popen, \
                    mock.patch.object(sandbox.os, "set_blocking"), \
                    mock.patch.object(sandbox.SandboxedKernel, "_read_reply", return_value={"ready": True}):
                popen.return_value.poll.return_value = 0
                with sandbox.SandboxedKernel(root):
                    pass
                command = run.call_args_list[0].args[0]
                for option, value in (
                    ("--network", "none"), ("--user", "65534:65534"),
                    ("--cap-drop", "ALL"), ("--security-opt", "no-new-privileges=true"),
                    ("--pids-limit", "64"), ("--memory", "8g"), ("--memory-swap", "8g"),
                    ("--cpus", "2"), ("--pull", "never"), ("--log-driver", "none"),
                ):
                    self.assertEqual(command[command.index(option) + 1], value)
                self.assertIn("--read-only", command)
                mounts = [command[i + 1] for i, value in enumerate(command) if value == "--mount"]
                self.assertEqual(len(mounts), 1)
                self.assertIn("target=/workspace/dataset/Bank/telemetry,readonly", mounts[0])
                self.assertIn("bind-recursive=disabled", mounts[0])
                self.assertNotIn("record.csv", " ".join(command))
                self.assertNotIn("config.json", " ".join(command))
                self.assertNotIn("docker.sock", " ".join(command))
                self.assertNotIn("--privileged", command)
                self.assertEqual(run.call_args_list[-1].args[0], ["/usr/bin/docker", "rm", "--force", "a" * 64])
                self.assertEqual(run.call_args_list[1].args[0], ["/usr/bin/docker", "pause", "a" * 64])

    def test_startup_timeout_removes_created_container(self):
        created = subprocess.CompletedProcess([], 0, b"a" * 64 + b"\n", b"")
        with mock.patch.object(sandbox.shutil, "which", return_value="/usr/bin/docker"), \
                mock.patch.object(sandbox.subprocess, "run", return_value=created) as run, \
                mock.patch.object(sandbox.subprocess, "Popen") as popen, \
                mock.patch.object(sandbox.os, "set_blocking"), \
                mock.patch.object(sandbox.SandboxedKernel, "_read_reply", side_effect=sandbox.SandboxError("timed out")):
            popen.return_value.poll.return_value = None
            with self.assertRaises(sandbox.SandboxError):
                sandbox.SandboxedKernel()
            self.assertEqual(run.call_args_list[-1].args[0], ["/usr/bin/docker", "rm", "--force", "a" * 64])
            popen.return_value.kill.assert_called_once()

    def test_cleanup_failure_is_reported(self):
        kernel = sandbox.SandboxedKernel.__new__(sandbox.SandboxedKernel)
        kernel._closed, kernel._process = False, None
        kernel._docker, kernel._container = "docker", "a" * 64
        with mock.patch.object(sandbox.subprocess, "run", return_value=subprocess.CompletedProcess([], 1, stderr=b"daemon unavailable")):
            with self.assertWarns(RuntimeWarning):
                kernel.close()

    def test_telemetry_symlink_cannot_mount_host_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "dataset"
            (root / "Bank").mkdir(parents=True)
            (root / "Bank/telemetry").symlink_to(Path(directory), target_is_directory=True)
            with mock.patch.object(sandbox.shutil, "which", return_value="docker"):
                with mock.patch.object(sandbox.subprocess, "run") as run:
                    with self.assertRaises(sandbox.SandboxError):
                        sandbox.SandboxedKernel(root)
                    run.assert_not_called()


class SandboxTransportTests(unittest.TestCase):
    def helper(self, source, timeout=1):
        # Trusted synthetic transport peer, never LLM-generated code. No Docker
        # means these tests exercise IPC failure handling, not OS isolation.
        kernel = sandbox.SandboxedKernel.__new__(sandbox.SandboxedKernel)
        kernel.timeout = timeout
        kernel._closed = False
        kernel._paused = False
        kernel._container = None
        kernel._docker = None
        kernel._buffer = bytearray()
        kernel._process = subprocess.Popen(
            [sys.executable, "-I", "-u", "-c", source], stdin=subprocess.PIPE,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, bufsize=0,
        )
        os.set_blocking(kernel._process.stdin.fileno(), False)
        os.set_blocking(kernel._process.stdout.fileno(), False)
        # Mock the Docker freezer for generic IPC tests. The forged-reply test
        # below uses a real OS stop to verify that execution cannot continue.
        kernel._set_paused = mock.Mock(side_effect=lambda paused, deadline: setattr(kernel, "_paused", paused))
        self.addCleanup(kernel.close)
        return kernel

    def test_only_plain_json_text_is_accepted(self):
        kernel = self.helper('import json, sys; sys.stdin.readline(); print(json.dumps({"success": True, "result": "42", "error": ""}))')
        self.assertEqual(kernel.run_cell("1 + 1"), sandbox.ExecutionResult(True, "42"))
        self.assertTrue(kernel._paused)

    def test_malformed_reply_and_python_object_are_rejected(self):
        for reply in ("not JSON", '{"success": true, "result": {"pickle": "payload"}, "error": ""}'):
            kernel = self.helper(f"import sys; sys.stdin.readline(); print({reply!r})")
            with self.assertRaises(sandbox.SandboxTerminatedError):
                kernel.run_cell("1")
            self.assertTrue(kernel._closed)
            with self.assertRaises(sandbox.SandboxTerminatedError):
                kernel.run_cell("1")

    def test_oversized_output_closes_peer(self):
        kernel = self.helper(f'import sys; sys.stdin.readline(); sys.stdout.write("x" * {sandbox.MAX_REPLY_BYTES + 1}); sys.stdout.flush()')
        with self.assertRaisesRegex(sandbox.SandboxTerminatedError, "output limit"):
            kernel.run_cell("1")
        self.assertIsNotNone(kernel._process.poll())

    def test_hung_cell_closes_peer(self):
        kernel = self.helper("while True: pass", timeout=0.1)
        with self.assertRaisesRegex(sandbox.SandboxTerminatedError, "timed out"):
            kernel.run_cell("1")
        self.assertIsNotNone(kernel._process.poll())

    def test_peer_exit_is_failure(self):
        kernel = self.helper("pass")
        with self.assertRaises(sandbox.SandboxTerminatedError):
            kernel.run_cell("1")
        self.assertTrue(kernel._closed)

    def test_forged_success_cannot_leave_peer_running_between_cells(self):
        kernel = self.helper(
            'import json, sys, time\nsys.stdin.readline()\n'
            'print(json.dumps({"success": True, "result": "forged", "error": ""}), flush=True)\n'
            'while True: time.sleep(0.01)\n', timeout=0.2,
        )
        stopped = []

        def freeze_peer(paused, deadline):
            if paused:
                os.kill(kernel._process.pid, signal.SIGSTOP)
                pid, status = os.waitpid(kernel._process.pid, os.WUNTRACED)
                stopped.append(pid == kernel._process.pid and os.WIFSTOPPED(status))
            elif kernel._paused:
                os.kill(kernel._process.pid, signal.SIGCONT)
            kernel._paused = paused

        kernel._set_paused = mock.Mock(side_effect=freeze_peer)
        self.assertTrue(kernel.run_cell("trusted transport fixture").success)
        self.assertEqual(stopped, [True])
        self.assertTrue(kernel._paused)
        time.sleep(0.25)  # Still frozen after the original active deadline.
        # Resuming the old unfinished cell does not produce another reply.
        with self.assertRaisesRegex(sandbox.SandboxTerminatedError, "timed out"):
            kernel.run_cell("next trusted fixture")
        self.assertTrue(kernel.closed)
        self.assertIsNotNone(kernel._process.poll())

    def test_freezer_failure_is_fatal_even_after_valid_json(self):
        kernel = self.helper('import json, sys; sys.stdin.readline(); print(json.dumps({"success": True, "result": "42", "error": ""}))')
        def pause_failure(paused, deadline):
            if paused:
                raise subprocess.CalledProcessError(1, "docker pause")
        kernel._set_paused.side_effect = pause_failure
        with self.assertRaises(sandbox.SandboxTerminatedError):
            kernel.run_cell("1")
        self.assertTrue(kernel.closed)

    def test_external_deadline_closes_peer_and_propagates(self):
        kernel = self.helper("while True: pass")
        kernel._write_request = mock.Mock(side_effect=TimeoutError("external deadline"))
        with self.assertRaises(TimeoutError):
            kernel.run_cell("1")
        self.assertTrue(kernel.closed)
        self.assertIsNotNone(kernel._process.poll())

    def test_real_freezer_commands_share_the_cell_deadline(self):
        kernel = self.helper('import json, sys; sys.stdin.readline(); print(json.dumps({"success": True, "result": "42", "error": ""}))')
        kernel._paused = True
        kernel._docker, kernel._container = "docker", "test-container"
        kernel._set_paused = sandbox.SandboxedKernel._set_paused.__get__(kernel)
        try:
            with mock.patch.object(sandbox.subprocess, "run", return_value=subprocess.CompletedProcess([], 0)) as run:
                self.assertTrue(kernel.run_cell("1").success)
            self.assertEqual([call.args[0] for call in run.call_args_list], [
                ["docker", "unpause", "test-container"],
                ["docker", "pause", "test-container"],
            ])
            for call in run.call_args_list:
                self.assertGreater(call.kwargs["timeout"], 0)
                self.assertLessEqual(call.kwargs["timeout"], kernel.timeout)
        finally:
            kernel._container = None


@unittest.skipUnless(os.environ.get("OPENRCA_SANDBOX_INTEGRATION") == "1", "Opt-in Docker integration test")
class DockerIsolationTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        root = Path(self.directory.name) / "dataset"
        telemetry = root / "Bank/telemetry"
        telemetry.mkdir(parents=True)
        self.csv = telemetry / "metric.csv"
        self.csv.write_text("value\n2\n4\n")
        (root / "Bank/record.csv").write_text("groundtruth")
        self.secret = Path(self.directory.name) / "host-secret"
        self.secret.write_text("test-secret")
        with mock.patch.dict(os.environ, {"OPENRCA_TEST_SECRET": "host-only"}):
            self.kernel = sandbox.SandboxedKernel(root, timeout=3, memory="1g")
        self.addCleanup(self.kernel.close)

    def cell(self, code):
        result = self.kernel.run_cell(code)
        self.assertTrue(result.success, result.error)
        return result.result

    def test_pandas_and_state_persist_across_steps(self):
        self.assertEqual(self.cell("df = pd.read_csv('dataset/Bank/telemetry/metric.csv')\nint(df.value.sum())"), "6")
        self.assertEqual(self.cell("int(df.value.mean())"), "3")

    def test_host_files_credentials_and_groundtruth_are_inaccessible(self):
        self.assertEqual(self.cell(
            "import os\nfrom pathlib import Path\n"
            f"(Path({str(self.secret)!r}).exists(), "
            "Path('dataset/Bank/record.csv').exists(), "
            "Path('/var/run/docker.sock').exists(), 'OPENRCA_TEST_SECRET' in os.environ)"
        ), "(False, False, False, False)")

    def test_write_and_delete_telemetry_fail(self):
        for code in (
            "open('dataset/Bank/telemetry/metric.csv', 'w').write('corrupted')",
            "import os as bypass\nbypass.remove('dataset/Bank/telemetry/metric.csv')",
        ):
            with self.subTest(code=code):
                self.assertFalse(self.kernel.run_cell(code).success)
                self.assertEqual(self.csv.read_text(), "value\n2\n4\n")

    def test_subprocess_cannot_access_host_secret(self):
        result = self.cell(
            "import subprocess as s\n"
            f"s.run(['cat', {str(self.secret)!r}], capture_output=True).returncode"
        )
        self.assertNotEqual(result, "0")
        self.assertEqual(self.secret.read_text(), "test-secret")

    def test_network_is_blocked(self):
        result = self.kernel.run_cell("import socket\nsocket.create_connection(('1.1.1.1', 443), timeout=1)")
        self.assertFalse(result.success)

    def test_infinite_loop_destroys_container(self):
        container = self.kernel._container
        with self.assertRaises(sandbox.SandboxTerminatedError):
            self.kernel.run_cell("while True: pass")
        self.assertTrue(self.kernel._closed)
        inspected = subprocess.run([self.kernel._docker, "inspect", container], capture_output=True)
        self.assertNotEqual(inspected.returncode, 0)

    def test_raw_output_flood_destroys_container(self):
        with self.assertRaises(sandbox.SandboxTerminatedError):
            self.kernel.run_cell("import os\nos.write(1, b'x' * (2 * 1024 * 1024))")
        self.assertTrue(self.kernel._closed)

    def test_container_is_frozen_during_model_calls(self):
        self.cell("value = 42\nvalue")
        paused = subprocess.check_output([
            self.kernel._docker, "inspect", "--format", "{{.State.Paused}}", self.kernel._container,
        ], text=True).strip()
        self.assertEqual(paused, "true")
        self.assertEqual(self.cell("value + 1"), "43")

    def test_forged_json_and_infinite_loop_are_frozen_then_terminated(self):
        payload = (
            "import os, json\n"
            "os.write(1, (json.dumps({'success': True, 'result': 'forged', 'error': ''}) + '\\n').encode())\n"
            "while True: pass"
        )
        self.assertTrue(self.kernel.run_cell(payload).success)
        paused = subprocess.check_output([
            self.kernel._docker, "inspect", "--format", "{{.State.Paused}}", self.kernel._container,
        ], text=True).strip()
        self.assertEqual(paused, "true")
        with self.assertRaises(sandbox.SandboxTerminatedError):
            self.kernel.run_cell("1+1")
        inspected = subprocess.run([self.kernel._docker, "inspect", self.kernel._container], capture_output=True)
        self.assertNotEqual(inspected.returncode, 0)


if __name__ == "__main__":
    unittest.main()
