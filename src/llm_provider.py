from __future__ import annotations  # type: ignore[all]

import time
from textwrap import dedent

import jinja2
import json

from logging import Logger
from collections.abc import Iterable
from typing import Dict, Generic, Any, TypeVar, get_args, get_origin, List, Optional, Type

from pydantic import BaseModel, create_model

from instructor.dsl.iterable import IterableModel
from instructor.dsl.simple_type import ModelAdapter, is_simple_type
from instructor.function_calls import OpenAISchema, openai_schema

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage

from src.llm_models import ChatModelWithName, openai_41 as lazy_openai_41

manual_rewrite_model = lazy_openai_41

T = TypeVar("T") 

def extract_json_tags(response: str) -> str:
    """
    Extracts the JSON tags from the response.
    """
    try:
        return response.split("```json")[1].split("```")[0]
    except IndexError as e:
        # assume that response is already json
        return response

def is_typed_dict(cls) -> bool:
    return (
        isinstance(cls, type)
        and issubclass(cls, dict)
        and hasattr(cls, "__annotations__")
    )

# pylint: skip-file
def prepare_response_model(response_model: type[T] | None) -> type[T] | None:
    """
    Prepares the response model for use in the API call.

    This function performs several transformations on the input response_model:
    1. If the response_model is None, it returns None.
    2. If it's a simple type, it wraps it in a ModelAdapter.
    3. If it's a TypedDict, it converts it to a Pydantic BaseModel.
    4. If it's an Iterable, it wraps the element type in an IterableModel.
    5. If it's not already a subclass of OpenAISchema, it applies the openai_schema decorator.

    Args:
        response_model (type[T] | None): The input response model to be prepared.

    Returns:
        type[T] | None: The prepared response model, or None if the input was None.
    """
    if response_model is None:
        return None

    if is_simple_type(response_model):
        response_model = ModelAdapter[response_model]

    if is_typed_dict(response_model):
        response_model: BaseModel = create_model(
            response_model.__name__,
            **{k: (v, ...) for k, v in response_model.__annotations__.items()},
        )

    if get_origin(response_model) is Iterable:
        iterable_element_class = get_args(response_model)[0]
        response_model = IterableModel(iterable_element_class)

    if not issubclass(response_model, OpenAISchema):
        response_model = openai_schema(response_model)  # type: ignore

    return response_model


class LMPVerificationException(Exception):
    """Thrown when post_process raises an error"""
    pass

# TODO: change to use generic[t]
# DESIGN: not sure how to enforce this but we should only allow JSON serializable
# args to be passed to the model, to be compatible with Braintrust 
class LMP(Generic[T]):
    """
    A language model progsram
    """
    prompt: str
    response_format: Type[T]
    templates: Dict = {}
    manual_response_models: List[str] = [
        "gemini-2.5-pro"
    ]
    manual_rewrite_model: Optional[BaseChatModel] = None
    manual_rewrite_prompt: str = """
Convert the following response into a valid JSON object:

{response}
"""

    def _prepare_prompt(self, templates={}, manual_rewrite: bool = False, **prompt_args) -> str:        
        prompt_str = jinja2.Template(self.prompt).render(**prompt_args, **templates)

        if not manual_rewrite:
            return prompt_str + self._get_instructor_prompt()
        else:
            return prompt_str
    
    def _prepare_manual_rewrite_prompt(self, response: str) -> str:
        prompt_str = self.manual_rewrite_prompt.format(response=response)
        return prompt_str + self._get_instructor_prompt()

    def _verify_or_raise(self, res, **prompt_args):
        return True

    def _process_result(self, res, **prompt_args) -> Any:
        return res
    
    def _get_instructor_prompt(self) -> str:
        if not self.response_format:
            return ""
    
        response_model = prepare_response_model(self.response_format)
        return f"""
        \n\n
Understand the content and provide
the parsed objects in json that match the following json_schema:\n

{json.dumps(response_model.model_json_schema(), indent=2, ensure_ascii=False)}

Make sure to return an instance of the JSON, not the schema itself
        """
    
    def invoke_with_msgs(
            self, 
            model: BaseChatModel,
            msgs: List[BaseMessage],
            **prompt_args
        ) -> Any:
        res = model.invoke(msgs)
        content = res.content

        if not isinstance(content, str):
            raise Exception("[LLM] CONTENT IS NOT A STRING")
        
        if self.response_format:
            content = extract_json_tags(content)
            content = self.response_format.model_validate_json(content)

        self._verify_or_raise(content, **prompt_args)
        # skip process_result
        return content

    def invoke(self, 
               model: BaseChatModel,
               max_retries: int = 3,
               retry_delay: int = 1,
               prompt_args: Dict = {},
               prompt_logger: Optional[Logger] = None,
               manual_rewrite: bool = False) -> Any:
        prompt = self._prepare_prompt(
            templates=self.templates,
            manual_rewrite=manual_rewrite,
            **prompt_args,
        )
        if prompt_logger:
            prompt_logger.info(f"[{self.__class__.__name__}]: {prompt}")

        # TODO: make this decorator
        current_retry = 1
        while current_retry <= max_retries:
            try:
                res = model.invoke(prompt)

                # two part model invocation
                if model.model_name in self.manual_response_models or manual_rewrite:
                    if not self.manual_rewrite_model:
                        self.manual_rewrite_model = lazy_openai_41()

                    prompt = self._prepare_manual_rewrite_prompt(res.content)
                    rewrite_res = self.manual_rewrite_model.invoke(prompt)
                    content = rewrite_res.content
                else:
                    print("--------------------------------")
                    print(res.content)
                    print("--------------------------------")

                    content = res.content

                if not isinstance(content, str):
                    raise Exception("[LLM] CONTENT IS NOT A STRING")
                
                if self.response_format:
                    content = extract_json_tags(content)
                    content = self.response_format.model_validate_json(content)

                self._verify_or_raise(content, **prompt_args)
                return self._process_result(content, **prompt_args)
            
            except Exception as e:
                current_retry += 1
                
                if current_retry > max_retries:
                    raise e
                
                # Exponential backoff: retry_delay * (2 ^ attempt)
                current_delay = retry_delay * (2 ** (current_retry - 1))
                time.sleep(current_delay)
                print(f"Retry attempt {current_retry}/{max_retries} after error: {str(e)}. Waiting {current_delay}s")