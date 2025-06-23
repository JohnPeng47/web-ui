from typing import Dict, Any
from langchain_openai import ChatOpenAI
from langchain_together import ChatTogether
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_cohere import ChatCohere
from langchain_google_genai import ChatGoogleGenerativeAI

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
    "cohere_command_a": cohere_command_a,
    "deepseek_r1": together_deepseek_r1,
    "openai_4o": openai_4o,
    "openai_4.1": openai_41,
    "gemini_25_flash": gemini_25_flash,
    "default": cohere_command_a,
}

class LLMHub:
    """
    Thin convenience wrapper around a collection of LangChain chat models.

    Args:
        providers (Dict[str, BaseChatModel]):
            Mapping of model-name → model instance.
            One key **must** be "default".  That entry is used by ``invoke``.
    """

    def __init__(self, providers: Dict[str, BaseChatModel]) -> None:
        if "default" not in providers:
            raise ValueError('"default" key missing from providers mapping')

        self._providers: Dict[str, BaseChatModel] = providers
        self.default: BaseChatModel = providers["default"]

    # ------------- convenience helpers -----------------
    def set_default(self, name: str) -> None:
        """Switch the default model."""
        if name not in self._providers:
            raise KeyError(f"model {name!r} not found")
        self.default = self._providers[name]
        self._providers["default"] = self.default

    def get(self, name: str) -> BaseChatModel:
        """Return a specific provider by name."""
        return self._providers[name]

    # ------------- primary public API ------------------
    def invoke(self, message: str, **kwargs: Any):
        """
        Proxy call to the **current** default model.

        Extra kwargs are passed through verbatim, so you can still do e.g.
        ``hub.invoke("hi", temperature=0.2)``.
        """
        return self.default.invoke(message, **kwargs)
    
llm_hub = LLMHub(LLM_MODELS)