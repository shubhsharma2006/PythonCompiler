from __future__ import annotations

import copy

from compiler.core.types import ValueType
from compiler.ir.analysis import compute_dominators, reachable_block_names, rebuild_edges
from compiler.ir.cfg import (
    Assign,
    BasicBlock,
    BinaryOp,
    BranchTerminator,
    Call,
    CFGFunction,
    CFGModule,
    DecRef,
    JumpTerminator,
    LoadConst,
    Phi,
    Print,
    ReturnTerminator,
    UnaryOp,
)


def immediate_dominators(function: CFGFunction) -> dict[str, str | None]:
    dominators = compute_dominators(function)
    idoms: dict[str, str | None] = {}
    for block_name, doms in dominators.items():
        if block_name == function.entry_block:
            idoms[block_name] = None
            continue
        strict = doms - {block_name}
        candidate = None
        for dom in strict:
            if all(dom == other or dom not in dominators.get(other, set()) for other in strict):
                candidate = dom
                break
        idoms[block_name] = candidate
    return idoms


def dominance_frontiers(function: CFGFunction) -> dict[str, set[str]]:
    rebuild_edges(function)
    idoms = immediate_dominators(function)
    frontiers = {block.name: set() for block in function.blocks}
    block_map = {block.name: block for block in function.blocks}

    for block in function.blocks:
        if len(block.predecessors) < 2:
            continue
        for pred in block.predecessors:
            runner = pred
            while runner is not None and runner != idoms.get(block.name):
                frontiers.setdefault(runner, set()).add(block.name)
                runner = idoms.get(runner)

    return frontiers


class SSATransformer:
    def transform(self, module: CFGModule) -> CFGModule:
        ssa_module = copy.deepcopy(module)
        self._transform_function(ssa_module.main)
        for function in ssa_module.functions:
            self._transform_function(function)
        return ssa_module

    def _transform_function(self, function: CFGFunction) -> None:
        rebuild_edges(function)
        frontiers = dominance_frontiers(function)
        block_map = {block.name: block for block in function.blocks}
        idoms = immediate_dominators(function)
        dom_tree = {block.name: [] for block in function.blocks}
        for block_name, idom in idoms.items():
            if idom is not None:
                dom_tree[idom].append(block_name)

        variables = self._phi_candidates(function)
        defsites = self._definition_sites(function, variables)
        for variable in variables:
            work = list(defsites.get(variable, set()))
            placed: set[str] = set()
            while work:
                block_name = work.pop()
                for frontier in frontiers.get(block_name, set()):
                    if frontier in placed:
                        continue
                    block = block_map[frontier]
                    phi = Phi(target=variable, variable=variable, inputs={}, value_type=self._value_type(function, variable))
                    block.phis.append(phi)
                    placed.add(frontier)
                    if frontier not in defsites.get(variable, set()):
                        work.append(frontier)

        counters: dict[str, int] = {}
        stacks = {variable: [] for variable in variables}
        self._rename_block(function.entry_block, block_map, dom_tree, counters, stacks)

    def _rename_block(self, block_name, block_map, dom_tree, counters, stacks):
        block = block_map[block_name]
        pushed: list[str] = []

        for phi in block.phis:
            new_name = self._new_name(phi.variable, counters)
            stacks[phi.variable].append(new_name)
            phi.target = new_name
            pushed.append(phi.variable)

        for instruction in block.instructions:
            self._rename_instruction_uses(instruction, stacks)
            defined = self._defined_name(instruction)
            if defined is not None and defined in stacks:
                new_name = self._new_name(defined, counters)
                self._rename_definition(instruction, new_name)
                stacks[defined].append(new_name)
                pushed.append(defined)

        self._rename_terminator(block.terminator, stacks)

        for successor_name in block.successors:
            successor = block_map[successor_name]
            for phi in successor.phis:
                stack = stacks.get(phi.variable)
                if stack:
                    phi.inputs[block.name] = stack[-1]

        for child_name in dom_tree.get(block_name, []):
            self._rename_block(child_name, block_map, dom_tree, counters, stacks)

        for variable in reversed(pushed):
            stacks[variable].pop()

    def _rename_instruction_uses(self, instruction, stacks):
        if isinstance(instruction, Assign):
            instruction.source = self._current_name(instruction.source, stacks)
        elif isinstance(instruction, BinaryOp):
            instruction.left = self._current_name(instruction.left, stacks)
            instruction.right = self._current_name(instruction.right, stacks)
        elif isinstance(instruction, UnaryOp):
            instruction.operand = self._current_name(instruction.operand, stacks)
        elif isinstance(instruction, Call):
            instruction.args = [self._current_name(arg, stacks) for arg in instruction.args]
        elif isinstance(instruction, DecRef):
            instruction.target = self._current_name(instruction.target, stacks)
        elif isinstance(instruction, Print):
            instruction.value = self._current_name(instruction.value, stacks)

    def _rename_terminator(self, terminator, stacks):
        if isinstance(terminator, BranchTerminator):
            terminator.condition = self._current_name(terminator.condition, stacks)
        elif isinstance(terminator, ReturnTerminator) and terminator.value is not None:
            terminator.value = self._current_name(terminator.value, stacks)

    @staticmethod
    def _defined_name(instruction):
        if isinstance(instruction, (LoadConst, Assign, BinaryOp, UnaryOp)):
            return instruction.target
        if isinstance(instruction, Call):
            return instruction.target
        return None

    @staticmethod
    def _rename_definition(instruction, new_name: str) -> None:
        instruction.target = new_name

    @staticmethod
    def _new_name(variable: str, counters: dict[str, int]) -> str:
        counters[variable] = counters.get(variable, 0) + 1
        return f"{variable}.{counters[variable]}"

    @staticmethod
    def _current_name(name: str, stacks) -> str:
        stack = stacks.get(name)
        if stack:
            return stack[-1]
        return name

    @staticmethod
    def _phi_candidates(function: CFGFunction) -> set[str]:
        candidates = {name for name, _ in function.params}
        candidates.update(name for name in function.locals if not name.startswith("_t"))
        return candidates

    @staticmethod
    def _definition_sites(function: CFGFunction, variables: set[str]) -> dict[str, set[str]]:
        defsites = {name: set() for name in variables}
        entry = next((block for block in function.blocks if block.name == function.entry_block), None)
        if entry is not None:
            for name, _ in function.params:
                if name in defsites:
                    defsites[name].add(entry.name)

        for block in function.blocks:
            for instruction in block.instructions:
                defined = SSATransformer._defined_name(instruction)
                if defined in defsites:
                    defsites[defined].add(block.name)
        return defsites

    @staticmethod
    def _value_type(function: CFGFunction, variable: str):
        for name, value_type in function.params:
            if name == variable:
                return value_type
        return function.locals.get(variable)


