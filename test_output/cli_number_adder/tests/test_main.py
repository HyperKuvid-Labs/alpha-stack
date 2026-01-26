import pytest
import sys
from src.main import main

def test_main_success_integers(monkeypatch, capsys):
    monkeypatch.setattr(sys, 'argv', ['main.py', '5', '10'])
    main()
    captured = capsys.readouterr()
    assert captured.out == "The sum is: 15.0\n"
    assert captured.err == ""

def test_main_success_floats(monkeypatch, capsys):
    monkeypatch.setattr(sys, 'argv', ['main.py', '2.5', '3.5'])
    main()
    captured = capsys.readouterr()
    assert captured.out == "The sum is: 6.0\n"
    assert captured.err == ""

def test_main_success_negative_numbers(monkeypatch, capsys):
    monkeypatch.setattr(sys, 'argv', ['main.py', '-10', '5'])
    main()
    captured = capsys.readouterr()
    assert captured.out == "The sum is: -5.0\n"
    assert captured.err == ""

def test_main_success_with_zero(monkeypatch, capsys):
    monkeypatch.setattr(sys, 'argv', ['main.py', '0', '-99.5'])
    main()
    captured = capsys.readouterr()
    assert captured.out == "The sum is: -99.5\n"
    assert captured.err == ""

def test_main_not_enough_arguments(monkeypatch, capsys):
    monkeypatch.setattr(sys, 'argv', ['main.py', '5'])
    with pytest.raises(SystemExit) as e:
        main()
    assert e.type == SystemExit
    assert e.value.code == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "Usage: python src/main.py <num1> <num2>" in captured.err

def test_main_too_many_arguments(monkeypatch, capsys):
    monkeypatch.setattr(sys, 'argv', ['main.py', '5', '10', '15'])
    with pytest.raises(SystemExit) as e:
        main()
    assert e.type == SystemExit
    assert e.value.code == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "Usage: python src/main.py <num1> <num2>" in captured.err

def test_main_no_arguments(monkeypatch, capsys):
    monkeypatch.setattr(sys, 'argv', ['main.py'])
    with pytest.raises(SystemExit) as e:
        main()
    assert e.type == SystemExit
    assert e.value.code == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "Usage: python src/main.py <num1> <num2>" in captured.err

@pytest.mark.parametrize("arg1, arg2", [
    ("a", "10"),
    ("10", "b"),
    ("foo", "bar"),
    ("5", "five")
])
def test_main_invalid_argument_type(monkeypatch, capsys, arg1, arg2):
    monkeypatch.setattr(sys, 'argv', ['main.py', arg1, arg2])
    with pytest.raises(SystemExit) as e:
        main()
    assert e.type == SystemExit
    assert e.value.code == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "Error: Both arguments must be valid numbers." in captured.err
