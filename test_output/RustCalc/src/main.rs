mod cli;
mod parser;

use std::process;
use crate::cli::Args;
use crate::cli::run;

fn main() {
    let args = Args::parse();
    if let Err(err) = run(args) {
        eprintln!("{}", err);
        process::exit(1);
    }
}
