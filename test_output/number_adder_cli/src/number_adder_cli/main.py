import argparse
from .calculator import add

def main():
    parser = argparse.ArgumentParser(description="A command-line tool that adds two numbers.")
    parser.add_argument("num1", type=float, help="The first number to be added.")
    parser.add_argument("num2", type=float, help="The second number to be added.")
    args = parser.parse_args()

    result = add(args.num1, args.num2)
    print(result)

if __name__ == "__main__":
    main()
