system = """Let's play a game. In this game, your task is to generate a issue related to DevOps failure diagnosis based on a given set of specifications. The goal is to make the issue realistic enough that even top human experts might believe it reflects a genuine issue an engineer could encounter at work. They should not be able to tell that the issue was generated by an AI Assistant based on specifications.

The specifications provided to you include the following components:

```known
(The known information explicitly provided in the issue.)
```

```query
(The target query that required the user to answer.)
```

Your response should follow the JSON format below:

{
    "issue": (Your generated issue based on the specifications.)
}
(DO NOT contain "```json" and "```" tags. DO contain the JSON object with the brackets "{}" only.)

For example, if the following specifications are given:
 
```known
- number of failures: 1
- time range: 2022-03-21 11:30:00 to 2022-03-21 12:00:00
- system: None
```

```query
- root cause occurrence time: **UNKNOWN**
```

Then, you could generate a issue be like:

{
    "issue": "During the specified time range of March 21, 2022, from 11:30 to 12:00, the cloud service system experience a failure. The exact time of the root cause occurrence is unknown, which complicates the diagnosis process. Please pinpoint the root cause occurrence datetime."
}

There is another example: 

```known
- number of failures: 2
- time range: 2022-03-20 09:30:00 to 2022-03-20 10:00:00
- system: cloudbed-1
```

```query
- root cause occurrence time: **UNKNOWN**
- root cause component: **UNKNOWN**
- root cause reason: **UNKNOWN**
```

The generated issue be like:

{
    "issue": "The cloud service system, cloudbed-1, may have experienced two failures within the time range of March 20, 2022, from 09:30 to 10:00. The exact number of failures, the time of occurrence, the affected components, and the underlying reasons for these failures are currently unknown. You are tasked with identifying the root cause occurrence datetime, the root cause component, and the root cause reason."
}

Some rules to follow:

1. Do not tell the user "how to solve the issue" (e.g., retrieve the telemetry data like metrics/logs/traces).
2. Do not involve human interaction in the issue (e.g., "ask the engineer for more information").
3. Do not include any specific values that are not mentioned in the specification (e.g., "the CPU usage was 80%").

Now, let's get started!"""

user = """Please generate a issue related to DevOps failure diagnosis based on the following specifications:

```known
{input_specification}
```

```query
{output_specification}
```"""