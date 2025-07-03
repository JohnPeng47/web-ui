from typing import Dict, Any, Callable
from langchain_openai import ChatOpenAI
from langchain_together import ChatTogether
from langchain_core.messages import BaseMessage
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_cohere import ChatCohere
from langchain_google_genai import ChatGoogleGenerativeAI

import json
import os

gemini_25_flash = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    api_key=os.getenv("GEMINI_API_KEY")
)
openai_4o = ChatOpenAI(model="gpt-4o")
openai_41 = ChatOpenAI(model="gpt-4.1")
cohere_command_a = ChatCohere(
    model="command-a-03-2025", 
    cohere_api_key=os.getenv("COHERE_API_KEY")
)
together_deepseek_r1 = ChatTogether(
    model="deepseek-ai/DeepSeek-R1-0528-tput",
    api_key=os.getenv("TOGETHER_API_KEY")
)

LLM_MODELS = {
    "command-a-03-2025": cohere_command_a,
    # "deepseeks_r1": together_deepseek_r1,
    "gpt-4o": openai_4o,
    "gpt-4.1": openai_41,
    "gemini-2.5-flash": gemini_25_flash,
    "default": cohere_command_a,
}

MODEL_DICT = {
    "browser_use": "gemini-2.5-flash",
    "check_plan_completion" : "gemini-2.5-flash",
    "determine_new_page" : "default",
    "create_plan" : "default",
    "update_plan" : "gemini-2.5-flash",
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
            providers: Dict[str, BaseChatModel] = LLM_MODELS
        ) -> None:
        self._providers = providers
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

    def get(self, function_name: str) -> BaseChatModel:
        """Return a wrapper for a specific provider by function name."""
        model_name = self._function_map.get(function_name)
        
        if model_name is None:
            raise KeyError(f"function {function_name!r} not found in function map")
        elif model_name not in self._providers:
            raise KeyError(f"model {model_name!r} not found")
        else:
            model_to_wrap = self._providers[model_name]
        
        return BaseChatWrapper(function_name, model_to_wrap, self.log_cost)

    def get_costs(self):
        return self._total_costs
    
llm_hub = LLMHub(providers=LLM_MODELS, function_map={})