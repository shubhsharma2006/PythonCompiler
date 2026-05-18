a = -7
b = 2

# Python modulo semantics differ from C for negative operands
print(a % b)     # 1
print(7 % -2)    # -1
print(-7 % -2)   # -1

# Truthiness semantics (unboxed native types)
if 0:
    print("bad")
else:
    print("ok")

if "":
    print("bad")
else:
    print("ok")

if "x":
    print("ok")
else:
    print("bad")

# Float truthiness
if 0.0:
    print("bad")
else:
    print("ok")

if -0.0:
    print("bad")
else:
    print("ok")

if 0.5:
    print("ok")
else:
    print("bad")

print("Native semantics done!")
