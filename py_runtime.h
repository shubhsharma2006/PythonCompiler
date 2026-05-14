#ifndef PY_RUNTIME_H
#define PY_RUNTIME_H

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/* Runtime type ids (extend as needed) */
enum {
    PY_TYPE_UNKNOWN = 0,
    PY_TYPE_STR = 1,
    PY_TYPE_LIST = 2,
    PY_TYPE_DICT = 3,
    PY_TYPE_SET = 4,
    PY_TYPE_TUPLE = 5,
    PY_TYPE_OBJECT = 6,
    PY_TYPE_FUNCTION = 7,
};

/* GC/ownership header */
typedef struct PyObjectHeader {
    int refcount;
    int type_id;
    uint32_t flags;
    struct PyObjectHeader *gc_next;
    struct PyObjectHeader *gc_prev;
    const char *alloc_file;
    int alloc_line;
} PyObjectHeader;

/* Reference-counted allocation helpers */
void *py_malloc(size_t size, int type_id);
void *py_malloc_site(size_t size, int type_id, const char *file, int line);
void py_incref(void *obj);
void py_decref(void *obj);

/* GC helpers (scaffolding) */
void gc_register(PyObjectHeader *header);
void gc_unregister(PyObjectHeader *header);
size_t py_gc_count(void);
void py_gc_collect(void);
void py_dump_live_objects(void);

/* Type metadata/visitor hooks */
typedef void (*py_destroy_fn)(void *obj);
typedef void (*py_visit_fn)(void *obj, void (*visit)(void *child, void *ctx), void *ctx);
void py_register_type(int type_id, const char *name, py_destroy_fn destroy, py_visit_fn visit);
void py_visit_children(void *obj, void (*visit)(void *child, void *ctx), void *ctx);

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
