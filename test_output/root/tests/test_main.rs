#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_addition() {
        assert_eq!(add(2, 3), 5);
        assert_eq!(add(-1, 1), 0);
        assert_eq!(add(0, 0), 0);
    }

    #[test]
    fn test_subtraction() {
        assert_eq!(subtract(5, 2), 3);
        assert_eq!(subtract(-2, -3), 1);
        assert_eq!(subtract(0, 0), 0);
    }

    #[test]
    fn test_multiplication() {
        assert_eq!(multiply(3, 4), 12);
        assert_eq!(multiply(-2, 3), -6);
        assert_eq!(multiply(0, 5), 0);
    }

    #[test]
    fn test_division() {
        assert_eq!(divide(10, 2), 5);
        assert_eq!(divide(-8, 2), -4);
        assert_eq!(divide(0, 5), 0);
    }

    #[test]
    #[should_panic]
    fn test_division_by_zero() {
        divide(5, 0);
    }

    #[test]
    fn test_invalid_input() {
        assert_eq!(evaluate("2 + 3"), "5");
        assert_eq!(evaluate("5 * 2"), "10");
        assert_eq!(evaluate("10 / 0"), "Error: Division by zero");
    }
}
