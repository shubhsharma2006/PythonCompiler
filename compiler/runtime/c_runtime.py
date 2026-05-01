from __future__ import annotations

import os

from compiler.core.types import ValueType, c_type_name


class CRuntimeSupport:
    header_name = "py_runtime.h"
    source_name = "py_runtime.c"

    def include_directive(self) -> str:
        return f'#include "{self.header_name}"'

    def header_source(self) -> str:
        return "\n".join(
            [
                "#ifndef PY_RUNTIME_H",
                "#define PY_RUNTIME_H",
                "",
                "#ifdef __cplusplus",
                'extern "C" {',
                "#endif",
                "",
                "/* Print with newline */",
                "void py_print_int(int value);",
                "void py_print_float(double value);",
                "void py_print_str(const char *value);",
                "void py_print_bool(int value);",
                "",
                "/* Print without newline (raw) */",
                "void py_write_int(int value);",
                "void py_write_float(double value);",
                "void py_write_str(const char *value);",
                "void py_write_bool(int value);",
                "",
                "/* Type conversions */",
                "const char *py_int_to_str(int value);",
                "const char *py_float_to_str(double value);",
                "const char *py_bool_to_str(int value);",
                "const char *py_str_identity(const char *value);",
                "",
                "/* String operations */",
                "const char *py_str_concat(const char *a, const char *b);",
                "",
                "/* Arithmetic helpers */",
                "int py_floor_div_int(int a, int b);",
                "int py_mod_int(int a, int b);",
                "int py_pow_int(int base, int exp);",
                "",
                "/* Truthiness helpers */",
                "int py_truthy_int(int value);",
                "int py_truthy_float(double value);",
                "int py_truthy_str(const char *value);",
                "",
                "#ifdef __cplusplus",
                "}",
                "#endif",
                "",
                "#endif",
                "",
            ]
        )

    def implementation_source(self) -> str:
        return "\n".join(
            [
                '#include "py_runtime.h"',
                "",
                "#include <stdio.h>",
                "#include <stdlib.h>",
                "#include <string.h>",
                "#include <limits.h>",
                "",
                "void py_print_int(int value) {",
                '    printf("%d\\n", value);',
                "}",
                "",
                "void py_print_float(double value) {",
                '    printf("%g\\n", value);',
                "}",
                "",
                "void py_print_str(const char *value) {",
                '    printf("%s\\n", value ? value : "");',
                "}",
                "",
                "void py_print_bool(int value) {",
                '    printf("%s\\n", value ? "True" : "False");',
                "}",
                "",
                "void py_write_int(int value) {",
                '    printf("%d", value);',
                "}",
                "",
                "void py_write_float(double value) {",
                '    printf("%g", value);',
                "}",
                "",
                "void py_write_str(const char *value) {",
                '    printf("%s", value ? value : "");',
                "}",
                "",
                "void py_write_bool(int value) {",
                '    printf("%s", value ? "True" : "False");',
                "}",
                "",
                "const char *py_int_to_str(int value) {",
                "    char *buf = (char *)malloc(32);",
                '    snprintf(buf, 32, "%d", value);',
                "    return buf;",
                "}",
                "",
                "const char *py_float_to_str(double value) {",
                "    char *buf = (char *)malloc(64);",
                '    snprintf(buf, 64, "%g", value);',
                "    return buf;",
                "}",
                "",
                "const char *py_bool_to_str(int value) {",
                '    return value ? "True" : "False";',
                "}",
                "",
                "const char *py_str_identity(const char *value) {",
                '    return value ? value : "";',
                "}",
                "",
                "const char *py_str_concat(const char *a, const char *b) {",
                '    const char *sa = a ? a : "";',
                '    const char *sb = b ? b : "";',
                "    size_t la = strlen(sa);",
                "    size_t lb = strlen(sb);",
                "    char *result = (char *)malloc(la + lb + 1);",
                "    memcpy(result, sa, la);",
                "    memcpy(result + la, sb, lb + 1);",
                "    return result;",
                "}",
                "",
                "int py_floor_div_int(int a, int b) {",
                "    /* Python semantics: floor(a / b) for integers. */",
                "    if (b == 0) {",
                "        /* Match Python's runtime error loosely; we abort for now. */",
                "        fprintf(stderr, \"ZeroDivisionError: integer division or modulo by zero\\n\");",
                "        abort();",
                "    }",
                "    int q = a / b;",
                "    int r = a % b;",
                "    /* If remainder is non-zero and signs differ, round down. */",
                "    if (r != 0 && ((r > 0) != (b > 0))) {",
                "        q -= 1;",
                "    }",
                "    return q;",
                "}",
                "",
                "int py_pow_int(int base, int exp) {",
                "    /* Python semantics for ints: exp < 0 yields float in Python; we don't support that in native mode. */",
                "    if (exp < 0) {",
                "        fprintf(stderr, \"ValueError: negative exponent not supported for int pow in native mode\\n\");",
                "        abort();",
                "    }",
                "    int result = 1;",
                "    int b = base;",
                "    int e = exp;",
                "    while (e > 0) {",
                "        if (e & 1) {",
                "            result = result * b;",
                "        }",
                "        e >>= 1;",
                "        if (e) {",
                "            b = b * b;",
                "        }",
                "    }",
                "    return result;",
                "}",
                "",
                "int py_mod_int(int a, int b) {",
                "    /* Python semantics: a % b has the sign of b and is defined via floor division. */",
                "    if (b == 0) {",
                "        fprintf(stderr, \"ZeroDivisionError: integer modulo by zero\\n\");",
                "        abort();",
                "    }",
                "    int q = py_floor_div_int(a, b);",
                "    return a - q * b;",
                "}",
                "",
                "int py_truthy_int(int value) {",
                "    return value != 0;",
                "}",
                "",
                "int py_truthy_float(double value) {",
                "    return value != 0.0;",
                "}",
                "",
                "int py_truthy_str(const char *value) {",
                "    return value && value[0] != '\\0';",
                "}",
                "",
            ]
        )

    def emit_files(self, output_path: str) -> tuple[str, str]:
        directory = os.path.dirname(os.path.abspath(output_path)) or "."
        header_path = os.path.join(directory, self.header_name)
        source_path = os.path.join(directory, self.source_name)

        with open(header_path, "w", encoding="utf-8") as handle:
            handle.write(self.header_source())
        with open(source_path, "w", encoding="utf-8") as handle:
            handle.write(self.implementation_source())

        return header_path, source_path

    def print_call(self, value_name: str, value_type: ValueType, newline: bool = True) -> str:
        helper = self._print_helper_name(value_type, newline)
        return f"{helper}({value_name});"

    @staticmethod
    def _print_helper_name(value_type: ValueType, newline: bool = True) -> str:
        if newline:
            if value_type == ValueType.FLOAT:
                return "py_print_float"
            if value_type == ValueType.STRING:
                return "py_print_str"
            if value_type == ValueType.BOOL:
                return "py_print_bool"
            return "py_print_int"
        else:
            if value_type == ValueType.FLOAT:
                return "py_write_float"
            if value_type == ValueType.STRING:
                return "py_write_str"
            if value_type == ValueType.BOOL:
                return "py_write_bool"
            return "py_write_int"

    @staticmethod
    def str_converter(value_type: ValueType) -> str:
        if value_type == ValueType.INT:
            return "py_int_to_str"
        if value_type == ValueType.FLOAT:
            return "py_float_to_str"
        if value_type == ValueType.BOOL:
            return "py_bool_to_str"
        if value_type == ValueType.STRING:
            return "py_str_identity"
        return "py_int_to_str"

    @staticmethod
    def runtime_type_name(value_type: ValueType) -> str:
        return c_type_name(value_type)
