#include "py_runtime.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define PY_GC_FLAG_LIVE 0x1u

typedef struct {
    const char *name;
    py_destroy_fn destroy;
    py_visit_fn visit;
} PyTypeInfo;

static PyObjectHeader *gc_head = NULL;
static PyObjectHeader *gc_tail = NULL;
static size_t gc_live_count = 0;
static size_t gc_total_allocs = 0;
static size_t gc_total_frees = 0;
static PyErrorState py_error_state = {0, NULL, NULL};

static PyTypeInfo type_registry[256] = {
    [PY_TYPE_UNKNOWN] = {"unknown", NULL, NULL},
    [PY_TYPE_STR] = {"str", NULL, NULL},
    [PY_TYPE_LIST] = {"list", NULL, NULL},
    [PY_TYPE_DICT] = {"dict", NULL, NULL},
    [PY_TYPE_SET] = {"set", NULL, NULL},
    [PY_TYPE_TUPLE] = {"tuple", NULL, NULL},
    [PY_TYPE_OBJECT] = {"object", NULL, NULL},
    [PY_TYPE_FUNCTION] = {"function", NULL, NULL},
};

static PyObjectHeader *py_lookup_header(void *obj) {
    if (!obj) return NULL;
    PyObjectHeader *p = gc_head;
    while (p) {
        if ((void *)(p + 1) == obj) {
            return p;
        }
        p = p->gc_next;
    }
    return NULL;
}

void gc_register(PyObjectHeader *header) {
    if (!header) return;
    header->gc_prev = gc_tail;
    header->gc_next = NULL;
    if (gc_tail) {
        gc_tail->gc_next = header;
    } else {
        gc_head = header;
    }
    gc_tail = header;
    gc_live_count += 1;
    gc_total_allocs += 1;
}

void gc_unregister(PyObjectHeader *header) {
    if (!header) return;
    if (header->gc_prev) {
        header->gc_prev->gc_next = header->gc_next;
    } else {
        gc_head = header->gc_next;
    }
    if (header->gc_next) {
        header->gc_next->gc_prev = header->gc_prev;
    } else {
        gc_tail = header->gc_prev;
    }
    header->gc_next = NULL;
    header->gc_prev = NULL;
    if (gc_live_count > 0) gc_live_count -= 1;
    gc_total_frees += 1;
}

void *py_malloc_site(size_t size, int type_id, const char *file, int line) {
    PyObjectHeader *header = (PyObjectHeader *)malloc(sizeof(PyObjectHeader) + size);
    if (!header) {
        py_set_error("MemoryError", "allocation failed");
        return NULL;
    }
    header->refcount = 1;
    header->type_id = type_id;
    header->flags = PY_GC_FLAG_LIVE;
    header->gc_next = NULL;
    header->gc_prev = NULL;
    header->alloc_file = file;
    header->alloc_line = line;
    gc_register(header);
    return (void *)(header + 1);
}

void *py_malloc(size_t size, int type_id) {
    return py_malloc_site(size, type_id, NULL, 0);
}

void py_incref(void *obj) {
    PyObjectHeader *header = py_lookup_header(obj);
    if (!header) return;
    header->refcount += 1;
}

void py_decref(void *obj) {
    PyObjectHeader *header = py_lookup_header(obj);
    if (!header) return;
    header->refcount -= 1;
    if (header->refcount <= 0) {
        PyTypeInfo *info = &type_registry[header->type_id & 0xFF];
        if (info && info->destroy) {
            info->destroy(obj);
        }
        gc_unregister(header);
        free(header);
    }
}

size_t py_gc_count(void) {
    return gc_live_count;
}

void py_gc_collect(void) {
    /* scaffolding: log live objects; no sweep yet */
    fprintf(stderr, "[py_gc_collect] live objects = %zu\n", py_gc_count());
}

void py_dump_live_objects(void) {
    fprintf(stderr, "Leaked Objects:\n----------------\n");
    PyObjectHeader *p = gc_head;
    while (p) {
        const char *name = type_registry[p->type_id & 0xFF].name;
        if (!name) name = "unknown";
        const char *file = p->alloc_file ? p->alloc_file : "<unknown>";
        int line = p->alloc_line;
        fprintf(stderr, "%s @ %p refcount=%d\n", name, (void *)(p + 1), p->refcount);
        fprintf(stderr, "Allocated at: %s:%d\n", file, line);
        p = p->gc_next;
    }
    fprintf(stderr, "Total allocs: %zu, frees: %zu, live: %zu\n", gc_total_allocs, gc_total_frees, gc_live_count);
}

