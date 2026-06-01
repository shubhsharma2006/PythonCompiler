# Graph Report - compiler project  (2026-05-27)

## Corpus Check
- 120 files · ~86,350 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1741 nodes · 4072 edges · 142 communities (111 shown, 31 thin omitted)
- Extraction: 61% EXTRACTED · 39% INFERRED · 0% AMBIGUOUS · INFERRED: 1581 edges (avg confidence: 0.63)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `735a1410`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- [[_COMMUNITY_Community 0|Community 0]]
- [[_COMMUNITY_Community 1|Community 1]]
- [[_COMMUNITY_Community 2|Community 2]]
- [[_COMMUNITY_Community 3|Community 3]]
- [[_COMMUNITY_Community 4|Community 4]]
- [[_COMMUNITY_Community 5|Community 5]]
- [[_COMMUNITY_Community 6|Community 6]]
- [[_COMMUNITY_Community 7|Community 7]]
- [[_COMMUNITY_Community 8|Community 8]]
- [[_COMMUNITY_Community 9|Community 9]]
- [[_COMMUNITY_Community 10|Community 10]]
- [[_COMMUNITY_Community 11|Community 11]]
- [[_COMMUNITY_Community 12|Community 12]]
- [[_COMMUNITY_Community 13|Community 13]]
- [[_COMMUNITY_Community 14|Community 14]]
- [[_COMMUNITY_Community 16|Community 16]]
- [[_COMMUNITY_Community 17|Community 17]]
- [[_COMMUNITY_Community 18|Community 18]]
- [[_COMMUNITY_Community 19|Community 19]]
- [[_COMMUNITY_Community 20|Community 20]]
- [[_COMMUNITY_Community 21|Community 21]]
- [[_COMMUNITY_Community 22|Community 22]]
- [[_COMMUNITY_Community 23|Community 23]]
- [[_COMMUNITY_Community 24|Community 24]]
- [[_COMMUNITY_Community 25|Community 25]]
- [[_COMMUNITY_Community 26|Community 26]]
- [[_COMMUNITY_Community 27|Community 27]]
- [[_COMMUNITY_Community 28|Community 28]]
- [[_COMMUNITY_Community 29|Community 29]]
- [[_COMMUNITY_Community 30|Community 30]]
- [[_COMMUNITY_Community 31|Community 31]]
- [[_COMMUNITY_Community 32|Community 32]]
- [[_COMMUNITY_Community 33|Community 33]]
- [[_COMMUNITY_Community 34|Community 34]]
- [[_COMMUNITY_Community 35|Community 35]]
- [[_COMMUNITY_Community 36|Community 36]]
- [[_COMMUNITY_Community 37|Community 37]]
- [[_COMMUNITY_Community 38|Community 38]]
- [[_COMMUNITY_Community 39|Community 39]]
- [[_COMMUNITY_Community 40|Community 40]]
- [[_COMMUNITY_Community 41|Community 41]]
- [[_COMMUNITY_Community 42|Community 42]]
- [[_COMMUNITY_Community 43|Community 43]]
- [[_COMMUNITY_Community 44|Community 44]]
- [[_COMMUNITY_Community 45|Community 45]]
- [[_COMMUNITY_Community 46|Community 46]]
- [[_COMMUNITY_Community 47|Community 47]]
- [[_COMMUNITY_Community 48|Community 48]]
- [[_COMMUNITY_Community 49|Community 49]]
- [[_COMMUNITY_Community 50|Community 50]]
- [[_COMMUNITY_Community 51|Community 51]]
- [[_COMMUNITY_Community 52|Community 52]]
- [[_COMMUNITY_Community 53|Community 53]]
- [[_COMMUNITY_Community 54|Community 54]]
- [[_COMMUNITY_Community 55|Community 55]]
- [[_COMMUNITY_Community 56|Community 56]]
- [[_COMMUNITY_Community 57|Community 57]]
- [[_COMMUNITY_Community 58|Community 58]]
- [[_COMMUNITY_Community 59|Community 59]]
- [[_COMMUNITY_Community 60|Community 60]]
- [[_COMMUNITY_Community 61|Community 61]]
- [[_COMMUNITY_Community 62|Community 62]]
- [[_COMMUNITY_Community 63|Community 63]]
- [[_COMMUNITY_Community 65|Community 65]]
- [[_COMMUNITY_Community 66|Community 66]]
- [[_COMMUNITY_Community 67|Community 67]]
- [[_COMMUNITY_Community 68|Community 68]]
- [[_COMMUNITY_Community 69|Community 69]]
- [[_COMMUNITY_Community 70|Community 70]]
- [[_COMMUNITY_Community 71|Community 71]]
- [[_COMMUNITY_Community 72|Community 72]]
- [[_COMMUNITY_Community 73|Community 73]]
- [[_COMMUNITY_Community 74|Community 74]]
- [[_COMMUNITY_Community 75|Community 75]]
- [[_COMMUNITY_Community 76|Community 76]]
- [[_COMMUNITY_Community 77|Community 77]]
- [[_COMMUNITY_Community 78|Community 78]]
- [[_COMMUNITY_Community 79|Community 79]]
- [[_COMMUNITY_Community 80|Community 80]]
- [[_COMMUNITY_Community 81|Community 81]]
- [[_COMMUNITY_Community 82|Community 82]]
- [[_COMMUNITY_Community 83|Community 83]]
- [[_COMMUNITY_Community 84|Community 84]]
- [[_COMMUNITY_Community 85|Community 85]]
- [[_COMMUNITY_Community 86|Community 86]]
- [[_COMMUNITY_Community 87|Community 87]]
- [[_COMMUNITY_Community 88|Community 88]]
- [[_COMMUNITY_Community 89|Community 89]]
- [[_COMMUNITY_Community 90|Community 90]]
- [[_COMMUNITY_Community 91|Community 91]]
- [[_COMMUNITY_Community 92|Community 92]]
- [[_COMMUNITY_Community 93|Community 93]]
- [[_COMMUNITY_Community 95|Community 95]]
- [[_COMMUNITY_Community 96|Community 96]]
- [[_COMMUNITY_Community 97|Community 97]]
- [[_COMMUNITY_Community 98|Community 98]]
- [[_COMMUNITY_Community 99|Community 99]]
- [[_COMMUNITY_Community 101|Community 101]]
- [[_COMMUNITY_Community 102|Community 102]]
- [[_COMMUNITY_Community 103|Community 103]]
- [[_COMMUNITY_Community 104|Community 104]]
- [[_COMMUNITY_Community 107|Community 107]]
- [[_COMMUNITY_Community 108|Community 108]]
- [[_COMMUNITY_Community 109|Community 109]]
- [[_COMMUNITY_Community 110|Community 110]]
- [[_COMMUNITY_Community 111|Community 111]]
- [[_COMMUNITY_Community 112|Community 112]]
- [[_COMMUNITY_Community 113|Community 113]]

