import os 
from functools import cache
from agents import OpenAIChatCompletionsModel
from openai import AsyncOpenAI
from agents import ModelSettings

@cache
def get_openai_model() -> OpenAIChatCompletionsModel:
    model_name = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    client = get_openai_client()
    return OpenAIChatCompletionsModel(model_name, 
                                      openai_client=client)
@cache
def get_openai_client() -> AsyncOpenAI:
    return AsyncOpenAI()

@cache
def get_openai_model_settings():
    temperature = float(os.getenv("OPENAI_TEMPERATURE", 0.0))
    return ModelSettings(temperature=temperature)
