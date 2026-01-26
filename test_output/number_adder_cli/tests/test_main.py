import pytest
import sys
from unittest.mock import patch

from number_adder_cli.main import main


@pytest.mark.parametrize(
    "num1_str, num2_str, expected_output",
    [
        ("5", "10", "15.0\n"),
        ("2.5", "3.5", "6.0\n"),
        ("-5", "-10", "-15.0\n"),
        ("10", "-3", "7.0\n"),
        ("0", "0", "0.0\n"),
        ("123.456", "765.432", "888.888\n"),
        ("-10.5", "10.5", "0.0\n"),
    ],
)
def test_main_success_scenarios(monkeypatch, capsys, num1_str, num2_str, expected_output):
    monkeypatch.setattr(sys, "argv", ["main.py", num1_str, num2_str])
    main()
    captured = capsys.readouterr()
    assert captured.out == expected_output


def test_main_calls_calculator_add(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["main.py", "100", "200"])
    with patch("number_adder_cli.main.add") as mock_add:
        mock_add.return_value = 300.0
        main()
        mock_add.assert_called_once_with(100.0, 200.0)


@pytest.mark.parametrize(
    "argv_list, expected_error_message",
    [
        (["main.py"], "the following arguments are required: num1, num2"),
        (["main.py", "10"], "the following arguments are required: num2"),
        (["main.py", "ten", "5"], "invalid float value: 'ten'"),
        (["main.py", "5", "five"], "invalid float value: 'five'"),
        (["main.py", "1", "2", "3"], "unrecognized arguments: 3"),
    ],
)
def test_main_argument_parsing_errors(monkeypatch, capsys, argv_list, expected_error_message):
    monkeypatch.setattr(sys, "argv", argv_list)
    with pytest.raises(SystemExit) as e:
        main()

    assert e.type == SystemExit
    assert e.value.code == 2

    captured = capsys.readouterr()
    assert expected_error_message in captured.err
