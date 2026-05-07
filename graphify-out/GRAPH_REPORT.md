# Graph Report - compiler project  (2026-05-07)

## Corpus Check
- 106 files · ~58,277 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1089 nodes · 2889 edges · 84 communities (57 shown, 27 thin omitted)
- Extraction: 58% EXTRACTED · 42% INFERRED · 0% AMBIGUOUS · INFERRED: 1208 edges (avg confidence: 0.62)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `f8791219`
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
- [[_COMMUNITY_Community 15|Community 15]]
- [[_COMMUNITY_Community 16|Community 16]]
- [[_COMMUNITY_Community 17|Community 17]]
- [[_COMMUNITY_Community 18|Community 18]]
- [[_COMMUNITY_Community 19|Community 19]]
- [[_COMMUNITY_Community 20|Community 20]]
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
- [[_COMMUNITY_Community 51|Community 51]]
- [[_COMMUNITY_Community 52|Community 52]]
- [[_COMMUNITY_Community 55|Community 55]]
- [[_COMMUNITY_Community 56|Community 56]]
- [[_COMMUNITY_Community 57|Community 57]]
- [[_COMMUNITY_Community 58|Community 58]]
- [[_COMMUNITY_Community 59|Community 59]]
- [[_COMMUNITY_Community 60|Community 60]]
- [[_COMMUNITY_Community 61|Community 61]]
- [[_COMMUNITY_Community 62|Community 62]]
- [[_COMMUNITY_Community 63|Community 63]]

## God Nodes (most connected - your core abstractions)
1. `ValueType` - 94 edges
2. `StmtParser` - 82 edges
3. `TypeChecker` - 73 edges
4. `BytecodeLowerer` - 71 edges
5. `NameResolver` - 70 edges
6. `PipelineTests` - 67 edges
7. `PythonSubsetLowerer` - 67 edges
8. `ExprParser` - 59 edges
9. `VMError` - 54 edges
10. `CFGLowering` - 49 edges

## Surprising Connections (you probably didn't know these)
- `early_return()` --calls--> `Print`  [INFERRED]
  test_optimizer.py → compiler/ir/cfg.py
- `side()` --calls--> `Print`  [INFERRED]
  test_booleans.py → compiler/ir/cfg.py
- `main()` --calls--> `py_write_float()`  [INFERRED]
  output.c → py_runtime.c
- `test_break()` --calls--> `Print`  [INFERRED]
  test_loop_control.py → compiler/ir/cfg.py
- `test_continue()` --calls--> `Print`  [INFERRED]
  test_loop_control.py → compiler/ir/cfg.py

## Communities (84 total, 27 thin omitted)

### Community 0 - "Community 0"
Cohesion: 0.09
Nodes (78): CompilationResult, AssignStmt, AttributeAssignStmt, AttributeExpr, BinaryExpr, BoolOpExpr, BreakStmt, CallExpr (+70 more)

### Community 1 - "Community 1"
Cohesion: 0.06
Nodes (58): Exception, Protocol, str, _Host, VMRuntimeTests, _adapt_host_callable(), build_builtins(), builtin_isinstance() (+50 more)

### Community 2 - "Community 2"
Cohesion: 0.06
Nodes (16): parse(), Legacy compatibility module.  The active parser stage lives in `compiler.fronten, Legacy compatibility module.  The active semantic implementation lives in `compi, SemanticAnalyser, SemanticError, lower_cst(), ParsedModule, lex_source() (+8 more)

### Community 3 - "Community 3"
Cohesion: 0.07
Nodes (10): bind_call_arguments(), can_truth_test(), is_numeric(), merge_types(), Scope, _import_binding_name(), _is_builtin_function(), _import_binding_name() (+2 more)

### Community 4 - "Community 4"
Cohesion: 0.08
Nodes (10): Error recovery utilities for the owned parser.  Provides :func:`synchronize` whi, Advance *cursor* past tokens until a likely statement boundary.      This allows, synchronize(), parse_to_program(), Recursive descent statement parser — all stages (A through D)., Top-level parser that drives the token cursor and expression parser., Public entry: parse tokens into a Program AST directly., StmtParser (+2 more)

### Community 5 - "Community 5"
Cohesion: 0.07
Nodes (24): _analyze_source(), check_source(), compile_source(), execute_source(), _load_bytecode_module(), _module_name_for_filename(), _program_uses_call_kwargs_splats(), _program_uses_call_signature_features() (+16 more)

### Community 6 - "Community 6"
Cohesion: 0.1
Nodes (24): Enum, _Lexer, OwnedToken, Fully owned, indentation-aware Python lexer.  Replaces CPython's ``tokenize.gene, A single token produced by the owned lexer., Tokenize *source* into a list of :class:`OwnedToken` values.      Returns a ``(t, Internal state-machine lexer., tokenize_source() (+16 more)