## God Nodes (most connected - your core abstractions)
1. `ValueType` - 103 edges
2. `PipelineTests` - 101 edges
3. `StmtParser` - 83 edges
4. `BytecodeLowerer` - 82 edges
5. `TypeChecker` - 82 edges
6. `NameResolver` - 74 edges
7. `PythonSubsetLowerer` - 72 edges
8. `CFGLowering` - 64 edges
9. `ExprParser` - 63 edges
10. `compile_source()` - 60 edges

## Surprising Connections (you probably didn't know these)
- `main()` --calls--> `py_error_occurred()`  [INFERRED]
  output_try_finally.c → py_runtime.c
- `main()` --calls--> `py_clear_error()`  [INFERRED]
  output_try_finally.c → py_runtime.c
- `main()` --calls--> `py_write_float()`  [INFERRED]
  output.c → py_runtime.c
- `main()` --calls--> `py_truthy_int()`  [INFERRED]
  output_try_finally.c → py_runtime.c
- `parse()` --calls--> `ErrorHandler`  [INFERRED]
  parser.py → compiler/utils/error_handler.py

## Communities (142 total, 31 thin omitted)

### Community 0 - "Community 0"
Cohesion: 0.05
Nodes (95): CompilationResult, AssignStmt, AttributeAssignStmt, AttributeExpr, BinaryExpr, BoolOpExpr, BreakStmt, CallExpr (+87 more)

### Community 1 - "Community 1"
Cohesion: 0.05
Nodes (64): Exception, Protocol, str, _Host, VMRuntimeTests, _adapt_host_callable(), build_builtins(), builtin_isinstance() (+56 more)

