# Compressed Codebase Assessment

## Inputs

- `graphify-out/graph.json`
- `graphify-out/GRAPH_REPORT.md`
- active `compiler/` source tree
- current tests and pipeline files

Notes:

- `graphify-out/graph.json` was built from commit `f8791219`
- current workspace `HEAD` is `5f62d39`
- `tools/export_graph.py` is not present in this workspace, so this assessment uses the existing graph artifact directly
- graph analysis below filters to the active `compiler/` tree and ignores structural graph edges like `contains` / `method`

## Executive Summary

The architecture is mostly clean at the package level and **acyclic at the file/module level**, but it is highly centralized around a small set of schema and orchestration modules:

- `compiler/core/ast.py`
- `compiler/core/types.py`
- `compiler/ir/cfg.py`
- `compiler/pipeline/`
- `compiler/vm/objects.py`

The biggest architectural issue is **hub concentration**, not circular imports.

The codebase has two very different maturity levels:

- `VM path`: broad language support, good tests, main semantic truth
- `native path`: real compiler infrastructure, but still a much narrower subset

If the goal is production readiness, the next work should focus on:

1. reducing central bottlenecks
2. documenting the true VM/native capability split
3. cleaning repo/tooling drift
4. expanding the native path in a controlled order

## Central Compiler Subsystems

### 1. Core schema layer

Files:

- `compiler/core/ast.py`
- `compiler/core/types.py`
- `compiler/core/signature.py`

Role:

- shared AST node model
- shared type/value model
- common function signature binding rules

Architectural meaning:

- this is the common language contract across frontend, semantic analysis, VM lowering, optimizer, and IR lowering
- it is the most reused layer in the codebase

### 2. Frontend

Files:

- `compiler/frontend/lexer.py`
- `compiler/frontend/owned_lexer.py`
- `compiler/frontend/parser/expr_parser.py`
- `compiler/frontend/parser/stmt_parser.py`
- `compiler/frontend/parser_legacy.py`
- `compiler/frontend/ast_lowering.py`

Role:

- tokenization
- owned parser path
- CPython-backed parse/lower path
- lowering parsed syntax into project AST

Architectural meaning:

- the frontend depends heavily on `core/ast.py`
- `ast_lowering.py`, `stmt_parser.py`, and `expr_parser.py` are major emitters into the AST layer

### 3. Semantic analysis

Files:

- `compiler/semantic/symbols.py`
- `compiler/semantic/resolver.py`
- `compiler/semantic/type_checker.py`
- `compiler/semantic/control_flow.py`
- `compiler/semantic/analyzer.py`

Role:

- symbol collection
- name resolution
- type inference/checking
- control-flow validation

Architectural meaning:

- semantic analysis is cleanly separated as a subsystem
- it is still tightly coupled to the monolithic AST/type model

### 4. VM execution lane

Files:

- `compiler/vm/lowering.py`
- `compiler/vm/interpreter.py`
- `compiler/vm/objects.py`
- `compiler/vm/errors.py`
- `compiler/vm/builtins.py`
- `compiler/vm/bytecode.py`

Role:

- lower AST to bytecode
- execute bytecode
- host runtime object model and helpers

Architectural meaning:

- this is the semantic source of truth for most implemented language features
- runtime helpers are concentrated in a few large modules

### 5. Native compilation lane

Files:

- `compiler/ir/cfg.py`
- `compiler/ir/lowering.py`
- `compiler/ir/ssa.py`
- `compiler/ir/passes.py`
- `compiler/backend/c_codegen.py`
- `compiler/runtime/c_runtime.py`

Role:

- lower AST to CFG IR
- optimize using SSA/passes
- emit C and runtime support

Architectural meaning:

- strong compiler infrastructure exists
- native feature surface is still intentionally limited

### 6. Orchestration layer

Files:

- `compiler/pipeline/`
- `compiler/cli/app.py`

Role:

- entrypoint selection
- frontend choice
- semantic passes
- VM execution
- native feature gating
- IR/codegen/runtime emission

Architectural meaning:

- the `pipeline/` package is the bridge between nearly every subsystem
- it is the main architectural choke point

## Graph Findings

## Overly-centralized modules

### Dependency sinks

These modules receive the most incoming compiler-file dependencies in the graph-derived file graph:

- `compiler/core/ast.py`: `533` incoming dependency weight
- `compiler/ir/cfg.py`: `151`
- `compiler/core/types.py`: `126`
- `compiler/vm/errors.py`: `58`
- `compiler/vm/objects.py`: `54`
- `compiler/vm/bytecode.py`: `36`

