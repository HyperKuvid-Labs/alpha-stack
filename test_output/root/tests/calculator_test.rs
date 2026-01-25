#[test]
fn test_addition_positive() {
    assert_eq!(calculator::add(5, 3), 8);
}

#[test]
fn test_addition_negative() {
    assert_eq!(calculator::add(-2, -4), -6);
}

#[test]
fn test_addition_zero() {
    assert_eq!(calculator::add(0, 0), 0);
}

#[test]
fn test_addition_large() {
    assert_eq!(calculator::add(1000000, 2000000), 3000000);
}

#[test]
fn test_subtraction_positive() {
    assert_eq!(calculator::subtract(10, 4), 6);
}

#[test]
fn test_subtraction_negative() {
    assert_eq!(calculator::subtract(-3, 5), -8);
}

#[test]
fn test_subtraction_zero() {
    assert_eq!(calculator::subtract(0, 0), 0);
}

#[test]
fn test_subtraction_large() {
    assert_eq!(calculator::subtract(5000000, 1000000), 4000000);
}

#[test]
fn test_multiplication_positive() {
    assert_eq!(calculator::multiply(7, 8), 56);
}

#[test]
fn test_multiplication_negative() {
    assert_eq!(calculator::multiply(-3, 4), -12);
}

#[test]
fn test_multiplication_zero() {
    assert_eq!(calculator::multiply(0, 5), 0);
}

#[test]
fn test_multiplication_large() {
    assert_eq!(calculator::multiply(1000, 1000), 1000000);
}

#[test]
fn test_division_positive() {
    assert_eq!(calculator::divide(10, 2), 5);
}

#[test]
fn test_division_negative() {
    assert_eq!(calculator::divide(-10, 2), -5);
}

#[test]
fn test_division_zero() {
    assert!(calculator::divide(10, 0).is_err());
}

#[test]
fn test_division_large() {
    assert_eq!(calculator::divide(1000000, 2), 500000);
}

#[test]
fn test_division_by_zero_error() {
    let result = calculator::divide(5, 0);
    assert!(result.is_err());
    assert_eq!(result.err().unwrap().to_string(), "Division by zero error");
}