### Community 2 - "Community 2"
Cohesion: 0.06
Nodes (10): bind_call_arguments(), can_truth_test(), is_numeric(), merge_types(), Scope, _import_binding_name(), _is_builtin_function(), _import_binding_name() (+2 more)

### Community 4 - "Community 4"
Cohesion: 0.07
Nodes (30): main(), add(), greet(), main(), square(), main(), gc_register(), gc_unregister() (+22 more)

### Community 5 - "Community 5"
Cohesion: 0.07
Nodes (24): _analyze_source(), check_source(), compile_source(), execute_source(), _load_bytecode_module(), _module_name_for_filename(), _program_uses_call_kwargs_splats(), _program_uses_call_signature_features() (+16 more)

### Community 6 - "Community 6"
Cohesion: 0.11
Nodes (35): compile_source(), _container_elem_type_for_expr(), _program_uses_len_with_non_string(), _program_uses_tuple_index_assign(), _program_uses_unsupported_container_literals(), _program_uses_unsupported_index_assign(), _program_uses_unsupported_indexing(), _program_uses_unsupported_slicing() (+27 more)

### Community 7 - "Community 7"
Cohesion: 0.1
Nodes (24): Enum, _Lexer, OwnedToken, Fully owned, indentation-aware Python lexer.  Replaces CPython's ``tokenize.gene, A single token produced by the owned lexer., Tokenize *source* into a list of :class:`OwnedToken` values.      Returns a ``(t, Internal state-machine lexer., tokenize_source() (+16 more)

### Community 8 - "Community 8"
Cohesion: 0.08
Nodes (22): build_use_def_map(), _collect_constants(), _current_name(), _defined_name(), _definition_sites(), dominance_frontiers(), _fold_binary(), immediate_dominators() (+14 more)

### Community 9 - "Community 9"
Cohesion: 0.05
Nodes (42): 1. Current State & Percentage Done, 1️⃣ Frontend — Lexer & Parser, 2️⃣ AST Lowering — Python `ast` → Internal AST, 2. What is Still Left to Implement?, 3. Next Steps: How to Proceed?, 3️⃣ Semantic Analysis, 3a. Name Resolver (`resolver.py`), 3b. Type Checker (`type_checker.py`) (+34 more)

### Community 10 - "Community 10"
Cohesion: 0.09
Nodes (17): parse_to_program(), Recursive descent statement parser — all stages (A through D)., Public entry: parse tokens into a Program AST directly., Public entry: parse tokens into a Program AST directly., Token stream cursor for the owned parser.  Provides :class:`TokenCursor` — a pos, Skip NEWLINE, NL, COMMENT, and ENCODING tokens., Build a SourceSpan from *start_token* to the previously consumed token., Navigates a flat ``list[LexToken]`` with single-token lookahead. (+9 more)

### Community 11 - "Community 11"
Cohesion: 0.09
Nodes (19): main(), run_cli_smoke(), run_negative_test(), run_positive_test(), run_quiet_mode_smoke(), run_source_test(), side(), test_break() (+11 more)

### Community 12 - "Community 12"
Cohesion: 0.11
Nodes (11): _build_type_map(), CCodeGenerator, _default_initializer(), _literal(), Generate a C function call., Generate a C function call., c_type_name(), CRuntimeSupport (+3 more)

### Community 13 - "Community 13"
Cohesion: 0.32
Nodes (24): FunctionType, Assign, BasicBlock, BinaryOp, BranchTerminator, CFGFunction, CFGModule, DecRef (+16 more)

### Community 14 - "Community 14"
Cohesion: 0.14
Nodes (11): Call, ExceptionalLivenessAnalysis, _instruction_defines(), _update_alive_set(), ExceptionCleanupLowering, Lower exception_live metadata into specialized cleanup blocks.      For each Cal, ExceptionCleanupValidation, Validate exception cleanup lowering.      Checks that every raising call with an (+3 more)

### Community 16 - "Community 16"
Cohesion: 0.07
Nodes (29): 🥇 1. Visualization Separated by Compiler Phase — Correct Architecture, 🥈 2. The SSA Visualization Design Is the Strongest Section, 🥉 3. Transformation Flow Modeled Correctly, 🏆 4. Cross-Layer Linkage Is the Real Killer Feature, 🧠 5. SSA Correctly Identified as the "Hero Phase", 🏆 Architectural Review — What This Is Really Becoming, code:block15 (before → transform → after), code:block16 (token → AST node → CFG block → SSA variable → machine instru) (+21 more)

