# test_optimizer.py — Tests the constant folding optimizer

# All of these should be folded at compile time
a = 2 + 3
b = 10 * 5
c = 100 - 30
d = 50 / 2

# Nested constant expressions
e = (2 + 3) * (4 + 6)

# Mixed: only the constant part folds
x = 7
f = x + 2 * 3

# Comparison folding
g = 5 > 3
h = 10 == 10

print(a)
print(b)
print(c)
print(d)
print(e)
print(f)
print(g)
print(h)

# Dead code elimination test
def test_dead_code(n) {
    return n * 2
}

result = test_dead_code(21)
print(result)

print("Optimizer test done!")
