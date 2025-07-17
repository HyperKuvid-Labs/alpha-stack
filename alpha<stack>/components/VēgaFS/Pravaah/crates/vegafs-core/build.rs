fn main() {
    // This tells Cargo to re-run this build script if `build.rs` itself changes.
    // This is good practice to ensure the build script's logic is always up-to-date.
    println!("cargo:rerun-if-changed=build.rs");

    // Also re-run if `Cargo.toml` changes. Changes to dependencies, features, or package metadata
    // can affect the build, making it necessary to re-execute the build script.
    println!("cargo:rerun-if-changed=Cargo.toml");

    // Re-run if the main library source file changes. While Cargo usually handles this,
    // explicitly stating it ensures the build script is re-evaluated with any changes
    // that might indirectly affect its logic (e.g., if it were generating code based on source).
    println!("cargo:rerun-if-changed=src/lib.rs");

    // Embed the current Cargo build profile (e.g., "debug", "release") into the binary.
    // This can be useful for runtime diagnostics, especially in production environments
    // where you might want to verify the build configuration.
    let profile = std::env::var("PROFILE").unwrap_or_else(|_| "unknown".to_string());
    println!("cargo:rustc-env=VEGAFS_CORE_BUILD_PROFILE={}", profile);

    // Embed the package version defined in Cargo.toml into the binary.
    // This allows the Rust core to report its own version, which is crucial for
    // API versioning, logging, and debugging.
    let pkg_version = std::env::var("CARGO_PKG_VERSION").unwrap_or_else(|_| "unknown".to_string());
    println!("cargo:rustc-env=VEGAFS_CORE_PKG_VERSION={}", pkg_version);

    // You can also capture the git commit hash for more precise version tracking.
    // This requires `git` to be available in the build environment.
    // This part is commented out by default to avoid adding a dependency on `git`
    // being present in environments where it might not be. Uncomment if needed.
    /*
    if let Ok(output) = std::process::Command::new("git").args(&["rev-parse", "HEAD"]).output() {
        if output.status.success() {
            let git_hash = String::from_utf8_lossy(&output.stdout)
                .trim()
                .to_string();
            println!("cargo:rustc-env=VEGAFS_CORE_GIT_HASH={}", git_hash);
        } else {
            println!("cargo:warning=Failed to get git commit hash: {}", String::from_utf8_lossy(&output.stderr));
            println!("cargo:rustc-env=VEGAFS_CORE_GIT_HASH=unknown");
        }
    } else {
        println!("cargo:warning=Git command not found or failed. Cannot embed git hash.");
        println!("cargo:rustc-env=VEGAFS_CORE_GIT_HASH=unknown");
    }
    */

    // Print a warning during compilation to confirm the build script is running and
    // to provide quick feedback on the embedded information. This is visible in Cargo's output.
    println!(
        "cargo:warning=VēgaFS Core build information: Profile={}, Version={}",
        profile, pkg_version
    );

    // Placeholder for potential C/C++ dependency linking.
    // If the Rust core were to depend on external C/C++ libraries (e.g., for specific file system operations),
    // this is where you would use crates like `cc` or `pkg-config` to compile and link them.
    // For example:
    // cc::Build::new()
    //     .file("path/to/my_c_lib.c")
    //     .compile("my_c_lib");
    // println!("cargo:rustc-link-lib=static=my_c_lib");
}