# Mixed int/float operator semantics

# floor division with float should produce float in Python
print(7.0 // 2)
print(7 // 2.0)

# power with float exponent should produce float in Python
print(2 ** 3.0)
print(2.0 ** 3)

print("Mixed numeric ops done!")
