import os
import yaml
import time

def load_config(config_path="./api_config.yaml"):
    configs = dict(os.environ)
    with open(config_path, "r") as file:
        yaml_data = yaml.safe_load(file)
    configs.update(yaml_data)
    return configs

configs = load_config()

def OpenAI_chat_completion(messages, temperature):    
    from openai import OpenAI
    client = OpenAI(
        api_key=configs["API_KEY"]
    )
    return client.chat.completions.create(
        model = configs["MODEL"],
        messages = messages,
        temperature = temperature,
    ).choices[0].message.content

def Google_chat_completion(messages, temperature):
    import google.generativeai as genai
    genai.configure(
        api_key=configs["API_KEY"]
    )
    genai.GenerationConfig(temperature=temperature)
    system_instruction = messages[0]["content"] if messages[0]["role"] == "system" else None
    messages = [item for item in messages if item["role"] != "system"]
    messages = [{"role": "model" if item["role"] == "assistant" else item["role"], "parts": item["content"]} for item in messages]
    history = messages[:-1]
    message = messages[-1]
    return genai.GenerativeModel(
        model_name=configs["MODEL"],
        system_instruction=system_instruction
        ).start_chat(
            history=history if history != [] else None
            ).send_message(message).text

def Anthropic_chat_completion(messages, temperature):
    import anthropic
    client = anthropic.Anthropic(
        api_key=configs["API_KEY"]
    )
    return client.messages.create(
        model=configs["MODEL"],
        messages=messages,
        temperature=temperature
    ).content

# for 3-rd party API which is compatible with OpenAI API (with different 'API_BASE')
def AI_chat_completion(messages, temperature):    
    from openai import OpenAI
    client = OpenAI(
        api_key=configs["API_KEY"],
        base_url=configs["API_BASE"]
    )
    return client.chat.completions.create(
        model = configs["MODEL"],
        messages = messages,
        temperature = temperature,
    ).choices[0].message.content

def get_chat_completion(messages, temperature=0.0):

    def send_request():
        if configs["SOURCE"] == "AI":
            return AI_chat_completion(messages, temperature)
        elif configs["SOURCE"] == "OpenAI":
            return AI_chat_completion(messages, temperature)
        elif configs["SOURCE"] == "Google":
            return Google_chat_completion(messages, temperature)
    
    for i in range(3):
        try:
            return send_request()
        except Exception as e:
            print(e)
            if '429' in str(e):
                print("Rate limit exceeded. Waiting for 1 second.")
                time.sleep(1)
                continue
            else:
                raise e