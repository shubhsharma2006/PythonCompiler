# 🔬 Live Compiler Visualization — Full Design Spec

> From high-level Python source to machine-level C/binary — every stage rendered live, in 2D and 3D.
> This document covers all compiler phases, technology choices, 2D vs 3D ideas, drawbacks, and limitations.

---

## 🗺️ The Full Journey: High Level → Machine Level

When you type `x = a + b * 2` and hit **Compile**, here is everything that happens — and what you will *watch* in the visualization:

```
Source Code (text string)
        │
        ▼ Phase 1 ── LEXICAL ANALYSIS (Tokenization)
   Raw characters → Token stream
   "x" "=" "a" "+" "b" "*" "2"
        │
        ▼ Phase 2 ── SYNTAX ANALYSIS (Parsing)
   Token stream → Abstract Syntax Tree (AST)
        │
        ▼ Phase 3 ── AST LOWERING
   CPython/owned AST → compiler.core.ast (custom nodes)
        │
        ▼ Phase 4 ── SEMANTIC ANALYSIS
   Name resolution + Type inference → SemanticModel
        │
        ▼ Phase 5 ── AST OPTIMIZATION
   Constant folding, dead branch elimination
        │
        ├─────── VM LANE ─────────────────────────────────────┐
        │  Phase 6a: Bytecode Lowering                        │
        │  Phase 7a: VM Execution (stack machine)             │
        └─────────────────────────────────────────────────────┘
        │
        └─────── NATIVE LANE ─────────────────────────────────┐
           Phase 6b: IR / CFG Construction                    │
           Phase 7b: SSA Construction (φ-nodes, renaming)     │
           Phase 8b: SSA Optimizations (4 passes)             │
           Phase 9b: SSA Destruction                          │
           Phase 10b: C Code Generation                       │
           Phase 11b: gcc/clang → Machine Binary              │
        ────────────────────────────────────────────────────────┘
```

---

## 📡 Technologies Required

### Core Visualization

| Technology | Purpose | Why |
|-----------|---------|-----|
| **Cytoscape.js** | Graph rendering for AST, CFG, SSA | Best-in-class for node/edge graphs; dagre layout built-in |
| **Three.js** | 3D layer stack, fly-through camera | WebGL-based, handles 10k+ nodes |
| **D3.js** | Token stream rail, timeline, bar charts | SVG-based, excellent for data-driven animations |
| **GSAP** | Animation sequencing, morphing text | Industry-standard JS animation library |
| **CodeMirror 6** | Source code editor with range highlighting | Syntax highlight + cursor tracking |
| **vis-network** | Alternative graph (already in graphify-out) | Lower overhead for simple CFGs |

### Backend / Server

| Technology | Purpose |
|-----------|---------|
| **Python stdlib HTTPServer** | Zero-dependency server (`viz_server.py`) |
| **FastAPI** (optional upgrade) | WebSocket support for streaming steps live |
| **WebSocket** | Push SSA micro-steps to browser as they compute |

### 3D Specific

| Technology | Purpose |
|-----------|---------|
| **Three.js + OrbitControls** | Camera orbit, zoom, pan |
| **TWEEN.js** | Smooth 3D transitions between layers |
| **CSS3DRenderer** | Embed HTML panels inside 3D scene |
| **Cannon.js / Rapier** | Physics — blocks "fall" when eliminated |

---

## 🎬 Phase-by-Phase Visualization Design

---

### Phase 1 — Lexical Analysis (Tokenization)

**What happens:** The raw source string is scanned character by character. Each recognized sequence (keyword, identifier, operator, literal) becomes a **Token** with a `kind`, `text`, `line`, and `column`.

#### 2D Design

```
Source Code Panel (top, syntax highlighted):
   x   =   a   +   b   *   2

Tokenizer "Scanner" animation:
   ┌──────────────────────────────────────────────────────────────┐
   │  [NAME:x] [OP:=] [NAME:a] [OP:+] [NAME:b] [OP:*] [INT:2]   │
   └──────────────────────────────────────────────────────────────┘
   ▲ Each token appears as a colored pill/chip animating right-to-left
   Color = token type:
     NAME    = #7eb8f7  (blue)
     OP      = #ffd700  (gold)
     INT     = #00e676  (green)
     STRING  = #ff8f00  (orange)
     KEYWORD = #ef5350  (red)
     INDENT  = #ab47bc  (purple)
     DEDENT  = #7b1fa2  (dark purple)
```

**Interactions:**
- Hover any token → highlight the exact character range in the source editor
- Click token → show full `LexToken` struct: `kind`, `text`, `line`, `col`, `end_line`, `end_col`, `exact_kind`
- Speed slider: 0.1x to 10x (watch it scan slowly or blitz through)

#### 3D Design

- Source text lies on a flat **Z=0 plane**
- Characters rise as **glowing pillars** when the scanner reads them
- Token pills fly off and land on a **conveyor belt** at Z=2
- Camera angle: isometric, tiltable

---

### Phase 2 — Syntax Analysis (Parsing)

**What happens:** The Pratt parser reads the token stream and builds a tree. Each grammar rule reduces a sequence of tokens into a node.

#### 2D Design

- Token rail at the top, AST tree builds downward
- Each **reduce** action: tokens "collapse" into a parent node with a merge animation
- Node color = AST node type:

| Node Type | Color |
|-----------|-------|
| `Program` | `#4E79A7` (blue-grey, root) |
| `FunctionDef` | `#E15759` (red) |
| `ClassDef` | `#B07AA1` (purple) |
| `IfStmt` / `WhileStmt` | `#F28E2B` (orange) |
| `AssignStmt` | `#59A14F` (green) |
| `BinaryExpr` | `#76B7B2` (teal) |
| `CallExpr` | `#EDC948` (yellow) |
| `ConstantExpr` | `#ffffff` (white) |
| `NameExpr` | `#aaaaaa` (grey) |

- Operators show their **precedence level** as a number badge (higher = tighter binding)
- Parenthesized expressions show a faint bracket grouping around their subtree

**Interactions:**
- Click any AST node → highlight the exact token range it was built from (back-links to Phase 1)
- Expand/collapse subtrees
- "Show raw Python ast" toggle — compare to the stdlib ast

#### 3D Design

- AST is a **3D tree** floating in space
- Root at top, children below connected by glowing beams
- Each node is a labeled sphere, size proportional to subtree depth
- Rotation: drag to rotate the whole tree
- Parser animation: watch nodes snap together from the bottom up

---

### Phase 3 — AST Lowering

