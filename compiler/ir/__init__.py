from compiler.ir.cfg import (
    Assign,
    BasicBlock,
    BinaryOp,
    BranchTerminator,
    Call,
    CFGFunction,
    CFGModule,
    DecRef,
    IRInstruction,
    JumpTerminator,
    LoadConst,
    Phi,
    Print,
    ReturnTerminator,
    UnaryOp,
)
from compiler.ir.analysis import compute_dominators, reachable_block_names, rebuild_edges, reverse_post_order
from compiler.ir.lowering import CFGLowering
from compiler.ir.passes import CFGConstantPropagation
from compiler.ir.ownership import OwnerKind, SSAValueInfo, default_value_info
from compiler.ir.ownership_pass import OwnershipDecrefPlacement
from compiler.ir.exception_analysis import ExceptionalLivenessAnalysis
from compiler.ir.ssa import (
    SSAConstantPropagation,
    SSACopyPropagation,
    SSADeadCodeEliminator,
    SSADestructor,
    SSAValuePropagation,
    SSATransformer,
    build_use_def_map,
    dominance_frontiers,
    immediate_dominators,
    replace_ssa_uses,
    ssa_defined_name,
    ssa_uses,
)

IRGenerator = CFGLowering
IRFunction = CFGFunction
IRModule = CFGModule

__all__ = [
    "Assign",
    "BasicBlock",
    "BinaryOp",
    "BranchTerminator",
    "Call",
    "CFGFunction",
    "CFGModule",
    "DecRef",
    "CFGConstantPropagation",
    "CFGLowering",
    "IRFunction",
    "IRGenerator",
    "IRInstruction",
    "IRModule",
    "OwnerKind",
    "SSAValueInfo",
    "default_value_info",
    "OwnershipDecrefPlacement",
    "ExceptionalLivenessAnalysis",
    "Phi",
    "JumpTerminator",
    "LoadConst",
    "Phi",
    "Print",
    "ReturnTerminator",
    "SSAConstantPropagation",
    "SSACopyPropagation",
    "SSADeadCodeEliminator",
    "SSADestructor",
    "SSAValuePropagation",
    "SSATransformer",
    "build_use_def_map",
    "UnaryOp",
    "compute_dominators",
    "dominance_frontiers",
    "immediate_dominators",
    "reachable_block_names",
    "rebuild_edges",
    "replace_ssa_uses",
    "reverse_post_order",
    "ssa_defined_name",
    "ssa_uses",
]
