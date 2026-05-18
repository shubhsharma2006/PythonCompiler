a = 10
b = 4

print(a + b)
print(a - b)
print(a * b)
print(a / b)

print(2 + 3 * 4)
print((2 + 3) * 4)


def square(x):
    return x * x


def add(x, y):
    return x + y


print(square(5))
print(add(10, 20))

if a > b:
    print(42)

i = 3
while i > 0:
    print(i)
    i -= 1

folded = 100 + 200 * 3 - 100
print(folded)

print("All tests passed!")
