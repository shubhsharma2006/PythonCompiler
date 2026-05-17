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
    if (!header) return NULL;
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

/* ----- existing runtime helpers ----- */
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

int py_floor_div_int(int a, int b) {
    /* Python semantics: floor(a / b) for integers. */
    if (b == 0) {
        /* Match Python's runtime error loosely; we abort for now. */
        fprintf(stderr, "ZeroDivisionError: integer division or modulo by zero\n");
        abort();
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
        fprintf(stderr, "ValueError: negative exponent not supported for int pow in native mode\n");
        abort();
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
        fprintf(stderr, "ZeroDivisionError: integer modulo by zero\n");
        abort();
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
