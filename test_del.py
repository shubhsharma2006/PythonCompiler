class Box:
    def __init__(self):
        self.value = 1

box = Box()
print(box.value)
del box.value
# print(box.value) should fail but there are no exceptions in C backend yet, let's just make sure it compiles