void py_register_type(int type_id, const char *name, py_destroy_fn destroy, py_visit_fn visit) {
    if (type_id < 0 || type_id >= 256) return;
    type_registry[type_id].name = name ? name : "unknown";
    type_registry[type_id].destroy = destroy;
    type_registry[type_id].visit = visit;
}

void py_visit_children(void *obj, void (*visit)(void *child, void *ctx), void *ctx) {
    PyObjectHeader *header = py_lookup_header(obj);
    if (!header) return;
    PyTypeInfo *info = &type_registry[header->type_id & 0xFF];
    if (info && info->visit) {
        info->visit(obj, visit, ctx);
    }
}

static int py_runtime_initialized = 0;

static void py_list_destroy(void *obj) {
    PyList *list = (PyList *)obj;
    if (!list) return;
    if (list->items) {
        if (list->element_type == PY_ELEM_STR) {
            const char **items = (const char **)list->items;
            for (size_t i = 0; i < list->size; i++) {
                if (items[i]) py_decref((void *)items[i]);
            }
        }
        free(list->items);
        list->items = NULL;
    }
    list->size = 0;
    list->capacity = 0;
}

static void py_tuple_destroy(void *obj) {
    PyTuple *tuple = (PyTuple *)obj;
    if (!tuple) return;
    if (tuple->items) {
        if (tuple->element_type == PY_ELEM_STR) {
            const char **items = (const char **)tuple->items;
            for (size_t i = 0; i < tuple->size; i++) {
                if (items[i]) py_decref((void *)items[i]);
            }
        }
        free(tuple->items);
        tuple->items = NULL;
    }
    tuple->size = 0;
}

void py_runtime_init(void) {
    if (py_runtime_initialized) return;
    py_runtime_initialized = 1;
    py_register_type(PY_TYPE_LIST, "list", py_list_destroy, NULL);
    py_register_type(PY_TYPE_TUPLE, "tuple", py_tuple_destroy, NULL);
}

static PyList *py_list_alloc(int element_type, size_t size, size_t item_size) {
    PyList *list = (PyList *)py_malloc(sizeof(PyList), PY_TYPE_LIST);
    if (!list) return NULL;
    list->element_type = element_type;
    list->size = size;
    list->capacity = size;
    list->items = NULL;
    if (size > 0) {
        list->items = calloc(size, item_size);
        if (!list->items) {
            py_set_error("MemoryError", "allocation failed");
            py_decref(list);
            return NULL;
        }
    }
    return list;
}

static PyTuple *py_tuple_alloc(int element_type, size_t size, size_t item_size) {
    PyTuple *tuple = (PyTuple *)py_malloc(sizeof(PyTuple), PY_TYPE_TUPLE);
    if (!tuple) return NULL;
    tuple->element_type = element_type;
    tuple->size = size;
    tuple->items = NULL;
    if (size > 0) {
        tuple->items = calloc(size, item_size);
        if (!tuple->items) {
            py_set_error("MemoryError", "allocation failed");
            py_decref(tuple);
            return NULL;
        }
    }
    return tuple;
}

PyList *py_list_new_int(size_t size) {
    return py_list_alloc(PY_ELEM_INT, size, sizeof(int));
}

PyList *py_list_new_float(size_t size) {
    return py_list_alloc(PY_ELEM_FLOAT, size, sizeof(double));
}

PyList *py_list_new_bool(size_t size) {
    return py_list_alloc(PY_ELEM_BOOL, size, sizeof(int));
}

PyList *py_list_new_str(size_t size) {
    return py_list_alloc(PY_ELEM_STR, size, sizeof(const char *));
}

static int py_list_check_index(PyList *list, int index) {
    if (!list) {
        py_set_error("TypeError", "list is null");
        return 0;
    }
    if (index < 0 || (size_t)index >= list->size) {
        py_set_error("IndexError", "list index out of range");
        return 0;
    }
    return 1;
}

