import unittest
from src.calculator.operations import add

class TestOperations(unittest.TestCase):

    def test_add_positive_integers(self):
        self.assertEqual(add(2, 3), 5)

    def test_add_negative_integers(self):
        self.assertEqual(add(-2, -3), -5)

    def test_add_mixed_integers(self):
        self.assertEqual(add(5, -3), 2)
        self.assertEqual(add(-10, 4), -6)

    def test_add_with_zero(self):
        self.assertEqual(add(5, 0), 5)
        self.assertEqual(add(0, 5), 5)
        self.assertEqual(add(0, 0), 0)
        self.assertEqual(add(-5, 0), -5)

    def test_add_positive_floats(self):
        self.assertAlmostEqual(add(0.1, 0.2), 0.3)
        self.assertAlmostEqual(add(1.5, 2.5), 4.0)

    def test_add_negative_floats(self):
        self.assertAlmostEqual(add(-1.5, -2.5), -4.0)

    def test_add_mixed_floats(self):
        self.assertAlmostEqual(add(5.5, -2.2), 3.3)

    def test_add_integer_and_float(self):
        self.assertAlmostEqual(add(5, 2.5), 7.5)
        self.assertAlmostEqual(add(3.5, 2), 5.5)

    def test_type_error_for_string_input(self):
        with self.assertRaises(TypeError):
            add('2', 3)
        with self.assertRaises(TypeError):
            add(2, '3')
        with self.assertRaises(TypeError):
            add('a', 'b')

    def test_type_error_for_list_input(self):
        with self.assertRaises(TypeError):
            add([1], 2)

    def test_type_error_for_none_input(self):
        with self.assertRaises(TypeError):
            add(None, 5)
        with self.assertRaises(TypeError):
            add(5, None)

if __name__ == '__main__':
    unittest.main()
