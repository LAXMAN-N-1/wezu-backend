from __future__ import annotations
def foo(x: int | None) -> int | None:
    return x
print(foo(1))
print("Success")
