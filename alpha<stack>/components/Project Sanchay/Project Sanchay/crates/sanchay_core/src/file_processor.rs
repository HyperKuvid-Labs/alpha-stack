use std::fs::File;
use std::io::{self, Read};
use std::path::{Path, PathBuf};

/// `blake3` is chosen for its speed and security, making it ideal for high-performance hashing.
/// It must be declared as a dependency in `crates/sanchay_core/Cargo.toml`.
use blake3::Hasher;

/// Defines the buffer size for reading files in chunks.
/// This prevents loading entire large files into memory, adhering to the
/// "streaming data" non-functional requirement. A 64KB chunk size is a common
/// and efficient choice for disk I/O.
const CHUNK_SIZE: usize = 64 * 1024; // 64 KB

/// `FileProcessor` encapsulates the logic for processing a single file.
/// It holds the path to the file and provides methods to perform operations
/// like computing a cryptographic hash.
#[derive(Debug, Clone)]
pub struct FileProcessor {
    path: PathBuf,
}

impl FileProcessor {
    /// Creates a new `FileProcessor` instance.
    ///
    /// # Arguments
    /// * `path` - The `PathBuf` representing the file to be processed.
    pub fn new(path: PathBuf) -> Self {
        FileProcessor { path }
    }

    /// Returns a reference to the path of the file being processed.
    pub fn path(&self) -> &Path {
        &self.path
    }

    /// Computes the Blake3 hash of the file's content.
    ///
    /// The file is read in chunks (`CHUNK_SIZE`) to minimize memory usage,
    /// making this method suitable for processing very large files efficiently.
    ///
    /// # Returns
    /// A `Result` which is:
    /// * `Ok(String)`: The hexadecimal string representation of the Blake3 hash if successful.
    /// * `Err(io::Error)`: An `io::Error` if the file cannot be opened or read.
    pub fn compute_blake3_hash(&self) -> io::Result<String> {
        // Attempt to open the file. This might fail if the file doesn't exist or
        // due to permission issues.
        let mut file = File::open(&self.path)?;
        let mut hasher = Hasher::new();
        let mut buffer = vec![0; CHUNK_SIZE];

        loop {
            // Read a chunk of data from the file into the buffer.
            let bytes_read = file.read(&mut buffer)?;

            // If `bytes_read` is 0, it means we have reached the end of the file.
            if bytes_read == 0 {
                break;
            }

            // Update the hasher with the bytes read. Only the valid portion of the
            // buffer (up to `bytes_read`) is used.
            hasher.update(&buffer[..bytes_read]);
        }

        // Finalize the hash computation and convert it to a hexadecimal string.
        Ok(hasher.finalize().to_hex().to_string())
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::fs;
    use std::io::Write;
    use tempfile::tempdir; // Requires `tempfile` as a `dev-dependency` in Cargo.toml

    /// Helper function to create a temporary file with specific content for testing.
    fn create_temp_file(dir: &Path, filename: &str, content: &[u8]) -> PathBuf {
        let file_path = dir.join(filename);
        let mut file = fs::File::create(&file_path).unwrap();
        file.write_all(content).unwrap();
        file_path
    }

    #[test]
    fn test_compute_blake3_hash_empty_file() {
        let dir = tempdir().unwrap();
        let file_path = create_temp_file(dir.path(), "empty.txt", b"");
        let processor = FileProcessor::new(file_path);
        let hash = processor.compute_blake3_hash().unwrap();
        // Known Blake3 hash for an empty byte array.
        assert_eq!(hash, "af1349b9f5f1a6a4a04d5b2c938c49e1248067b57cf762b9a7657d0793d937a0");
    }

    #[test]
    fn test_compute_blake3_hash_small_file() {
        let dir = tempdir().unwrap();
        let file_path = create_temp_file(dir.path(), "small.txt", b"hello world");
        let processor = FileProcessor::new(file_path);
        let hash = processor.compute_blake3_hash().unwrap();
        // Known Blake3 hash for "hello world".
        assert_eq!(hash, "8973d41f02c6171569a9b23b56658dfa647000c0a316b27072a392e21b089c89");
    }

    #[test]
    fn test_compute_blake3_hash_file_larger_than_chunk_size() {
        let dir = tempdir().unwrap();
        // Create content slightly larger than CHUNK_SIZE to ensure chunking logic is hit.
        let content = vec![b'x'; CHUNK_SIZE + 123];
        let file_path = create_temp_file(dir.path(), "chunked_file.bin", &content);
        let processor = FileProcessor::new(file_path.clone());
        let hash = processor.compute_blake3_hash().unwrap();

        // Compute the hash directly with blake3 to verify the chunked reader.
        let expected_hash = blake3::hash(&content).to_hex().to_string();
        assert_eq!(hash, expected_hash);

        // Ensure the temporary file still exists after processing.
        assert!(file_path.exists());
    }

    #[test]
    fn test_compute_blake3_hash_file_not_found() {
        let file_path = PathBuf::from("non_existent_file_xyz.txt");
        let processor = FileProcessor::new(file_path);
        let err = processor.compute_blake3_hash().unwrap_err();
        // Verify that the correct error kind is returned.
        assert_eq!(err.kind(), io::ErrorKind::NotFound);
    }

    #[test]
    fn test_path_accessor() {
        let expected_path = PathBuf::from("/test/path/to/some_file.txt");
        let processor = FileProcessor::new(expected_path.clone());
        assert_eq!(processor.path(), expected_path.as_path());
    }

    #[test]
    fn test_file_processor_clone_and_debug() {
        let path = PathBuf::from("/test/path/test.txt");
        let processor = FileProcessor::new(path.clone());
        let cloned_processor = processor.clone();

        assert_eq!(cloned_processor.path(), processor.path());
        assert_eq!(format!("{:?}", processor), format!("FileProcessor {{ path: {:?} }}", path));
    }
}