def ssa_defined_name(node) -> str | None:
    if isinstance(node, Phi):
        return node.target
    if isinstance(node, (LoadConst, Assign, BinaryOp, UnaryOp)):
        return node.target
    if isinstance(node, Call):
        return node.target
    return None


def ssa_uses(node) -> list[str]:
    if isinstance(node, Phi):
        return list(node.inputs.values())
    if isinstance(node, Assign):
        return [node.source]
    if isinstance(node, BinaryOp):
        return [node.left, node.right]
    if isinstance(node, UnaryOp):
        return [node.operand]
    if isinstance(node, Call):
        return list(node.args)
    if isinstance(node, Print):
        return [node.value]
    if isinstance(node, BranchTerminator):
        return [node.condition]
    if isinstance(node, ReturnTerminator) and node.value is not None:
        return [node.value]
    return []

    if isinstance(node, DecRef):
        return [node.target]

def replace_ssa_uses(node, resolve) -> None:
    if isinstance(node, Phi):
        node.inputs = {pred: resolve(name) for pred, name in node.inputs.items()}
    elif isinstance(node, Assign):
        node.source = resolve(node.source)
    elif isinstance(node, BinaryOp):
        node.left = resolve(node.left)
        node.right = resolve(node.right)
    elif isinstance(node, UnaryOp):
        node.operand = resolve(node.operand)
    elif isinstance(node, Call):
        node.args = [resolve(arg) for arg in node.args]
    elif isinstance(node, Print):
        node.value = resolve(node.value)
    elif isinstance(node, BranchTerminator):
        node.condition = resolve(node.condition)
    elif isinstance(node, ReturnTerminator) and node.value is not None:
        node.value = resolve(node.value)