void py_list_set_int(PyList *list, int index, int value) {
    if (!py_list_check_index(list, index)) return;
    ((int *)list->items)[index] = value;
}

void py_list_set_float(PyList *list, int index, double value) {
    if (!py_list_check_index(list, index)) return;
    ((double *)list->items)[index] = value;
}

void py_list_set_bool(PyList *list, int index, int value) {
    if (!py_list_check_index(list, index)) return;
    ((int *)list->items)[index] = value ? 1 : 0;
}

void py_list_set_str(PyList *list, int index, const char *value) {
    if (!py_list_check_index(list, index)) return;
    const char **items = (const char **)list->items;
    if (items[index]) py_decref((void *)items[index]);
    items[index] = value;
    if (value) py_incref((void *)value);
}

int py_list_get_int(PyList *list, int index) {
    if (!py_list_check_index(list, index)) return 0;
    return ((int *)list->items)[index];
}

double py_list_get_float(PyList *list, int index) {
    if (!py_list_check_index(list, index)) return 0.0;
    return ((double *)list->items)[index];
}

int py_list_get_bool(PyList *list, int index) {
    if (!py_list_check_index(list, index)) return 0;
    return ((int *)list->items)[index];
}

const char *py_list_get_str(PyList *list, int index) {
    if (!py_list_check_index(list, index)) return "";
    return ((const char **)list->items)[index];
}

int py_list_len(PyList *list) {
    if (!list) {
        py_set_error("TypeError", "list is null");
        return 0;
    }
    return (int)list->size;
}

PyTuple *py_tuple_new_int(size_t size) {
    return py_tuple_alloc(PY_ELEM_INT, size, sizeof(int));
}

PyTuple *py_tuple_new_float(size_t size) {
    return py_tuple_alloc(PY_ELEM_FLOAT, size, sizeof(double));
}

PyTuple *py_tuple_new_bool(size_t size) {
    return py_tuple_alloc(PY_ELEM_BOOL, size, sizeof(int));
}

PyTuple *py_tuple_new_str(size_t size) {
    return py_tuple_alloc(PY_ELEM_STR, size, sizeof(const char *));
}

static int py_tuple_check_index(PyTuple *tuple, int index) {
    if (!tuple) {
        py_set_error("TypeError", "tuple is null");
        return 0;
    }
    if (index < 0 || (size_t)index >= tuple->size) {
        py_set_error("IndexError", "tuple index out of range");
        return 0;
    }
    return 1;
}

void py_tuple_set_int(PyTuple *tuple, int index, int value) {
    if (!py_tuple_check_index(tuple, index)) return;
    ((int *)tuple->items)[index] = value;
}

void py_tuple_set_float(PyTuple *tuple, int index, double value) {
    if (!py_tuple_check_index(tuple, index)) return;
    ((double *)tuple->items)[index] = value;
}

void py_tuple_set_bool(PyTuple *tuple, int index, int value) {
    if (!py_tuple_check_index(tuple, index)) return;
    ((int *)tuple->items)[index] = value ? 1 : 0;
}

void py_tuple_set_str(PyTuple *tuple, int index, const char *value) {
    if (!py_tuple_check_index(tuple, index)) return;
    const char **items = (const char **)tuple->items;
    if (items[index]) py_decref((void *)items[index]);
    items[index] = value;
    if (value) py_incref((void *)value);
}

int py_tuple_get_int(PyTuple *tuple, int index) {
    if (!py_tuple_check_index(tuple, index)) return 0;
    return ((int *)tuple->items)[index];
}

double py_tuple_get_float(PyTuple *tuple, int index) {
    if (!py_tuple_check_index(tuple, index)) return 0.0;
    return ((double *)tuple->items)[index];
}

int py_tuple_get_bool(PyTuple *tuple, int index) {
    if (!py_tuple_check_index(tuple, index)) return 0;
    return ((int *)tuple->items)[index];
}

const char *py_tuple_get_str(PyTuple *tuple, int index) {
    if (!py_tuple_check_index(tuple, index)) return "";
    return ((const char **)tuple->items)[index];
}

int py_tuple_len(PyTuple *tuple) {
    if (!tuple) {
        py_set_error("TypeError", "tuple is null");
        return 0;
    }
    return (int)tuple->size;
}

