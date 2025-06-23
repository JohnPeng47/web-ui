from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field

from src.llm_provider import LMP

class PlanItem(BaseModel):
    description: str
    completed: bool = False
    children: List["PlanItem"] = Field(default_factory=list, repr=False)

    # -------------------- internal helper -------------------- #
    def _add_child(self, description: str, *, completed: bool = False) -> "PlanItem":
        child = PlanItem(description=description, completed=completed)
        self.children.append(child)
        return child

    # -------------------- public API ------------------------- #
    def add_to_root(self, description: str, *, completed: bool = False) -> "PlanItem":
        return self._add_child(description=description, completed=completed)

    def get(self, path: str) -> Optional["PlanItem"]:
        """Return node at dotted path (1-based indices) or None."""
        try:
            idxs = [int(x) for x in path.split(".")]
        except ValueError:
            raise ValueError(f"Invalid path {path!r} (non-integer component)")

        node: "PlanItem" = self
        if idxs and idxs[0] != 1:
            return None

        for idx in idxs[1:]:
            if 1 <= idx <= len(node.children):
                node = node.children[idx - 1]
            else:
                return None
        return node

    def add(
        self,
        parent_path: str,
        description: str,
        *,
        completed: bool = False,
    ) -> "PlanItem":
        """
        Append a new child under *parent_path*.

        Example:
            root.add("1.2", "Click OK")   # adds next child of node 1.2
            root.add("1",   "Settings")   # adds to root’s children
        """
        parent = self.get(parent_path)
        if parent is None:
            raise ValueError(f"Parent path does not exist: {parent_path!r}")

        return parent._add_child(description=description, completed=completed)
    
    # -------------------- pretty print ----------------------- #
    def _collect_lines(self, prefix: List[int], out: List[str]) -> None:
        out.append(f"[{'.'.join(map(str, prefix))}] {self.description}")
        for i, child in enumerate(self.children, start=1):
            child._collect_lines(prefix + [i], out)

    def __str__(self) -> str:  # noqa: D401
        lines: List[str] = []
        self._collect_lines([1], lines)
        return "\n".join(lines)

    class Config:
        arbitrary_types_allowed = True

class InitialPlan(BaseModel):
    plan_descriptions: List[str]

class CreatePlan(LMP):
    """LLM program that returns a Plan (possibly nested)."""

    prompt = """
You are tasked with creating a plan for navigating a webpage. The plan should be exhaustive in covering steps for every 
possible interaction with the current webpage. Here is the current webpage:
{{curr_page_contents}}

Guidelines for writing the plan:
- Refer to interactive elements by their visible label, not a numeric index.
- List higher-leverage interactions earlier.
- If a large task can be broken down, create sub-items inside that plan item. 
  Continue nesting until each leaf task is an atomic user interaction.

Return JSON that conforms to the Plan schema.
"""
    response_format: InitialPlan
    
    # def _process_result(self, res: InitialPlan, **prompt_args) -> PlanItem:
    #     # TODO: replace with URL?
    #     root = PlanItem(description="HomePage")
    #     for plan_description in res.plan_descriptions:
    #         root.add(plan_description)
    #     return root
        
# -------------------- example usage ----------------------- #

if __name__ == "__main__":
    root = PlanItem(description="Page")
    root.add_to_root("Subpage")
    root.add("1.1", "Click Me")
    root.add_to_root("Subpage 2")
    root.add_to_root("Profile")

    print(root)
    print("get('1.1') ->", root.get("1.1"))