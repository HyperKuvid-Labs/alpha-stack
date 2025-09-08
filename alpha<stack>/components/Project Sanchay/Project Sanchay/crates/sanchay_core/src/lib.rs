pub mod error;
pub mod walker;
pub mod file_processor;
pub mod database;
pub mod bindings; // This module contains the PyO3 module definition and Python-callable functions

// Re-export the custom error type and Result alias for convenient access throughout the crate
pub use error::{SanchayError, Result};

// You might add other public re-exports here if internal Rust modules need to expose
// specific types or functions directly through the `sanchay_core` crate facade.
// For example:
// pub use file_processor::FileMetadata;
// pub use walker::DirectoryStats;