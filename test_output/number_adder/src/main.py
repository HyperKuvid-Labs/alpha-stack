import sys
from .calculator import add

def main():
    if len(sys.argv) != 3:
        print("Usage: python -m src.main <num1> <num2>", file=sys.stderr)
        sys.exit(1)

    try:
        num1 = float(sys.argv[1])
        num2 = float(sys.argv[2])
    except ValueError:
        print("Error: Both inputs must be valid numbers.", file=sys.stderr)
        sys.exit(1)

    result = add(num1, num2)
    print(f"The sum is: {result}")

if __name__ == "__main__":
    main()
