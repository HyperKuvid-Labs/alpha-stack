import argparse
from .calculator import add

def main():
    parser = argparse.ArgumentParser(
        prog="number_adder",
        description="A command-line tool that accepts two numbers as arguments and prints their sum."
    )
    parser.add_argument("num1", type=float, help="The first number.")
    parser.add_argument("num2", type=float, help="The second number.")
    args = parser.parse_args()
    result = add(args.num1, args.num2)
    print(result)

if __name__ == "__main__":
    main()
