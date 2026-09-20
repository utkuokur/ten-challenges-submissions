"""Validate and display the Cantor normal forms reported by the Lean checker."""
from __future__ import annotations


def parse_cnf(value, depth=0, budget=None) -> tuple:
    """Return lexicographically comparable tuples; coefficients remain exact."""
    if budget is None:
        budget = [4096]
    if depth > 128 or not isinstance(value, list):
        raise ValueError("Invalid ordinal normal form.")
    result = []
    for term in value:
        budget[0] -= 1
        if budget[0] < 0 or not isinstance(term, list) or len(term) != 2:
            raise ValueError("Invalid ordinal normal form.")
        exponent, coefficient = term
        if (not isinstance(coefficient, str) or not coefficient.isascii()
                or not coefficient.isdecimal() or coefficient.startswith("0")
                or len(coefficient) > 1300):
            raise ValueError("Invalid ordinal coefficient.")
        exponent = parse_cnf(exponent, depth + 1, budget)
        if result and result[-1][0] <= exponent:
            raise ValueError("Ordinal exponents must strictly decrease.")
        result.append((exponent, int(coefficient)))
    return tuple(result)


def display_cnf(normal: tuple) -> str:
    terms = []
    one = (((), 1),)
    for exponent, coefficient in normal:
        if not exponent:
            term = str(coefficient)
        else:
            term = "ω" if exponent == one else f"ω^({display_cnf(exponent)})"
            if coefficient != 1:
                term += f"*{coefficient}"
        terms.append(term)
    return " + ".join(terms) or "0"
