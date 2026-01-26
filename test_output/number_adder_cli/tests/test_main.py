import pytest
from src.number_adder_cli.__main__ import main

@pytest.mark.parametrize("argv, expected_output", [
    (['__main__.py', '5', '10'], '15.0\n'),
    (['__main__.py', '2.5', '3.5'], '6.0\n'),
    (['__main__.py', '-8', '3'], '-5.0\n'),
    (['__main__.py', '0', '0'], '0.0\n'),
    (['__main__.py', '-1.5', '-2.5'], '-4.0\n'),
    (['__main__.py', '100', '200'], '300.0\n'),
    (['__main__.py', '0', '42.7'], '42.7\n'),
])
def test_main_success_scenarios(monkeypatch, capsys, argv, expected_output):
    monkeypatch.setattr('sys.argv', argv)
    main()
    captured = capsys.readouterr()
    assert captured.out == expected_output
    assert captured.err == ''

@pytest.mark.parametrize("argv, expected_error_fragment", [
    (['__main__.py'], 'the following arguments are required: num1, num2'),
    (['__main__.py', '10'], 'the following arguments are required: num2'),
    (['__main__.py', 'a', '10'], "invalid float value: 'a'"),
    (['__main__.py', '10', 'b'], "invalid float value: 'b'"),
    (['__main__.py', '1', '2', '3'], 'unrecognized arguments: 3'),
])
def test_main_error_scenarios(monkeypatch, capsys, argv, expected_error_fragment):
    monkeypatch.setattr('sys.argv', argv)
    with pytest.raises(SystemExit) as excinfo:
        main()
    
    assert excinfo.type == SystemExit
    assert excinfo.value.code == 2

    captured = capsys.readouterr()
    assert captured.out == ''
    assert expected_error_fragment in captured.err
