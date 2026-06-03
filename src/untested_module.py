#!/usr/bin/env python3
# Copyright (c) 2026 <Your Name(s)>
# Tatung University — I4210 AI實務專題

# This module has no tests — intentionally causes coverage to drop below 90%


def uncovered_function_a(x: int) -> int:
    return x * 2


def uncovered_function_b(x: int) -> int:
    return x + 100


def uncovered_function_c(x: int, y: int) -> int:
    if x > y:
        return x - y
    return y - x
