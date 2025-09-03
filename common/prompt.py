from typing import Optional, Union, Dict, Any, Tuple
from pydantic import BaseModel
from dataclasses import dataclass
from enum import Enum
from opik import Opik as opik_client

class PromptStrategy(Enum):
    OPIK = "opik"
    MANUAL = "manual"

@dataclass
class OpikPrompt:
    """Represents a prompt retrieved from Opik."""
    prompt: str
    name: str
    commit: str

class PromptConfig(BaseModel):
    """Configuration for prompt resolution supporting both Opik and manual strategies."""

    strategy: PromptStrategy    
    name: Optional[str] = None
    commit: Optional[str] = None
    prompt: Optional[str] = None
        
    def resolve_prompt(self, fallback_prompts: Optional[Dict[str, OpikPrompt]] = None) -> Tuple[str, str, str]:
        """
        Resolve the prompt using either Opik or manual strategy.
        
        Args:
            fallback_prompts: Dictionary mapping prompt names to OpikPrompt objects for fallback
            
        Returns:
            Tuple of (prompt_text, name, commit)
            
        Raises:
            ValueError: If neither strategy is properly configured or resolution fails
        """
        # Strategy 1: Opik resolution
        if self.strategy == PromptStrategy.OPIK:
            if self.name is None:
                raise ValueError("Opik strategy requires 'name' to be specified")
            try:
                opik_prompt = opik_client().get_prompt(self.name, commit=self.commit)
                if opik_prompt:
                    return (
                        opik_prompt.prompt,
                        opik_prompt.name,
                        opik_prompt.commit
                    )
                else:
                    raise ValueError(f"No opik prompt found for {self.name}")
            except Exception as e:
                # Fallback to local prompts if available
                if fallback_prompts and self.name in fallback_prompts:
                    fallback = fallback_prompts[self.name]
                    return (fallback.prompt, fallback.name, fallback.commit)
                raise e
        
        # Strategy 2: Manual prompt
        elif self.strategy == PromptStrategy.MANUAL:
            if self.prompt is None:
                raise ValueError("Manual strategy requires 'prompt' to be specified")
            return (
                self.prompt,
                "",
                ""
            )
        
        else:
            raise ValueError(f"Unknown strategy: {self.strategy}")
    
    def is_opik_strategy(self) -> bool:
        """Returns True if this config uses Opik resolution strategy."""
        return self.strategy == PromptStrategy.OPIK
    
    def is_manual_strategy(self) -> bool:
        """Returns True if this config uses manual prompt strategy."""
        return self.strategy == PromptStrategy.MANUAL
