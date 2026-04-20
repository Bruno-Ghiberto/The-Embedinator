"""Red-CI demo: intentional type error — DO NOT MERGE.
Triggers mypy error: Incompatible return value type (backend-type-check, CO-E advisory).
"""


def demo_bar(n: int) -> int:
    return "hello"
