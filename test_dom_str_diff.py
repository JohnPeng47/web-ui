import re
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional, Set
import difflib

DOM1 = """
Interactive Elements: |SCROLL|<mat-sidenav-content /> (0.5 pages above, 0.1 pages below)
\t[1]<div aria-label=Click for more information about the product />
\t\t[2]<img role=button alt=Apple Juice (1000ml) />
\t[3]<div aria-label=Click for more information about the product />
\t\t[4]<img role=button alt=Apple Pomace />
\t[5]<div aria-label=Click for more information about the product />
\t\t[6]<img role=button alt=Banana Juice (1000ml) />
\t[7]<div aria-label=Click for more information about the product />
\t\t[8]<img role=button alt=Best Juice Shop Salesman Artwork />
\t[9]<div aria-label=Click for more information about the product />
\t\t[10]<img role=button alt=Carrot Juice (1000ml) />
\t\t[11]<div />
\t\t\t[12]<div />
\t\t\t\tCarrot Juice (1000ml)
\t\t\t[13]<div />
\t\t\t\t[14]<span />
\t\t\t\t\t2.99¤
\t[15]<div aria-label=Click for more information about the product />
\t\t[16]<img role=button alt=Eggfruit Juice (500ml) />
\t\t[17]<div />
\t\t\t[18]<div />
\t\t\t\tEggfruit Juice (500ml)
\t\t\t[19]<div />
\t\t\t\t[20]<span />
\t\t\t\t\t8.99¤
\t[21]<div aria-label=Click for more information about the product />
\t\t[22]<img role=button alt=Fruit Press />
\t\t[23]<div />
\t\t\t[24]<div />
\t\t\t\tFruit Press
\t\t\t[25]<div />
\t\t\t\t[26]<span />
\t\t\t\t\t89.99¤
\t[27]<div aria-label=Click for more information about the product />
\t\t[28]<img role=button alt=Green Smoothie />
\t\t[29]<div />
\t\t\t[30]<div />
\t\t\t\tGreen Smoothie
\t\t\t[31]<div />
\t\t\t\t[32]<span />
\t\t\t\t\t1.99¤
\tOnly 1 left
\t[33]<div aria-label=Click for more information about the product />
\t\t[34]<img role=button alt=Juice Shop "Permafrost" 2020 Edition />
\t\t[35]<div />
\t\t\t[36]<div />
\t\t\t\tJuice Shop "Permafrost" 2020 Edition
\t\t\t[37]<div />
\t\t\t\t[38]<span />
\t\t\t\t\t9999.99¤
\t[39]<div aria-label=Click for more information about the product />
\t\t[40]<img role=button alt=Lemon Juice (500ml) />
\t\t[41]<div />
\t\t\t[42]<div />
\t\t\t\tLemon Juice (500ml)
\t\t\t[43]<div />
\t\t\t\t[44]<span />
\t\t\t\t\t2.99¤
\tOnly 3 left
\t[45]<div aria-label=Click for more information about the product />
\t\t[46]<img role=button alt=Melon Bike (Comeback-Product 2018 Edition) />
\t\t[47]<div />
\t\t\t[48]<div />
\t\t\t\tMelon Bike (Comeback-Product 2018 Edition)
\t\t\t[49]<div />
\t\t\t\t[50]<span />
\t\t\t\t\t2999¤
\tSold Out
\t[51]<div aria-label=Click for more information about the product />
\t\t[52]<img role=button alt=OWASP Juice Shop "King of the Hill" Facemask />
\t\t[53]<div />
\t\t\t[54]<div />
\t\t\t\tOWASP Juice Shop "King of the Hill" Facemask
\t\t\t[55]<div />
\t\t\t\t[56]<span />
\t\t\t\t\t13.49¤
"""

