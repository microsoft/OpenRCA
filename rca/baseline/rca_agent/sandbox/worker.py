"""Container-only JSON worker. Never import or run this on the application host."""

from contextlib import redirect_stderr, redirect_stdout
import io
import json
import sys
import traceback

from IPython.core.interactiveshell import InteractiveShell
import pandas as pd


MAX_OUTPUT_CHARS = 64 * 1024


class LimitedOutput(io.StringIO):
    def write(self, value):
        if self.tell() + len(value) > MAX_OUTPUT_CHARS:
            raise RuntimeError("Cell output limit exceeded")
        return super().write(value)


def main():
    protocol_in, protocol_out = sys.stdin, sys.stdout
    shell = InteractiveShell()
    shell.user_ns["pd"] = pd
    pd.set_option("display.width", 427)
    pd.set_option("display.max_columns", 10)
    pd.set_option("display.max_rows", 10)
    protocol_out.write(json.dumps({"ready": True}) + "\n")
    protocol_out.flush()
    for line in protocol_in:
        try:
            code = json.loads(line)["code"]
            output = LimitedOutput()
            with redirect_stdout(output), redirect_stderr(output):
                execution = shell.run_cell(code, store_history=False)
                error = execution.error_before_exec or execution.error_in_exec
                result = str(execution.result) if execution.result is not None else ""
            if error is not None:
                reply = {"success": False, "result": "", "error": "".join(
                    traceback.format_exception(type(error), error, error.__traceback__)
                )[:MAX_OUTPUT_CHARS]}
            else:
                # Include print output for cells without a final expression.
                reply = {"success": True, "result": (result or output.getvalue())[:MAX_OUTPUT_CHARS], "error": ""}
        except BaseException as error:
            reply = {"success": False, "result": "", "error": str(error)[:MAX_OUTPUT_CHARS]}
        protocol_out.write(json.dumps(reply) + "\n")
        protocol_out.flush()


if __name__ == "__main__":
    main()
