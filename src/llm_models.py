from pathlib import Path
from typing import Dict, Any, Callable
from langchain_core.messages import BaseMessage
from langchain_core.language_models.chat_models import BaseChatModel

import json
import os

COST_MAP = None

# singleton cost map
# https://raw.githubusercontent.com/BerriAI/litellm/main/model_prices_and_context_window.json
def load_cost_map() -> Dict:
    global COST_MAP
    if not COST_MAP:
        with open(Path(__file__).parent.parent / "model_api_prices.json", "r") as f:
            COST_MAP = json.load(f)

    return COST_MAP

# TODO: this is for all contents and purposes a BaseChatModel
class ChatModelWithName:
    """Wrapper for BaseChatModel that adds a model_name attribute."""
    
    def __init__(self, model: BaseChatModel, model_name: str):
        self._model = model
        self.model_name = model_name
        self.log_fn = None
        self.function_name = ""

        self._cost_map = load_cost_map()
        self._cost = 0

    def get_cost(self) -> float:
        return self._cost

    def set_log_fn(self, log_fn: Callable[[BaseMessage, str], None], function_name: str) -> None:
        self.log_fn = log_fn
        self.function_name = function_name
    
    def log_cost(self, res: BaseMessage) -> None:
        invoke_cost = 0
        invoke_cost += self._cost_map[self.model_name]["input_cost_per_token"] * res.usage_metadata["input_tokens"]
        invoke_cost += self._cost_map[self.model_name]["output_cost_per_token"] * res.usage_metadata["output_tokens"]
        self._cost += invoke_cost
        
        if self.log_fn:
            self.log_fn(invoke_cost, self.function_name)

    def invoke(self, *args: Any, **kwargs: Any) -> Any:
        structured_output = kwargs.pop("structured_output", None)
        if structured_output:
            model = self._model.with_structured_output(structured_output)
        else:
            model = self._model

        res = model.invoke(*args, **kwargs)
        self.log_cost(res)
        return res
    
    def __getattr__(self, name: str) -> Any:
        # Delegate all other attribute access to the wrapped model
        return getattr(self._model, name)

# Lazy-init models
def gemini_25_flash():
    from langchain_google_genai import ChatGoogleGenerativeAI
    return ChatModelWithName(
        ChatGoogleGenerativeAI(
            model="gemini-2.5-flash",
            api_key=os.getenv("GEMINI_API_KEY"),
            enable_thinking=True
        ),
        "gemini-2.5-flash"
    )

def gemini_25_pro():
    from langchain_google_genai import ChatGoogleGenerativeAI
    return ChatModelWithName(
        ChatGoogleGenerativeAI(
            model="gemini-2.5-pro",
            api_key=os.getenv("GEMINI_API_KEY")
        ),
        "gemini-2.5-pro"
    )

def openai_o3_mini():
    from langchain_openai import ChatOpenAI
    return ChatModelWithName(
        ChatOpenAI(model="o3-mini"),
        "o3-mini"
    )

def openai_o4_mini():
    from langchain_openai import ChatOpenAI
    return ChatModelWithName(
        ChatOpenAI(model="o4-mini"),
        "o4-mini"
    )

def openai_4o():
    from langchain_openai import ChatOpenAI
    return ChatModelWithName(
        ChatOpenAI(model="gpt-4o"),
        "gpt-4o"
    )

def openai_41():
    from langchain_openai import ChatOpenAI
    return ChatModelWithName(
        ChatOpenAI(model="gpt-4.1"),
        "gpt-4.1"
    )

def openai_5():
    from langchain_openai import ChatOpenAI
    return ChatModelWithName(
        ChatOpenAI(model="gpt-5"),
        "gpt-5"
    )

def grok4():
    from langchain_xai import ChatXAI
    return ChatModelWithName(
        ChatXAI(
            model="grok-4", 
            api_key=os.getenv("XAI_API_KEY")
        ),
        "grok-4"
    )