class SSAConstantPropagation:
    def optimize(self, module: CFGModule) -> CFGModule:
        self._optimize_function(module.main)
        for function in module.functions:
            self._optimize_function(function)
        return module

    def _optimize_function(self, function: CFGFunction) -> None:
        changed = True
        while changed:
            changed = False
            constants = self._infer_constants(function)
            for block in function.blocks:
                lowered_phis: list[LoadConst] = []
                rewritten_phis = []
                for phi in block.phis:
                    const = constants.get(phi.target)
                    if const is not None:
                        lowered_phis.append(LoadConst(phi.target, const[0], const[1]))
                        changed = True
                        continue
                    rewritten_phis.append(phi)
                block.phis = rewritten_phis

                rewritten = []
                if lowered_phis:
                    rewritten.extend(lowered_phis)
                for instruction in block.instructions:
                    replacement = self._rewrite_instruction(instruction, constants)
                    if replacement is not instruction:
                        changed = True
                    rewritten.append(replacement)
                block.instructions = rewritten

                if block.terminator is not None:
                    replacement = self._rewrite_terminator(block.terminator, constants)
                    if replacement is not block.terminator:
                        changed = True
                    block.terminator = replacement

            if self._prune_unreachable(function):
                changed = True

    def _infer_constants(self, function: CFGFunction) -> dict[str, tuple[object, ValueType]]:
        defs = build_use_def_map(function)
        constants: dict[str, tuple[object, ValueType]] = {}
        changed = True
        while changed:
            changed = False
            for name, node in defs.items():
                const = self._node_constant(node, constants)
                if const is None:
                    continue
                if constants.get(name) != const:
                    constants[name] = const
                    changed = True
        return constants

    def _rewrite_instruction(self, instruction, constants: dict[str, tuple[object, ValueType]]):
        defined = ssa_defined_name(instruction)
        if defined is None:
            return instruction
        const = constants.get(defined)
        if const is not None and not (
            isinstance(instruction, LoadConst)
            and instruction.value == const[0]
            and instruction.value_type == const[1]
        ):
            return LoadConst(defined, const[0], const[1])
        return instruction

    def _rewrite_terminator(self, terminator, constants: dict[str, tuple[object, ValueType]]):
        if isinstance(terminator, BranchTerminator):
            condition = constants.get(terminator.condition)
            if condition is not None:
                target = terminator.true_target if bool(condition[0]) else terminator.false_target
                return JumpTerminator(target)
        return terminator

    @staticmethod
    def _prune_unreachable(function: CFGFunction) -> bool:
        rebuild_edges(function)
        reachable = reachable_block_names(function)
        if reachable == {block.name for block in function.blocks}:
            changed = False
        else:
            function.blocks = [block for block in function.blocks if block.name in reachable]
            changed = True
        rebuild_edges(function)
        for block in function.blocks:
            for phi in block.phis:
                filtered = {pred: name for pred, name in phi.inputs.items() if pred in block.predecessors}
                if filtered != phi.inputs:
                    phi.inputs = filtered
                    changed = True
        return changed

    def _node_constant(self, node, constants: dict[str, tuple[object, ValueType]]):
        if isinstance(node, LoadConst):
            return (node.value, node.value_type)
        if isinstance(node, Assign):
            return constants.get(node.source)
        if isinstance(node, Phi):
            incoming = [constants.get(value) for value in node.inputs.values()]
            if incoming and all(item is not None and item == incoming[0] for item in incoming):
                return incoming[0]
            return None
        if isinstance(node, UnaryOp):
            operand = constants.get(node.operand)
            if operand is None:
                return None
            if node.op == "-":
                return (-operand[0], node.value_type)
            if node.op == "!":
                return (not bool(operand[0]), ValueType.BOOL)
            return None
        if isinstance(node, BinaryOp):
            left = constants.get(node.left)
            right = constants.get(node.right)
            if left is None or right is None:
                return None
            folded = self._fold_binary(node.op, left[0], right[0])
            if folded is None:
                return None
            return (folded, node.value_type)
        return None

    @staticmethod
    def _fold_binary(op: str, left: object, right: object):
        if op == "+":
            return left + right
        if op == "-":
            return left - right
        if op == "*":
            return left * right
        if op == "/" and right != 0:
            return left / right
        if op == "%" and right != 0:
            return left % right
        if op == "==":
            return left == right
        if op == "!=":
            return left != right
        if op == "<":
            return left < right
        if op == "<=":
            return left <= right
        if op == ">":
            return left > right
        if op == ">=":
            return left >= right
        return None


