import re
import ast
import time
from datetime import datetime
from rca.api_router import get_chat_completion
import tiktoken
from rca.baseline.rca_agent.sandbox import MAX_CODE_BYTES, SandboxedKernel, SandboxTerminatedError

system = """You are a DevOps assistant for writing Python code to answer DevOps questions. For each question, you need to write Python code to solve it by retrieving and processing telemetry data of the target system. Your generated Python code will be automatically submitted to a IPython Kernel. The execution result output in IPython Kernel will be used as the answer to the question.

{rule}

There is some domain knowledge for you:

{background}

Your response should follow the Python block format below:

{format}"""

format = """```python
(YOUR CODE HERE)
```"""

summary = """The code execution is successful. The execution result is shown below: 

{result}

Please summarize a straightforward answer to the question based on the execution results. Use plain English."""

conclusion = """{answer}

The original code execution output of IPython Kernel is also provided below for reference:

{result}"""

rule = """## RULES OF PYTHON CODE WRITING:

1. Reuse variables as much as possible for execution efficiency since the IPython Kernel is stateful, i.e., variables define in previous steps can be used in subsequent steps. 
2. Use variable name rather than `print()` to display the execution results since your Python environment is IPython Kernel rather than Python.exe. If you want to display multiple variables, use commas to separate them, e.g. `var1, var2`.
3. Use pandas Dataframe to process and display tabular data for efficiency and briefness. Avoid transforming Dataframe to list or dict type for display.
4. If you encounter an error or unexpected result, rewrite the code by referring to the given IPython Kernel error message.
5. Do not simulate any virtual situation or assume anything unknown. Solve the real problem.
6. Do not store any data as files in the disk. Only cache the data as variables in the memory.
7. Do not visualize the data or draw pictures or graphs via Python. You can only provide text-based results. Never include the `matplotlib` or `seaborn` library in the code.
8. Do not generate anything else except the Python code block except the instruction tell you to 'Use plain English'. If you find the input instruction is a summarization task (which is typically happening in the last step), you should comprehensively summarize the conclusion as a string in your code and display it directly.
9. Do not calculate threshold AFTER filtering data within the given time duration. Always calculate global thresholds using the entire KPI series of a specific component within a metric file BEFORE filtering data within the given time duration.
10. All issues use **UTC+8** time. However, the local machine's default timezone is unknown. Please use `pytz.timezone('Asia/Shanghai')` to explicityly set the timezone to UTC+8.
"""

def extract_python(response: str) -> str:
    """Accept one complete Python fence, never arbitrary prose or IPython syntax.

    This is input validation, not a security sandbox; valid Python still needs
    the isolated container even when it looks like ordinary pandas code.
    """
    if not isinstance(response, str) or len(response.encode("utf-8")) > MAX_CODE_BYTES:
        raise ValueError("Expected a Python code block within the size limit")
    match = re.fullmatch(r"\s*```python[ \t]*\r?\n(.*?)\r?\n```\s*", response, re.DOTALL)
    if match is None or not match.group(1).strip():
        raise ValueError("Expected exactly one fenced Python code block")
    code = match.group(1).strip()
    tree = ast.parse(code)
    for node in ast.walk(tree):
        modules = []
        if isinstance(node, ast.Import):
            modules = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            modules = [node.module or ""]
        if any(module.split(".")[0] in {"matplotlib", "seaborn"} for module in modules):
            raise ValueError("Provide text-based results instead of visualizations")
    return code


def execute_act(instruction:str, background:str, history, attempt, kernel: SandboxedKernel, logger) -> str:

    if not isinstance(kernel, SandboxedKernel):
        raise TypeError("Executor requires a SandboxedKernel; host execution is disabled")
    if kernel.closed:
        raise SandboxTerminatedError("Sandbox is closed; current diagnosis must stop")

    logger.debug("Start execution")
    t1 = datetime.now()
    if history == []:
        history = [
                {'role': 'system', 'content': system.format(rule=rule, background=background, format=format)},
            ]
    code = ""
    result = ""
    retry_flag = False
    status = False
    history.extend([{'role': 'user', 'content': instruction}])
    prompt = history.copy()
    note = [{'role': 'user', 'content': f"Continue your code writing process following the rules:\n\n{rule}\n\nResponse format:\n\n{format}"}]
    tokenizer = tiktoken.encoding_for_model("gpt-4")
    for i in range(2):
        try:
            if not retry_flag:
                response = get_chat_completion(
                    messages=prompt + note,
                )
            else:
                response = get_chat_completion(
                    messages=prompt,
                )
                retry_flag = False
            try:
                code = extract_python(response)
            except (ValueError, SyntaxError) as error:
                logger.warning(f"Invalid executor code: {error}")
                prompt.append({'role': 'assistant', 'content': response})
                prompt.append({'role': 'user', 'content': f"{error}. Please return one valid Python code block."})
                retry_flag = True
                continue
            logger.debug(f"Raw Code:\n{code}")
            exec = kernel.run_cell(code)
            status = exec.success
            if status:
                result = str(exec.result).strip()
                tokens_len = len(tokenizer.encode(result))
                if tokens_len > 16384:
                    logger.warning(f"Token length exceeds the limit: {tokens_len}")
                    continue
                t2 = datetime.now()
                row_pattern = r"\[(\d+)\s+rows\s+x\s+\d+\s+columns\]"
                match = re.search(row_pattern, result)
                if match:
                    rows = int(match.group(1))
                    if rows > 10:
                        result += f"\n\n**Note**: The printed pandas DataFrame is truncated due to its size. Only **10 rows** are displayed, which may introduce observation bias due to the incomplete table. If you want to comprehensively understand the details without bias, please ask Executor using `df.head(X)` to display more rows."
                logger.debug(f"Execution Result:\n{result}")
                logger.debug(f"Execution finished. Time cost: {t2-t1}")
                history.extend([
                    {'role': 'assistant', 'content': code},
                    {'role': 'user', 'content': summary.format(result=result)},
                ])
                answer = get_chat_completion(
                    messages=history,
                )
                logger.debug(f"Brief Answer:\n{answer}")
                history.extend([
                    {'role': 'assistant', 'content': answer},
                ])
                result = conclusion.format(answer=answer, result=result)
                
                return code, result, status, history
            else:
                result = exec.error
                t2 = datetime.now()
                logger.warning(f"Execution failed. Error message: {result}")
                logger.debug(f"Execution finished. Time cost: {t2-t1}")
                prompt.append({'role': 'assistant', 'content': code})
                prompt.append({'role': 'user', 'content': f"Execution failed:\n{result}\nPlease revise your code and retry."})
                retry_flag = True
            
        except (SandboxTerminatedError, TimeoutError):
            raise
        except Exception as e:
            logger.error(e)
            time.sleep(1)
    
    t2 = datetime.now()
    logger.error(f"Max try reached. Please check the history. Time cost: {t2-t1}")
    err = "The Executor failed to complete the instruction, please re-write a new instruction for Executor."
    history.extend([{'role': 'assistant', 'content': err}])
    return err, err, False, history
