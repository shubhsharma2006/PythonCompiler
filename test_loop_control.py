def test_break():
    i = 0
    while i < 10:
        if i == 5:
            break
        print(i)
        i = i + 1
    print(99)

def test_continue():
    j = 0
    while j < 5:
        j = j + 1
        if j == 3:
            continue
        print(j)
    print(100)

test_break()
test_continue()