DOM2 = """
Interactive Elements: |SCROLL|<mat-sidenav-content /> (0.2 pages above, 0.4 pages below)
\t[1]<div aria-label=Click for more information about the product />
\t\t[2]<img role=button alt=Apple Juice (1000ml) />
\t\t[3]<div />
\t\t\t[4]<div />
\t\t\t\tApple Juice (1000ml)
\t\t\t[5]<div />
\t\t\t\t[6]<span />
\t\t\t\t\t1.99¤
\t[7]<div aria-label=Click for more information about the product />
\t\t[8]<img role=button alt=Apple Pomace />
\t\t[9]<div />
\t\t\t[10]<div />
\t\t\t\tApple Pomace
\t\t\t[11]<div />
\t\t\t\t[12]<span />
\t\t\t\t\t0.89¤
\t[13]<div aria-label=Click for more information about the product />
\t\t[14]<img role=button alt=Banana Juice (1000ml) />
\t\t[15]<div />
\t\t\t[16]<div />
\t\t\t\tBanana Juice (1000ml)
\t\t\t[17]<div />
\t\t\t\t[18]<span />
\t\t\t\t\t1.99¤
\tOnly 1 left
\t[19]<div aria-label=Click for more information about the product />
\t\t[20]<img role=button alt=Best Juice Shop Salesman Artwork />
\t\t[21]<div />
\t\t\t[22]<div />
\t\t\t\tBest Juice Shop Salesman Artwork
\t\t\t[23]<div />
\t\t\t\t[24]<span />
\t\t\t\t\t5000¤
\t[25]<div aria-label=Click for more information about the product />
\t\t[26]<img role=button alt=Carrot Juice (1000ml) />
\t\t[27]<div />
\t\t\t[28]<div />
\t\t\t\tCarrot Juice (1000ml)
\t\t\t[29]<div />
\t\t\t\t[30]<span />
\t\t\t\t\t2.99¤
\t[31]<div aria-label=Click for more information about the product />
\t\t[32]<img role=button alt=Eggfruit Juice (500ml) />
\t\t[33]<div />
\t\t\t[34]<div />
\t\t\t\tEggfruit Juice (500ml)
\t\t\t[35]<div />
\t\t\t\t[36]<span />
\t\t\t\t\t8.99¤
\t[37]<div aria-label=Click for more information about the product />
\t\t[38]<img role=button alt=Fruit Press />
\t\t[39]<div />
\t\t\t[40]<div />
\t\t\t\tFruit Press
\t\t\t[41]<div />
\t\t\t\t[42]<span />
\t\t\t\t\t89.99¤
\t[43]<div aria-label=Click for more information about the product />
\t\t[44]<img role=button alt=Green Smoothie />
\t\t[45]<div />
\t\t\t[46]<div />
\t\t\t\tGreen Smoothie
\t\t\t[47]<div />
\t\t\t\t[48]<span />
\t\t\t\t\t1.99¤
\tOnly 1 left
\t[49]<div aria-label=Click for more information about the product />
\t\t[50]<img role=button alt=Juice Shop "Permafrost" 2020 Edition />
\t\t[51]<div />
\t\t\t[52]<div />
\t\t\t\tJuice Shop "Permafrost" 2020 Edition
\t[53]<div aria-label=Click for more information about the product />
\t\t[54]<img role=button alt=Lemon Juice (500ml) />
\t\t[55]<div />
\t\t\t[56]<div />
\t\t\t\tLemon Juice (500ml)
\tOnly 3 left
\t[57]<div aria-label=Click for more information about the product />
\t\t[58]<img role=button alt=Melon Bike (Comeback-Product 2018 Edition) />
\t\t[59]<div />
\t\t\t[60]<div />
\t\t\t\tMelon Bike (Comeback-Product 2018 Edition)
\tSold Out
\t[61]<div aria-label=Click for more information about the product />
\t\t[62]<img role=button alt=OWASP Juice Shop "King of the Hill" Facemask />
\t\t[63]<div />
\t\t\t[64]<div />
\t\t\t\tOWASP Juice Shop "King of the Hill" Facemask
[65]<mat-dialog-container role=dialog />
\tApple Juice (1000ml)
\tThe all-time classic.
\t[66]<p />
\t\t1.99¤
\t[67]<mat-divider role=separator />
\t[68]<button />
\t[69]<mat-expansion-panel-header role=button />
\t\t[70]<span />
\t\t\t[71]<mat-panel-title />
\t\t\t\t[72]<span />
\t\t\t\t\tReviews
\t\t\t\t[73]<span />
\t\t\t\t\t(1)
\t\t[74]<span />
\t[75]<mat-divider role=separator />
\t[76]<button aria-label=Close Dialog type=button />
\t\tclose
\t\tClose
"""

