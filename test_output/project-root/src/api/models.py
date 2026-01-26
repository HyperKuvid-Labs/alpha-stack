from dataclasses import dataclass

@dataclass
class AdditionRequest:
    num1: float
    num2: float

@dataclass
class AdditionResponse:
    sum: float
    status: str
