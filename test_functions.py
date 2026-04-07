# test_functions.py — Tests function features
# Nested calls, multiple functions, expressions in args

def multiply(a, b) {
    return a * b
}

def add(a, b) {
    return a + b
}

def compute(x, y, z) {
    t = multiply(x, y)
    return add(t, z)
}

# Simple calls
r1 = multiply(6, 7)
print(r1)

# Nested function results
r2 = add(multiply(3, 4), 5)
print(r2)

# Three-parameter function
r3 = compute(2, 3, 10)
print(r3)

# Expression as argument
r4 = multiply(2 + 3, 4 - 1)
print(r4)

print("Functions test done!")
