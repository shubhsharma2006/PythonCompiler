from __future__ import annotations

from compiler.ir.cfg import BranchTerminator, Call, CFGFunction, JumpTerminator, ReturnTerminator


def block_map(function: CFGFunction) -> dict[str, object]:
    return {block.name: block for block in function.blocks}


def reachable_block_names(function: CFGFunction) -> set[str]:
    blocks = block_map(function)
    if function.entry_block not in blocks:
        return set()

    seen: set[str] = set()
    stack = [function.entry_block]
    while stack:
        name = stack.pop()
        if name in seen:
            continue
        seen.add(name)
        block = blocks[name]
        # include exceptional successors so exception-only paths remain reachable
        succs = set(block.successors)
        if hasattr(block, "exceptional_successors"):
            succs |= set(block.exceptional_successors)
        stack.extend(sorted(succs - seen))
    return seen


def reverse_post_order(function: CFGFunction) -> list[str]:
    blocks = block_map(function)
    if function.entry_block not in blocks:
        return []

    seen: set[str] = set()
    order: list[str] = []

    def dfs(name: str) -> None:
        if name in seen:
            return
        seen.add(name)
        for successor in sorted(blocks[name].successors):
            dfs(successor)
        order.append(name)

    dfs(function.entry_block)
    order.reverse()
    return order


def compute_dominators(function: CFGFunction) -> dict[str, set[str]]:
    blocks = block_map(function)
    order = reverse_post_order(function)
    if not order:
        return {}

    all_blocks = set(order)
    dominators: dict[str, set[str]] = {}
    for name in order:
        if name == function.entry_block:
            dominators[name] = {name}
        else:
            dominators[name] = set(all_blocks)

    changed = True
    while changed:
        changed = False
        for name in order[1:]:
            predecessors = blocks[name].predecessors
            if not predecessors:
                new_dom = {name}
            else:
                pred_sets = [dominators[pred] for pred in predecessors if pred in dominators]
                new_dom = set.intersection(*pred_sets) if pred_sets else set()
                new_dom.add(name)
            if new_dom != dominators[name]:
                dominators[name] = new_dom
                changed = True

    return dominators


def compute_post_dominators(function: CFGFunction) -> dict[str, set[str]]:
    blocks = block_map(function)
    rebuild_edges(function)
    if not blocks:
        return {}

    exits = [block.name for block in function.blocks if isinstance(block.terminator, ReturnTerminator)]
    if not exits:
        exits = [function.entry_block]

    all_blocks = set(blocks.keys())
    postdominators: dict[str, set[str]] = {}
    for name in blocks:
        if name in exits:
            postdominators[name] = {name}
        else:
            postdominators[name] = set(all_blocks)

    changed = True
    while changed:
        changed = False
        for name, block in blocks.items():
            if name in exits:
                continue
            successors = block.successors
            if not successors:
                new_post = {name}
            else:
                succ_sets = [postdominators[s] for s in successors if s in postdominators]
                new_post = set.intersection(*succ_sets) if succ_sets else set()
                new_post.add(name)
            if new_post != postdominators[name]:
                postdominators[name] = new_post
                changed = True

    return postdominators


def immediate_post_dominators(function: CFGFunction) -> dict[str, str | None]:
    postdoms = compute_post_dominators(function)
    idoms: dict[str, str | None] = {}
    for block_name, doms in postdoms.items():
        strict = doms - {block_name}
        candidate = None
        for dom in strict:
            if all(dom == other or dom not in postdoms.get(other, set()) for other in strict):
                candidate = dom
                break
        idoms[block_name] = candidate
    return idoms


def rebuild_edges(function: CFGFunction) -> None:
    blocks = block_map(function)
    for block in function.blocks:
        block.predecessors.clear()
        block.successors.clear()
        block.exceptional_predecessors.clear()
        block.exceptional_successors.clear()

    for block in function.blocks:
        for instruction in block.instructions:
            if isinstance(instruction, Call) and instruction.can_raise and instruction.exception_target:
                if instruction.exception_target in blocks:
                    block.exceptional_successors.add(instruction.exception_target)
                    blocks[instruction.exception_target].exceptional_predecessors.add(block.name)
        terminator = block.terminator
        if isinstance(terminator, JumpTerminator):
            block.successors.add(terminator.target)
            if terminator.target in blocks:
                blocks[terminator.target].predecessors.add(block.name)
        elif isinstance(terminator, BranchTerminator):
            for target in (terminator.true_target, terminator.false_target):
                block.successors.add(target)
                if target in blocks:
                    blocks[target].predecessors.add(block.name)
