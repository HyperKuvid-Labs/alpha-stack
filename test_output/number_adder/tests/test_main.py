import pytest
import sys
from src.main import main

@pytest.mark.parametrize("argv, expected_output", [
    (['main.py', '5', '10'], "The sum is: 15.0\n"),
    (['main.py', '-5', '-10'], "The sum is: -15.0\n"),
    (['main.py', '5', '-10'], "The sum is: -5.0\n"),
    (['main.py', '0', '0'], "The sum is: 0.0\n"),
    (['main.py', '3.14', '2.86'], "The sum is: 6.0\n"),
    (['main.py', '-1.5', '1.5'], "The sum is: 0.0\n"),
    (['main.py', '1000', '2.5'], "The sum is: 1002.5\n"),
])
def test_main_success(monkeypatch, capsys, argv, expected_output):
    monkeypatch.setattr(sys, 'argv', argv)
    main()
    captured = capsys.readouterr()
    assert captured.out == expected_output
    assert captured.err == ""

@pytest.mark.parametrize("argv", [
    (['main.py']),
    (['main.py', '1']),
    (['main.py', '1', '2', '3']),
])
def test_main_incorrect_arg_count(monkeypatch, capsys, argv):
    monkeypatch.setattr(sys, 'argv', argv)
    with pytest.raises(SystemExit) as e:
        main()
    
    assert e.type == SystemExit
    assert e.value.code == 1
    
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "Usage: python main.py <num1> <num2>\n" in captured.err

@pytest.mark.parametrize("argv", [
    (['main.py', 'a', '5']),
    (['main.py', '5', 'b']),
    (['main.py', 'a', 'b']),
    (['main.py', '5.a', '2']),
    (['main.py', 'five', 'two']),
])
def test_main_non_numeric_args(monkeypatch, capsys, argv):
    monkeypatch.setattr(sys, 'argv', argv)
    with pytest.raises(SystemExit) as e:
        main()
        
    assert e.type == SystemExit
    assert e.value.code == 1
    
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "Error: Both arguments must be numbers.\n" in captured.err
