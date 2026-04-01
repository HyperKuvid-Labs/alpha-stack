from calc.ui import TermCalcApp
from calc.engine import CalculatorEngine

def evaluate_expression(expression: str) -> float:
    return CalculatorEngine.calculate(expression)

__all__ = ["TermCalcApp", "evaluate_expression"]
