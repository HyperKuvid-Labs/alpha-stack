#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_addition() {
        assert_eq!(evaluate("1 + 2"), Ok(3.0));
    }

    #[test]
    fn test_subtraction() {
        assert_eq!(evaluate("5 - 3"), Ok(2.0));
    }

    #[test]
    fn test_multiplication() {
        assert_eq!(evaluate("3 * 4"), Ok(12.0));
    }

    #[test]
    fn test_division() {
        assert_eq!(evaluate("8 / 2"), Ok(4.0));
    }

    #[test]
    fn test_precedence_multiplication_over_addition() {
        assert_eq!(evaluate("2 + 3 * 4"), Ok(14.0));
    }

    #[test]
    fn test_precedence_division_over_subtraction() {
        assert_eq!(evaluate("10 - 6 / 2"), Ok(7.0));
    }

    #[test]
    fn test_precedence_equal_left() {
        assert_eq!(evaluate("10 - 3 + 2"), Ok(9.0));
    }

    #[test]
    fn test_parentheses_override() {
        assert_eq!(evaluate("(2 + 3) * 4"), Ok(20.0));
    }

    #[test]
    fn test_nested_parentheses() {
        assert_eq!(evaluate("((1 + 2) * 3)"), Ok(9.0));
    }

    #[test]
    fn test_complex_expression() {
        assert_eq!(evaluate("2 * (3 + 4) / 7"), Ok(2.0));
    }

    #[test]
    fn test_whitespace_handling() {
        assert_eq!(evaluate("  10   +   20  "), Ok(30.0));
    }

    #[test]
    fn test_no_whitespace() {
        assert_eq!(evaluate("10+20"), Ok(30.0));
    }

    #[test]
    fn test_floating_point_numbers() {
        assert_eq!(evaluate("1.5 + 2.5"), Ok(4.0));
    }

    #[test]
    fn test_division_by_zero() {
        let result = evaluate("5 / 0");
        assert!(result.is_ok());
        assert!(result.unwrap().is_infinite());
    }

    #[test]
    fn test_invalid_character() {
        assert!(evaluate("10 # 5").is_err());
    }

    #[test]
    fn test_mismatched_opening_parenthesis() {
        assert!(evaluate("(10 + 5").is_err());
    }

    #[test]
    fn test_mismatched_closing_parenthesis() {
        assert!(evaluate("10 + 5)").is_err());
    }

    #[test]
    fn test_empty_input() {
        assert!(evaluate("").is_err());
    }

    #[test]
    fn test_consecutive_operators() {
        assert!(evaluate("5 + + 3").is_err());
    }

    #[test]
    fn test_trailing_operator() {
        assert!(evaluate("5 +").is_err());
    }

    #[test]
    fn test_leading_operator() {
        assert!(evaluate("+ 5").is_err());
    }
}
