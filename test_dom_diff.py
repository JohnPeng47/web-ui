from browser_use.dom.views import from_json
from browser_use.dom.diff import diff_dom_trees
from browser_use.dom.serializer.serializer import DOMTreeSerializer

import json

# @file purpose: Serializes enhanced DOM trees to string format for LLM consumption
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from browser_use.dom.serializer.clickable_elements import ClickableElementDetector
from browser_use.dom.utils import cap_text_length
from browser_use.dom.views import (
    DOMRect,
    DOMSelectorMap,
    EnhancedDOMTreeNode,
    NodeType,
    PropagatingBounds,
    SerializedDOMState,
    SimplifiedNode,
)

with open("dom_tree_1.json") as f:
    dom1 = from_json(json.loads(f.read()))

with open("dom_tree_2.json") as f:
    dom2 = from_json(json.loads(f.read()))

results = diff_dom_trees(dom1, dom2)
parent_id = results.diff_parents[0]
dom2.print_tree()
print(parent_id)

# parent_node = dom2.find_child_by_id(parent_id.backend_dom_id, parent_id.target_id)
# print(parent_node.xpath)
# serialized_dom, _ = DOMTreeSerializer(parent_node).serialize_accessible_elements()
# print(serialized_dom.llm_representation())