### Community 8 - "Community 8"
Cohesion: 0.11
Nodes (13): Token stream cursor for the owned parser.  Provides :class:`TokenCursor` — a pos, Skip NEWLINE, NL, COMMENT, and ENCODING tokens., Build a SourceSpan from *start_token* to the previously consumed token., Navigates a flat ``list[LexToken]`` with single-token lookahead., Return current token without consuming it., Return the token after current (1-ahead lookahead)., Consume and return the current token., Return True if current token matches *kind* (and optionally *text*). (+5 more)

### Community 9 - "Community 9"
Cohesion: 0.11
Nodes (19): _collect_constants(), _current_name(), _defined_name(), _definition_sites(), dominance_frontiers(), immediate_dominators(), _is_one(), _is_side_effecting() (+11 more)

### Community 10 - "Community 10"
Cohesion: 0.09
Nodes (16): main(), add(), main(), square(), py_decref(), py_float_to_str(), py_floor_div_int(), py_header() (+8 more)

### Community 11 - "Community 11"
Cohesion: 0.35
Nodes (23): FunctionType, Assign, BasicBlock, BinaryOp, BranchTerminator, Call, CFGFunction, CFGModule (+15 more)

### Community 12 - "Community 12"
Cohesion: 0.12
Nodes (15): main(), run_cli_smoke(), run_negative_test(), run_positive_test(), run_quiet_mode_smoke(), run_source_test(), side(), test_break() (+7 more)

### Community 13 - "Community 13"
Cohesion: 0.14
Nodes (9): _build_type_map(), CCodeGenerator, _default_initializer(), _literal(), Generate a C function call., c_type_name(), CRuntimeSupport, _print_helper_name() (+1 more)

### Community 14 - "Community 14"
Cohesion: 0.22
Nodes (3): ASTVisualiser, ast_viz.py — AST Visualisation with Graphviz (Enhanced) ========================, visualise_ast()

### Community 16 - "Community 16"
Cohesion: 0.1
Nodes (20): 1. Overall Completion Status, 2. What Is Working (VM Path), 3. What Is Missing (Hard Blockers), 4. Priority Roadmap, 5. Implementation Steps, 6. Antigravity Reference, 7. Milestones, After Fix (+12 more)

### Community 17 - "Community 17"
Cohesion: 0.19
Nodes (4): Instruction, _collect_scope_declarations(), _import_binding_name(), _resolve_labels()

### Community 19 - "Community 19"
Cohesion: 0.2
Nodes (3): SemanticAnalyzer, ControlFlowChecker, SemanticModel

### Community 20 - "Community 20"
Cohesion: 0.14
Nodes (14): Best Reading Of Overall Progress From Phase 1, code:text (source), code:text (source), Current Execution Flow, Immediate Remaining Work, Prioritized, Phase 1, Phase 1 Component Assessment, Phase 2 Candidates (+6 more)

### Community 22 - "Community 22"
Cohesion: 0.22
Nodes (3): build_use_def_map(), _fold_binary(), SSATests

### Community 23 - "Community 23"
Cohesion: 0.28
Nodes (7): block_map(), compute_dominators(), reachable_block_names(), rebuild_edges(), reverse_post_order(), _prune_unreachable(), IRTests

### Community 24 - "Community 24"
Cohesion: 0.15
Nodes (12): 1. Current State & Percentage Done, 2. What is Still Left to Implement?, 3. Next Steps: How to Proceed?, A. Missing AST & Parser Features, B. The C-Backend (Native Code Generator), C. Standard Library and Builtins, Compilation Pipeline Status & Gap Analysis, Step 1: Upgrade the C-Backend's features (Control Flow) (+4 more)

### Community 25 - "Community 25"
Cohesion: 0.15
Nodes (13): Best Reading Of Overall Progress After Phase 2, Frontend Ownership Status, Immediate Remaining Work, Prioritized, Phase 2, Phase 2 Component Assessment, Phase 3 Candidates, Semantic Pipeline Status, What Is Still Missing, Visible From This Phase (+5 more)

### Community 26 - "Community 26"
Cohesion: 0.2
Nodes (8): ASTTransformer, ASTVisitor, visitor.py — Base Visitor pattern for AST traversal. All analysis/transform pass, Dispatch to the correct visit_* method based on node class name., Called when no specific visitor exists. Override for custom fallback., A visitor that returns transformed nodes.     Used for optimization passes that, Visit all child nodes listed in node.children (if defined)., Base visitor class implementing the Visitor Pattern.     Subclasses override vis

