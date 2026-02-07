import os
import yaml
import time

def load_config(config_path="rca/api_config.yaml"):
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
    from google import genai
    from google.genai import types
    client = genai.Client(api_key=configs["API_KEY"], http_options=types.HttpOptions(timeout=120_000))
    system_instruction = None
    if messages and messages[0]["role"] == "system":
        system_instruction = messages[0]["content"]
        messages = messages[1:]
    contents = []
    for item in messages:
        role = "model" if item["role"] == "assistant" else "user"
        contents.append(types.Content(role=role, parts=[types.Part.from_text(text=item["content"])]))
    config = types.GenerateContentConfig(
        temperature=temperature,
        system_instruction=system_instruction,
    )
    response = client.models.generate_content(
        model=configs["MODEL"],
        contents=contents,
        config=config,
    )
    return response.text

def Anthropic_chat_completion(messages, temperature):
    import anthropic
    client = anthropic.Anthropic(
        api_key=configs["API_KEY"]
    )
    system = None
    if messages and messages[0]["role"] == "system":
        system = messages[0]["content"]
        messages = messages[1:]
    kwargs = dict(
        model=configs["MODEL"],
        messages=messages,
        temperature=temperature,
        max_tokens=128000,
    )
    if system:
        kwargs["system"] = system
    text = ""
    with client.messages.stream(**kwargs) as stream:
        for chunk in stream.text_stream:
            text += chunk
    return text

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
            return OpenAI_chat_completion(messages, temperature)
        elif configs["SOURCE"] == "Google":
            return Google_chat_completion(messages, temperature)
        elif configs["SOURCE"] == "Anthropic":
            return Anthropic_chat_completion(messages, temperature)
        else:
            raise ValueError("Invalid SOURCE in api_config file.")
    
    max_retries = 60
    for i in range(max_retries):
        try:
            return send_request()
        except Exception as e:
            print(e)
            if '429' in str(e):
                if 'insufficient_quota' in str(e):
                    wait = 60
                else:
                    wait = min(2 ** i, 30)
                print(f"Rate limit exceeded. Waiting for {wait} seconds (attempt {i+1}/{max_retries}).")
                time.sleep(wait)
                continue
            elif 'Connection' in type(e).__name__ or 'ConnectionError' in str(type(e)):
                wait = min(2 ** i, 30)
                print(f"Connection error. Waiting for {wait} seconds (attempt {i+1}/{max_retries}).")
                time.sleep(wait)
                continue
            else:
                raise e
    raise RuntimeError(f"API request failed after {max_retries} retries due to rate limiting.")