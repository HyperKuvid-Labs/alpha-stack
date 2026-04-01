import math
import operator
import ast

class CalculatorEngine:
    """
    Safe scientific calculator engine that evaluates mathematical expressions.
    """

    ALLOWED_OPERATORS = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.Pow: operator.pow,
        ast.USub: operator.neg,
        ast.UAdd: operator.pos,
    }

    ALLOWED_FUNCTIONS = {
        'sin': math.sin,
        'cos': math.cos,
        'tan': math.tan,
        'sqrt': math.sqrt,
        'log': math.log,
        'exp': math.exp,
        'pi': math.pi,
        'e': math.e,
        'abs': abs,
        'round': round,
    }

    def __init__(self):
        self._safe_names = self.ALLOWED_FUNCTIONS.copy()

    def evaluate(self, expression: str) -> float:
        """
        Parses and evaluates a mathematical string expression safely.
        """
        try:
            tree = ast.parse(expression, mode='eval')
            return self._eval_node(tree.body)
        except Exception as e:
            raise ValueError(f"Invalid expression: {e}")

    def _eval_node(self, node):
        if isinstance(node, ast.Constant):
            return node.value
        
        elif isinstance(node, ast.BinOp):
            left = self._eval_node(node.left)
            right = self._eval_node(node.right)
            return self.ALLOWED_OPERATORS[type(node.op)](left, right)
        
        elif isinstance(node, ast.UnaryOp):
            operand = self._eval_node(node.operand)
            return self.ALLOWED_OPERATORS[type(node.op)](operand)
        
        elif isinstance(node, ast.Name):
            if node.id in self._safe_names:
                return self._safe_names[node.id]
            raise ValueError(f"Unsupported variable or constant: {node.id}")
            
        elif isinstance(node, ast.Call):
            func = self._eval_node(node.func)
            args = [self._eval_node(arg) for arg in node.args]
            return func(*args)
        
        elif isinstance(node, ast.Attribute):
            value = self._eval_node(node.value)
            return getattr(value, node.attr)

        else:
            raise TypeError(f"Unsupported operation: {type(node).__name__}")
