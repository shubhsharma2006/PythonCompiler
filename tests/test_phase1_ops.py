a = 7
b = 2

print(a // b)
print(a ** b)
print(a & b)
print(a | b)
print(a ^ b)
print(a << 1)
print(a >> 1)
print(+a)
print(~a)

print("Phase 1 ops done!")

# Extra coverage: Python vs C differences
print(-7 // 2)   # -4 in Python (floor), -3 in truncating C division
print(7 // -2)   # -4 in Python
print(-7 // -2)  # 3 in Python
print(2 ** 10)   # 1024

print("Phase 1 ops edge cases done!")
