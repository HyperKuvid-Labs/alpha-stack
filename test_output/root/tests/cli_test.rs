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
        assert_eq!(sub(5, 3), 2);
        assert_eq!(sub(-2, -3), 1);
        assert_eq!(sub(0, 5), -5);
    }

    #[test]
    fn test_multiplication() {
        assert_eq!(mul(4, 3), 12);
        assert_eq!(mul(-2, 3), -6);
        assert_eq!(mul(0, 5), 0);
    }

    #[test]
    fn test_division() {
        assert_eq!(div(10, 2), 5);
        assert_eq!(div(-6, 3), -2);
        assert_eq!(div(5, 2), 2.5);
        assert!(div(5, 0).is_err());
    }

    #[test]
    fn test_division_by_zero() {
        assert!(div(1, 0).is_err());
        assert!(div(-1, 0).is_err());
    }
}
