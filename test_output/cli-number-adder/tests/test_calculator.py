import unittest
from number_adder.calculator import add

class TestCalculator(unittest.TestCase):

    def test_add_positive_integers(self):
        self.assertEqual(add(5, 10), 15)

    def test_add_negative_integers(self):
        self.assertEqual(add(-5, -10), -15)

    def test_add_mixed_sign_integers(self):
        self.assertEqual(add(10, -5), 5)
        self.assertEqual(add(-10, 5), -5)

    def test_add_with_zero(self):
        self.assertEqual(add(0, 5), 5)
        self.assertEqual(add(5, 0), 5)
        self.assertEqual(add(0, 0), 0)
        self.assertEqual(add(-5, 0), -5)

    def test_add_positive_floats(self):
        self.assertAlmostEqual(add(1.5, 2.5), 4.0)
        self.assertAlmostEqual(add(0.1, 0.2), 0.3)

    def test_add_negative_floats(self):
        self.assertAlmostEqual(add(-1.5, -2.5), -4.0)

    def test_add_mixed_sign_floats(self):
        self.assertAlmostEqual(add(5.5, -2.5), 3.0)

    def test_add_integer_and_float(self):
        self.assertAlmostEqual(add(5, 2.5), 7.5)
        self.assertAlmostEqual(add(-5, 2.5), -2.5)

    def test_add_large_numbers(self):
        self.assertEqual(add(1_000_000_000, 2_000_000_000), 3_000_000_000)

    def test_add_commutative_property(self):
        self.assertEqual(add(123, 456), add(456, 123))
        self.assertAlmostEqual(add(12.3, 45.6), add(45.6, 12.3))

if __name__ == '__main__':
    unittest.main()
