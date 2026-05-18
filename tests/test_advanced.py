counter = 10
counter += 5
print(counter)

counter -= 2
print(counter)

counter *= 2
print(counter)

counter /= 2
print(counter)

x = 50
if x > 100:
    print("big")
elif x > 10:
    print("medium")
else:
    print("small")

total = 0
i = 1
while i <= 10:
    total += i
    i += 1
print(total)


def factorial(n):
    if n <= 1:
        return 1
    return n * factorial(n - 1)


def is_even(n):
    if n == 0:
        return True
    return is_odd(n - 1)


def is_odd(n):
    if n == 0:
        return False
    return is_even(n - 1)


result = factorial(5)
print(result)
print(is_even(4))
print(is_odd(3))
print("Advanced tests passed!")
