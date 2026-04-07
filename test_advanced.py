# test_advanced.py — Tests advanced features: elif, augmented assignment, recursion

# ── Augmented assignment operators ─────────────────────────
counter = 10
counter += 5
print(counter)

counter -= 2
print(counter)

counter *= 2
print(counter)

counter /= 2
print(counter)

# ── Elif chains ───────────────────────────────────────────
x = 50
if x > 100 {
    print("big")
} elif x > 10 {
    print("medium")
} else {
    print("small")
}

# ── While loop with augmented assignment ──────────────────
sum = 0
i = 1
while i <= 10 {
    sum += i
    i += 1
}
print(sum)

# ── Recursive function (factorial) ───────────────────────
def factorial(n) {
    if n <= 1 {
        return 1
    }
    return n * factorial(n - 1)
}

result = factorial(5)
print(result)

print("Advanced tests passed!")
