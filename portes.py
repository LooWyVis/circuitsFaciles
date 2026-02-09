# portes.py

def non(a: bool) -> bool:
    return not a

def ou(a: bool, b: bool) -> bool:
    return a or b

def et(a: bool, b: bool) -> bool:
    return a and b

def nor(a: bool, b: bool) -> bool:
    return non(ou(a, b))

def xor(a: bool, b: bool) -> bool:
    return (a and not b) or (not a and b)


if __name__ == "__main__":
    assert non(False) is True
    assert non(True) is False

    assert ou(False, False) is False
    assert ou(False, True) is True
    assert ou(True, False) is True
    assert ou(True, True) is True

    assert et(False, False) is False
    assert et(False, True) is False
    assert et(True, False) is False
    assert et(True, True) is True

    assert nor(False, False) is True
    assert nor(False, True) is False
    assert nor(True, False) is False
    assert nor(True, True) is False

    assert xor(False, False) is False
    assert xor(False, True) is True
    assert xor(True, False) is True
    assert xor(True, True) is False
