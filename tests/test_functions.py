def multiply(a, b):
    return a * b


def add(a, b):
    return a + b


def compute(a, b, c):
    return multiply(a, b) + c


print(multiply(6, 7))
print(add(multiply(3, 4), 5))
print(compute(2, 3, 10))
print(multiply(2 + 3, 4 - 1))
print("Functions test done!")
