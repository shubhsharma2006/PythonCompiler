#ifndef PY_RUNTIME_H
#define PY_RUNTIME_H

#ifdef __cplusplus
extern "C" {
#endif

/* Print with newline */
void py_print_int(int value);
void py_print_float(double value);
void py_print_str(const char *value);
void py_print_bool(int value);

/* Print without newline (raw) */
void py_write_int(int value);
void py_write_float(double value);
void py_write_str(const char *value);
void py_write_bool(int value);

/* Type conversions */
const char *py_int_to_str(int value);
const char *py_float_to_str(double value);
const char *py_bool_to_str(int value);
const char *py_str_identity(const char *value);

/* String operations */
const char *py_str_concat(const char *a, const char *b);

/* Arithmetic helpers */
int py_floor_div_int(int a, int b);
int py_mod_int(int a, int b);
int py_pow_int(int base, int exp);

/* Truthiness helpers */
int py_truthy_int(int value);
int py_truthy_float(double value);
int py_truthy_str(const char *value);

#ifdef __cplusplus
}
#endif

#endif
