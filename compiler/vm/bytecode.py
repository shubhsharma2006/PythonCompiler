from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Instruction:
    opcode: str
    arg: object | None = None

    def __str__(self) -> str:
        return self.opcode if self.arg is None else f"{self.opcode} {self.arg}"


@dataclass
class BytecodeFunction:
    key: str
    name: str
    params: list[str]
    owner_class_name: str | None = None
    is_generator: bool = False
    kwonly_params: list[str] = field(default_factory=list)
    kwonly_defaults: dict[str, object] = field(default_factory=dict)
    vararg_name: str | None = None
    kwarg_name: str | None = None
    instructions: list[Instruction] = field(default_factory=list)
    defaults: list[object] = field(default_factory=list)
    global_names: set[str] = field(default_factory=set)
    nonlocal_names: set[str] = field(default_factory=set)

    def __str__(self) -> str:
        prefix = "generator " if self.is_generator else "function "
        lines = [f"{prefix}{self.name} [{self.key}] ({', '.join(self.params)})"]
        for index, instruction in enumerate(self.instructions):
            lines.append(f"  {index:04}: {instruction}")
        return "\n".join(lines)


@dataclass
class BytecodeModule:
    name: str
    filename: str
    functions: dict[str, BytecodeFunction]
    top_level_bindings: dict[str, str]
    entrypoint: BytecodeFunction

    def __str__(self) -> str:
        sections = [f"module {self.name} ({self.filename})", "", str(self.entrypoint)]
        for name in sorted(self.functions):
            sections.append(str(self.functions[name]))
        return "\n\n".join(sections)