@dataclass
class Node:
    idx: int
    sig: str
    depth: int
    line_no: int
    raw_line: str
    parent: Optional[int] = None  # node id (internal)
    children: List[int] = field(default_factory=list)
    path_sig: Tuple[str, ...] = field(default_factory=tuple)
    sib_index: int = 0  # order among siblings

def normalize_sig(sig: str) -> str:
    # Collapse whitespace and strip
    s = re.sub(r"\s+", " ", sig.strip())
    return s

line_pat = re.compile(r"^(?P<indent>\t*)\[(?P<idx>\d+)\]\s*(?P<rest><.*)$")

def parse_dom(dom: str) -> Tuple[List[str], List[Node], Dict[int, int]]:
    """
    Returns: (lines, nodes, map from node idx to internal node id)
    """
    lines = dom.strip("\n").splitlines()
    nodes: List[Node] = []
    idx_to_nid: Dict[int, int] = {}
    depth_stack: List[int] = []  # internal node ids by depth
    last_at_depth: Dict[int, int] = {}

    for i, line in enumerate(lines):
        m = line_pat.match(line)
        if not m:
            continue
        depth = len(m.group("indent"))
        idx = int(m.group("idx"))
        rest = m.group("rest")
        sig = normalize_sig(rest)
        n = Node(idx=idx, sig=sig, depth=depth, line_no=i, raw_line=line)
        nid = len(nodes)
        nodes.append(n)
        idx_to_nid[idx] = nid

        # Fix depth stack
        # Ensure stack length == depth
        while len(depth_stack) > depth:
            depth_stack.pop()
        if len(depth_stack) == depth and depth > 0:
            # sibling under same parent
            pass
        elif len(depth_stack) < depth:
            # new deeper level; should be +1
            # if not, we still allow but fill with last known
            while len(depth_stack) < depth:
                depth_stack.append(depth_stack[-1] if depth_stack else -1)

        # parent
        parent_nid = depth_stack[-1] if depth_stack else None
        if parent_nid is not None and parent_nid != -1:
            n.parent = parent_nid
            nodes[parent_nid].children.append(nid)
            # set sibling index
            n.sib_index = len(nodes[parent_nid].children) - 1
        else:
            n.parent = None
            n.sib_index = 0

        # push self as current at this depth
        if len(depth_stack) == depth:
            depth_stack.append(nid)
        else:
            depth_stack[depth] = nid

    # compute path signatures
    for nid, n in enumerate(nodes):
        path = []
        cur = nid
        while cur is not None and cur != -1:
            path.append(nodes[cur].sig)
            cur = nodes[cur].parent if nodes[cur].parent is not None else None
        n.path_sig = tuple(reversed(path))
    return lines, nodes, idx_to_nid

def count_by(items: List[Node], key=lambda n: n.sig) -> Dict[str, int]:
    d: Dict[str, int] = {}
    for n in items:
        k = key(n)
        d[k] = d.get(k, 0) + 1
    return d

def build_signature_index(nodes: List[Node]) -> Dict[str, List[int]]:
    idx: Dict[str, List[int]] = {}
    for nid, n in enumerate(nodes):
        idx.setdefault(n.sig, []).append(nid)
    return idx