**What happens:** The Python standard `ast` (or our owned parser's `Program`) is lowered into `compiler.core.ast` custom dataclasses. Each node maps 1-to-1 or is decomposed.

#### 2D Design

- **Side-by-side diff**: Left = Python ast node, Right = compiler.core.ast node
- Animated arrows showing the mapping
- Nodes that split (e.g., `AugAssign` → `Assign(name, BinaryExpr(...))`) show a "split" animation
- Nodes with `NotImplementedError` stubs (async, yield-from) flash **amber warning**

---

### Phase 4 — Semantic Analysis

**What happens:** Two passes: `NameResolver` builds scope chains and binds every `NameExpr` to its definition. `TypeChecker` infers types for every expression.

#### 2D Design — Scope Visualization

```
 ┌──────── Module Scope ──────────────────────┐
 │  x: INT   y: FLOAT   f: FunctionType       │
 │                                            │
 │  ┌──── Function Scope: f(a, b) ─────────┐  │
 │  │  a: INT   b: INT   result: UNKNOWN   │  │
 │  │                                      │  │
 │  │  ┌── Nested Scope (lambda) ────────┐ │  │
 │  │  │  z: captured from outer        │ │  │
 │  │  └────────────────────────────────┘ │  │
 │  └──────────────────────────────────────┘  │
 └────────────────────────────────────────────┘
```

- **Nested bubbles** = lexical scopes
- **Variable orbs** inside each bubble, colored by type:
  - INT = `#7eb8f7` blue
  - FLOAT = `#00bcd4` teal
  - STRING = `#ff8f00` orange
  - BOOL = `#ab47bc` purple
  - UNKNOWN = `#616161` grey
- **Closure arrows** = dotted lines connecting a captured variable to its outer scope
- Hover any `NameExpr` in the AST → its orb **pulses** in the scope bubble

#### 2D Design — Type Propagation

- Expression tree with type labels at every node
- Animation: type inference flows **bottom-up** through the tree
- Where types merge (if/else branches): show both types combining with `merge_types()`
- `UNKNOWN` propagation shown in grey with a warning icon

#### 3D Design

- Scopes as **nested translucent cubes**
- Variables are **glowing dots** orbiting inside their cube
- Closure captures: a bright **arc** connects a dot to its outer cube

---

### Phase 5 — AST Optimization (Constant Folding)

**What happens:** `ConstantFolder` walks the AST. When both children of a `BinaryExpr` are `ConstantExpr`, the whole node is replaced with a single constant.

#### 2D Design

- AST shown with foldable subtrees **outlined in dashed yellow**
- Animation:
  1. `3 * 2` subtree glows
  2. Both children collapse inward
  3. A new `ConstantExpr(6)` node "crystallizes" in their place
  4. Dead branches of `if True:` / `if False:` fade grey and dissolve

#### What You See Fold

| Before | After | Animation |
|--------|-------|-----------|
| `BinaryExpr(+, Const(3), Const(4))` | `ConstantExpr(7)` | Merge + crystallize |
| `IfExpr(Const(True), a, b)` | `a` (dead branch gone) | `b` branch fades red |
| `UnaryExpr(not, Const(True))` | `ConstantExpr(False)` | Flip animation |
| `BoolOpExpr(and, Const(False), x)` | `ConstantExpr(False)` | Short-circuit glow |

---

### Phase 6 — IR / CFG Construction

**What happens:** The AST is lowered into a Control Flow Graph. Each function becomes a set of `BasicBlock`s. Each block has `instructions` (flat, no nesting) and a `terminator` (jump/branch/return).

#### 2D Design

```
   ┌──────────────┐
   │  entry (B0)  │  ← green border
   │  x.0 = 10    │
   │  JUMP → B1   │
   └──────┬───────┘
          │
   ┌──────▼───────┐      ┌──────────────┐
   │  B1 (cond)   │─true─▶   B2         │
   │  t.0 = x < 5 │      │  y.0 = x + 1 │
   └──────┬───────┘      └──────┬───────┘
    false │                     │
   ┌──────▼───────┐             │
   │  B3          │◀────────────┘
   │  RETURN x.0  │  ← purple border
   └──────────────┘
```

- Block nodes: rounded rectangles
- True edges: green arrows
- False edges: red arrows
- Jump edges: blue arrows
- Back-edges (loops): curved yellow arrows
- Click a block → expand to show all instructions

#### 3D Design

- Blocks as **3D floating boxes** with depth proportional to instruction count
- Edges are **3D tubes** (green/red/blue)
- Loop back-edges are **spiral tubes** wrapping back upward
- Camera starts top-down; can be rotated to any angle

---

### Phase 7 — SSA Construction

**What happens:** Variables are renamed with version suffixes. φ-nodes are placed at dominance frontiers — points where two different definitions of the same variable merge.

#### 2D Design

**Before SSA:**
```
B0: x = 10         B1: x = 20
         \         /
          B2: print(x)   ← which x?
```

**After SSA (animated transition):**
```
B0: x.0 = 10      B1: x.1 = 20
          \        /
     B2: x.2 = φ(B0: x.0, B1: x.1)
         print(x.2)
```

**Animation sequence:**
1. Variable names split: `x` → `x.0`, `x.1` with a "fork" animation
2. φ-node materializes at B2 as a **spinning gold diamond**
3. Input arrows from B0 and B1 glow and connect to the φ-node

**φ-node visualization:**
```
        x.0 ──────┐
                  ▼
        B0 ──→ [ φ ] → x.2
                  ▲
        x.1 ──────┘
```

---

### Phase 8 — SSA Optimization Passes

Each pass is animated live. This is the core of the visualization.

#### SSA Constant Propagation

**Animation:** If a φ-node has all inputs equal to the same constant:
1. φ diamond pulses bright white
2. Inputs collapse inward
3. φ dissolves → replaced by a `LoadConst` node (solid crystal)
4. Unreachable blocks (constant branch = always true/false) **sink downward** and fade

#### SSA Value Propagation

**Animation:** Algebraic identity detected:
1. Instruction text glows amber: `x.1 = y.0 + 0`
2. The `+ 0` part fades with a strikethrough
3. Text morphs: `x.1 = y.0 + 0` → `x.1 = y.0`

| Identity | Before → After |
|----------|---------------|
| `x + 0` | `x` |
| `x * 1` | `x` |
| `x - 0` | `x` |
| `x / 1` | `x` |
| `x ** 1` | `x` |
| `0 * x` | `0` |

#### SSA Dead Code Elimination

**Animation:**
1. Unused definition highlighted with dashed red border
2. All uses checked (none found — counter shows `uses: 0`)
3. Instruction strikes through and dissolves
4. If entire block becomes empty → block collapses and sinks out of frame

#### SSA Copy Propagation

**Animation:**
1. Trivial phi `x.2 = φ(x.1)` — only one unique input
2. φ-diamond compresses to a point
3. All uses of `x.2` reroute their arrows directly to `x.1`
4. Copy chain: `a=b`, `b=c`, `c=42` → all become `a=42`, `b=42`, `c=42`

#### SSA Destruction (Final Pass)

**Animation:**
1. φ-nodes at block edges split into parallel copy instructions
2. Version numbers (`x.1`) sanitize to C-safe names (`x__ssa_1`)
3. The graph "flattens" — phi edges dissolve, replaced by assignment arrows

---

### Phase 9 — C Code Generation

**What happens:** The destroyed SSA is traversed block by block. Each block emits C code with `goto` labels for control flow.

#### 2D Design

- **Split panel**: Left = CFG blocks, Right = C code output
- As each block is processed, the corresponding C code **types out** (typewriter effect)
- `goto` arrows in the C code match the block edges
- Ref-count operations (`py_incref`, `py_decref`) highlighted in orange
- Python-correct helpers (`py_floor_div_int`, `py_str_concat`) highlighted in cyan

#### Example Animated Output

```c
// B0 — entry
int x__ssa_0 = 10;
goto B1;

// B1
B1:;
int t__ssa_0 = x__ssa_0 < 5;
if (t__ssa_0) goto B2; else goto B3;

// B2
B2:;
int y__ssa_0 = x__ssa_0 + 1;
goto B3;

// B3
B3:;
return x__ssa_0;
```

---

### Phase 10 — Machine Code / Binary

**What happens:** `gcc` or `clang` compiles the C code. The result is a native binary. This is outside our compiler but can be visualized.

#### 2D Design

- C code panel on left
- Assembly output panel on right (from `gcc -S`)
- Each C line maps to highlighted assembly lines with animated connecting arrows
- Register allocation shown: variable names → `%rax`, `%rbx`, etc.
- Final binary: hex dump with ASCII sidebar

---

## 🎨 2D vs 3D — Full Comparison

### 2D Visualization

**Approach:** All phases on the same screen, stacked vertically. Navigate by scrolling. Each phase is a panel with its own internal animation.

**Advantages:**
- Works in any browser, no WebGL required
- Easier to read text (instructions, code)
- Faster to implement (D3.js + Cytoscape.js)
- Better for educational/debugging use
- Accessible (screen readers can parse 2D SVG)
- Lower CPU/GPU usage — runs on laptops

**Disadvantages:**
- Hard to show relationships *between* phases
- Screen gets cluttered with many phases visible
- No sense of "flow" or transformation journey
- Less impressive visually

**Best for:** Education, debugging, presenting compiler behavior

---

### 3D Visualization

**Approach:** Each phase occupies a distinct **floating 3D plane** at a different Z-depth. The camera can fly between layers or pull back to see all 10 planes simultaneously.

```
Z=0   Source Code (flat panel)
Z=1   Token stream (bead rail)
Z=2   AST (3D tree)
Z=3   Semantic Model (nested cubes)
Z=4   Optimized AST (morphed tree)
Z=5   CFG (3D boxes + tubes)
Z=6   SSA (glowing phi diamonds)
Z=7   Optimized SSA (crystallized)
Z=8   C Code (floating text panel)
Z=9   Binary (hex display)
```

**Advantages:**
- Immediately communicates the "transformation pipeline" concept
- Data flow between layers is visible as 3D arrows
- Visually stunning — excellent for demos, talks, portfolio
- Time-travel: scrub backward, watch layers "rewind"
- Click a token in Layer 1 → highlight its AST node in Layer 2 → its CFG block in Layer 5

**Disadvantages:**
- High implementation complexity (6–8 weeks)
- WebGL required — may not work on older devices
- Text readability degrades at angles
- 3D graph layout (no perfect algorithm for DAGs in 3D)
- Occlusion: deeper layers obscure foreground
- Performance: 1000+ nodes in 3D at 60fps requires aggressive culling

**Best for:** Demos, conference talks, portfolio showcase, educational explainer

---

## 🚧 Drawbacks & Limitations

### Technical Limitations

| Limitation | Impact | Mitigation |
|-----------|--------|------------|
| CFG only exists for native lane — VM programs don't generate IR | Half the programs don't reach SSA viz | Add bytecode viz for VM lane separately |
| SSA tracer must deepcopy the entire module after each micro-step | Memory usage = O(steps × module_size). Large programs → slow | Capture diffs only, not full snapshots |
| Cytoscape.js layout (dagre) is computed in-browser JS | Large CFGs (100+ blocks) → laggy layout | Pre-compute layout on server; send `x,y` coordinates |
| 3D Three.js with 1000+ nodes at 60fps | GPU bottleneck on low-end machines | Level-of-detail: collapse distant blocks |
| CodeMirror + Cytoscape.js + Three.js + GSAP + D3 all loaded | ~2MB JS bundle | Lazy-load phases on demand |
| WebSocket streaming requires persistent connection | HTTP/1.1 polling fallback needed | Implement SSE (Server-Sent Events) as fallback |
| Python `copy.deepcopy` on CFGModule is slow | Each SSA step snapshot takes ~50ms for large programs | Profile and optimize; use structural sharing |

### Semantic Limitations

| Limitation | Impact |
|-----------|--------|
| Only programs that pass native-lane checks generate IR/SSA | Imports, exceptions, containers, closures → no CFG to visualize |
| Type info in SSA is coarse (`INT`, `FLOAT`, `STRING`, `UNKNOWN`) | Can't show precise types for complex expressions |
| SSA destruction produces C-safe names (`x__ssa_1`) not user names | Confusing for users who expect to see `x`, `y` |
| For-loops only support `range()` in native lane | `for x in list` programs fall to VM lane — no SSA viz |
| The VM bytecode lane has no SSA equivalent | Bytecode visualization is a separate (simpler) problem |

### UX Limitations

| Limitation | Impact |
|-----------|--------|
| Hundreds of SSA micro-steps for a 20-line program | Timeline scrubber is very granular — easy to get lost |
| 3D perspective makes instruction text hard to read | Need a "flatten to 2D" toggle at all times |
| Cross-layer highlighting (token → AST → CFG → SSA) requires tracking node IDs across all phases | Complex mapping to implement correctly |
| Animation speed vs understanding tradeoff | Too fast = confusing; too slow = boring |

---

## 📋 Example Programs Showing Each Phase

### Minimal (shows all phases clearly)
```python
x = 10
y = x + 5
print(y)
```

### Constant Folding + Branch Pruning
```python
DEBUG = False
if DEBUG:
    print("debug mode")
result = 3 * 7 + 1
print(result)
```

### SSA φ-nodes (full loop)
```python
i = 0
total = 0
while i < 10:
    total = total + i
    i = i + 1
print(total)
```

### Copy Chain Collapse
```python
a = 42
b = a
c = b
d = c
print(d)
```

### Dead Code Elimination
```python
x = 100
y = 200
unused = x * y
z = x + 1
print(z)
```

---

## 📁 Files to Create

| File | Lines | Purpose |
|------|-------|---------|
| `compiler/viz/__init__.py` | 1 | Package |
| `compiler/viz/ssa_tracer.py` | ~220 | Instruments all 6 SSA passes |
| `compiler/viz/bytecode_tracer.py` | ~150 | Instruments VM bytecode steps |
| `compiler/viz/phase_serializer.py` | ~200 | Serializes all 10 phases to JSON |
| `viz_server.py` | ~90 | HTTP server + `/compile` endpoint |
| `ssa_viz.html` | ~700 | Full 2D visualization (all phases) |
| `ssa_viz_3d.html` | ~900 | 3D layer stack visualization |

---

## 🏁 Implementation Roadmap

| Week | Milestone |
|------|-----------|
| 1 | `ssa_tracer.py` + `viz_server.py` running, raw JSON output |
| 2 | 2D: Token stream + AST phase panels (D3 + Cytoscape.js) |
| 3 | 2D: Semantic + CFG + SSA panels with step animations |
| 4 | 2D: C codegen panel + full timeline scrubber |
| 5 | 3D: Three.js skeleton + 7 floating planes |
| 6 | 3D: Cross-layer highlight links + camera fly-through |
| 7 | Polish: performance, mobile layout, export to video |

---

## ✅ Status Checklist

- [ ] `compiler/viz/__init__.py`
- [ ] `compiler/viz/ssa_tracer.py`
- [ ] `compiler/viz/phase_serializer.py` (all 10 phases → JSON)
- [ ] `viz_server.py`
- [ ] `ssa_viz.html` (2D, all phases)
- [ ] `ssa_viz_3d.html` (3D, layer stack)
- [ ] Add `python viz_server.py` to README

---

*This is the complete design specification for the live compiler visualization layer.*

---

---

# 🏆 Architectural Review — What This Is Really Becoming

> This section captures a deep critical review of the visualization architecture above.
> Read this before building anything.

---

## Overall Scorecard

| Dimension | Score | Notes |
|-----------|-------|-------|
| Technical imagination | **10/10** | Genuinely novel concepts |
| Compiler correctness awareness | **9/10** | Accurate mapping of phase behavior |
| Visualization architecture | **9.5/10** | Phase-separated structure is correct |
| Educational value | **10/10** | Among the best explainer tools designed |
| Systems coherence | **9/10** | Clean separation of concerns |
| Production feasibility | **7/10** | Achievable with discipline |
| Scope control | **4/10** | ⚠️ Biggest risk — must be managed aggressively |

---

## ✅ What This Design Does Extremely Well

### 🥇 1. Visualization Separated by Compiler Phase — Correct Architecture

Most visualization tools make **one giant graph** that becomes unreadable immediately.

This design separates:
- Lexer
- Parser
- Semantic
- CFG
- SSA
- Codegen

**This is the right architecture.** It preserves semantic meaning at each layer. A token visualization and an SSA visualization have completely different semantics — merging them destroys both.

---

### 🥈 2. The SSA Visualization Design Is the Strongest Section

Specifically these ideas are genuinely well-designed and map correctly onto real compiler behavior:

- ✅ φ-node animations (φ-diamond materializing at dominance frontiers)
- ✅ Crystallization metaphor (constant phi collapsing to a solid node)
- ✅ Dead block sinking (eliminated blocks fall and fade)
- ✅ Copy propagation rerouting (arrows redirect)
- ✅ SSA destruction flattening (phi edges dissolve into assignment arrows)

These are **not gimmicks**. They reflect actual algorithmic behavior. That is rare in educational tooling.

---

### 🥉 3. Transformation Flow Modeled Correctly

The design consistently models:

```
before → transform → after
```

Not static graphs. This is the correct mental model for compilers because **compilers are transformation pipelines**. Every phase takes a representation and produces a different one. The visualization reflects that.

---

### 🏆 4. Cross-Layer Linkage Is the Real Killer Feature

```
token → AST node → CFG block → SSA variable → machine instruction
```

This creates **semantic traceability** — you can click a token and watch it light up all the way through to the emitted C code.

This is more valuable than 3D. More valuable than AI integration. This is what makes it a **platform** rather than a pretty tool.

---

### 🧠 5. SSA Correctly Identified as the "Hero Phase"

Most educational compiler tools stop at parsing or AST visualization. This design correctly recognizes that **CFG + SSA is where real compiler intelligence happens** — dead code elimination, constant folding, value propagation. The emphasis is right.

---

## 🚨 Critical Problems to Fix

### ❌ Problem 1: Too Many Phases at Once — Visual Overload

10 simultaneous layers is too much for human cognition. The system risks becoming overwhelming rather than illuminating.

**Solution: Progressive Disclosure**

Only show the current phase + directly linked phases.

When viewing SSA, show:
- CFG (what SSA is built from)
- SSA (current)
- Source mapping (where it came from)

Do **not** show simultaneously:
- Token rail
- Semantic cubes
- Binary hex dump

**Add a "Focus Mode"** — user picks one phase, everything else collapses to a sidebar:

```
[ Lexer ]    [ Parser ]    [ Semantic ]    [ CFG ]    [ SSA ★ ]    [ Codegen ]
                                                        ↑ active
```

---

### ❌ Problem 2: Tokens Are Overemphasized

The token visualization is interesting once. But tokens are not the intellectually rich part of a compiler.

**Better weighting:**

| Phase | Visual Weight |
|-------|--------------|
| Lexer / Tokens | Minimal — compact strip |
| AST | Moderate |
| Semantic Analysis | Moderate |
| CFG | Dominant |
| SSA + Optimizations | **Dominant** — this is the differentiator |
| C Codegen | Secondary |

The lexer animation should take 5% of the visual budget. The SSA section should take 40%.

---

### 🚨 Huge Missing Piece: "Why" Metadata on Every Transformation

The current design shows **what changed**. The next level is **why it changed**.

Instead of:
```
Block B4 removed
```

Show:
```
Block B4 removed because:
  Branch condition `1 < 2` resolved to constant True
  during SSA Constant Propagation.
  False branch became permanently unreachable.
```

**Implementation:** Every optimization emits a structured provenance record:

```python
@dataclass
class TransformationEvent:
    pass_name: str          # "SSAConstantPropagation"
    event_type: str         # "block_eliminated"
    before: str             # human-readable before state
    after: str              # human-readable after state
    reason: str             # WHY this transformation happened
    affected_nodes: list[str]  # block/instruction IDs
    source_location: tuple  # line, col in original source
```

This makes the system **explainable optimization** — not just visual, but reasoned.

---

### 🚨 Most Important Missing Piece: Timeline-First Architecture

The current design describes mostly **spatial** visualization. But compiler transformations are fundamentally **temporal**.

**The system should feel like watching the compiler think — not staring at graphs.**

Add a **timeline-first architecture**:

```
Step  1: source loaded
Step  2: tokens produced
Step  3: AST parsed
Step  4: names resolved
Step  5: types inferred
Step  6: CFG built
Step  7: phi inserted at B2 (x.2 = φ(x.0, x.1))
Step  8: phi inserted at B4 (i.1 = φ(i.0, i.2))
Step  9: constant propagation: phi x.2 → x.0 = 5
Step 10: dead block B3 eliminated
Step 11: copy chain a.0 = b.0 = c.0 collapsed
Step 12: SSA destroyed
Step 13: C emitted: B0, B1, B2
Step 14: binary ready
```

Every step is **replayable**. Drag the scrubber to Step 7, then forward to Step 9, and watch the phi crystallize in real time.

---

## 🏆 The Correct Architecture: Event-Based

The current design risks building a **massive coupled visualization system**. The correct architecture is:

```
Compiler
    ↓
Phase Serializer
    ↓
Event Stream   (list of CompilerEvent objects)
    ↓
Visualization Engine   (subscribes to events, renders)
```

**Everything is event-based.** The compiler emits events. The UI subscribes.

### Compiler Event Model

| Event | Emitted By | Payload |
|-------|-----------|---------|
| `token_created` | Lexer | `{kind, text, line, col}` |
| `ast_node_reduced` | Parser | `{node_type, children, source_range}` |
| `scope_entered` | NameResolver | `{scope_name, parent}` |
| `name_bound` | NameResolver | `{name, definition_site}` |
| `type_inferred` | TypeChecker | `{expr, type, confidence}` |
| `block_created` | CFG Lowering | `{block_id, predecessor}` |
| `phi_inserted` | SSATransformer | `{block, variable, inputs}` |
| `variable_renamed` | SSATransformer | `{old_name, new_name, version}` |
| `constant_folded` | ConstProp | `{phi_target, constant_value, reason}` |
| `block_eliminated` | DeadCodeElim | `{block_id, reason}` |
| `instruction_removed` | DeadCodeElim | `{instruction, reason}` |
| `identity_simplified` | ValueProp | `{before, after, identity}` |
| `copy_collapsed` | CopyProp | `{chain, resolved_to}` |
| `phi_destroyed` | SSADestructor | `{phi, copy_sequence}` |
| `c_line_emitted` | CCodegen | `{block_id, c_code}` |

With this model, the visualization becomes a **pure event consumer**. Swap out the renderer (2D → 3D → terminal → IDE plugin) without touching the compiler.

---

## 🚀 "Transformation Stories" — Signature Feature

This could be the most memorable feature. After each major optimization, show a natural-language story:

```
📖 SSA Constant Propagation — Step 9

Condition found:    if 1 < 2
Evaluated at:       compile time
Result:             always True

Consequence:
  The false branch (Block B3) can never execute.
  Block B3 and all instructions inside it are now dead.

Optimization applied:
  Dead block B3 eliminated.
  Jump from B1 simplified: unconditional JUMP → B2.

Lines of source affected: 4–7
Performance gain: removed 3 instructions from hot path.
```

**This changes the system from a graph viewer into a compiler explainer.** That is a fundamentally different product.

---

## 🚀 Runtime Execution Overlay (Future Phase)

During VM execution, highlight live:
- The currently executing CFG block (glows)
- Current SSA variable values (shown as live badges on nodes)
- VM stack depth (animated bar)
- Hot paths (blocks executed 100+ times turn progressively hotter — yellow → orange → red)
- Branch frequency (edge thickness grows with execution count)

This becomes **live execution introspection** — watching the program run through the compiler's own representation. Extremely rare capability.

---

## 🚨 What to Remove or Deprioritize

| Element | Decision | Reason |
|---------|---------|--------|
| Glowing token bead rail | **Deprioritize** | Low long-term value; tokens aren't interesting |
| Token 3D pillar animation | **Cut from v1** | Beautiful but adds no semantic insight |
| 10 simultaneous layers | **Replace with progressive disclosure** | Cognitive overload |
| Binary hex dump panel | **Defer to v3** | Far from the compiler's domain |
| Physics (blocks falling) | **Keep subtle only** | Fun but can distract from meaning |

**What matters most:**
- ✅ Semantic linkage across layers
- ✅ Transformation reasoning (why, not just what)
- ✅ Optimization traceability
- ✅ Timeline replay
- ✅ Explainability

---

## 🏁 Revised Priority Order (Build in This Sequence)

| Priority | What to Build | Why First |
|----------|--------------|-----------|
| **1** | Event-based compiler architecture (`CompilerEvent` model) | Everything else depends on this |
| **2** | 2D AST + CFG + SSA visualizer (2D only) | Fastest path to working product |
| **3** | Timeline replay system (scrubber, step-through) | Core interaction model |
| **4** | Cross-layer linking (click token → light up SSA) | The real killer feature |
| **5** | Optimization explanations ("why" metadata) | Turns it from a viewer into an explainer |
| **6** | Transformation Stories (natural language per pass) | Signature/memorable feature |
| **7** | Runtime execution overlays (VM introspection) | Requires VM instrumentation |
| **8** | AI error explainer integration | Depends on stable event model |
| **9** | Heatmaps + execution profiling | Requires runtime data |
| **10** | 3D Observatory (layer stack, fly-through camera) | Build last — rendering is easiest part |

> **Key insight:** The difficult engineering challenge is not rendering. It is **semantic synchronization** — maintaining correct mappings between source, AST, CFG, SSA, and runtime across every transformation. Build that data model first. The visuals come naturally after.

---

## 🏆 Final Verdict: What This Is Actually Becoming

This is no longer a "compiler project with nice graphs."

This is evolving into:

> **A visual semantic introspection platform for programming languages.**

It exposes:
- Structure (how code is organized)
- Flow (how control moves)
- Transformations (how the compiler changes the representation)
- Reasoning (why each optimization fires)
- Runtime behavior (how the program actually executes)

That positioning is **far more differentiated** than competing on:
- Language coverage
- Raw execution speed
- LLVM compatibility

The correct analogy: **an MRI for compilers**. Not a compiler with a pretty UI — a tool that makes the invisible mechanics of compilation visible, navigable, and understandable.

---

*Review written May 2026. Build event architecture first. Ship 2D before 3D. Prioritize "why" over "what".*

---

---

# 💡 The Next Level — A Better Idea: The Compiler Debugger Protocol

> Everything above builds a visualizer. This proposes something categorically different.
> A visualizer shows you what happened. A debugger lets you intervene, rewind, and ask "what if."

---

## The Core Shift in Thinking

The existing design answers: **"What did the compiler do?"**

The better question is: **"Why did the compiler produce *this* output, and what would happen if it did something different?"**

That shift — from observation to interrogation — is the difference between a **dashboard** and a **debugger**.

The proposal: build a **Compiler Debugger Protocol (CDP)** — modeled on Chrome DevTools Protocol, but for compilation internals instead of runtime JavaScript.

---

## What Exists vs. What This Proposes

| Existing Plan | This Proposal |
|--------------|--------------|
| Watch compilation happen | Pause, inspect, and resume compilation |
| See what changed | Ask why, get a causal explanation |
| Replay a fixed recording | Rewind and re-run with modified passes |
| One visualization app | A protocol any tool can speak |
| Static event stream | Live bidirectional debugger session |

---

## The Three New Ideas

---

### 💡 Idea 1: Compilation Breakpoints

Just like `gdb` lets you pause a running *program*, this lets you pause a running *compilation*.

```python
# Example: pause compilation when DCE tries to eliminate a block
compiler.set_breakpoint(
    pass_name="SSADeadCodeEliminator",
    event_type="block_eliminated",
    condition=lambda e: e.block_id == "B3"
)

result = compiler.compile(source)
# → compilation PAUSES at the breakpoint
# → visualizer shows the exact CFG state at that moment
# → user can inspect every variable, every phi node
# → user hits "Continue" or "Step Over" to proceed
```

**Why this matters:** You can stop time inside the compiler. No more "I wonder what the CFG looked like just before that block got eliminated." You just set a breakpoint and look.

**Breakpoint types:**

| Breakpoint | When it fires |
|-----------|--------------|
| `pass_start(pass_name)` | Before a pass runs |
| `pass_end(pass_name)` | After a pass runs |
| `block_eliminated(block_id)` | When DCE removes a block |
| `phi_inserted(variable)` | When SSA places a phi-node |
| `type_inferred(expr, type)` | When type checker resolves a type |
| `instruction_changed(before, after)` | Any instruction-level mutation |
| `conditional` | Any breakpoint with a `lambda` condition |

---

### 💡 Idea 2: Time-Travel Compilation (Fork & Replay)

Every existing visualization design captures events linearly. This proposes **compilation as a version-controlled tree** — not a single timeline but a branching history.

```
Compilation history:

main ──●──●──●──●──●──●──● (normal compile)
                │
                └──●──●──●  (fork: applied ValueProp before ConstProp)
                        │
                        └──●  (fork: disabled DCE entirely)
```

**How it works:**

1. Every compilation phase checkpoints its state (cheaply, using structural sharing — not full deepcopy)
2. The user can **fork** from any checkpoint
3. On a fork, they can: reorder passes, disable a pass, inject a custom pass
4. The result of each fork is compared side-by-side

**The UI: Side-by-side diff of two compilations**

```
┌─────────────────────────┬─────────────────────────┐
│  Run A (normal)         │  Run B (no DCE)          │
│                         │                          │
│  CFG: 3 blocks          │  CFG: 7 blocks           │
│  Instructions: 12       │  Instructions: 19        │
│  B3: [ELIMINATED]       │  B3: x.2 = y.1 + 0       │
│                         │     (dead, never reached) │
│                         │                          │
│  C output: 45 lines     │  C output: 67 lines      │
└─────────────────────────┴─────────────────────────┘
Semantic diff: both produce identical runtime output.
Performance diff: Run A is 32% fewer instructions.
```

**Why this is genuinely new:** No compiler tool does this. Researchers manually modify source code or pass flags to explore optimization tradeoffs. This makes it interactive and instant.

---

### 💡 Idea 3: The Compilation Replay Format (.crf)

A portable, self-contained binary format that captures a complete compilation trace — every event, every state snapshot, every transformation with its reason.

Think: `.har` files for HTTP sessions, `.cpuprofile` for Chrome performance recordings. But for compilations.

```
my_program.crf
├── metadata.json          (compiler version, source hash, flags)
├── source.py              (original source code)
├── events/
│   ├── 0001_token_created.json
│   ├── 0002_token_created.json
│   │   ...
│   ├── 0847_phi_inserted.json
│   ├── 0848_block_eliminated.json
│   │   ...
│   └── 1203_c_line_emitted.json
├── snapshots/
│   ├── after_ssa_construction.pkl
│   ├── after_constant_prop.pkl
│   └── after_dce.pkl
└── stories/
    ├── constant_prop_story.md
    └── dce_story.md
```

**What you can do with a `.crf` file:**

| Action | Description |
|--------|-------------|
| Open in visualizer | Full replay of the compilation, step by step |
| `crf diff a.crf b.crf` | Compare two compilations of different source versions |
| Share with a colleague | They see exactly your compilation — reproducible bug reports |
| `crf blame B3 eliminated` | Trace back which pass and which decision eliminated B3 |
| `crf annotate source.py` | Annotate source with which instructions each line produced |
| Upload to a web viewer | No local install — open `compiler.tools/view?crf=<url>` |

**Bug reporting revolution:** Instead of "my program produces wrong output," you send a `.crf` file. The recipient opens it, sees the exact compilation that went wrong, and can pinpoint the exact step where the error was introduced.

---

## The Compiler Debugger Protocol (CDP)

This is the infrastructure that makes all three ideas work together.

A **bidirectional JSON-over-WebSocket protocol** between the compiler and any visualization tool.

```
Compiler Process                     Debugger Client (browser/IDE)
      │                                        │
      │ ←── {"method": "Compilation.pause",    │
      │       "params": {"after_pass":         │
      │       "SSAConstantPropagation"}} ───── │
      │                                        │
      │ ──→ {"event": "Compilation.paused",    │
      │       "state": { CFG snapshot }}  ───→ │
      │                                        │
      │ ←── {"method": "Compilation.step"}     │
      │ ──→ {"event": "phi_inserted", ...} ──→ │
      │                                        │
      │ ←── {"method": "Compilation.fork",     │
      │       "params": {"disable_pass":       │
      │       "SSADeadCodeEliminator"}} ─────  │
      │                                        │
      │ ──→ (runs fork compilation) ────────→  │
      │ ──→ {"event": "fork_complete",         │
      │       "diff": { A vs B }} ──────────→  │
```

**CDP Methods:**

| Method | Action |
|--------|--------|
| `Compilation.start(source)` | Begin compilation |
| `Compilation.pause()` | Pause at current step |
| `Compilation.step()` | Execute one event and pause |
| `Compilation.continue()` | Run until next breakpoint |
| `Compilation.setBreakpoint(...)` | Set a breakpoint |
| `Compilation.fork(modifications)` | Fork from current state |
| `Compilation.getState()` | Get full current CFG snapshot |
| `Compilation.export(format)` | Export as `.crf`, JSON, or SVG |
| `Compilation.blame(node_id)` | Trace which pass created/modified a node |

**CDP Events:**

Everything from the compiler event model, plus:
- `Compilation.paused` — hit a breakpoint
- `Compilation.forked` — fork completed
- `Compilation.completed` — all passes done
- `Compilation.diffReady` — A/B diff computed

---

## What This Enables (That Nothing Else Does)

### 1. "Blame" Mode

*"I see instruction `x__ssa_3 = 42` in the C output. How did it get there?"*

```
$ crf blame --instruction "x__ssa_3 = 42"

Trace:
  Step 003 │ token_created        │ source: line 2, col 4: `x`
  Step 041 │ ast_node_reduced     │ AssignStmt(x, ConstantExpr(42))
  Step 187 │ block_created        │ B0: x.0 = LoadConst(42)
  Step 312 │ variable_renamed     │ x.0 → x__ssa_0
  Step 445 │ constant_folded      │ phi x__ssa_2 → x__ssa_0 (all inputs = 42)
  Step 521 │ copy_collapsed       │ x__ssa_3 ← x__ssa_0 (chain collapsed)
  Step 698 │ c_line_emitted       │ int x__ssa_3 = 42;
```

This is **provenance tracking** all the way from source token to machine instruction. No compiler tool does this today.

---

### 2. Optimization Sensitivity Analysis

*"How much does disabling each pass change the output?"*

Run `n` fork compilations, one per pass disabled. Report:

```
Pass Sensitivity Analysis for: loop_program.py

Pass                      │ Instructions removed │ Size change │ Semantic change
──────────────────────────┼──────────────────────┼─────────────┼────────────────
SSAConstantPropagation    │ 7                    │ -18%        │ None
SSADeadCodeEliminator     │ 4                    │ -11%        │ None
SSAValuePropagation       │ 2                    │ -5%         │ None
SSACopyPropagation        │ 1                    │ -2%         │ None

Recommendation: ConstantPropagation is highest value for this program.
```

---

### 3. Compiler Correctness Oracle

Run the same program through both VM and native lanes. Compare outputs. If they differ — flag a compiler bug.

```
Correctness Check: loop_program.py

VM output:    55
Native output: 55
Status: ✅ Both lanes agree

Correctness Check: edge_case.py

VM output:    -1
Native output: 0
Status: ❌ DIVERGENCE DETECTED
  Possible cause: augmented assignment on complex target (BUG-003)
  Affected pass: IR Lowering → C Codegen
  .crf file saved: edge_case_bug.crf
```

This turns the compiler into its own test oracle. Any semantic divergence between VM and native is automatically a bug report.

---

### 4. Compiler as a Learning Tool (Classroom Mode)

A `--classroom` mode that:
- Slows down every pass to human speed
- Speaks each transformation aloud ("Now I am inserting a phi node at block B2 because x is defined in two predecessor blocks...")
- Shows prerequisites: "To understand why this phi node is here, first look at the dominator tree"
- Has quizzes: "Which of these blocks will be eliminated by dead code elimination? (A) B2 (B) B3 (C) B4"
- Tracks student understanding across sessions

This is the educational application. University-level compiler courses could use this instead of drawing CFGs on whiteboards.

---

## Architecture Summary

```
┌──────────────────────────────────────────────────────────────────────┐
│                    COMPILER DEBUGGER PROTOCOL                        │
│                                                                      │
│  Python Source                                                       │
│      ↓                                                               │
│  Instrumented Compiler Pipeline                                      │
│      ↓  (emits CompilerEvents with full provenance)                  │
│  Event Store (append-only, indexed by node ID)                       │
│      ↓                                                               │
│  CDP Server (WebSocket, port 7474)                                   │
│      ↓          ↓           ↓            ↓                           │
│  Browser    IDE Plugin   CLI Tool    .crf Exporter                   │
│  Visualizer  (VSCode)   (crf blame)  (share/archive)                 │
│                                                                      │
│  Shared Data Model:                                                  │
│    TransformationEvent { pass, event_type, before, after,            │
│                          reason, affected_nodes, source_loc }        │
│    CompilationCheckpoint { cfg_snapshot, event_index }               │
│    ForkResult { run_a, run_b, semantic_diff, size_diff }             │
└──────────────────────────────────────────────────────────────────────┘
```

---

## Why This Is Better Than Everything Before It

| Previous Design | This Design |
|----------------|-------------|
| Watch compilation | Debug compilation |
| Fixed recording | Live, pauseable, forkable |
| "What happened" | "Why, and what if" |
| One visualization | Protocol — any client can connect |
| Pretty graphs | Actionable information |
| Educational tool | Educational + research + debugging tool |
| App | Platform |

The previous design is a **compiler movie player**. This is a **compiler gdb**.

---

## Build Order for This Proposal

| Week | Milestone |
|------|-----------|
| 1 | `TransformationEvent` dataclass + provenance tracking in all 6 SSA passes |
| 2 | Event store with node-ID index (enables "blame") |
| 3 | CDP WebSocket server — `start`, `pause`, `step`, `continue` |
| 4 | 2D visualizer as first CDP client (subscribes to event stream) |
| 5 | Breakpoints + fork/replay infrastructure |
| 6 | `.crf` file format — export and import |
| 7 | `crf blame` CLI tool |
| 8 | Side-by-side diff viewer (A vs B compilation) |
| 9 | Correctness oracle (VM vs native comparison) |
| 10 | Classroom mode + 3D Observatory as second CDP client |

---

## One-Line Summary

> Stop building a compiler visualizer.
> Build a **compiler debugger** — and make the visualizer just one of many clients that connects to it.

That's the idea.

---

*Proposed May 2026. The CDP architecture unlocks every feature in this document and beyond.*

---

---

# 🌌 The Unified Vision — The Compiler Observatory

> Combining both ideas: the live 3D visualization layer **is** the primary CDP client.
> The debugger's event stream **is** what drives every animation.
> One platform. One data model. Two faces — visual and programmatic.

---

## The Synthesis Insight

The visualization design asked: *"How do we show compilation beautifully?"*

The debugger protocol asked: *"How do we make compilation interrogatable?"*

The answer to both is the same: **a live, event-driven, bidirectional connection between the compiler and its observer.**

The visualization was always going to need the event stream to animate correctly.
The debugger was always going to need a UI to show what it paused on.

They are the same system. Split into two because we were thinking about them separately.

---

## Unified Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                                                                             │
│                     THE COMPILER OBSERVATORY                                │
│                                                                             │
│   ┌─────────────────────────────────────────────────────────────────────┐  │
│   │                  INSTRUMENTED COMPILER CORE                         │  │
│   │                                                                     │  │
│   │  Source → Lexer → Parser → Semantic → CFG → SSA → Passes → Codegen │  │
│   │                     ↓ at every micro-step                           │  │
│   │             TransformationEvent { type, before, after,              │  │
│   │                                   reason, affected_nodes,           │  │
│   │                                   source_loc, pass_name }           │  │
│   └──────────────────────────┬──────────────────────────────────────────┘  │
│                              │                                              │
│                    Event Store + CDP Server                                 │
│                    (WebSocket, port 7474)                                   │
│                    breakpoints · checkpoints · forks                        │
│                              │                                              │
│          ┌───────────────────┼───────────────────┐                         │
│          ▼                   ▼                   ▼                         │
│  ┌──────────────┐   ┌──────────────┐   ┌──────────────────┐               │
│  │  2D PANEL    │   │  3D OBSERVATORY│  │  CLI / IDE / .crf│               │
│  │  (focus mode)│   │  (layer stack) │  │  (blame, diff)   │               │
│  └──────────────┘   └──────────────┘   └──────────────────┘               │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

The compiler emits one event stream. Every client — the 2D panel, the 3D observatory, the CLI `blame` tool, the `.crf` exporter — subscribes to the same stream. **No duplication. No separate data models.**

---

## How Each Feature from Both Ideas Maps to the Unified System

### From the Visualization Design

| Feature | How It Works in Unified System |
|---------|-------------------------------|
| Token stream animation | Subscribes to `token_created` events → animates bead rail |
| AST node snap-together | Subscribes to `ast_node_reduced` events → animates tree build |
| φ-node gold diamond spawn | Subscribes to `phi_inserted` events → materializes diamond |
| Dead block sinking | Subscribes to `block_eliminated` events → triggers sink animation |
| Crystallization of constant phi | Subscribes to `constant_folded` events → plays crystallize animation |
| Cross-layer highlight | Click any node → CDP `blame(node_id)` → highlights its full trace |
| Timeline scrubber | Scrubbing to step N → CDP `Compilation.pause(at_step=N)` → renders that checkpoint |
| 3D layer stack rotation | Same event data rendered by Three.js instead of D3 |

### From the Debugger Protocol

| Feature | How It Works in Unified System |
|---------|-------------------------------|
| Compilation breakpoints | Set via UI: right-click a pass → "Pause before this pass" |
| Fork & replay | UI: drag any checkpoint, click "Fork" → opens side-by-side diff panel |
| `.crf` export | File menu → "Save Compilation Recording" → `my_program.crf` |
| `crf blame` | Click any instruction in the C code panel → provenance trace appears |
| Correctness oracle | Toolbar button: "Run VM vs Native" → diff panel shows divergence |
| Sensitivity analysis | Toolbar button: "Analyze Passes" → runs N forks, shows table |
| Classroom mode | Mode selector in top bar |

---

## The Unified UI Layout

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ 🌌 Compiler Observatory  [2D ▼] [3D] [Debug] [Classroom]      [● REC] [⚙]  │
├─────────────┬──────────────────────────────────────────┬──────────────────────┤
│             │                                          │                      │
│  CODE       │         MAIN VISUALIZATION CANVAS        │  INSPECTOR           │
│  EDITOR     │                                          │  ──────────────────  │
│             │  [Phase Tabs]                            │  Node: phi x.2       │
│  x = 10     │  Lexer │ AST │ Semantic │ CFG │ SSA ★  │  Type: φ-node        │
│  if x > 5:  │        ↓ (active phase rendered here)   │  Inputs:             │
│    y = x+1  │                                          │   B0 → x.0 = 10     │
│  else:      │  ┌─────────┐    ┌─────────┐             │   B1 → x.1 = 20     │
│    y = x-1  │  │  B0     │──▶ │  B1     │             │  Reason for φ:       │
│  print(y)   │  │ x.0=10  │    │ x.1=20  │             │  x defined in 2      │
│             │  └────┬────┘    └────┬────┘             │  predecessor blocks  │
│  [▶ Run]    │       └──────┬───────┘                  │                      │
│  [⏸ Pause] │         ┌────▼────┐                     │  [Blame this node]   │
│  [⑂ Fork]  │         │  B2     │ ← glowing            │  [Set Breakpoint]    │
│             │         │ φ(x.2)  │                     │  [Fork from here]    │
│  STORY      │         │PRINT x.2│                     │                      │
│  ─────────  │         └─────────┘                     │                      │
│  SSA built  │                                          │                      │
│  x renamed  │                                          │                      │
│  x.0 → x.2  │                                          │                      │
├─────────────┴──────────────────────────────────────────┴──────────────────────┤
│  ◀◀  ◀  [━━━━━━━━━━━━━━━━━━━━━━━●━━━━━━━━━━━━━━━] ▶  ▶▶   Step 8 / 42     │
│  SSA Construction — phi inserted: x.2 = φ(B0: x.0, B1: x.1)                 │
└──────────────────────────────────────────────────────────────────────────────┘
```

**Four modes, same data:**

| Mode | Primary View | Best For |
|------|-------------|---------|
| **2D** | Phase tabs, flat panels, D3 graph | Debugging, reading instructions |
| **3D** | Layer stack, Three.js, camera orbit | Demos, presentations, deep exploration |
| **Debug** | Breakpoints, fork panel, blame trace | Compiler development, bug hunting |
| **Classroom** | Narration, quizzes, step-locked | Teaching, learning compiler theory |

---

## The Unified Interaction Model

### Scenario A: Educational Use

1. Open Observatory, select **Classroom mode**
2. Paste `x = 10; y = x + 5; print(y)`
3. Click **Run** — compilation plays at 1 step/second with narration
4. At SSA step: "Quiz: will a φ-node be inserted here? Yes / No"
5. Answer → explanation appears in Inspector
6. Continue → watch dead code elimination remove zero dead blocks
7. Export: **Save as `.crf`** → share with classmates

### Scenario B: Debugging a Compiler Bug

1. Open Observatory, select **Debug mode**
2. Paste program that produces wrong C output
3. Set breakpoint: right-click "SSAConstantPropagation" → "Pause before"
4. Click **Run** — compilation halts at breakpoint
5. Inspector shows exact CFG state
6. Click **Step** → watch each phi node collapse
7. Notice: phi `x.3` collapsed incorrectly
8. Right-click `x.3` → **Blame** → trace shows it came from line 4 with wrong input
9. **Fork** → disable ConstantPropagation → compare output
10. Export `.crf` → file a bug report with the exact reproduction trace

### Scenario C: Research — Optimization Exploration

1. Open Observatory, select **Debug mode**
2. Paste a loop-heavy program
3. Click **Analyze Passes** → runs 4 fork compilations
4. Sensitivity table shows: ConstProp removes 40% of instructions
5. Fork: reorder ValueProp before ConstProp → compare result
6. 3D mode: fly through both compilations' layer stacks simultaneously
7. Export both as `.crf` → `crf diff run_a.crf run_b.crf`

### Scenario D: Conference Demo

1. Open Observatory, select **3D mode**
2. Paste a 10-line program
3. Click **Run** — camera pulls back to show all 10 layers simultaneously
4. Watch tokens fly up from source, snap into AST, lower into CFG
5. φ-nodes appear as spinning gold diamonds
6. Dead block sinks with a physics drop
7. Camera flies to Layer 8 (C code) — typewriter effect
8. Audience: *wow*

---

## The Unified Data Model (One Schema for Everything)

```python
@dataclass
class CompilerEvent:
    """Single event type. Every feature subscribes to this."""
    event_id: int                    # monotonic, globally unique
    timestamp: float                 # seconds since compilation start
    pass_name: str                   # "SSAConstantPropagation"
    event_type: str                  # "phi_inserted", "block_eliminated", ...
    source_loc: tuple[int,int] | None  # (line, col) in original source
    node_id: str                     # unique ID of the affected node
    before: str                      # human-readable before state
    after: str                       # human-readable after state
    reason: str                      # WHY this happened (the key innovation)
    affected_nodes: list[str]        # all node IDs touched by this event
    viz_layer: int                   # which 3D layer (0=source, 9=binary)
    story_fragment: str | None       # natural-language sentence for Classroom mode
    checkpoint_id: str | None        # if this event creates a fork point


@dataclass
class CompilationSession:
    """Everything about one compilation run."""
    session_id: str
    source: str
    events: list[CompilerEvent]      # the full ordered event log
    checkpoints: dict[str, CFGModule]  # snapshots for fork/rewind
    stories: list[str]               # per-pass natural language explanations
    forks: dict[str, "CompilationSession"]  # child sessions from forks
```

**One schema powers:**
- 2D animation (subscribes to `events`)
- 3D animation (same events, different renderer)
- Timeline scrubber (seek to `event_id`)
- Blame trace (filter `events` by `node_id`)
- Fork/replay (branch at `checkpoint_id`)
- `.crf` file (serialize `CompilationSession`)
- Classroom narration (use `story_fragment`)
- Correctness oracle (compare two `CompilationSession.events`)

---

## What This Becomes

Combining both ideas produces something with no direct equivalent:

| Existing Tool | What It Does | What's Missing |
|---------------|-------------|----------------|
| **Godbolt / Compiler Explorer** | Shows assembly output | No intermediate stages, no replay, no debug |
| **LLVM viz tools** | Shows CFG as static graph | No animation, no timeline, no blame |
| **Python Tutor** | Shows runtime execution | Shows runtime, not compilation |
| **GDB** | Debugs runtime programs | Can't debug the compiler itself |
| **This project** | **Debugs and visualizes compilation itself** | Nothing in this space |

The gap is real. No tool today lets you:
- Watch SSA construction happen step by step
- Pause compilation at a specific optimization
- Fork and compare two optimization orderings
- Trace an instruction back to its source token
- Export a reproducible compilation recording

This project would be the first to do all five simultaneously.

---

## Revised Final Priority Order (Unified)

| Priority | What | Why |
|----------|------|-----|
| **1** | `CompilerEvent` dataclass + provenance in SSA passes | Foundation of everything |
| **2** | CDP WebSocket server + event store | Powers all clients |
| **3** | 2D phase visualizer (first CDP client) | Fastest working demo |
| **4** | Timeline scrubber + checkpoint system | Core interaction |
| **5** | Breakpoints + pause/step/continue | Makes it a debugger |
| **6** | Cross-layer blame (click → trace) | The killer feature |
| **7** | Transformation Stories (reason strings) | Makes it an explainer |
| **8** | Fork & replay + diff panel | Research/power users |
| **9** | `.crf` format + CLI tools | Sharing & persistence |
| **10** | 3D Observatory (second CDP client) | Showcase / demos |
| **11** | Correctness oracle (VM vs native) | Self-testing |
| **12** | Classroom mode + quizzes | Education |
| **13** | Heatmaps + execution overlays | Advanced |

---

## One-Line Summary of the Combined Vision

> **The Compiler Observatory** — a live, pauseable, forkable, 3D-explorable debugger for the entire compilation pipeline, from source token to machine instruction, with cross-layer semantic traceability and a portable replay format.

Not a visualizer. Not a debugger. Both. One platform.

---

*Combined vision written May 2026.*
*Start with `CompilerEvent`. Everything else follows.*

---

---

# 🗺️ Strategic Build Guide — Tools, Order, and the Honest Answer

> Where to start, what to install, and yes — finish the compiler first.

---

## The Honest Answer First

**Yes. Finish the compiler before building the observatory.**

Here is why:

The observatory visualizes the compiler's internal state. If the compiler has bugs — silent drops, wrong types, incorrect SSA, diverging lanes — then the visualization faithfully shows you **wrong things beautifully**. That is worse than no visualization at all because it looks correct.

The three compiler bugs that would break the observatory most severely right now:

| Bug | Why It Breaks Viz |
|-----|-------------------|
| **BUG-001** — `->` annotation drops entire function silently | Visualizer shows a program that doesn't match what the user typed |
| **BUG-011** — `yield from` raises `NotImplementedError` at runtime | Crashes the event stream mid-compilation |
| **IR lowering — range-only loops** | Half of loop programs fall to VM lane and produce no CFG to visualize |

Fix these three first. Everything else in the observatory can be built correctly after.

---

## Gate: What the Compiler Needs to Be Before You Build the Observatory

Work through this checklist before writing any observatory code:

### Gate 1 — Compiler Stability (Must Complete First)

- [ ] **BUG-001**: Stop dropping functions with `->` annotations — parse but ignore annotation
- [ ] **BUG-005**: Parse tuple exception types `except (TypeError, ValueError):`
- [ ] **BUG-008**: Fix SSA name sanitization collision edge case
- [ ] **BUG-011**: Implement `yield from` in VM or raise a clean user-facing error
- [ ] Delete the 6 `tmp*.py` files from project root — they pollute the module graph
- [ ] Migrate stale root `test_*.py` files into `tests/` — confirm all tests pass

**Estimated time:** 3–5 days  
**Signal that Gate 1 is done:** `python run_tests.py` shows 0 failures

---

### Gate 2 — Native Lane Stability (Must Complete Before Observatory SSA Phase)

The SSA visualizer only has something to show if programs successfully reach the native lane. Right now most programs fall back to VM.

- [ ] Generalize IR `for` loop lowering beyond `range()` only
- [ ] Verify SSA ConstantPropagation, DeadCodeEliminator, CopyPropagation all pass clean on 10 example programs
- [ ] Verify C codegen produces correct output for the 5 example programs listed in this doc

**Estimated time:** 1 week  
**Signal that Gate 2 is done:** All 5 example programs in this doc compile through native lane and print correct output

---

## Tools Needed — Full List

### Python (Backend)

| Package | Purpose | Install |
|---------|---------|---------|
| `dataclasses` | `CompilerEvent`, `CompilationSession` | stdlib — already there |
| `copy` | Checkpointing SSA state | stdlib — already there |
| `json` | Event serialization / CDP messages | stdlib — already there |
| `asyncio` + `websockets` | CDP WebSocket server | `pip install websockets` |
| `http.server` | Minimal HTTP server for HTML | stdlib — already there |
| `pickle` | Fast CFG snapshot serialization | stdlib — already there |
| `zipfile` | `.crf` file format (zip container) | stdlib — already there |
| `pytest` | Replacing `run_tests.py` | `pip install pytest` |

**No new heavy dependencies needed for the core.** The entire CDP server + event store can run on stdlib + `websockets`.

---

### JavaScript (Frontend — loaded from CDN, nothing to install)

| Library | CDN | Purpose |
|---------|-----|---------|
| **Cytoscape.js** | `cdnjs` | CFG/AST graph rendering — best-in-class for node graphs |
| **Cytoscape-dagre** | `cdnjs` | Automatic hierarchical layout for CFG/AST |
| **D3.js v7** | `cdnjs` | Token stream rail, timelines, heatmaps |
| **CodeMirror 6** | `cdnjs` | Source editor with syntax highlighting + range markers |
| **GSAP 3** | `cdnjs` | Animation sequencing — phi crystallize, block sink |
| **Three.js r160** | `cdnjs` | 3D layer stack (Phase 10 only) |
| **OrbitControls** | bundled with Three.js | Camera drag/zoom in 3D mode |

**For Phase 1–9 (everything except 3D):** Cytoscape.js + D3 + CodeMirror + GSAP is sufficient.  
**Three.js is only needed for Phase 10 — 3D Observatory.**

---

### Development Tools

| Tool | Purpose | Install |
|------|---------|---------|
| `python -m http.server` | Serving the HTML during development | stdlib |
| Browser DevTools | Debugging the visualization JS | built-in |
| `websocat` (optional) | Testing CDP WebSocket manually | `brew install websocat` |
| `jq` (optional) | Inspecting `.crf` JSON from CLI | `brew install jq` |

---

## Build Order — Phase by Phase

### Phase 0 — Finish the Compiler (Gate 1 + Gate 2)
**Do this first. Do not skip it.**

```
compiler/frontend/parser/stmt_parser.py  ← fix BUG-001 (→ annotation)
compiler/frontend/parser/stmt_parser.py  ← fix BUG-005 (tuple except)
compiler/ir/lowering.py                  ← generalize for-loop beyond range()
compiler/ir/ssa.py                       ← verify all 4 passes clean
compiler/backend/c_codegen.py            ← verify 5 example programs work
```

**Done when:** 5 example programs all produce correct C output.

---

### Phase 1 — The Event Model (1 week)
**This is the foundation. Everything else builds on it.**

```
compiler/viz/__init__.py         ← create (1 line)
compiler/viz/events.py           ← CompilerEvent dataclass
compiler/viz/session.py          ← CompilationSession dataclass
compiler/viz/ssa_tracer.py       ← instruments SSA passes with events
compiler/viz/phase_serializer.py ← serializes all phases to event list
```

**Test it:** `python -c "from compiler.viz.ssa_tracer import SSATracer; print('ok')"`

**Done when:** Running a program produces a `CompilationSession` with a full `events` list you can print.

---

### Phase 2 — CDP Server (3 days)
**The server that everything connects to.**

```
viz_server.py     ← HTTP + WebSocket server
                     routes: GET / → ssa_viz.html
                              POST /compile → runs pipeline, returns session JSON
                              WS /debug → CDP bidirectional channel
```

**Test it:** `python viz_server.py` → `curl -X POST http://localhost:7474/compile -d '{"source":"x=1"}'`

**Done when:** You can POST a source string and get back a full `CompilationSession` JSON.

---

### Phase 3 — 2D Visualizer, CFG + SSA only (2 weeks)
**The first real UI. Focus mode: CFG and SSA tabs only.**

```
ssa_viz.html     ← single HTML file
                    CodeMirror editor (left)
                    Cytoscape.js CFG graph (center)
                    Inspector panel (right)
                    Timeline scrubber (bottom)
```

**Do NOT build all 10 phases at once.** Build CFG + SSA first. Ship that. Then add other phases.

**Done when:** You can type a program, click Run, and watch the CFG appear. Clicking the SSA tab shows φ-nodes.

---

### Phase 4 — Animation (1 week)
**Add GSAP animations to the existing graph. Don't rebuild — animate what's already there.**

```
ssa_viz.html    ← add GSAP animations:
                   phi_inserted     → diamond materializes
                   block_eliminated → block sinks + fades
                   constant_folded  → crystallize
                   copy_collapsed   → edge reroutes
```

**Done when:** Clicking through the timeline scrubber plays smooth animations between steps.

---

### Phase 5 — Blame + Cross-Layer (1 week)
**The killer feature.**

```
compiler/viz/events.py  ← add node_id tracking to every event
ssa_viz.html            ← right-click any node → "Blame"
                           show filtered event list for that node_id
                           highlight corresponding source range in CodeMirror
```

**Done when:** You can right-click a φ-node, see every event that touched it, and the source line glows.

---

### Phase 6 — Transformation Stories (3 days)
**Add reason strings to every event.**

```
compiler/viz/ssa_tracer.py  ← add reason= to every event emitted
ssa_viz.html                ← Story panel: show reason string for current step
                               format as natural language, not raw data
```

**Done when:** Each step shows a one-sentence explanation like "Phi x.2 collapsed because both inputs equal constant 5."

---

### Phase 7 — Breakpoints + Fork (2 weeks)
**Turns it from a visualizer into a debugger.**

```
compiler/viz/session.py    ← add checkpoint() method (structural share)
viz_server.py              ← CDP methods: setBreakpoint, step, fork
ssa_viz.html               ← Debug mode UI:
                               right-click pass → "Pause before"
                               Fork button → opens diff panel
```

**Done when:** You can pause compilation at SSADeadCodeEliminator, inspect state, then fork with it disabled.

---

### Phase 8 — `.crf` Format (1 week)

```
compiler/viz/crf.py   ← export CompilationSession → .crf (zipfile)
compiler/viz/crf.py   ← import .crf → CompilationSession
crf_cli.py            ← CLI: crf blame, crf diff, crf annotate
```

**Done when:** `python crf_cli.py blame my_program.crf --node x__ssa_3` prints a full trace.

---

### Phase 9 — Remaining 2D Phases (1 week)
**Now add the other phases to the visualizer — after CFG/SSA is solid.**

```
ssa_viz.html  ← add tabs: Lexer | AST | Semantic | Codegen
               Lexer:    token strip (D3)
               AST:      Cytoscape tree
               Semantic: nested scope bubbles (D3)
               Codegen:  typewriter C panel
```

---

### Phase 10 — 3D Observatory (2 weeks, optional)
**The showcase feature. Build it last because the hard part (event model) is already done.**

```
ssa_viz_3d.html   ← Three.js layer stack
                     7 floating planes at Z=0 to Z=6
                     same CompilationSession events, different renderer
                     OrbitControls for camera
                     GSAP for inter-layer animations
```

---

## Summary: The Real Build Order

```
┌────────────────────────────────────────────────────────────┐
│                                                            │
│  MUST DO FIRST                                             │
│  ─────────────────────────────────────────────────────     │
│  0. Fix BUG-001, BUG-005, BUG-011            (3–5 days)   │
│  0. Generalize IR for-loop                    (3 days)     │
│  0. Verify 5 example programs compile native  (2 days)     │
│                                                            │
│  THEN BUILD                                                │
│  ─────────────────────────────────────────────────────     │
│  1. CompilerEvent + SSATracer                 (1 week)     │
│  2. CDP WebSocket server                      (3 days)     │
│  3. 2D CFG + SSA panels (no animation yet)    (1 week)     │
│  4. GSAP animations for SSA passes            (1 week)     │
│  5. Blame + cross-layer highlight             (1 week)     │
│  6. Transformation Stories (reason strings)   (3 days)     │
│  7. Breakpoints + Fork/Replay                 (2 weeks)    │
│  8. .crf format + CLI                         (1 week)     │
│  9. Remaining 2D phases (Lexer, AST, Sem)     (1 week)     │
│  10. 3D Observatory                           (2 weeks)    │
│                                                            │
│  TOTAL: ~12 weeks from clean compiler baseline             │
│                                                            │
└────────────────────────────────────────────────────────────┘
```

---

## The One-Sentence Answer

> Fix the three critical compiler bugs, verify 5 programs compile through native lane, then start with `CompilerEvent` — the visualization, the debugger, the `.crf` format, and the 3D Observatory all follow automatically from that one dataclass.

---

*Strategic guide written May 2026.*