### Community 17 - "Community 17"
Cohesion: 0.24
Nodes (3): LoadConst, CFGLowering, _container_suffix()

### Community 18 - "Community 18"
Cohesion: 0.22
Nodes (3): ASTVisualiser, ast_viz.py — AST Visualisation with Graphviz (Enhanced) ========================, visualise_ast()

### Community 20 - "Community 20"
Cohesion: 0.08
Nodes (23): 1️⃣ Full GC (Generational & Cycle Detection), 2️⃣ Python Standard Library (~250 Modules), 3️⃣ Async/Await, Generators, Threading, and GIL, 4️⃣ C Extension API & `ctypes`, 5️⃣ Full Python Object Model, 🚀 Advanced Features Architectural Roadmap, 📈 Complexity Assessment & Priority, 🔍 Current State (+15 more)

### Community 22 - "Community 22"
Cohesion: 0.09
Nodes (23): Build Order — Phase by Phase, code:block36 (compiler/frontend/parser/stmt_parser.py  ← fix BUG-001 (→ an), code:block37 (compiler/viz/__init__.py         ← create (1 line)), code:block38 (viz_server.py     ← HTTP + WebSocket server), code:block39 (ssa_viz.html     ← single HTML file), code:block40 (ssa_viz.html    ← add GSAP animations:), code:block41 (compiler/viz/events.py  ← add node_id tracking to every even), code:block42 (compiler/viz/ssa_tracer.py  ← add reason= to every event emi) (+15 more)

### Community 23 - "Community 23"
Cohesion: 0.17
Nodes (13): block_map(), compute_dominators(), compute_post_dominators(), immediate_post_dominators(), reachable_block_names(), rebuild_edges(), reverse_post_order(), _collect_uses() (+5 more)

### Community 24 - "Community 24"
Cohesion: 0.16
Nodes (4): Instruction, _collect_scope_declarations(), _import_binding_name(), _resolve_labels()

### Community 25 - "Community 25"
Cohesion: 0.1
Nodes (20): 1. Overall Completion Status, 2. What Is Working (VM Path), 3. What Is Missing (Hard Blockers), 4. Priority Roadmap, 5. Implementation Steps, 6. Antigravity Reference, 7. Milestones, After Fix (+12 more)

### Community 26 - "Community 26"
Cohesion: 0.15
Nodes (7): Legacy compatibility module.  The active semantic implementation lives in `compi, SemanticAnalyser, SemanticError, RuntimeError, SemanticAnalyzer, CompilerIssue, ErrorHandler

### Community 27 - "Community 27"
Cohesion: 0.21
Nodes (10): _analyze_source(), _normalize_program_for_frontend_compare(), check_source(), execute_source(), _load_bytecode_module(), _module_name_for_filename(), _resolve_import_path(), CompilationResult (+2 more)

### Community 28 - "Community 28"
Cohesion: 0.12
Nodes (16): Analyze only, code:bash (pip install -e .), code:bash (python3 main.py program.py), code:bash (python3 main.py program.py --check), code:bash (python3 main.py program.py --compile-native), code:bash (python3 main.py program.py --run-native), code:bash (python3 main.py program.py --dump tokens), code:bash (python3 -m compiler program.py) (+8 more)

### Community 29 - "Community 29"
Cohesion: 0.13
Nodes (15): Architecture, Bottom Line, Capability Contract, code:mermaid (flowchart LR), Current Development Priorities, Current native path, Current VM-supported surface, Explicitly unsupported today (+7 more)

### Community 30 - "Community 30"
Cohesion: 0.16
Nodes (8): parse(), Legacy compatibility module.  The active parser stage lives in `compiler.fronten, lower_cst(), ParsedModule, lex_source(), parse_source(), parse_tokens(), SourceFile

### Community 31 - "Community 31"
Cohesion: 0.13
Nodes (15): BUG-001: `return` annotation silently drops the function, BUG-002: Parameter annotations silently discarded, BUG-003: Augmented assignment only works on simple names, BUG-004: `with` statement only handles single context managers, BUG-005: `except` type only accepts bare names, BUG-006: `for` target only parses single names or simple tuples, BUG-007: Walrus operator in native lane causes silent wrong output, BUG-008: SSA name sanitization is fragile (+7 more)

### Community 32 - "Community 32"
Cohesion: 0.14
Nodes (14): Best Reading Of Overall Progress From Phase 1, code:text (source), code:text (source), Current Execution Flow, Immediate Remaining Work, Prioritized, Phase 1, Phase 1 Component Assessment, Phase 2 Candidates (+6 more)

### Community 33 - "Community 33"
Cohesion: 0.14
Nodes (14): code:block33 (┌───────────────────────────────────────────────────────────), code:block34 (┌───────────────────────────────────────────────────────────), code:python (@dataclass), From the Debugger Protocol, From the Visualization Design, How Each Feature from Both Ideas Maps to the Unified System, One-Line Summary of the Combined Vision, Revised Final Priority Order (Unified) (+6 more)

### Community 34 - "Community 34"
Cohesion: 0.14
Nodes (13): Builtins And Output, Core Control Flow, Data And Containers, Exceptions And Control Transfer, Feature Matrix, Functions And Calls, Modules And Context Management, Native is currently missing or intentionally restricted for (+5 more)

### Community 35 - "Community 35"
Cohesion: 0.15
Nodes (13): Best Reading Of Overall Progress After Phase 2, Frontend Ownership Status, Immediate Remaining Work, Prioritized, Phase 2, Phase 2 Component Assessment, Phase 3 Candidates, Semantic Pipeline Status, What Is Still Missing, Visible From This Phase (+5 more)

### Community 36 - "Community 36"
Cohesion: 0.15
Nodes (12): code:block47 (┌───────────────────────────────────────────────────────────), Development Tools, Gate 1 — Compiler Stability (Must Complete First), Gate 2 — Native Lane Stability (Must Complete Before Observatory SSA Phase), Gate: What the Compiler Needs to Be Before You Build the Observatory, JavaScript (Frontend — loaded from CDN, nothing to install), Python (Backend), 🗺️ Strategic Build Guide — Tools, Order, and the Honest Answer (+4 more)

### Community 37 - "Community 37"
Cohesion: 0.2
Nodes (8): ASTTransformer, ASTVisitor, visitor.py — Base Visitor pattern for AST traversal. All analysis/transform pass, Dispatch to the correct visit_* method based on node class name., Called when no specific visitor exists. Override for custom fallback., A visitor that returns transformed nodes.     Used for optimization passes that, Visit all child nodes listed in node.children (if defined)., Base visitor class implementing the Visitor Pattern.     Subclasses override vis

### Community 38 - "Community 38"
Cohesion: 0.35
Nodes (4): CFGConstantPropagation, _const_for_name(), _fold_binary(), _same_constant()

### Community 39 - "Community 39"
Cohesion: 0.18
Nodes (11): 1. 🧠 LLM-Powered Error Explanation Layer, 2. 🔮 AI-Assisted Type Inference, 3. 📈 AI-Powered Optimization Hints, 4. 🔬 Neural Constant Propagation, 5. 🧬 Self-Improving Compiler via Feedback Loops, 6. 🔗 Semantic Code Search, 7. 🤖 AI Code Generation / Completion, code:block6 (SyntaxError: only simple name augmented assignment is suppor) (+3 more)

### Community 40 - "Community 40"
Cohesion: 0.18
Nodes (10): **AI-Grade Compiler Potential: Massive — unique opportunity**, code:block1 (Source Code (.py)), 📊 Completion % Per Module, 📐 Full Pipeline at a Glance, 🐛 Known Bugs & Issues, 🟡 Medium Bugs, Overall: **~88% complete** for the defined VM-first Python subset, **Overall Production Grade: 73% / 100** (+2 more)

### Community 41 - "Community 41"
Cohesion: 0.18
Nodes (11): code:python (x = 10), code:python (DEBUG = False), code:python (i = 0), code:python (a = 42), code:python (x = 100), Constant Folding + Branch Pruning, Copy Chain Collapse, Dead Code Elimination (+3 more)

### Community 42 - "Community 42"
Cohesion: 0.18
Nodes (11): 2D Design, 2D Design, 2D Design, 2D Design, 3D Design, Phase 10 — Machine Code / Binary, Phase 2 — Syntax Analysis (Parsing), Phase 3 — AST Lowering (+3 more)

### Community 43 - "Community 43"
Cohesion: 0.2
Nodes (10): 🌐 3D Visualization Layer — Design Specification, Architecture: 7-Layer 3D Stack, code:block10 (Frontend:   Three.js + React (or Vanilla JS)), code:python (@dataclass), code:block9 (┌─────────────────────────┐  ← Layer 7: Native Binary / WASM), Concept: "The Compiler Observatory", Implementation Plan (3D Viz), Interaction Model (+2 more)

### Community 44 - "Community 44"
Cohesion: 0.2
Nodes (10): code:block1 (Source Code (text string)), 🚧 Drawbacks & Limitations, 📁 Files to Create, 🏁 Implementation Roadmap, 🔬 Live Compiler Visualization — Full Design Spec, Semantic Limitations, ✅ Status Checklist, Technical Limitations (+2 more)

### Community 45 - "Community 45"
Cohesion: 0.2
Nodes (10): Architecture Summary, Build Order for This Proposal, code:block28 (Compiler Process                     Debugger Client (browse), code:block32 (┌───────────────────────────────────────────────────────────), One-Line Summary, The Compiler Debugger Protocol (CDP), The Core Shift in Thinking, 💡 The Next Level — A Better Idea: The Compiler Debugger Protocol (+2 more)

### Community 46 - "Community 46"
Cohesion: 0.22
Nodes (8): Compressed Codebase Assessment, Dependency sinks, Executive Summary, Graph Findings, High fan-out modules, Inputs, Overly-centralized modules, Production-Ready Gaps

### Community 47 - "Community 47"
Cohesion: 0.22
Nodes (9): Best Reading Of Overall Progress After Phase 3, Builtin-Call Strategy, Bytecode Structure and Lowering, Phase 3, Phase 3 Component Assessment, Phase 4 Candidates, Runtime Value and Object Representation, What Is Still Missing, Visible From This Phase (+1 more)

### Community 48 - "Community 48"
Cohesion: 0.22
Nodes (8): Architectural Takeaways, Pending Future Sections, Phase 6 Component Assessment, Phase 6: Deep Dive into the Native Compilation Pipeline, Project Snapshot, PythonCompiler Knowledge Base, The Native Pipeline Deep Dive, What This Phase Answers

### Community 49 - "Community 49"
Cohesion: 0.22
Nodes (9): Layer 0 — Source Code Plane, Layer 1 — Token Stream, Layer 2 — AST (Abstract Syntax Tree), Layer 3 — Semantic Model, Layer 4 — CFG (Control Flow Graph), Layer 5 — SSA Graph, Layer 6 — C Code, Layer 7 — Binary / Output (+1 more)

### Community 51 - "Community 51"
Cohesion: 0.25
Nodes (8): Best Reading Of Overall Progress After Phase 4, Phase 4, Phase 4 Component Assessment, Phase 5 Candidates, The Native C Runtime Support, The Refactored Native Pipeline, What Is Still Missing, Visible From This Phase, What This Phase Answers

### Community 52 - "Community 52"
Cohesion: 0.25
Nodes (8): code:python (# Example: pause compilation when DCE tries to eliminate a b), code:block25 (Compilation history:), code:block26 (┌─────────────────────────┬─────────────────────────┐), code:block27 (my_program.crf), 💡 Idea 1: Compilation Breakpoints, 💡 Idea 2: Time-Travel Compilation (Fork & Replay), 💡 Idea 3: The Compilation Replay Format (.crf), The Three New Ideas

### Community 53 - "Community 53"
Cohesion: 0.25
Nodes (8): 1. "Blame" Mode, 2. Optimization Sensitivity Analysis, 3. Compiler Correctness Oracle, 4. Compiler as a Learning Tool (Classroom Mode), code:block29 ($ crf blame --instruction "x__ssa_3 = 42"), code:block30 (Pass Sensitivity Analysis for: loop_program.py), code:block31 (Correctness Check: loop_program.py), What This Enables (That Nothing Else Does)

### Community 54 - "Community 54"
Cohesion: 0.29
Nodes (7): 1. Core schema layer, 2. Frontend, 3. Semantic analysis, 4. VM execution lane, 5. Native compilation lane, 6. Orchestration layer, Central Compiler Subsystems

### Community 55 - "Community 55"
Cohesion: 0.29
Nodes (7): 1. Split `compiler/pipeline/` further, 2. Break up `compiler/core/ast.py`, 3. Separate semantic types from backend/runtime types in `compiler/core/types.py`, 4. Split `compiler/ir/cfg.py`, 5. Split `compiler/vm/objects.py`, 6. Introduce explicit capability tables, Suggested subsystem separation improvements

### Community 56 - "Community 56"
Cohesion: 0.29
Nodes (7): Architectural bottlenecks, Best next feature, Best next refactor, Best production-readiness move, Bottom Line, Circular dependencies, Over-centralized modules

### Community 58 - "Community 58"
Cohesion: 0.33
Nodes (6): Architecture hotspots, Hotspot 1. Shared schema concentration, Hotspot 2. Native IR concentration, Hotspot 3. VM runtime concentration, Hotspot 4. Frontend emitter concentration, Hotspot 5. Orchestration concentration

### Community 59 - "Community 59"
Cohesion: 0.33
Nodes (6): Conclusion: Project State, Phase 5, Phase 5 Component Assessment, Test Suite and Feature Verification, The Internal Native Pipeline Structure, What This Phase Answers

### Community 60 - "Community 60"
Cohesion: 0.33
Nodes (6): 1. Target: Educational & Research Compiler (Near Term), 2. Target: Production-Grade Compiler (Long Term), Conclusion, Project Completion Matrix & Roadmap, Roadmap: Educational/Research Compiler vs. Production-Grade, Subsystem Completion Status

### Community 61 - "Community 61"
Cohesion: 0.33
Nodes (6): Core Subsystems, Frontend, Native compiler, Orchestration, Semantic analysis, VM runtime

### Community 62 - "Community 62"
Cohesion: 0.33
Nodes (6): 1. Time-Travel Debugging, 2. Compiler-Aware IDE Plugin (VSCode), 3. Differential Compilation, 4. LLVM IR Backend, 5. JIT Compilation Mode, 💡 Other Unique Features to Add (AI-Grade Differentiators)

### Community 63 - "Community 63"
Cohesion: 0.33
Nodes (6): Phase 8 — SSA Optimization Passes, SSA Constant Propagation, SSA Copy Propagation, SSA Dead Code Elimination, SSA Destruction (Final Pass), SSA Value Propagation

### Community 65 - "Community 65"
Cohesion: 0.7
Nodes (4): build_parser(), _emit_dump(), main(), _maybe_emit_ast_viz()

### Community 66 - "Community 66"
Cohesion: 0.4
Nodes (5): Priority 0: truth and hygiene, Priority 1: architecture bottlenecks, Priority 2: production-readiness gaps, Priority 3: next implementation target, Refactoring priorities

### Community 67 - "Community 67"
Cohesion: 0.4
Nodes (5): Frontend -> Core, High coupling areas, IR -> Core, Semantic -> Core, VM -> Core

### Community 68 - "Community 68"
Cohesion: 0.4
Nodes (5): `compiler/core/ast.py`, `compiler/core/types.py`, `compiler/ir/cfg.py`, `compiler/pipeline/`, Dependency bottlenecks

### Community 69 - "Community 69"
Cohesion: 0.4
Nodes (5): 2D Design, code:block5 (B0: x = 10         B1: x = 20), code:block6 (B0: x.0 = 10      B1: x.1 = 20), code:block7 (x.0 ──────┐), Phase 7 — SSA Construction

### Community 70 - "Community 70"
Cohesion: 0.4
Nodes (5): 2D Design — Scope Visualization, 2D Design — Type Propagation, 3D Design, code:block3 (┌──────── Module Scope ──────────────────────┐), Phase 4 — Semantic Analysis

### Community 71 - "Community 71"
Cohesion: 0.4
Nodes (5): Scenario A: Educational Use, Scenario B: Debugging a Compiler Bug, Scenario C: Research — Optimization Exploration, Scenario D: Conference Demo, The Unified Interaction Model

### Community 72 - "Community 72"
Cohesion: 0.5
Nodes (3): Optimizer, Legacy compatibility module.  The active optimizer lives in `compiler.optimizer`, ConstantFolder

### Community 76 - "Community 76"
Cohesion: 0.5
Nodes (3): Error recovery utilities for the owned parser.  Provides :func:`synchronize` whi, Advance *cursor* past tokens until a likely statement boundary.      This allows, synchronize()

### Community 77 - "Community 77"
Cohesion: 0.5
Nodes (4): Broadly available on the native lane, Broadly available on the VM lane, Still intentionally limited on the native lane, Supported Surface, At A High Level

### Community 78 - "Community 78"
Cohesion: 0.5
Nodes (4): Tier 1 — Must Have (Blocking Production), Tier 2 — Should Have, Tier 3 — Nice to Have, 🚀 What's Left for Full Production Grade

### Community 79 - "Community 79"
Cohesion: 0.5
Nodes (4): 3D Specific, Backend / Server, Core Visualization, 📡 Technologies Required

### Community 80 - "Community 80"
Cohesion: 0.5
Nodes (4): 2D Design, code:c (// B0 — entry), Example Animated Output, Phase 9 — C Code Generation

### Community 81 - "Community 81"
Cohesion: 0.5
Nodes (4): 2D Design, 3D Design, code:block4 (┌──────────────┐), Phase 6 — IR / CFG Construction

### Community 82 - "Community 82"
Cohesion: 0.5
Nodes (4): 2D Visualization, 🎨 2D vs 3D — Full Comparison, 3D Visualization, code:block9 (Z=0   Source Code (flat panel))

### Community 83 - "Community 83"
Cohesion: 0.5
Nodes (4): 2D Design, 3D Design, code:block2 (Source Code Panel (top, syntax highlighted):), Phase 1 — Lexical Analysis (Tokenization)

### Community 97 - "Community 97"
Cohesion: 0.67
Nodes (3): Caveat, Cyclic dependencies, Result

### Community 98 - "Community 98"
Cohesion: 0.67
Nodes (3): code:text (compiler/), Repository Layout, Usage

### Community 99 - "Community 99"
Cohesion: 0.67
Nodes (3): Execution Model, Native lane, VM lane

## Knowledge Gaps
- **421 isolated node(s):** `Legacy compatibility module.  The active semantic implementation lives in `compi`, `Legacy compatibility module.  The active IR implementation lives in `compiler.ir`, `Legacy compatibility module.  The active parser stage lives in `compiler.fronten`, `Legacy compatibility module.  The compiler now parses Python source via the stdl`, `Legacy compatibility module.  The active optimizer lives in `compiler.optimizer`` (+416 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **31 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `ValueType` connect `Community 0` to `Community 1`, `Community 2`, `Community 38`, `Community 7`, `Community 8`, `Community 11`, `Community 12`, `Community 13`, `Community 14`, `Community 17`?**
  _High betweenness centrality (0.106) - this node is a cross-community bridge._
- **Why does `compile_source()` connect `Community 6` to `Community 65`, `Community 5`, `Community 38`, `Community 8`, `Community 12`, `Community 13`, `Community 14`, `Community 15`, `Community 23`, `Community 27`?**
  _High betweenness centrality (0.045) - this node is a cross-community bridge._
- **Why does `BytecodeLowerer` connect `Community 0` to `Community 24`, `Community 1`, `Community 27`, `Community 5`?**
  _High betweenness centrality (0.041) - this node is a cross-community bridge._
- **Are the 100 inferred relationships involving `ValueType` (e.g. with `SSATests` and `ExceptionCleanupTests`) actually correct?**
  _`ValueType` has 100 INFERRED edges - model-reasoned connections that need verification._
- **Are the 44 inferred relationships involving `StmtParser` (e.g. with `AssignStmt` and `AttributeAssignStmt`) actually correct?**
  _`StmtParser` has 44 INFERRED edges - model-reasoned connections that need verification._
- **Are the 61 inferred relationships involving `BytecodeLowerer` (e.g. with `AssignStmt` and `AttributeAssignStmt`) actually correct?**
  _`BytecodeLowerer` has 61 INFERRED edges - model-reasoned connections that need verification._
- **Are the 60 inferred relationships involving `TypeChecker` (e.g. with `AssignStmt` and `AttributeAssignStmt`) actually correct?**
  _`TypeChecker` has 60 INFERRED edges - model-reasoned connections that need verification._