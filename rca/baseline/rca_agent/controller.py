import json
import re
from IPython.terminal.embed import InteractiveShellEmbed

from rca.baseline.rca_agent.executor import execute_act

from rca.api_router import get_chat_completion

system = """You are the Administrator of a DevOps Assistant system for failure diagnosis. To solve each given issue, you should iteratively instruct an Executor to write and execute Python code for data analysis on telemetry files of target system. By analyzing the execution results, you should approximate the answer step-by-step.

There is some domain knowledge for you:

{background}

{agent}

The issue you are going to solve is:

{objective}

Solve the issue step-by-step. In each step, your response should follow the JSON format below:

{format}

Let's begin."""

format = """{
    "analysis": (Your analysis of the code execution result from Executor in the last step, with detailed reasoning of 'what have been done' and 'what can be derived'. Respond 'None' if it is the first step.),
    "completed": ("True" if you believe the issue is resolved, and an answer can be derived in the 'instruction' field. Otherwise "False"),
    "instruction": (Your instruction for the Executor to perform via code execution in the next step. Do not involve complex multi-step instruction. Keep your instruction atomic, with clear request of 'what to do' and 'how to do'. Respond a summary by yourself if you believe the issue is resolved. Respond a summary by yourself if you believe the issue is resolved. Respond a summary by yourself if you believe the issue is resolved.)
}
(DO NOT contain "```json" and "```" tags. DO contain the JSON object with the brackets "{}" only. Use '\\n' instead of an actual newline character to ensure JSON compatibility when you want to insert a line break within a string.)"""

summary = """Now, you have decided to finish your reasoning process. You should now provide the final answer to the issue. The candidates of possible root cause components and reasons are provided to you. The root cause components and reasons must be selected from the provided candidates.

{cand}

Recall the issue is: {objective}

Please first review your previous reasoning process to infer an exact answer of the issue. Then, summarize your final answer of the root causes using the following JSON format at the end of your response:

```json
{{
    "1": {{
        "root cause occurrence datetime": (if asked by the issue, format: '%Y-%m-%d %H:%M:%S', otherwise ommited),
        "root cause component": (if asked by the issue, one selected from the possible root cause component list, otherwise ommited),
        "root cause reason": (if asked by the issue, one selected from the possible root cause reason list, otherwise ommited),
    }}, (mandatory)
    "2": {{
        "root cause occurrence datetime": (if asked by the issue, format: '%Y-%m-%d %H:%M:%S', otherwise ommited),
        "root cause component": (if asked by the issue, one selected from the possible root cause component list, otherwise ommited),
        "root cause reason": (if asked by the issue, one selected from the possible root cause reason list, otherwise ommited),
    }}, (only if the failure number is "unknown" or "more than one" in the issue)
    ... (only if the failure number is "unknown" or "more than one" in the issue)
}}
```
(Please use "```json" and "```" tags to wrap the JSON object. You only need to provide the elements asked by the issue, and ommited the other fields in the JSON.)
Note that all the root cause components and reasons must be selected from the provided candidates. Do not reply 'unknown' or 'null' or 'not found' in the JSON. Do not be too conservative in selecting the root cause components and reasons. Be decisive to infer a possible answer based on your current observation."""

def control_loop(objective:str, plan:str, ap, bp, logger, max_step = 15, max_turn = 3) -> str:
   
    prompt = [
            {'role': 'system', 'content': system.format(objective=objective,
                                                        format=format,
                                                        agent=ap.rules, 
                                                        background=bp.schema)},
            {'role': 'user', 'content': "Let's begin."}
        ]

    history = []
    trajectory = []
    observation = "Let's begin."
    status = False
    kernel = InteractiveShellEmbed()
    init_code = "import pandas as pd\n"+ \
            "pd.set_option('display.width', 427)\n"+ \
            "pd.set_option('display.max_columns', 10)\n"
    kernel.run_cell(init_code)

    for step in range(max_step):
        
        note = [{'role': 'user', 'content': f"Continue your reasoning process for the target issue:\n\n{objective}\n\nFollow the rules during issue solving:\n\n{ap.rules}.\n\nResponse format:\n\n{format}"}]
        attempt_actor = []
        try:
            response_raw = get_chat_completion(
                messages=prompt + note,
            )
            if "```json" in response_raw:
                response_raw = re.search(r"```json\n(.*)\n```", response_raw, re.S).group(1).strip()
            logger.debug(f"Raw Response:\n{response_raw}")
            if '"analysis":' not in response_raw or '"instruction":' not in response_raw or '"completed":' not in response_raw:
                logger.warning("Invalid response format. Please provide a valid JSON response.")
                prompt.append({'role': 'assistant', 'content': response_raw})
                prompt.append({'role': 'user', 'content': "Please provide your analysis in requested JSON format."})
                continue
            response = json.loads(response_raw)
            analysis = response['analysis']
            instruction = response['instruction']
            completed = response['completed']
            logger.info('-'*80 + '\n' + f"### Step[{step+1}]\nAnalysis: {analysis}\nInstruction: {instruction}" + '\n' + '-'*80)

            if completed == "True":
                kernel.reset()
                prompt.append({'role': 'assistant', 'content': response_raw})
                prompt.append({'role': 'user', 'content': summary.format(objective=objective,
                                                                                cand=bp.cand)})
                answer = get_chat_completion(
                    messages=prompt,
                )
                logger.debug(f"Raw Final Answer:\n{answer}")
                prompt.append({'role': 'assistant', 'content': answer})
                if "```json" in answer:
                    answer = re.search(r"```json\n(.*)\n```", answer, re.S).group(1).strip()
                return answer, trajectory, prompt

            code, result, status, new_history = execute_act(instruction, bp.schema, history, attempt_actor, kernel, logger)
            if not status:
                logger.warn(f'Self-Correction failed.')
                observation = "The Executor failed to execute the instruction. Please provide a new instruction."
            observation = f"{result}"
            history = new_history
            trajectory.append({'code': f"# In[{step+1}]:\n\n{code}", 'result': f"Out[{step+1}]:\n```\n{result}```"})
            logger.info('-'*80 + '\n' + f"Step[{step+1}]\n### Observation:\n{result}" + '\n' + '-'*80)
            prompt.append({'role': 'assistant', 'content': response_raw})
            prompt.append({'role': 'user', 'content': observation})

        except Exception as e:
            logger.error(e)
            prompt.append({'role': 'assistant', 'content': response_raw})
            prompt.append({'role': 'user', 'content': f"{str(e)}\nPlease provide your analysis in requested JSON format."})
            if 'context_length_exceeded' in str(e):
                logger.warning("Token length exceeds the limit.")
                kernel.reset()
                return "Token length exceeds. No root cause found.", trajectory, prompt

    logger.warning("Max steps reached. Please check the history.")
    kernel.reset()
    final_prompt = {'role': 'user', 'content': summary.format(objective=objective,
                                                                    cand=bp.cand).replace('Now, you have decided to finish your reasoning process. ', 'Now, the maximum steps of your reasoning have been reached. ')}
    if prompt[-1]['role'] == 'user':
        prompt[-1]['content'] = final_prompt['content']
    else:
        prompt.append({'role': 'user', 'content': final_prompt['content']})
    answer = get_chat_completion(
        messages=prompt,
    )
    logger.debug(f"Raw Final Answer:\n{answer}")
    prompt.append({'role': 'assistant', 'content': answer})
    if "```json" in answer:
        answer = re.search(r"```json\n(.*)\n```", answer, re.S).group(1).strip()
    return answer, trajectory, prompt