static void py_slice_normalize_bounds(size_t len, int start, int end, int step, int has_start, int has_end, int *out_start, int *out_end) {
    int s;
    int e;
    if (step > 0) {
        s = has_start ? start : 0;
        e = has_end ? end : (int)len;
        if (s < 0) s = (int)len + s;
        if (e < 0) e = (int)len + e;
        if (s < 0) s = 0;
        if (e < 0) e = 0;
        if (s > (int)len) s = (int)len;
        if (e > (int)len) e = (int)len;
        if (e < s) e = s;
    } else {
        s = has_start ? start : (int)len - 1;
        e = has_end ? end : -1;
        if (s < 0) s = (int)len + s;
        if (has_end && e < 0) e = (int)len + e;
        if (s >= (int)len) s = (int)len - 1;
        if (s < 0) s = -1;
        if (e >= (int)len) e = (int)len - 1;
        if (e < -1) e = -1;
    }
    *out_start = s;
    *out_end = e;
}

static size_t py_slice_result_length(int start, int end, int step) {
    size_t out_len = 0;
    if (step > 0) {
        for (int i = start; i < end; i += step) {
            out_len += 1;
        }
    } else {
        for (int i = start; i > end; i += step) {
            out_len += 1;
        }
    }
    return out_len;
}

#define PY_DEFINE_LIST_SLICE(NAME, CTYPE, ELEM_TYPE) \
PyList *py_list_slice_##NAME(PyList *list, int start, int end, int step, int has_start, int has_end, int has_step) { \
    int st = has_step ? step : 1; \
    if (st == 0) { \
        py_set_error("ValueError", "slice step cannot be zero"); \
        return NULL; \
    } \
    if (!list) { \
        py_set_error("TypeError", "list is null"); \
        return NULL; \
    } \
    if (list->element_type != ELEM_TYPE) { \
        py_set_error("TypeError", "list element type mismatch"); \
        return NULL; \
    } \
    int s; \
    int e; \
    py_slice_normalize_bounds(list->size, start, end, st, has_start, has_end, &s, &e); \
    size_t out_len = py_slice_result_length(s, e, st); \
    PyList *result = py_list_new_##NAME(out_len); \
    if (!result) return NULL; \
    size_t out_index = 0; \
    for (int i = s; st > 0 ? i < e : i > e; i += st) { \
        py_list_set_##NAME(result, (int)out_index, ((CTYPE *)list->items)[i]); \
        out_index += 1; \
    } \
    return result; \
}

#define PY_DEFINE_TUPLE_SLICE(NAME, CTYPE, ELEM_TYPE) \
PyTuple *py_tuple_slice_##NAME(PyTuple *tuple, int start, int end, int step, int has_start, int has_end, int has_step) { \
    int st = has_step ? step : 1; \
    if (st == 0) { \
        py_set_error("ValueError", "slice step cannot be zero"); \
        return NULL; \
    } \
    if (!tuple) { \
        py_set_error("TypeError", "tuple is null"); \
        return NULL; \
    } \
    if (tuple->element_type != ELEM_TYPE) { \
        py_set_error("TypeError", "tuple element type mismatch"); \
        return NULL; \
    } \
    int s; \
    int e; \
    py_slice_normalize_bounds(tuple->size, start, end, st, has_start, has_end, &s, &e); \
    size_t out_len = py_slice_result_length(s, e, st); \
    PyTuple *result = py_tuple_new_##NAME(out_len); \
    if (!result) return NULL; \
    size_t out_index = 0; \
    for (int i = s; st > 0 ? i < e : i > e; i += st) { \
        py_tuple_set_##NAME(result, (int)out_index, ((CTYPE *)tuple->items)[i]); \
        out_index += 1; \
    } \
    return result; \
}

PY_DEFINE_LIST_SLICE(int, int, PY_ELEM_INT)
PY_DEFINE_LIST_SLICE(float, double, PY_ELEM_FLOAT)
PY_DEFINE_LIST_SLICE(bool, int, PY_ELEM_BOOL)
PY_DEFINE_LIST_SLICE(str, const char *, PY_ELEM_STR)

PY_DEFINE_TUPLE_SLICE(int, int, PY_ELEM_INT)
PY_DEFINE_TUPLE_SLICE(float, double, PY_ELEM_FLOAT)
PY_DEFINE_TUPLE_SLICE(bool, int, PY_ELEM_BOOL)
PY_DEFINE_TUPLE_SLICE(str, const char *, PY_ELEM_STR)

