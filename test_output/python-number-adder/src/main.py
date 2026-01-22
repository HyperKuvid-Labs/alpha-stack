from calculator.operations import add

if __name__ == "__main__":
    num1 = 5
    num2 = 10
    result = add(num1, num2)
    print(f"The sum of {num1} and {num2} is: {result}")

    num3 = 3.5
    num4 = 7.2
    float_result = add(num3, num4)
    print(f"The sum of {num3} and {num4} is: {float_result}")