Meaning:

- `core/ast.py` and `core/types.py` are the dominant shared abstractions
- `ir/cfg.py` is the central native-IR schema bottleneck
- VM runtime internals are concentrated in `vm/errors.py` and `vm/objects.py`

### High fan-out modules

These modules push the most outward dependency weight:

- `compiler/frontend/ast_lowering.py`: `120`
- `compiler/ir/ssa.py`: `99`
- `compiler/frontend/parser/stmt_parser.py`: `85`
- `compiler/frontend/parser/expr_parser.py`: `76`
- `compiler/vm/interpreter.py`: `69`
- `compiler/semantic/type_checker.py`: `67`
- `compiler/semantic/resolver.py`: `61`
- `compiler/vm/lowering.py`: `61`
- `compiler/pipeline/` orchestration layer: `58`
- `compiler/ir/lowering.py`: `56`

Meaning:

- these are the highest-complexity implementation modules
- they are likely to accumulate maintenance cost fastest

## Dependency bottlenecks

### `compiler/core/ast.py`

Biggest file-to-file edges:

- `frontend/ast_lowering.py -> core/ast.py`: `118`
- `frontend/parser/stmt_parser.py -> core/ast.py`: `76`
- `frontend/parser/expr_parser.py -> core/ast.py`: `71`
- `vm/lowering.py -> core/ast.py`: `50`
- `semantic/type_checker.py -> core/ast.py`: `49`
- `semantic/resolver.py -> core/ast.py`: `49`
- `optimizer/folding.py -> core/ast.py`: `41`
- orchestration layer -> `core/ast.py`: `37`
- `ir/lowering.py -> core/ast.py`: `20`

Interpretation:

- AST is a god-schema module
- almost every major phase depends on it directly
- any AST change has wide ripple cost

### `compiler/core/types.py`

Strong consumers:

- `core/ast.py -> core/types.py`: `56`
- `ir/cfg.py -> core/types.py`: `30`
- `semantic/type_checker.py -> core/types.py`: `10`

Interpretation:

- semantic type concepts and backend/native type concepts are still packed into one shared center

### `compiler/ir/cfg.py`

Strong consumers:

- `ir/ssa.py -> ir/cfg.py`: `86`
- `ir/lowering.py -> ir/cfg.py`: `35`
- `ir/passes.py -> ir/cfg.py`: `22`

Interpretation:

- CFG schema, IR instructions, and pass protocols are concentrated in one place
- this is the native backend’s core bottleneck

### `compiler/pipeline/`

It does not have the highest raw edge count, but it has the highest bridging score in the graph sample and acts as the orchestration hotspot.

Interpretation:

- it knows too much about frontend selection, semantic flow, VM execution, native feature gates, import loading, runtime emission, and `gcc` invocation
- this is the clearest “architecture choke point” in the project

## Cyclic dependencies

### Result

No circular dependencies were detected at the compiler file/module level in either:

- the filtered graph-derived dependency graph
- a static Python import-graph cross-check over the `compiler/` tree

That is a real architectural positive.

### Caveat

The graph still shows high centralization. Lack of cycles does **not** mean low coupling.

## Architecture hotspots

### Hotspot 1. Shared schema concentration

Hot files:

- `compiler/core/ast.py`
- `compiler/core/types.py`

Risk:

- schema changes ripple through frontend, semantic, optimizer, VM, and IR layers

### Hotspot 2. Native IR concentration

Hot files:

- `compiler/ir/cfg.py`
- `compiler/ir/ssa.py`
- `compiler/ir/lowering.py`

Risk:

- IR representation and pass logic are tightly clustered
- this increases regression risk when expanding native features

### Hotspot 3. VM runtime concentration

Hot files:

- `compiler/vm/objects.py`
- `compiler/vm/interpreter.py`
- `compiler/vm/errors.py`

Risk:

- runtime semantics, callable dispatch, attribute/index behavior, and exception behavior are concentrated in a small area

### Hotspot 4. Frontend emitter concentration

Hot files:

- `compiler/frontend/ast_lowering.py`
- `compiler/frontend/parser/stmt_parser.py`
- `compiler/frontend/parser/expr_parser.py`

Risk:

- syntax feature growth will keep landing in a few large files

### Hotspot 5. Orchestration concentration

Hot file:

- `compiler/pipeline/`

Risk:

- too many system-level decisions live in one module

## High coupling areas