# def cohere_command_a():
#     from langchain_cohere import ChatCohere
#     return ChatModelWithName(
#         ChatCohere(
#             model="command-a-03-2025", 
#             cohere_api_key=os.getenv("COHERE_API_KEY")
#         ),
#         "command-a-03-2025"
#     )

def together_deepseek_r1():
    from langchain_together import ChatTogether
    return ChatModelWithName(
        ChatTogether(
            model="deepseek-ai/DeepSeek-R1-0528-tput",
            api_key=os.getenv("TOGETHER_API_KEY")
        ),
        "deepseek-ai/DeepSeek-R1-0528-tput"
    )

def openai_o3():
    from langchain_openai import ChatOpenAI
    return ChatModelWithName(
        ChatOpenAI(model="o3"),
        "o3"
    )

def anthropic_claude_3_5_sonnet():
    from langchain_anthropic import ChatAnthropic
    return ChatModelWithName(
        ChatAnthropic(model="claude-3-5-sonnet-20240620"),
        "claude-3-5-sonnet-20240620"
    )

def claude_4_sonnet():
    from langchain_anthropic import ChatAnthropic
    return ChatModelWithName(
        ChatAnthropic(model="claude-sonnet-4-20250514", max_tokens=15000),
        "claude-sonnet-4-20250514"
    )

LLM_MODELS = {
    # "command-a-03-2025": cohere_command_a,
    # "deepseeks_r1": together_deepseek_r1,
    "gpt-4o": openai_4o,
    "gpt-4.1": openai_41,
    "gemini-2.5-flash": gemini_25_flash,
    "gemini-2.5-pro": gemini_25_pro,
    # "default": cohere_command_a,
    "o4-mini": openai_o4_mini,
    "o3": openai_o3,
    "o3-mini": openai_o3_mini,
    "claude-3-5-sonnet-20240620": anthropic_claude_3_5_sonnet,
    "claude-sonnet-4-20250514": claude_4_sonnet,
    "gpt-5": openai_5,
}

# incredibly dumb hack to appease the type checker
class BaseChatWrapper:
    def __init__(
            self, 
            function_name: str, 
            model: BaseChatModel, 
            log_fn: Callable[[BaseMessage, str], None]
        ):
        self._function_name = function_name
        self._model = model
        self._log_fn = log_fn

    def invoke(self, *args: Any, **kwargs: Any) -> Any:
        res = self._model.invoke(*args, **kwargs)
        self._log_fn(res, self._function_name)
        return res

class LLMHub:
    """
    Thin convenience wrapper around a collection of LangChain chat models.

    Args:
        providers (Dict[str, BaseChatModel]):
            Mapping of model-name → model instance.
        function_map (Dict[str, str]):
            Mapping of function-name -> model-name.
    """

    def __init__(
            self, 
            function_map: Dict[str, str], 
            providers: Dict[str, Callable[[], ChatModelWithName] | ChatModelWithName] = LLM_MODELS
        ) -> None:
        self._providers = providers # lazily convert these to actually initialized models
        self._function_map = function_map
        self._total_costs = {function_name: 0.0 for function_name in function_map.keys()}

    def log_cost(self, invoke_cost: float, function_name: str) -> None:
        self._total_costs[function_name] += invoke_cost

    # ------------- convenience helpers -----------------
    def set_default(self, name: str) -> None:
        """Switch the default model."""
        if name not in self._providers:
            raise KeyError(f"model {name!r} not found")

    def get(self, function_name: str) -> ChatModelWithName:
        """Return a wrapper for a specific provider by function name."""
        model_name = self._function_map.get(function_name)
        
        if model_name is None:
            raise KeyError(f"function {function_name!r} not found in function map")
        elif model_name not in self._providers:
            raise KeyError(f"model {model_name!r} not found")
        
        provider_entry = self._providers[model_name]

        # Lazy-init if we stored a factory (callable)
        if callable(provider_entry):
            provider_entry: ChatModelWithName = provider_entry()
            self._providers[model_name] = provider_entry  # cache the instance
            provider_entry.set_log_fn(self.log_cost, function_name)

        return provider_entry

    def get_costs(self):
        return self._total_costs