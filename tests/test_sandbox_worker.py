"""Worker protocol tests using only fixed, trusted fixtures on the test host.

These tests do not assert OS isolation. Untrusted payloads belong exclusively
in the opt-in Docker integration suite.
"""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


class WorkerProtocolTests(unittest.TestCase):
    def test_trusted_cells_state_output_and_errors(self):
        worker = Path(__file__).resolve().parents[1] / "rca/baseline/rca_agent/sandbox/worker.py"
        cells = [
            "x = 40\nx + 2",
            "x + 3",
            "df = pd.DataFrame({'value': [2, 4]})\nint(df.value.sum())",
            "print('trusted output')",
            "1 / 0",
            "if",  # Exercises error_before_exec, not just error_in_exec.
        ]
        payload = "".join(json.dumps({"code": code}) + "\n" for code in cells)
        with tempfile.TemporaryDirectory() as directory:
            env = {
                "PATH": os.environ.get("PATH", ""), "HOME": directory,
                "IPYTHONDIR": directory, "OPENBLAS_NUM_THREADS": "1",
            }
            process = subprocess.run(
                [sys.executable, "-I", "-u", str(worker)], input=payload,
                text=True, capture_output=True, env=env, timeout=30, check=True,
            )
        replies = [json.loads(line) for line in process.stdout.splitlines()]
        self.assertEqual(replies[0], {"ready": True})
        self.assertEqual([reply["result"] for reply in replies[1:5]], ["42", "43", "6", "trusted output\n"])
        self.assertTrue(all(reply["success"] for reply in replies[1:5]))
        self.assertFalse(replies[5]["success"])
        self.assertIn("ZeroDivisionError", replies[5]["error"])
        self.assertFalse(replies[6]["success"])
        self.assertIn("SyntaxError", replies[6]["error"])


if __name__ == "__main__":
    unittest.main()
