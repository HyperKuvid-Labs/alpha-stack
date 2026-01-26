import pytest
import sys
from number_adder_cli.__main__ import main

@pytest.mark.parametrize(
    "argv, expected_output",
    [
        (["__main__.py", "5", "10"], "The sum is: 15.0\n"),
        (["__main__.py", "3.14", "2.71"], "The sum is: 5.85\n"),
        (["__main__.py", "-5", "-10"], "The sum is: -15.0\n"),
        (["__main__.py", "10", "-3"], "The sum is: 7.0\n"),
        (["__main__.py", "123", "0"], "The sum is: 123.0\n"),
        (["__main__.py", "0", "0"], "The sum is: 0.0\n"),
        (["__main__.py", "-5.5", "5.5"], "The sum is: 0.0\n"),
    ],
)
def test_main_success(monkeypatch, capsys, argv, expected_output):
    monkeypatch.setattr(sys, "argv", argv)
    main()
    captured = capsys.readouterr()
    assert captured.out == expected_output
    assert captured.err == ""

@pytest.mark.parametrize(
    "argv",
    [
        (["__main__.py"]),
        (["__main__.py", "1"]),
        (["__main__.py", "1", "2", "3"]),
    ],
)
def test_main_incorrect_arg_count(monkeypatch, capsys, argv):
    monkeypatch.setattr(sys, "argv", argv)
    with pytest.raises(SystemExit) as e:
        main()

    assert e.type == SystemExit
    assert e.value.code == 1

    captured = capsys.readouterr()
    assert "Error: Please provide exactly two numbers as arguments." in captured.err
    assert captured.out == ""

@pytest.mark.parametrize(
    "argv",
    [
        (["__main__.py", "hello", "5"]),
        (["__main__.py", "10", "world"]),
        (["__main__.py", "a", "b"]),
        (["__main__.py", "5", "5a"]),
    ],
)
def test_main_invalid_number_format(monkeypatch, capsys, argv):
    monkeypatch.setattr(sys, "argv", argv)
    with pytest.raises(SystemExit) as e:
        main()

    assert e.type == SystemExit
    assert e.value.code == 1

    captured = capsys.readouterr()
    assert "Error: Both arguments must be valid numbers." in captured.err
    assert captured.out == ""