def build_pathsig_index(nodes: List[Node]) -> Dict[Tuple[str, ...], List[int]]:
    idx: Dict[Tuple[str, ...], List[int]] = {}
    for nid, n in enumerate(nodes):
        idx.setdefault(n.path_sig, []).append(nid)
    return idx

def match_unique(a_nodes: List[Node], b_nodes: List[Node]) -> Dict[int, int]:
    a_by_sig = build_signature_index(a_nodes)
    b_by_sig = build_signature_index(b_nodes)
    a_by_path = build_pathsig_index(a_nodes)
    b_by_path = build_pathsig_index(b_nodes)

    match_a2b: Dict[int, int] = {}

    # unique by sig
    for sig, a_list in a_by_sig.items():
        if len(a_list) == 1 and len(b_by_sig.get(sig, [])) == 1:
            a_nid = a_list[0]
            b_nid = b_by_sig[sig][0]
            match_a2b[a_nid] = b_nid

    # unique by path
    for ps, a_list in a_by_path.items():
        if len(a_list) == 1 and len(b_by_path.get(ps, [])) == 1:
            a_nid = a_list[0]
            b_nid = b_by_path[ps][0]
            match_a2b[a_nid] = b_nid

    return match_a2b

def parent_lift(a_nodes: List[Node], b_nodes: List[Node], a2b: Dict[int, int]) -> int:
    progress = 0
    used_b: Set[int] = set(a2b.values())
    for a_nid, b_nid in list(a2b.items()):
        a_parent = a_nodes[a_nid].parent
        b_parent = b_nodes[b_nid].parent
        if a_parent is None or b_parent is None:
            continue
        if a_parent in a2b:
            continue
        if b_parent in used_b:
            continue
        # Safe to match the parents that actually contain the matched child
        a2b[a_parent] = b_parent
        used_b.add(b_parent)
        progress += 1
    return progress

def children_align_under_matched_parents(a_nodes: List[Node], b_nodes: List[Node], a2b: Dict[int, int]) -> int:
    progress = 0
    used_b: Set[int] = set(a2b.values())
    # for each matched parent pair, align children by signature groups and order
    for a_parent, b_parent in list(a2b.items()):
        a_kids = [cid for cid in a_nodes[a_parent].children if cid not in a2b]
        b_kids = [cid for cid in b_nodes[b_parent].children if cid not in used_b]
        if not a_kids or not b_kids:
            continue
        # group by signature
        sig_to_a = {}
        for cid in a_kids:
            sig_to_a.setdefault(a_nodes[cid].sig, []).append(cid)
        sig_to_b = {}
        for cid in b_kids:
            sig_to_b.setdefault(b_nodes[cid].sig, []).append(cid)
        # for each common signature, pair by order
        for sig in set(sig_to_a.keys()).intersection(sig_to_b.keys()):
            a_list = sig_to_a[sig]
            b_list = sig_to_b[sig]
            k = min(len(a_list), len(b_list))
            for i in range(k):
                ai = a_list[i]
                bi = b_list[i]
                if ai not in a2b and bi not in used_b:
                    a2b[ai] = bi
                    used_b.add(bi)
                    progress += 1
    return progress

