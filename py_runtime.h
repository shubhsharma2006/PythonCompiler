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

/* Container element type ids */
enum {
    PY_ELEM_INT = 1,
    PY_ELEM_FLOAT = 2,
    PY_ELEM_BOOL = 3,
    PY_ELEM_STR = 4,
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

typedef struct PyList {
    int element_type;
    size_t size;
    size_t capacity;
    void *items;
} PyList;

typedef struct PyTuple {
    int element_type;
    size_t size;
    void *items;
} PyTuple;

/* Reference-counted allocation helpers */
void *py_malloc(size_t size, int type_id);
void *py_malloc_site(size_t size, int type_id, const char *file, int line);
void py_incref(void *obj);
void py_decref(void *obj);

void py_runtime_init(void);

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

/* Exception state (scaffolding) */
typedef struct {
    int active;
    const char *type;
    const char *message;
} PyErrorState;

int py_error_occurred(void);
void py_set_error(const char *type, const char *message);
void py_clear_error(void);
const char *py_error_type(void);
const char *py_error_message(void);
int py_error_matches(const char *type);

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
const char *py_str_get_index(const char *value, int index);
const char *py_str_slice(const char *value, int start, int end, int step, int has_start, int has_end, int has_step);
int py_len_str(const char *value);

/* Container helpers */
PyList *py_list_new_int(size_t size);
PyList *py_list_new_float(size_t size);
PyList *py_list_new_bool(size_t size);
PyList *py_list_new_str(size_t size);
void py_list_set_int(PyList *list, int index, int value);
void py_list_set_float(PyList *list, int index, double value);
void py_list_set_bool(PyList *list, int index, int value);
void py_list_set_str(PyList *list, int index, const char *value);
int py_list_get_int(PyList *list, int index);
double py_list_get_float(PyList *list, int index);
int py_list_get_bool(PyList *list, int index);
const char *py_list_get_str(PyList *list, int index);
int py_list_len(PyList *list);
PyList *py_list_slice_int(PyList *list, int start, int end, int step, int has_start, int has_end, int has_step);
PyList *py_list_slice_float(PyList *list, int start, int end, int step, int has_start, int has_end, int has_step);
PyList *py_list_slice_bool(PyList *list, int start, int end, int step, int has_start, int has_end, int has_step);
PyList *py_list_slice_str(PyList *list, int start, int end, int step, int has_start, int has_end, int has_step);
int py_list_eq_int(PyList *left, PyList *right);
int py_list_eq_float(PyList *left, PyList *right);
int py_list_eq_bool(PyList *left, PyList *right);
int py_list_eq_str(PyList *left, PyList *right);
int py_list_contains_int(PyList *list, int value);
int py_list_contains_float(PyList *list, double value);
int py_list_contains_bool(PyList *list, int value);
int py_list_contains_str(PyList *list, const char *value);
const char *py_list_repr_int(PyList *list);
const char *py_list_repr_float(PyList *list);
const char *py_list_repr_bool(PyList *list);
const char *py_list_repr_str(PyList *list);
PyTuple *py_tuple_new_int(size_t size);
PyTuple *py_tuple_new_float(size_t size);
PyTuple *py_tuple_new_bool(size_t size);
PyTuple *py_tuple_new_str(size_t size);
void py_tuple_set_int(PyTuple *tuple, int index, int value);
void py_tuple_set_float(PyTuple *tuple, int index, double value);
void py_tuple_set_bool(PyTuple *tuple, int index, int value);
void py_tuple_set_str(PyTuple *tuple, int index, const char *value);
int py_tuple_get_int(PyTuple *tuple, int index);
double py_tuple_get_float(PyTuple *tuple, int index);
int py_tuple_get_bool(PyTuple *tuple, int index);
const char *py_tuple_get_str(PyTuple *tuple, int index);
int py_tuple_len(PyTuple *tuple);
PyTuple *py_tuple_slice_int(PyTuple *tuple, int start, int end, int step, int has_start, int has_end, int has_step);
PyTuple *py_tuple_slice_float(PyTuple *tuple, int start, int end, int step, int has_start, int has_end, int has_step);
PyTuple *py_tuple_slice_bool(PyTuple *tuple, int start, int end, int step, int has_start, int has_end, int has_step);
PyTuple *py_tuple_slice_str(PyTuple *tuple, int start, int end, int step, int has_start, int has_end, int has_step);
int py_tuple_eq_int(PyTuple *left, PyTuple *right);
int py_tuple_eq_float(PyTuple *left, PyTuple *right);
int py_tuple_eq_bool(PyTuple *left, PyTuple *right);
int py_tuple_eq_str(PyTuple *left, PyTuple *right);
int py_tuple_contains_int(PyTuple *tuple, int value);
int py_tuple_contains_float(PyTuple *tuple, double value);
int py_tuple_contains_bool(PyTuple *tuple, int value);
int py_tuple_contains_str(PyTuple *tuple, const char *value);
const char *py_tuple_repr_int(PyTuple *tuple);
const char *py_tuple_repr_float(PyTuple *tuple);
const char *py_tuple_repr_bool(PyTuple *tuple);
const char *py_tuple_repr_str(PyTuple *tuple);

/* Arithmetic helpers */
int py_floor_div_int(int a, int b);
int py_mod_int(int a, int b);
int py_pow_int(int base, int exp);

/* Truthiness helpers */
int py_truthy_int(int value);
int py_truthy_float(double value);
int py_truthy_str(const char *value);
int py_truthy_list(PyList *value);
int py_truthy_tuple(PyTuple *value);

#ifdef __cplusplus
}
#endif

#endif
