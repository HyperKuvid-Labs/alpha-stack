import ast
import operator
import math

class CalculatorEngine:
    SUPPORTED_OPERATORS = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.Pow: operator.pow,
        ast.USub: operator.neg,
    }

    @classmethod
    def calculate(cls, expression: str) -> float:
        try:
            # We want to support '*' for multiplication, but standard Python uses '*'
            # Let's see if the expression is just what we expect.
            # Using ast.parse immediately.
            tree = ast.parse(expression.strip(), mode='eval')
            return float(cls._eval_node(tree.body))
        except Exception as e:
            raise ValueError(f"Invalid expression: {str(e)}") from e

    @classmethod
    def _eval_node(cls, node):
        if isinstance(node, ast.Constant):
            return node.value
        elif isinstance(node, ast.UnaryOp):
            op = cls.SUPPORTED_OPERATORS.get(type(node.op))
            if op:
                return op(cls._eval_node(node.operand))
        elif isinstance(node, ast.BinOp):
            left = cls._eval_node(node.left)
            right = cls._eval_node(node.right)
            op = cls.SUPPORTED_OPERATORS.get(type(node.op))
            if op:
                return op(left, right)
        
        raise ValueError("Unsupported operation or structure")