def scored_greedy_for_ambiguous(a_nodes: List[Node], b_nodes: List[Node], a2b: Dict[int, int]) -> int:
    progress = 0
    used_b: Set[int] = set(a2b.values())
    a_by_sig = build_signature_index(a_nodes)
    b_by_sig = build_signature_index(b_nodes)
    # candidates only for signatures that exist in both
    for sig, a_list in a_by_sig.items():
        b_list = [nid for nid in b_by_sig.get(sig, []) if nid not in used_b]
        if not b_list:
            continue
        # collect unmatched A nodes of this signature
        a_unmatched = [nid for nid in a_list if nid not in a2b]
        for a_nid in a_unmatched:
            # score each candidate B by number of matched children they share
            a_children_mapped_to_b = set(a2b.get(cid) for cid in a_nodes[a_nid].children if cid in a2b)
            best_score = -1
            best_choice = None
            for b_nid in b_list:
                if b_nid in used_b:
                    continue
                b_child_set = set(b_nodes[b_nid].children)
                score = len(a_children_mapped_to_b.intersection(b_child_set))
                # tiebreaker: sibling position distance if they have parents matched
                if score >= 0:
                    tie = 0
                    a_par = a_nodes[a_nid].parent
                    if a_par is not None and a_par in a2b:
                        b_par = a2b[a_par]
                        # compute sibling positions among same-signature siblings
                        a_pos = a_nodes[a_nid].sib_index
                        b_pos = b_nodes[b_nid].sib_index
                        tie = -abs(a_pos - b_pos)
                    if (score, tie) > (best_score, -999999):
                        best_score = score
                        best_choice = b_nid
            if best_choice is not None and best_choice not in used_b:
                a2b[a_nid] = best_choice
                used_b.add(best_choice)
                progress += 1
    return progress

def rewrite_a_indices(a_lines: List[str], a_nodes: List[Node], a2b_idxmap: Dict[int, int]) -> List[str]:
    # Map from A original index -> B index
    def repl(m):
        a_idx = int(m.group(1))
        if a_idx in a2b_idxmap:
            return f"[{a2b_idxmap[a_idx]}]"
        return m.group(0)

    out = []
    for line in a_lines:
        # replace only the leading [n] if present
        out.append(re.sub(r"^\s*\[(\d+)\]", repl, line))
    return out

def run_diff(dom_a: str, dom_b: str):
    a_lines, a_nodes, a_idx2nid = parse_dom(dom_a)
    b_lines, b_nodes, b_idx2nid = parse_dom(dom_b)

    # initial anchors
    a2b_nid: Dict[int, int] = match_unique(a_nodes, b_nodes)

    # iterate expansion
    for _ in range(5):
        prog = 0
        prog += parent_lift(a_nodes, b_nodes, a2b_nid)
        prog += children_align_under_matched_parents(a_nodes, b_nodes, a2b_nid)
        prog += scored_greedy_for_ambiguous(a_nodes, b_nodes, a2b_nid)
        if prog == 0:
            break

    # build index mapping A.idx -> B.idx
    a2b_idx: Dict[int, int] = {a_nodes[a_nid].idx: b_nodes[b_nid].idx for a_nid, b_nid in a2b_nid.items()}

    # rewrite A
    a_rewritten = rewrite_a_indices(a_lines, a_nodes, a2b_idx)
    a_rewritten_str = "\n".join(a_rewritten)
    b_str = "\n".join(b_lines)

    # stats
    total_a = len(a_nodes)
    total_b = len(b_nodes)
    matched = len(a2b_nid)
    matched_b_unique = len(set(a2b_idx.values()))
    unmatched_a = total_a - matched
    unmatched_b = total_b - matched_b_unique

    print("=== Matching Stats ===")
    print(f"A indexed nodes: {total_a}")
    print(f"B indexed nodes: {total_b}")
    print(f"Matched pairs: {matched}")
    print(f"Unmatched in A: {unmatched_a}")
    print(f"Unmatched in B: {unmatched_b}")
    print()

    # show a compact unified diff of rewritten A vs B (first 80 lines)
    diff = list(difflib.unified_diff(
        a_rewritten_str.splitlines(keepends=False),
        b_str.splitlines(keepends=False),
        fromfile="A_rewritten",
        tofile="B",
        lineterm=""
    ))
    print("=== Unified diff (first 120 lines) ===")
    for i, line in enumerate(diff[:120]):
        print(line)

    return {
        "a_rewritten": a_rewritten_str,
        "b": b_str,
        "stats": {
            "A_indexed": total_a,
            "B_indexed": total_b,
            "matched": matched,
            "unmatched_A": unmatched_a,
            "unmatched_B": unmatched_b,
        },
    }

_ = run_diff(DOM1, DOM2)