static const char *py_str_quote(const char *value) {
    const char *src = value ? value : "";
    size_t extra = 2;
    for (const char *p = src; *p; ++p) {
        if (*p == '\\' || *p == '\'' || *p == '\n' || *p == '\r' || *p == '\t') {
            extra += 2;
        } else {
            extra += 1;
        }
    }
    char *result = (char *)py_malloc(extra + 1, PY_TYPE_STR);
    if (!result) return "";
    size_t pos = 0;
    result[pos++] = '\'';
    for (const char *p = src; *p; ++p) {
        if (*p == '\\' || *p == '\'') {
            result[pos++] = '\\';
            result[pos++] = *p;
        } else if (*p == '\n') {
            result[pos++] = '\\';
            result[pos++] = 'n';
        } else if (*p == '\r') {
            result[pos++] = '\\';
            result[pos++] = 'r';
        } else if (*p == '\t') {
            result[pos++] = '\\';
            result[pos++] = 't';
        } else {
            result[pos++] = *p;
        }
    }
    result[pos++] = '\'';
    result[pos] = '\0';
    return result;
}

static int py_list_check_type(PyList *list, int element_type) {
    if (!list) {
        py_set_error("TypeError", "list is null");
        return 0;
    }
    if (list->element_type != element_type) {
        py_set_error("TypeError", "list element type mismatch");
        return 0;
    }
    return 1;
}

static int py_tuple_check_type(PyTuple *tuple, int element_type) {
    if (!tuple) {
        py_set_error("TypeError", "tuple is null");
        return 0;
    }
    if (tuple->element_type != element_type) {
        py_set_error("TypeError", "tuple element type mismatch");
        return 0;
    }
    return 1;
}

#define PY_DEFINE_LIST_EQ(NAME, CTYPE, ELEM_TYPE, EQUALS_EXPR) \
int py_list_eq_##NAME(PyList *left, PyList *right) { \
    if (!py_list_check_type(left, ELEM_TYPE) || !py_list_check_type(right, ELEM_TYPE)) return 0; \
    if (left->size != right->size) return 0; \
    CTYPE *left_items = (CTYPE *)left->items; \
    CTYPE *right_items = (CTYPE *)right->items; \
    for (size_t i = 0; i < left->size; i++) { \
        CTYPE left_item = left_items[i]; \
        CTYPE right_item = right_items[i]; \
        if (!(EQUALS_EXPR)) return 0; \
    } \
    return 1; \
}

#define PY_DEFINE_TUPLE_EQ(NAME, CTYPE, ELEM_TYPE, EQUALS_EXPR) \
int py_tuple_eq_##NAME(PyTuple *left, PyTuple *right) { \
    if (!py_tuple_check_type(left, ELEM_TYPE) || !py_tuple_check_type(right, ELEM_TYPE)) return 0; \
    if (left->size != right->size) return 0; \
    CTYPE *left_items = (CTYPE *)left->items; \
    CTYPE *right_items = (CTYPE *)right->items; \
    for (size_t i = 0; i < left->size; i++) { \
        CTYPE left_item = left_items[i]; \
        CTYPE right_item = right_items[i]; \
        if (!(EQUALS_EXPR)) return 0; \
    } \
    return 1; \
}

#define PY_DEFINE_LIST_CONTAINS(NAME, CTYPE, ELEM_TYPE, EQUALS_EXPR) \
int py_list_contains_##NAME(PyList *list, CTYPE value) { \
    if (!py_list_check_type(list, ELEM_TYPE)) return 0; \
    CTYPE *items = (CTYPE *)list->items; \
    for (size_t i = 0; i < list->size; i++) { \
        CTYPE item = items[i]; \
        if (EQUALS_EXPR) return 1; \
    } \
    return 0; \
}

#define PY_DEFINE_TUPLE_CONTAINS(NAME, CTYPE, ELEM_TYPE, EQUALS_EXPR) \
int py_tuple_contains_##NAME(PyTuple *tuple, CTYPE value) { \
    if (!py_tuple_check_type(tuple, ELEM_TYPE)) return 0; \
    CTYPE *items = (CTYPE *)tuple->items; \
    for (size_t i = 0; i < tuple->size; i++) { \
        CTYPE item = items[i]; \
        if (EQUALS_EXPR) return 1; \
    } \
    return 0; \
}