### Frontend -> Core

Cross-subsystem dependency weight: `269`

Meaning:

- frontend is directly coupled to the full AST model, not a narrower construction interface

### Semantic -> Core

Cross-subsystem dependency weight: `142`

Meaning:

- semantic passes are tightly bound to shared AST/types representations

### IR -> Core

Cross-subsystem dependency weight: `59`

Meaning:

- the native path still depends directly on the high-level AST/type layer rather than a thinner lowered boundary

### VM -> Core

Cross-subsystem dependency weight: `51`

Meaning:

- the VM lowering/runtime stack still depends directly on shared high-level schema

## Suggested subsystem separation improvements

### 1. Split `compiler/pipeline/` further

Recommended split:

- `compiler/pipeline/analyze.py`
- `compiler/pipeline/execute_vm.py`
- `compiler/pipeline/compile_native.py`
- `compiler/pipeline/feature_gates.py`
- `compiler/pipeline/import_loader.py`

Why:

- reduces orchestration bottleneck
- makes VM/native flows independently easier to reason about

### 2. Break up `compiler/core/ast.py`

Recommended split:

- statements
- expressions
- module/function/class nodes
- spans/common node base

Why:

- AST is the single biggest coupling magnet in the codebase
- this will not remove coupling by itself, but it will reduce edit blast radius

### 3. Separate semantic types from backend/runtime types in `compiler/core/types.py`

Recommended split:

- semantic type model
- codegen/runtime/native type mapping

Why:

- current type center is shared too broadly

### 4. Split `compiler/ir/cfg.py`

Recommended split:

- IR instruction/node definitions
- CFG container structures
- ownership/exception metadata hooks

Why:

- `ir/cfg.py` is the native backend schema bottleneck

### 5. Split `compiler/vm/objects.py`

Recommended split:

- object model
- attribute access/binding
- index/container helpers
- callable invocation
- exception matching helpers

Why:

- it is a runtime hotspot and will keep growing

### 6. Introduce explicit capability tables

Recommended new docs/code boundary:

- `docs/feature_matrix.md`
- `compiler/capabilities/` or equivalent

Why:

- the implementation is ahead of the README
- VM/native support is now too large to track informally

## Refactoring priorities

### Priority 0: truth and hygiene

Do first.

1. Update `README.md` to match current tested behavior.
2. Add a VM vs native feature matrix.
3. Remove tracked generated artifacts and legacy root clutter from source control where possible.
4. Regenerate the graph from current `HEAD` and keep it fresh.

Current drift examples:

- README still says decorators, comprehensions, keyword-only parameters, `*args`, `**kwargs`, and starred unpacking are unsupported, but the VM tests cover several of them
- README understates the current native `try` / `finally` support

### Priority 1: architecture bottlenecks

1. Continue splitting `compiler/pipeline/`.
2. Split `compiler/vm/objects.py`.
3. Split `compiler/ir/cfg.py`.
4. Start shrinking direct dependence on `compiler/core/ast.py`.

### Priority 2: production-readiness gaps

1. Add lint/format/type-check CI gates.
2. Add parser and frontend fuzz/property tests.
3. Add native runtime stress tests for memory and exception-heavy paths.
4. Define a language subset spec instead of relying on README prose only.

### Priority 3: next implementation target

Best next native feature:

- lists / tuples
- indexing
- `len(...)`

Why:

- currently rejected by native compilation
- high user value
- lower risk than native imports, closures, classes, or generators
- forces runtime and ownership design to mature in a useful direction

## Production-Ready Gaps

The main gaps are:

- VM/native mismatch is still large
- documentation is not yet the source of truth
- graph/tooling freshness is weak
- no formal language contract exists
- repo root still contains historical and generated clutter
- native backend still lacks major real-program features

## Bottom Line

### Architectural bottlenecks

- `compiler/core/ast.py`
- `compiler/core/types.py`
- `compiler/ir/cfg.py`
- `compiler/pipeline/`
- `compiler/vm/objects.py`

### Circular dependencies

- none detected at compiler file/module level

### Over-centralized modules

- `core/ast.py` as schema hub
- `core/types.py` as shared type hub
- `pipeline/` as orchestration hub
- `ir/cfg.py` as native backend schema hub
- `vm/objects.py` as VM runtime hub

### Best next refactor

- continue simplifying `compiler/pipeline/`

### Best next feature

- native containers + indexing + `len(...)`

### Best production-readiness move

- create a real feature matrix and bring docs/repo structure back in sync with the implementation
