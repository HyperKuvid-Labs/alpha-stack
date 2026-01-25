use std::process::{Command, Stdio};
use std::io::Write;

#[test]
fn test_single_expression_addition() {
    let output = Command::new("target/debug/RustCalc")
        .args(["-e", "2 + 2"])
        .output()
        .expect("Failed to execute process");

    assert!(output.status.success());
    let stdout = String::from_utf8_lossy(&output.stdout);
    assert!(stdout.contains("4"));
}

#[test]
fn test_single_expression_subtraction() {
    let output = Command::new("target/debug/RustCalc")
        .args(["-e", "10 - 4"])
        .output()
        .expect("Failed to execute process");

    assert!(output.status.success());
    let stdout = String::from_utf8_lossy(&output.stdout);
    assert!(stdout.contains("6"));
}

#[test]
fn test_single_expression_multiplication() {
    let output = Command::new("target/debug/RustCalc")
        .args(["-e", "3 * 3"])
        .output()
        .expect("Failed to execute process");

    assert!(output.status.success());
    let stdout = String::from_utf8_lossy(&output.stdout);
    assert!(stdout.contains("9"));
}

#[test]
fn test_single_expression_division() {
    let output = Command::new("target/debug/RustCalc")
        .args(["-e", "20 / 4"])
        .output()
        .expect("Failed to execute process");

    assert!(output.status.success());
    let stdout = String::from_utf8_lossy(&output.stdout);
    assert!(stdout.contains("5"));
}

#[test]
fn test_operator_precedence() {
    let output = Command::new("target/debug/RustCalc")
        .args(["-e", "2 + 3 * 4"])
        .output()
        .expect("Failed to execute process");

    assert!(output.status.success());
    let stdout = String::from_utf8_lossy(&output.stdout);
    assert!(stdout.contains("14"));
}

#[test]
fn test_parentheses() {
    let output = Command::new("target/debug/RustCalc")
        .args(["-e", "(2 + 3) * 4"])
        .output()
        .expect("Failed to execute process");

    assert!(output.status.success());
    let stdout = String::from_utf8_lossy(&output.stdout);
    assert!(stdout.contains("20"));
}

#[test]
fn test_invalid_expression() {
    let output = Command::new("target/debug/RustCalc")
        .args(["-e", "2 + + 2"])
        .output()
        .expect("Failed to execute process");

    assert!(!output.status.success());
}

#[test]
fn test_interactive_mode_basic() {
    let mut child = Command::new("target/debug/RustCalc")
        .arg("-i")
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .spawn()
        .expect("Failed to spawn process");

    {
        let stdin = child.stdin.as_mut().expect("Failed to get stdin");
        stdin.write_all(b"5 + 5\n").unwrap();
        stdin.write_all(b"exit\n").unwrap();
    }

    let output = child.wait_with_output().expect("Failed to wait for process");
    assert!(output.status.success());
    let stdout = String::from_utf8_lossy(&output.stdout);
    assert!(stdout.contains("10"));
}

#[test]
fn test_interactive_mode_quit_command() {
    let mut child = Command::new("target/debug/RustCalc")
        .arg("-i")
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .spawn()
        .expect("Failed to spawn process");

    {
        let stdin = child.stdin.as_mut().expect("Failed to get stdin");
        stdin.write_all(b"100\n").unwrap();
        stdin.write_all(b"quit\n").unwrap();
    }

    let output = child.wait_with_output().expect("Failed to wait for process");
    assert!(output.status.success());
    let stdout = String::from_utf8_lossy(&output.stdout);
    assert!(stdout.contains("100"));
}

#[test]
fn test_interactive_mode_sequence() {
    let mut child = Command::new("target/debug/RustCalc")
        .arg("-i")
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .spawn()
        .expect("Failed to spawn process");

    {
        let stdin = child.stdin.as_mut().expect("Failed to get stdin");
        stdin.write_all(b"10 * 2\n").unwrap();
        stdin.write_all(b"5 / 2\n").unwrap();
        stdin.write_all(b"exit\n").unwrap();
    }

    let output = child.wait_with_output().expect("Failed to wait for process");
    assert!(output.status.success());
    let stdout = String::from_utf8_lossy(&output.stdout);
    assert!(stdout.contains("20"));
    assert!(stdout.contains("2") || stdout.contains("2.5"));
}

#[test]
fn test_interactive_mode_error_handling() {
    let mut child = Command::new("target/debug/RustCalc")
        .arg("-i")
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .expect("Failed to spawn process");

    {
        let stdin = child.stdin.as_mut().expect("Failed to get stdin");
        stdin.write_all(b"invalid\n").unwrap();
        stdin.write_all(b"exit\n").unwrap();
    }

    let output = child.wait_with_output().expect("Failed to wait for process");
    let stderr = String::from_utf8_lossy(&output.stderr);
    assert!(stderr.len() > 0);
}
