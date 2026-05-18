a = True
b = False

print(a)
print(b)

c = True and False
print(c)

d = True or False
print(d)

e = not True
print(e)

x = 10
if x > 5 and x < 20:
    print(1)

if x < 0 or x > 5:
    print(2)

if not False:
    print(3)


def side():
    print(99)
    return True


if True or side():
    print(4)

if False and side():
    print(5)

print("booleans done!")