class SSAValuePropagation:
    def optimize(self, module: CFGModule) -> CFGModule:
        self._optimize_function(module.main)
        for function in module.functions:
            self._optimize_function(function)
        return module

    def _optimize_function(self, function: CFGFunction) -> None:
        changed = True
        while changed:
            changed = False
            constants = self._collect_constants(function)
            for block in function.blocks:
                rewritten = []
                for instruction in block.instructions:
                    replacement = self._rewrite_instruction(instruction, constants)
                    if replacement is not instruction:
                        changed = True
                    rewritten.append(replacement)
                block.instructions = rewritten

    @staticmethod
    def _collect_constants(function: CFGFunction) -> dict[str, tuple[object, ValueType]]:
        constants: dict[str, tuple[object, ValueType]] = {}
        for block in function.blocks:
            for instruction in block.instructions:
                if isinstance(instruction, LoadConst):
                    constants[instruction.target] = (instruction.value, instruction.value_type)
        return constants

    def _rewrite_instruction(self, instruction, constants: dict[str, tuple[object, ValueType]]):
        if not isinstance(instruction, BinaryOp):
            return instruction

        left = constants.get(instruction.left)
        right = constants.get(instruction.right)

        replacement = self._simplify_binary(
            instruction.target,
            instruction.op,
            instruction.left,
            instruction.right,
            left,
            right,
            instruction.value_type,
        )
        return replacement or instruction

    @staticmethod
    def _simplify_binary(
        target: str,
        op: str,
        left_name: str,
        right_name: str,
        left_const: tuple[object, ValueType] | None,
        right_const: tuple[object, ValueType] | None,
        value_type: ValueType,
    ):
        if op == "+":
            if SSAValuePropagation._is_zero(left_const):
                return Assign(target, right_name)
            if SSAValuePropagation._is_zero(right_const):
                return Assign(target, left_name)

        if op == "-":
            if SSAValuePropagation._is_zero(right_const):
                return Assign(target, left_name)

        if op == "*":
            if SSAValuePropagation._is_one(left_const):
                return Assign(target, right_name)
            if SSAValuePropagation._is_one(right_const):
                return Assign(target, left_name)

        if op == "/":
            if value_type == ValueType.FLOAT and SSAValuePropagation._is_one(right_const):
                return Assign(target, left_name)

        return None

    @staticmethod
    def _is_zero(constant: tuple[object, ValueType] | None) -> bool:
        return constant is not None and constant[0] == 0 and constant[1] in (ValueType.INT, ValueType.FLOAT)

    @staticmethod
    def _is_one(constant: tuple[object, ValueType] | None) -> bool:
        return constant is not None and constant[0] == 1 and constant[1] in (ValueType.INT, ValueType.FLOAT)


def build_use_def_map(function: CFGFunction) -> dict[str, object]:
    defs: dict[str, object] = {}
    for block in function.blocks:
        for phi in block.phis:
            defined = ssa_defined_name(phi)
            if defined is not None:
                defs[defined] = phi
        for instruction in block.instructions:
            defined = ssa_defined_name(instruction)
            if defined is not None:
                defs[defined] = instruction
    return defs


class SSADeadCodeEliminator:
    def optimize(self, module: CFGModule) -> CFGModule:
        self._optimize_function(module.main)
        for function in module.functions:
            self._optimize_function(function)
        return module

    def _optimize_function(self, function: CFGFunction) -> None:
        defs = build_use_def_map(function)
        live_defs: set[str] = set()
        worklist: list[str] = []

        for block in function.blocks:
            for instruction in block.instructions:
                if self._is_side_effecting(instruction):
                    worklist.extend(ssa_uses(instruction))
            if block.terminator is not None:
                worklist.extend(ssa_uses(block.terminator))

        while worklist:
            name = worklist.pop()
            if name in live_defs:
                continue
            node = defs.get(name)
            if node is None:
                continue
            live_defs.add(name)
            worklist.extend(ssa_uses(node))

        for block in function.blocks:
            block.phis = [phi for phi in block.phis if phi.target in live_defs]
            kept = []
            for instruction in block.instructions:
                defined = ssa_defined_name(instruction)
                if defined is None:
                    kept.append(instruction)
                    continue
                if self._is_side_effecting(instruction) or defined in live_defs:
                    kept.append(instruction)
            block.instructions = kept

    @staticmethod
    def _is_side_effecting(instruction) -> bool:
        return isinstance(instruction, (Call, Print))


