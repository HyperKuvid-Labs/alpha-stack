import unittest
from unittest.mock import patch
from io import StringIO
import sys

from number_adder.__main__ import main

class TestMain(unittest.TestCase):

    @patch('sys.stdout', new_callable=StringIO)
    @patch('number_adder.__main__.add', return_value=8.0)
    @patch('sys.argv', ['__main__.py', '5', '3'])
    def test_main_with_positive_integers(self, mock_argv, mock_add, mock_stdout):
        main()
        mock_add.assert_called_once_with(5.0, 3.0)
        self.assertEqual(mock_stdout.getvalue().strip(), "8.0")

    @patch('sys.stdout', new_callable=StringIO)
    @patch('number_adder.__main__.add', return_value=3.5)
    @patch('sys.argv', ['__main__.py', '1.2', '2.3'])
    def test_main_with_positive_floats(self, mock_argv, mock_add, mock_stdout):
        main()
        mock_add.assert_called_once_with(1.2, 2.3)
        self.assertEqual(mock_stdout.getvalue().strip(), "3.5")

    @patch('sys.stdout', new_callable=StringIO)
    @patch('number_adder.__main__.add', return_value=-8.0)
    @patch('sys.argv', ['__main__.py', '-5', '-3'])
    def test_main_with_negative_numbers(self, mock_argv, mock_add, mock_stdout):
        main()
        mock_add.assert_called_once_with(-5.0, -3.0)
        self.assertEqual(mock_stdout.getvalue().strip(), "-8.0")

    @patch('sys.stdout', new_callable=StringIO)
    @patch('number_adder.__main__.add', return_value=-2.0)
    @patch('sys.argv', ['__main__.py', '3', '-5'])
    def test_main_with_mixed_sign_numbers(self, mock_argv, mock_add, mock_stdout):
        main()
        mock_add.assert_called_once_with(3.0, -5.0)
        self.assertEqual(mock_stdout.getvalue().strip(), "-2.0")

    @patch('sys.stdout', new_callable=StringIO)
    @patch('number_adder.__main__.add', return_value=5.0)
    @patch('sys.argv', ['__main__.py', '5', '0'])
    def test_main_with_zero_as_argument(self, mock_argv, mock_add, mock_stdout):
        main()
        mock_add.assert_called_once_with(5.0, 0.0)
        self.assertEqual(mock_stdout.getvalue().strip(), "5.0")

    @patch('sys.stderr', new_callable=StringIO)
    def test_main_with_no_arguments(self, mock_stderr):
        with patch('sys.argv', ['__main__.py']):
            with self.assertRaises(SystemExit) as cm:
                main()
            self.assertEqual(cm.exception.code, 2)
        self.assertIn("the following arguments are required: num1, num2", mock_stderr.getvalue())

    @patch('sys.stderr', new_callable=StringIO)
    def test_main_with_one_argument(self, mock_stderr):
        with patch('sys.argv', ['__main__.py', '10']):
            with self.assertRaises(SystemExit) as cm:
                main()
            self.assertEqual(cm.exception.code, 2)
        self.assertIn("the following arguments are required: num2", mock_stderr.getvalue())

    @patch('sys.stderr', new_callable=StringIO)
    def test_main_with_too_many_arguments(self, mock_stderr):
        with patch('sys.argv', ['__main__.py', '10', '20', '30']):
            with self.assertRaises(SystemExit) as cm:
                main()
            self.assertEqual(cm.exception.code, 2)
        self.assertIn("unrecognized arguments: 30", mock_stderr.getvalue())

    @patch('sys.stderr', new_callable=StringIO)
    def test_main_with_first_non_numeric_argument(self, mock_stderr):
        with patch('sys.argv', ['__main__.py', 'abc', '10']):
            with self.assertRaises(SystemExit) as cm:
                main()
            self.assertEqual(cm.exception.code, 2)
        self.assertIn("argument num1: invalid float value: 'abc'", mock_stderr.getvalue())

    @patch('sys.stderr', new_callable=StringIO)
    def test_main_with_second_non_numeric_argument(self, mock_stderr):
        with patch('sys.argv', ['__main__.py', '10', 'xyz']):
            with self.assertRaises(SystemExit) as cm:
                main()
            self.assertEqual(cm.exception.code, 2)
        self.assertIn("argument num2: invalid float value: 'xyz'", mock_stderr.getvalue())

if __name__ == '__main__':
    unittest.main()
