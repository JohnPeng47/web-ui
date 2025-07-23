from litellm.types.utils import ModelResponse
from opik.evaluation.models.litellm import opik_monitor, warning_filters
from opik.evaluation.models import base_model

from pydantic import BaseModel
import warnings
from textwrap import dedent
from typing import Any, List, Optional
import argparse
from logging import getLogger
import json

from johnllm import LLMModel

logger = getLogger(__name__)

def get_response_format_prompt(response_model: BaseModel | None) -> str:
    if not response_model:
        return ""
    
    message = dedent(
        f"""
As a genius expert, your task is to understand the content and provide
the parsed objects in json that match the following json_schema:\n

{json.dumps(response_model.model_json_schema(), indent=2, ensure_ascii=False)}

Make sure to return an instance of the JSON, not the schema itself
        """
    )
    return message

def parse_eval_args(prompt, response_format = None):
    """Parse command line arguments for experiment_name and project_name."""
    parser = argparse.ArgumentParser(description='Run evaluation with specified experiment and project names.')
    
    # Add arguments with both long and short forms
    parser.add_argument('-e', '--experiment', dest='experiment_name', required=False,
                        help='Name of the experiment to run')
    parser.add_argument('-p', '--project', dest='project_name', required=False,
                        help='Name of the project', default="")
    parser.add_argument('-r', '--prompt', dest='prompt', action='store_true', default=False,
                    help='Print the prompt')

    args = parser.parse_args()
    if args.prompt:
        prompt = prompt + get_response_format_prompt(response_format)
        print(prompt)

        import sys
        sys.exit(0)
    return args.experiment_name, args.project_name

class JohnLLMModel(base_model.OpikBaseModel):
    def __init__(
        self,
        model_name: str = "gpt-3.5-turbo",
        must_support_arguments: Optional[List[str]] = None,
        response_format: Any = None,
        **completion_kwargs: Any,
    ) -> None:
        """
        Initializes the base model with a given model name.
        Wraps `litellm.completion` function.
        You can find all possible completion_kwargs parameters here: https://docs.litellm.ai/docs/completion/input.

        Args:
            model_name: The name of the LLM to be used.
                This parameter will be passed to `litellm.completion(model=model_name)` so you don't need to pass
                the `model` argument separately inside **completion_kwargs.
            must_support_arguments: A list of openai-like arguments that the given model + provider pair must support.
                `litellm.get_supported_openai_params(model_name)` call is used to get
                supported arguments. If any is missing, ValueError is raised.
                You can pass the arguments from the table: https://docs.litellm.ai/docs/completion/input#translated-openai-params

            **completion_kwargs: key-value arguments to always pass additionally into `litellm.completion` function.
        """

        super().__init__(model_name=model_name)

        # self._check_model_name()
        # self._check_must_support_arguments(must_support_arguments)

        # self._completion_kwargs: Dict[str, Any] = (
        #     self._remove_unnecessary_not_supported_params(completion_kwargs)
        # )

        with warnings.catch_warnings():
            # This is the first time litellm is imported when opik is imported.
            # It filters out pydantic warning.
            # Litellm has already fixed that, but it is not released yet, so this filter
            # should be removed from here soon.
            warnings.simplefilter("ignore")
            import litellm

        warning_filters.add_warning_filters()
        self._response_format = response_format
        self._engine = LLMModel()

    def generate_provider_response(
        self,
        **kwargs: Any,
    ) -> "ModelResponse":
        """
        Generate a provider-specific response. Can be used to interface with
        the underlying model provider (e.g., OpenAI, Anthropic) and get raw output.
        You can find all possible input parameters here: https://docs.litellm.ai/docs/completion/input

        Args:
            kwargs: arguments required by the provider to generate a response.

        Returns:
            Any: The response from the model provider, which can be of any type depending on the use case and LLM.
        """
        if type(kwargs) is not dict:
            raise TypeError(
                "The arguments passed to the model should be a dictionary."
            )

        # we need to pop messages first, and after we will check the rest params
        messages = kwargs.pop("messages")
        if (
            opik_monitor.enabled_in_config()
            and not opik_monitor.opik_is_misconfigured()
        ):
            all_kwargs = opik_monitor.try_add_opik_monitoring_to_params(kwargs)

        response = self._engine.invoke(
            messages, model_name=self.model_name, response_format=self._response_format, **all_kwargs
        )
        return response

    async def agenerate_string(self, input: str, **kwargs: Any) -> str:
        """
        Simplified interface to generate a string output from the model. Async version.
        You can find all possible input parameters here: https://docs.litellm.ai/docs/completion/input

        Args:
            input: The input string based on which the model will generate the output.
            kwargs: Additional arguments that may be used by the model for string generation.

        Returns:
            str: The generated string output.
        """
        # valid_litellm_params = self._remove_unnecessary_not_supported_params(kwargs)

        # request = [
        #     {
        #         "content": input,
        #         "role": "user",
        #     },
        # ]

        # response = await self.agenerate_provider_response(
        #     messages=request, **valid_litellm_params
        # )
        # return response.choices[0].message.content
        return ""

    async def agenerate_provider_response(self, **kwargs: Any) -> ModelResponse | None:
        """
        Generate a provider-specific response. Can be used to interface with
        the underlying model provider (e.g., OpenAI, Anthropic) and get raw output. Async version.
        You can find all possible input parameters here: https://docs.litellm.ai/docs/completion/input

        Args:
            kwargs: arguments required by the provider to generate a response.

        Returns:
            Any: The response from the model provider, which can be of any type depending on the use case and LLM.
        """

        # we need to pop messages first, and after we will check the rest params
        # messages = kwargs.pop("messages")

        # valid_litellm_params = self._remove_unnecessary_not_supported_params(kwargs)
        # all_kwargs = {**self._completion_kwargs, **valid_litellm_params}

        # if opik_monitor.enabled_in_config():
        #     all_kwargs = opik_monitor.try_add_opik_monitoring_to_params(all_kwargs)

        # response = await self._engine.acompletion(
        #     model=self.model_name, messages=messages, **all_kwargs
        # )

        # return response
        return None
    
    def generate_string(self, input: str, **kwargs: Any) -> str:
        return ""