class SSACopyPropagation:
    def optimize(self, module: CFGModule) -> CFGModule:
        self._optimize_function(module.main)
        for function in module.functions:
            self._optimize_function(function)
        return module

    def _optimize_function(self, function: CFGFunction) -> None:
        changed = True
        while changed:
            changed = False
            replacements = self._collect_replacements(function)
            if not replacements:
                return

            def resolve(name: str) -> str:
                seen: set[str] = set()
                current = name
                while current in replacements and current not in seen:
                    seen.add(current)
                    current = replacements[current]
                return current

            for block in function.blocks:
                for phi in block.phis:
                    replace_ssa_uses(phi, resolve)
                for instruction in block.instructions:
                    replace_ssa_uses(instruction, resolve)
                if block.terminator is not None:
                    replace_ssa_uses(block.terminator, resolve)

                before_phi_count = len(block.phis)
                block.phis = [phi for phi in block.phis if phi.target not in replacements]
                if len(block.phis) != before_phi_count:
                    changed = True

                before_instr_count = len(block.instructions)
                block.instructions = [
                    instruction
                    for instruction in block.instructions
                    if ssa_defined_name(instruction) not in replacements
                ]
                if len(block.instructions) != before_instr_count:
                    changed = True

    def _collect_replacements(self, function: CFGFunction) -> dict[str, str]:
        replacements: dict[str, str] = {}
        for block in function.blocks:
            for phi in block.phis:
                replacement = self._trivial_phi_replacement(phi)
                if replacement is not None and replacement != phi.target:
                    replacements[phi.target] = replacement
            for instruction in block.instructions:
                if isinstance(instruction, Assign) and instruction.target and instruction.source:
                    replacements[instruction.target] = instruction.source
        return replacements

    @staticmethod
    def _trivial_phi_replacement(phi: Phi) -> str | None:
        values = {value for value in phi.inputs.values() if value != phi.target}
        if len(values) == 1:
            return next(iter(values))
        return None


