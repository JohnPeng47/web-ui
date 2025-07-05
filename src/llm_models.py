from typing import Dict, Any, Callable
from langchain_openai import ChatOpenAI
from langchain_together import ChatTogether
from langchain_core.messages import BaseMessage
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_cohere import ChatCohere
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_anthropic import ChatAnthropic

import json
import os

class ChatModelWithName:
    """Wrapper for BaseChatModel that adds a model_name attribute."""
    
    def __init__(self, model: BaseChatModel, model_name: str):
        self._model = model
        self.model_name = model_name
        self.log_fn = None
        self.function_name = None

    def set_log_fn(self, log_fn: Callable[[BaseMessage, str], None], function_name: str) -> None:
        self.log_fn = log_fn
        self.function_name = function_name
    
    def invoke(self, *args: Any, **kwargs: Any) -> Any:
        res = self._model.invoke(*args, **kwargs)
        if self.log_fn:
            self.log_fn(res, self.function_name)
        return res
    
    def __getattr__(self, name: str) -> Any:
        # Delegate all other attribute access to the wrapped model
        return getattr(self._model, name)

# Lazy-init models
gemini_25_flash = lambda: ChatModelWithName(
    ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        api_key=os.getenv("GEMINI_API_KEY")
    ),
    "gemini-2.5-flash"
)
gemini_25_pro = lambda: ChatModelWithName(
    ChatGoogleGenerativeAI(
        model="gemini-2.5-pro",
        api_key=os.getenv("GEMINI_API_KEY")
    ),
    "gemini-2.5-pro"
)
openai_4o = lambda: ChatModelWithName(
    ChatOpenAI(model="gpt-4o"),
    "gpt-4o"
)
openai_41 = lambda: ChatModelWithName(
    ChatOpenAI(model="gpt-4.1"),
    "gpt-4.1"
)
cohere_command_a = lambda: ChatModelWithName(
    ChatCohere(
        model="command-a-03-2025", 
        cohere_api_key=os.getenv("COHERE_API_KEY")
    ),
    "command-a-03-2025"
)
together_deepseek_r1 = lambda: ChatModelWithName(
    ChatTogether(
        model="deepseek-ai/DeepSeek-R1-0528-tput",
        api_key=os.getenv("TOGETHER_API_KEY")
    ),
    "deepseek-ai/DeepSeek-R1-0528-tput"
)
openai_o3 = lambda: ChatModelWithName(
    ChatOpenAI(model="o3"),
    "o3"
)
anthropic_claude_3_5_sonnet = lambda: ChatModelWithName(
    ChatAnthropic(model="claude-3-5-sonnet-20240620"),
    "claude-3-5-sonnet-20240620"
)
claude_4_sonnet = lambda: ChatModelWithName(
    ChatAnthropic(model="claude-sonnet-4-20250514"),
    "claude-sonnet-4-20250514"
)

LLM_MODELS = {
    "command-a-03-2025": cohere_command_a,
    # "deepseeks_r1": together_deepseek_r1,
    "gpt-4o": openai_4o,
    "gpt-4.1": openai_41,
    "gemini-2.5-flash": gemini_25_flash,
    "gemini-2.5-pro": gemini_25_pro,
    "default": cohere_command_a,
    "o3": openai_o3,
    "claude-3-5-sonnet-20240620": anthropic_claude_3_5_sonnet,
    "claude-sonnet-4-20250514": claude_4_sonnet,
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
        self._cost_map = self._load_cost_map()
        self._total_costs = {function_name: 0 for function_name in function_map.keys()}

    def _load_cost_map(self) -> Dict:
        with open("model_api_prices.json", "r") as f:
            return json.load(f)
        
    def log_cost(self, res: BaseMessage, function_name: str) -> None:
        model_name = self._function_map[function_name]

        self._total_costs[function_name] += self._cost_map[model_name]["input_cost_per_token"] * res.usage_metadata["input_tokens"]
        self._total_costs[function_name] += self._cost_map[model_name]["output_cost_per_token"] * res.usage_metadata["output_tokens"]

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

# if __name__ == "__main__":
#     import time
    
#     start_time = time.time()
    
#     print(LLM_MODELS["gemini-2.5-flash"].model_name)
#     print(LLM_MODELS["gemini-2.5-pro"].model_name)
#     print(LLM_MODELS["gpt-4o"].model_name)
#     print(LLM_MODELS["gpt-4.1"].model_name)
#     print(LLM_MODELS["command-a-03-2025"].model_name)
#     print(LLM_MODELS["o3"].model_name)
#     print(LLM_MODELS["claude-3-5-sonnet-20240620"].model_name)
#     print(LLM_MODELS["claude-sonnet-4-20250514"].model_name)
    
#     end_time = time.time()
#     execution_time = end_time - start_time
#     print(f"Execution time: {execution_time:.6f} seconds")