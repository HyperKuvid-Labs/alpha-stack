import unittest
import math
from calculator.engine import CalculatorEngine

class TestEngine(unittest.TestCase):
    def setUp(self):
        self.engine = CalculatorEngine()

    def test_arithmetic(self):
        self.assertEqual(self.engine.evaluate("2 + 3"), 5)
        self.assertEqual(self.engine.evaluate("10 - 4"), 6)
        self.assertEqual(self.engine.evaluate("3 * 4"), 12)
        self.assertEqual(self.engine.evaluate("10 / 2"), 5.0)
        self.assertEqual(self.engine.evaluate("2 ** 3"), 8)

    def test_trigonometric(self):
        self.assertAlmostEqual(self.engine.evaluate("sin(0)"), 0)
        self.assertAlmostEqual(self.engine.evaluate("cos(0)"), 1)
        self.assertAlmostEqual(self.engine.evaluate("sin(pi / 2)"), 1)
        self.assertAlmostEqual(self.engine.evaluate("tan(0)"), 0)

    def test_math_functions(self):
        self.assertAlmostEqual(self.engine.evaluate("sqrt(16)"), 4)
        self.assertAlmostEqual(self.engine.evaluate("abs(-5)"), 5)
        self.assertAlmostEqual(self.engine.evaluate("exp(1)"), math.e)

    def test_boundary_conditions(self):
        # Division by zero
        with self.assertRaises(ValueError):
            self.engine.evaluate("10 / 0")
        
        # Invalid expression
        with self.assertRaises(ValueError):
            self.engine.evaluate("invalid_func(10)")
            
        with self.assertRaises(ValueError):
            self.engine.evaluate("10 + ")

    def test_order_of_operations(self):
        self.assertEqual(self.engine.evaluate("2 + 3 * 4"), 14)
        self.assertEqual(self.engine.evaluate("(2 + 3) * 4"), 20)

if __name__ == '__main__':
    unittest.main()
