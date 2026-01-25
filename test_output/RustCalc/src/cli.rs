use clap::Parser;
use std::io::{self, Write};
use crate::parser::{evaluate, ParseError};

#[derive(Parser)]
#[command(name = "RustCalc")]
pub struct Args {
    #[arg(short, long)]
    pub expression: Option<String>,

    #[arg(short, long)]
    pub interactive: bool,
}

pub fn run(args: Args) -> Result<(), String> {
    if let Some(expr) = args.expression {
        match evaluate(expr) {
            Ok(result) => println!("{}", result),
            Err(e) => return Err(e.message),
        }
    }

    if args.interactive {
        let stdin = io::stdin();
        let mut stdout = io::stdout();

        loop {
            print!("> ");
            if stdout.flush().is_err() {
                return Err("Failed to flush stdout".to_string());
            }

            let mut input = String::new();
            if stdin.read_line(&mut input).is_err() {
                return Err("Failed to read input".to_string());
            }

            let input = input.trim();
            if input.is_empty() {
                continue;
            }

            if input.eq_ignore_ascii_case("exit") || input.eq_ignore_ascii_case("quit") {
                break;
            }

            match evaluate(input.to_string()) {
                Ok(result) => println!("= {}", result),
                Err(e) => eprintln!("{}", e.message),
            }
        }
    }

    Ok(())
}