PY_DEFINE_LIST_EQ(int, int, PY_ELEM_INT, left_item == right_item)
PY_DEFINE_LIST_EQ(float, double, PY_ELEM_FLOAT, left_item == right_item)
PY_DEFINE_LIST_EQ(bool, int, PY_ELEM_BOOL, left_item == right_item)
PY_DEFINE_LIST_EQ(str, const char *, PY_ELEM_STR, strcmp(left_item ? left_item : "", right_item ? right_item : "") == 0)

PY_DEFINE_TUPLE_EQ(int, int, PY_ELEM_INT, left_item == right_item)
PY_DEFINE_TUPLE_EQ(float, double, PY_ELEM_FLOAT, left_item == right_item)
PY_DEFINE_TUPLE_EQ(bool, int, PY_ELEM_BOOL, left_item == right_item)
PY_DEFINE_TUPLE_EQ(str, const char *, PY_ELEM_STR, strcmp(left_item ? left_item : "", right_item ? right_item : "") == 0)

PY_DEFINE_LIST_CONTAINS(int, int, PY_ELEM_INT, item == value)
PY_DEFINE_LIST_CONTAINS(float, double, PY_ELEM_FLOAT, item == value)
PY_DEFINE_LIST_CONTAINS(bool, int, PY_ELEM_BOOL, item == value)
PY_DEFINE_LIST_CONTAINS(str, const char *, PY_ELEM_STR, strcmp(item ? item : "", value ? value : "") == 0)

PY_DEFINE_TUPLE_CONTAINS(int, int, PY_ELEM_INT, item == value)
PY_DEFINE_TUPLE_CONTAINS(float, double, PY_ELEM_FLOAT, item == value)
PY_DEFINE_TUPLE_CONTAINS(bool, int, PY_ELEM_BOOL, item == value)
PY_DEFINE_TUPLE_CONTAINS(str, const char *, PY_ELEM_STR, strcmp(item ? item : "", value ? value : "") == 0)

#define PY_DEFINE_LIST_REPR(NAME, CTYPE, ELEM_TYPE, CONVERTER) \
const char *py_list_repr_##NAME(PyList *list) { \
    if (!py_list_check_type(list, ELEM_TYPE)) return ""; \
    const char **parts = list->size ? (const char **)calloc(list->size, sizeof(const char *)) : NULL; \
    if (list->size && !parts) { py_set_error("MemoryError", "allocation failed"); return ""; } \
    size_t total = 2; \
    CTYPE *items = (CTYPE *)list->items; \
    for (size_t i = 0; i < list->size; i++) { \
        parts[i] = CONVERTER(items[i]); \
        if (py_error_occurred()) { \
            for (size_t j = 0; j <= i; j++) py_decref((void *)parts[j]); \
            free(parts); \
            return ""; \
        } \
        total += strlen(parts[i]); \
        if (i + 1 < list->size) total += 2; \
    } \
    char *result = (char *)py_malloc(total + 1, PY_TYPE_STR); \
    if (!result) { \
        for (size_t i = 0; i < list->size; i++) py_decref((void *)parts[i]); \
        free(parts); \
        return ""; \
    } \
    size_t pos = 0; \
    result[pos++] = '['; \
    for (size_t i = 0; i < list->size; i++) { \
        size_t part_len = strlen(parts[i]); \
        memcpy(result + pos, parts[i], part_len); \
        pos += part_len; \
        if (i + 1 < list->size) { result[pos++] = ','; result[pos++] = ' '; } \
        py_decref((void *)parts[i]); \
    } \
    result[pos++] = ']'; \
    result[pos] = '\0'; \
    free(parts); \
    return result; \
}

