from typing import Optional, Type, TypeVar, Generic, Callable, Any
from pydantic import BaseModel
from browser_use.agent.views import ActionResult
from browser_use.controller.service import Controller, DoneAction
import logging
from abc import ABC, abstractmethod

class ObservationModel(ABC, BaseModel):
    @abstractmethod
    def to_msg(self):
        pass

# Define a TypeVar for the Observation type
ObservationType = TypeVar('ObservationType', bound=ObservationModel)

logger = logging.getLogger(__name__)


# SOMETHING_WRONG: doesnt work for some reason, keep getting tool call params wrong
class ObservationController(Controller, Generic[ObservationType]):
    def __init__(self, 
                 observation_model: Type[ObservationType],
                 exclude_actions: list[str] = [],
                 output_model: Optional[Type[BaseModel]] = None,
                 ):
        super().__init__(exclude_actions=exclude_actions, output_model=output_model)
        self.observation_model = observation_model
        self._register_custom_actions()

    def _register_custom_actions(self):
        """Register all custom browser actions"""
        
        if self.observation_model:
            @self.registry.action('Record the observation', param_model=self.observation_model)
            async def record_observation(params: ObservationType):
                msg = f"Recorded observation: {params.to_msg()}"
                return ActionResult(
                    extracted_content=msg, 
                    include_in_memory=True,
                )