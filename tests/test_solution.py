#!/usr/bin/env python3
# Copyright (c) 2026 <Your Name(s)>
# Tatung University — I4210 AI實務專題

from src.solution import add, main


def test_add_positive():
    assert add(2, 3) == 5


def test_add_negative():
    assert add(-1, 1) == 0


def test_main_prints_3(capsys):
    main()
    captured = capsys.readouterr()
    assert "3" in captured.out