#define PY_DEFINE_TUPLE_REPR(NAME, CTYPE, ELEM_TYPE, CONVERTER) \
const char *py_tuple_repr_##NAME(PyTuple *tuple) { \
    if (!py_tuple_check_type(tuple, ELEM_TYPE)) return ""; \
    const char **parts = tuple->size ? (const char **)calloc(tuple->size, sizeof(const char *)) : NULL; \
    if (tuple->size && !parts) { py_set_error("MemoryError", "allocation failed"); return ""; } \
    size_t total = 2; \
    if (tuple->size == 1) total += 1; \
    CTYPE *items = (CTYPE *)tuple->items; \
    for (size_t i = 0; i < tuple->size; i++) { \
        parts[i] = CONVERTER(items[i]); \
        if (py_error_occurred()) { \
            for (size_t j = 0; j <= i; j++) py_decref((void *)parts[j]); \
            free(parts); \
            return ""; \
        } \
        total += strlen(parts[i]); \
        if (i + 1 < tuple->size) total += 2; \
    } \
    char *result = (char *)py_malloc(total + 1, PY_TYPE_STR); \
    if (!result) { \
        for (size_t i = 0; i < tuple->size; i++) py_decref((void *)parts[i]); \
        free(parts); \
        return ""; \
    } \
    size_t pos = 0; \
    result[pos++] = '('; \
    for (size_t i = 0; i < tuple->size; i++) { \
        size_t part_len = strlen(parts[i]); \
        memcpy(result + pos, parts[i], part_len); \
        pos += part_len; \
        if (i + 1 < tuple->size) { result[pos++] = ','; result[pos++] = ' '; } \
        py_decref((void *)parts[i]); \
    } \
    if (tuple->size == 1) result[pos++] = ','; \
    result[pos++] = ')'; \
    result[pos] = '\0'; \
    free(parts); \
    return result; \
}

PY_DEFINE_LIST_REPR(int, int, PY_ELEM_INT, py_int_to_str)
PY_DEFINE_LIST_REPR(float, double, PY_ELEM_FLOAT, py_float_to_str)
PY_DEFINE_LIST_REPR(bool, int, PY_ELEM_BOOL, py_bool_to_str)
PY_DEFINE_LIST_REPR(str, const char *, PY_ELEM_STR, py_str_quote)

PY_DEFINE_TUPLE_REPR(int, int, PY_ELEM_INT, py_int_to_str)
PY_DEFINE_TUPLE_REPR(float, double, PY_ELEM_FLOAT, py_float_to_str)
PY_DEFINE_TUPLE_REPR(bool, int, PY_ELEM_BOOL, py_bool_to_str)
PY_DEFINE_TUPLE_REPR(str, const char *, PY_ELEM_STR, py_str_quote)

int py_error_occurred(void) {
    return py_error_state.active != 0;
}

void py_set_error(const char *type, const char *message) {
    py_error_state.active = 1;
    py_error_state.type = type ? type : "Error";
    py_error_state.message = message ? message : "";
}

void py_clear_error(void) {
    py_error_state.active = 0;
    py_error_state.type = NULL;
    py_error_state.message = NULL;
}

const char *py_error_type(void) {
    return py_error_state.type;
}

const char *py_error_message(void) {
    return py_error_state.message;
}

int py_error_matches(const char *type) {
    if (!py_error_state.active) return 0;
    if (!type || !py_error_state.type) return 0;
    return strcmp(py_error_state.type, type) == 0;
}

void py_print_int(int value) {
    printf("%d\n", value);
}

void py_print_float(double value) {
    printf("%g\n", value);
}

void py_print_str(const char *value) {
    printf("%s\n", value ? value : "");
}

void py_print_bool(int value) {
    printf("%s\n", value ? "True" : "False");
}

void py_write_int(int value) {
    printf("%d", value);
}

void py_write_float(double value) {
    printf("%g", value);
}

void py_write_str(const char *value) {
    printf("%s", value ? value : "");
}

void py_write_bool(int value) {
    printf("%s", value ? "True" : "False");
}

const char *py_int_to_str(int value) {
    char *buf = (char *)py_malloc(32, PY_TYPE_STR);
    if (!buf) return "";
    snprintf(buf, 32, "%d", value);
    return buf;
}

const char *py_float_to_str(double value) {
    char *buf = (char *)py_malloc(64, PY_TYPE_STR);
    if (!buf) return "";
    snprintf(buf, 64, "%g", value);
    return buf;
}

const char *py_bool_to_str(int value) {
    return value ? "True" : "False";
}

const char *py_str_identity(const char *value) {
    return value ? value : "";
}