class SSADestructor:
    def lower(self, module: CFGModule) -> CFGModule:
        lowered = copy.deepcopy(module)
        self._lower_function(lowered.main)
        for function in lowered.functions:
            self._lower_function(function)
        return lowered

    def _lower_function(self, function: CFGFunction) -> None:
        type_map = self._collect_types(function)
        rebuild_edges(function)
        block_map = {block.name: block for block in function.blocks}
        edge_blocks: list[BasicBlock] = []
        edge_counter = 0

        for block in list(function.blocks):
            if not block.phis:
                continue

            for predecessor_name in sorted(block.predecessors):
                assignments = []
                for phi in block.phis:
                    source = phi.inputs.get(predecessor_name)
                    if source is None:
                        continue
                    assignments.append(Assign(phi.target, source))
                    if phi.target not in type_map and phi.value_type is not None:
                        type_map[phi.target] = phi.value_type

                if not assignments:
                    continue

                predecessor = block_map[predecessor_name]
                edge_counter += 1
                edge_name = f"ssa_edge_{edge_counter}"
                edge_block = BasicBlock(
                    name=edge_name,
                    instructions=assignments,
                    terminator=JumpTerminator(block.name),
                )
                self._retarget_edge(predecessor, block.name, edge_name)
                edge_blocks.append(edge_block)
                block_map[edge_name] = edge_block

            block.phis = []

        function.blocks.extend(edge_blocks)
        rebuild_edges(function)
        self._sanitize_function_names(function, type_map)

    def _collect_types(self, function: CFGFunction) -> dict[str, ValueType]:
        type_map = {name: value_type for name, value_type in function.params}
        type_map.update(function.locals)

        changed = True
        while changed:
            changed = False
            for block in function.blocks:
                for phi in block.phis:
                    if type_map.get(phi.target) != phi.value_type:
                        type_map[phi.target] = phi.value_type
                        changed = True
                for instruction in block.instructions:
                    if isinstance(instruction, LoadConst):
                        if type_map.get(instruction.target) != instruction.value_type:
                            type_map[instruction.target] = instruction.value_type
                            changed = True
                    elif isinstance(instruction, BinaryOp):
                        if type_map.get(instruction.target) != instruction.value_type:
                            type_map[instruction.target] = instruction.value_type
                            changed = True
                    elif isinstance(instruction, UnaryOp):
                        if type_map.get(instruction.target) != instruction.value_type:
                            type_map[instruction.target] = instruction.value_type
                            changed = True
                    elif isinstance(instruction, Call) and instruction.target is not None:
                        if type_map.get(instruction.target) != instruction.value_type:
                            type_map[instruction.target] = instruction.value_type
                            changed = True
                    elif isinstance(instruction, Assign):
                        source_type = type_map.get(instruction.source)
                        if source_type is not None and type_map.get(instruction.target) != source_type:
                            type_map[instruction.target] = source_type
                            changed = True

        return type_map

    def _sanitize_function_names(self, function: CFGFunction, type_map: dict[str, ValueType]) -> None:
        mapping: dict[str, str] = {}

        for name, _ in function.params:
            mapping[name] = name
        for name in function.locals:
            mapping.setdefault(name, self._sanitize_name(name))
        for name in type_map:
            mapping.setdefault(name, self._sanitize_name(name))

        function.params = [(mapping.get(name, name), value_type) for name, value_type in function.params]
        param_names = {name for name, _ in function.params}
        function.locals = {
            mapping.get(name, name): value_type
            for name, value_type in type_map.items()
            if name not in param_names
        }
        function.globals_read = {mapping.get(name, name) for name in function.globals_read}
        function.ownership = {
            mapping.get(name, name): info
            for name, info in function.ownership.items()
        }
        for name, info in function.ownership.items():
            info.name = name

        for block in function.blocks:
            for instruction in block.instructions:
                self._rename_instruction(instruction, mapping)
            if block.terminator is not None:
                self._rename_terminator(block.terminator, mapping)

    @staticmethod
    def _retarget_edge(block: BasicBlock, old_target: str, new_target: str) -> None:
        terminator = block.terminator
        if isinstance(terminator, JumpTerminator):
            if terminator.target == old_target:
                terminator.target = new_target
            return
        if isinstance(terminator, BranchTerminator):
            if terminator.true_target == old_target:
                terminator.true_target = new_target
            if terminator.false_target == old_target:
                terminator.false_target = new_target

    @staticmethod
    def _sanitize_name(name: str) -> str:
        return name.replace(".", "__ssa_")

    @staticmethod
    def _rename_instruction(instruction, mapping: dict[str, str]) -> None:
        if isinstance(instruction, LoadConst):
            instruction.target = mapping.get(instruction.target, instruction.target)
        elif isinstance(instruction, Assign):
            instruction.target = mapping.get(instruction.target, instruction.target)
            instruction.source = mapping.get(instruction.source, instruction.source)
        elif isinstance(instruction, BinaryOp):
            instruction.target = mapping.get(instruction.target, instruction.target)
            instruction.left = mapping.get(instruction.left, instruction.left)
            instruction.right = mapping.get(instruction.right, instruction.right)
        elif isinstance(instruction, UnaryOp):
            instruction.target = mapping.get(instruction.target, instruction.target)
            instruction.operand = mapping.get(instruction.operand, instruction.operand)
        elif isinstance(instruction, Call):
            if instruction.target is not None:
                instruction.target = mapping.get(instruction.target, instruction.target)
            instruction.args = [mapping.get(arg, arg) for arg in instruction.args]
        elif isinstance(instruction, DecRef):
            instruction.target = mapping.get(instruction.target, instruction.target)
        elif isinstance(instruction, Print):
            instruction.value = mapping.get(instruction.value, instruction.value)

    @staticmethod
    def _rename_terminator(terminator, mapping: dict[str, str]) -> None:
        if isinstance(terminator, BranchTerminator):
            terminator.condition = mapping.get(terminator.condition, terminator.condition)
        elif isinstance(terminator, ReturnTerminator) and terminator.value is not None:
            terminator.value = mapping.get(terminator.value, terminator.value)
