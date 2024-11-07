import tiktoken
from utils import get_chat_completion

system = """You will be provided with some telemetry data and an issue statement explaining a root cause analysis problem to resolve.

{info}

{data}"""

user = """Now, I need you to provide an root cause analysis to the following question:

```issue
{objective}
```

Note: A root cause is the fundamental factor that triggers a service system failure, causing other system components to exhibit various anomalous behaviors. It consists of three elements: the root cause component, the start time of the root cause occurrence, and the reason for its occurrence. The objective of root cause analysis may vary, aiming to identify one or more of these elements based on the issue. Each failure has only one root cause. However, sometimes a system's abnormal state may be due to multiple simultaneous failures, each with its own root cause. If you find that there is a call relationship between multiple components exhibiting abnormal behavior, these anomalies originate from the same failure, with the component at the downstream end of the call chain being the root cause component. The anomalies in the other components are caused by the failure. If there is no call relationship between the abnormal components, each component may be the root cause of a different failure. Typically, the number of failures occurring within half an hour does not exceed three.

Please first conduct a comprehensive analysis on the given telemetry data step-by-step in your response. Then, summarize your findings using the following JSON format to provide a concise answer to the given issue at the end of your response. In the summarized ansewr, you only need to provide the elements asked by the issue, and ommited the other fields in the JSON. The overall format is as follows:

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
(DO NOT contain "```json" and "```" tags. DO contain the JSON object with the brackets "{{}}" only.)

Please follow the format above to provide your response of current issue.

Response below:"""

class CoTLM:
    def __init__(self, oracle, schema) -> None:
        self.tokenizer = tiktoken.encoding_for_model("gpt-4o")
        self.oracle = oracle
        self.schema = schema
    
        
    def run(self, instruction, period_data, sample_interval, logger, max_try=3):
        logger.info(f"Objective: {instruction}")
        
        data = f"""## TELEMETRY DATA (Sampled every {sample_interval/60} min):"""
        for key in sorted(period_data.keys()):
            value = period_data[key]
            data += "\n\n" + "".join([f"### {str(key).upper()} DATA", value])
            logger.debug(f"{str(key).upper()} DATA tokens: {len(self.tokenizer.encode(value))}")
        info = self.schema
        prompt = [
                    {'role': 'system', 'content': system.format(info=info, data=data)},
                    {'role': 'user', 'content': user.format(objective=instruction)}
        ]

        logger.debug(f"prompt tokens: {len(self.tokenizer.encode(prompt[0]['content']))}")
        
        for i in range(max_try):
            try:
                response = get_chat_completion(
                    messages=prompt,
                )
                logger.debug(f"Raw Response:\n{response}")
                return response, prompt
            except Exception as e:
                logger.error(e)
                if 'context_length_exceeded' in str(e):
                    logger.error("Token length exceeds the limit.")
                    return "EXCEED!", prompt
        logger.warning("Max steps reached. Please check the history.")
        return "Max steps reached. Please check the history.", prompt
                
                
                