const char *py_str_concat(const char *a, const char *b) {
    const char *sa = a ? a : "";
    const char *sb = b ? b : "";
    size_t la = strlen(sa);
    size_t lb = strlen(sb);
    char *result = (char *)py_malloc(la + lb + 1, PY_TYPE_STR);
    if (!result) return "";
    memcpy(result, sa, la);
    memcpy(result + la, sb, lb + 1);
    return result;
}

const char *py_str_get_index(const char *value, int index) {
    const char *str = value ? value : "";
    size_t len = strlen(str);
    int idx = index;
    if (idx < 0) {
        idx = (int)len + idx;
    }
    if (idx < 0 || (size_t)idx >= len) {
        py_set_error("IndexError", "string index out of range");
        return "";
    }
    char *result = (char *)py_malloc(2, PY_TYPE_STR);
    if (!result) return "";
    result[0] = str[idx];
    result[1] = '\0';
    return result;
}

const char *py_str_slice(const char *value, int start, int end, int step, int has_start, int has_end, int has_step) {
    const char *str = value ? value : "";
    size_t len = strlen(str);
    int st = has_step ? step : 1;
    if (st == 0) {
        py_set_error("ValueError", "slice step cannot be zero");
        return "";
    }
    int s;
    int e;
    if (st > 0) {
        s = has_start ? start : 0;
        e = has_end ? end : (int)len;
        if (s < 0) s = (int)len + s;
        if (e < 0) e = (int)len + e;
        if (s < 0) s = 0;
        if (e < 0) e = 0;
        if (s > (int)len) s = (int)len;
        if (e > (int)len) e = (int)len;
        if (e < s) e = s;
    } else {
        s = has_start ? start : (int)len - 1;
        e = has_end ? end : -1;
        if (s < 0) s = (int)len + s;
        if (has_end && e < 0) e = (int)len + e;
        if (s >= (int)len) s = (int)len - 1;
        if (s < 0) s = -1;
        if (e >= (int)len) e = (int)len - 1;
        if (e < -1) e = -1;
    }
    size_t out_len = 0;
    if (st > 0) {
        for (int i = s; i < e; i += st) {
            out_len += 1;
        }
    } else {
        for (int i = s; i > e; i += st) {
            out_len += 1;
        }
    }
    char *result = (char *)py_malloc(out_len + 1, PY_TYPE_STR);
    if (!result) return "";
    size_t pos = 0;
    if (st > 0) {
        for (int i = s; i < e; i += st) {
            result[pos++] = str[i];
        }
    } else {
        for (int i = s; i > e; i += st) {
            result[pos++] = str[i];
        }
    }
    result[pos] = '\0';
    return result;
}
int py_len_str(const char *value) {
    return (int)strlen(value ? value : "");
}

int py_floor_div_int(int a, int b) {
    /* Python semantics: floor(a / b) for integers. */
    if (b == 0) {
        py_set_error("ZeroDivisionError", "integer division or modulo by zero");
        return 0;
    }
    int q = a / b;
    int r = a % b;
    /* If remainder is non-zero and signs differ, round down. */
    if (r != 0 && ((r > 0) != (b > 0))) {
        q -= 1;
    }
    return q;
}

int py_pow_int(int base, int exp) {
    /* Python semantics for ints: exp < 0 yields float in Python; we don't support that in native mode. */
    if (exp < 0) {
        py_set_error("ValueError", "negative exponent not supported for int pow in native mode");
        return 0;
    }
    int result = 1;
    int b = base;
    int e = exp;
    while (e > 0) {
        if (e & 1) {
            result = result * b;
        }
        e >>= 1;
        if (e) {
            b = b * b;
        }
    }
    return result;
}

int py_mod_int(int a, int b) {
    /* Python semantics: a % b has the sign of b and is defined via floor division. */
    if (b == 0) {
        py_set_error("ZeroDivisionError", "integer modulo by zero");
        return 0;
    }
    int q = py_floor_div_int(a, b);
    return a - q * b;
}

int py_truthy_int(int value) {
    return value != 0;
}

int py_truthy_float(double value) {
    return value != 0.0;
}

int py_truthy_str(const char *value) {
    return value && value[0] != '\0';
}

int py_truthy_list(PyList *value) {
    return value && value->size > 0;
}

int py_truthy_tuple(PyTuple *value) {
    return value && value->size > 0;
}
