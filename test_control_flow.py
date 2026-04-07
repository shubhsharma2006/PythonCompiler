# test_control_flow.py — Tests if/else and while loops

x = 15

# Simple if
if x > 10 {
    print(1)
}

# If / else
if x > 100 {
    print(0)
} else {
    print(2)
}

# Nested if
if x > 5 {
    if x > 20 {
        print(99)
    } else {
        print(3)
    }
}

# While loop — sum from 1 to 5
sum = 0
i = 1
while i <= 5 {
    sum = sum + i
    i = i + 1
}
print(sum)

# While with if inside
j = 10
while j > 0 {
    if j == 5 {
        print(555)
    }
    j = j - 2
}

# Comparison operators
a = 10
b = 10
if a == b {
    print(4)
}
if a != 20 {
    print(5)
}

print("Control flow test done!")