### Community 27 - "Community 27"
Cohesion: 0.35
Nodes (4): CFGConstantPropagation, _const_for_name(), _fold_binary(), _same_constant()

### Community 28 - "Community 28"
Cohesion: 0.18
Nodes (10): code:text (Python source -> lexer -> parser -> CST -> AST lowering -> s), code:bash (# Install in editable mode), code:bash (python3 -m unittest discover -s tests -v), Current native path, Current VM-supported surface, Explicitly unsupported today, Project shape, Python VM-First Compiler (+2 more)

### Community 29 - "Community 29"
Cohesion: 0.22
Nodes (9): Best Reading Of Overall Progress After Phase 3, Builtin-Call Strategy, Bytecode Structure and Lowering, Phase 3, Phase 3 Component Assessment, Phase 4 Candidates, Runtime Value and Object Representation, What Is Still Missing, Visible From This Phase (+1 more)

### Community 30 - "Community 30"
Cohesion: 0.22
Nodes (8): Architectural Takeaways, Pending Future Sections, Phase 6 Component Assessment, Phase 6: Deep Dive into the Native Compilation Pipeline, Project Snapshot, PythonCompiler Knowledge Base, The Native Pipeline Deep Dive, What This Phase Answers

### Community 32 - "Community 32"
Cohesion: 0.25
Nodes (8): Best Reading Of Overall Progress After Phase 4, Phase 4, Phase 4 Component Assessment, Phase 5 Candidates, The Native C Runtime Support, The Refactored Native Pipeline, What Is Still Missing, Visible From This Phase, What This Phase Answers

### Community 34 - "Community 34"
Cohesion: 0.33
Nodes (6): 1. Target: Educational & Research Compiler (Near Term), 2. Target: Production-Grade Compiler (Long Term), Conclusion, Project Completion Matrix & Roadmap, Roadmap: Educational/Research Compiler vs. Production-Grade, Subsystem Completion Status

### Community 35 - "Community 35"
Cohesion: 0.33
Nodes (6): Conclusion: Project State, Phase 5, Phase 5 Component Assessment, Test Suite and Feature Verification, The Internal Native Pipeline Structure, What This Phase Answers

### Community 38 - "Community 38"
Cohesion: 0.7
Nodes (4): build_parser(), _emit_dump(), main(), _maybe_emit_ast_viz()

### Community 48 - "Community 48"
Cohesion: 0.5
Nodes (3): Optimizer, Legacy compatibility module.  The active optimizer lives in `compiler.optimizer`, ConstantFolder

## Knowledge Gaps
- **152 isolated node(s):** `Legacy compatibility module.  The active semantic implementation lives in `compi`, `Legacy compatibility module.  The active IR implementation lives in `compiler.ir`, `Legacy compatibility module.  The active parser stage lives in `compiler.fronten`, `Legacy compatibility module.  The compiler now parses Python source via the stdl`, `Legacy compatibility module.  The active optimizer lives in `compiler.optimizer`` (+147 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **27 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `ValueType` connect `Community 0` to `Community 1`, `Community 33`, `Community 3`, `Community 6`, `Community 11`, `Community 12`, `Community 13`, `Community 18`, `Community 19`, `Community 22`, `Community 27`?**
  _High betweenness centrality (0.210) - this node is a cross-community bridge._
- **Why does `execute_source()` connect `Community 5` to `Community 0`, `Community 1`, `Community 38`, `Community 7`, `Community 39`, `Community 15`?**
  _High betweenness centrality (0.089) - this node is a cross-community bridge._
- **Why does `BytecodeLowerer` connect `Community 0` to `Community 17`, `Community 5`, `Community 1`?**
  _High betweenness centrality (0.079) - this node is a cross-community bridge._
- **Are the 91 inferred relationships involving `ValueType` (e.g. with `SSATests` and `CompilationResult`) actually correct?**
  _`ValueType` has 91 INFERRED edges - model-reasoned connections that need verification._
- **Are the 43 inferred relationships involving `StmtParser` (e.g. with `AssignStmt` and `AttributeAssignStmt`) actually correct?**
  _`StmtParser` has 43 INFERRED edges - model-reasoned connections that need verification._
- **Are the 56 inferred relationships involving `TypeChecker` (e.g. with `AssignStmt` and `AttributeAssignStmt`) actually correct?**
  _`TypeChecker` has 56 INFERRED edges - model-reasoned connections that need verification._
- **Are the 55 inferred relationships involving `BytecodeLowerer` (e.g. with `AssignStmt` and `AttributeAssignStmt`) actually correct?**
  _`BytecodeLowerer` has 55 INFERRED edges - model-reasoned connections that need verification._