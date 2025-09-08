use rusqlite::{Connection, params, TransactionBehavior, Result as RusqliteResult};
use std::path::{Path, PathBuf};
use crate::error::SanchayCoreError; // Assuming error.rs defines SanchayCoreError

/// Represents file metadata to be stored in the database.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct FileMetadata {
    pub path: PathBuf,
    pub file_name: String,
    pub size: u64,
    pub checksum: String, // e.g., SHA256 hash
    pub modified_at: u64, // Unix timestamp (seconds since epoch)
    pub created_at: u64,  // Unix timestamp (seconds since epoch)
}

/// Manages interaction with the SQLite database for file metadata.
pub struct DatabaseManager {
    conn: Connection,
}

impl DatabaseManager {
    /// Opens a connection to the SQLite database at the specified path.
    /// If the database file does not exist, it will be created.
    /// Also ensures the necessary schema tables are set up.
    pub fn new(db_path: &Path) -> Result<Self, SanchayCoreError> {
        let conn = Connection::open(db_path).map_err(SanchayCoreError::DbConnection)?;
        let manager = DatabaseManager { conn };
        manager.setup_schema()?;
        Ok(manager)
    }

    /// Sets up the required database tables if they do not already exist.
    /// Creates the 'files' table with necessary columns and indexes.
    fn setup_schema(&self) -> Result<(), SanchayCoreError> {
        self.conn.execute_batch(
            "CREATE TABLE IF NOT EXISTS files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                path TEXT NOT NULL UNIQUE,
                file_name TEXT NOT NULL,
                size INTEGER NOT NULL,
                checksum TEXT NOT NULL,
                modified_at INTEGER NOT NULL,
                created_at INTEGER NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_files_checksum ON files (checksum);
            CREATE INDEX IF NOT EXISTS idx_files_path ON files (path);
            ",
        ).map_err(SanchayCoreError::DbSchema)?;
        Ok(())
    }

    /// Inserts a collection of `FileMetadata` entries into the database.
    /// Uses a transaction for performance and atomicity.
    /// If a file with the same `path` already exists, its metadata will be updated.
    pub fn insert_file_metadata(&self, metadata_entries: &[FileMetadata]) -> Result<(), SanchayCoreError> {
        let tx = self.conn.transaction_with_behavior(TransactionBehavior::Immediate)
            .map_err(SanchayCoreError::DbTransaction)?;

        {
            // Use prepare_cached for performance when inserting multiple entries
            let mut stmt = tx.prepare_cached(
                "INSERT OR REPLACE INTO files (path, file_name, size, checksum, modified_at, created_at)
                 VALUES (?, ?, ?, ?, ?, ?)",
            ).map_err(SanchayCoreError::DbStatement)?;

            for entry in metadata_entries {
                stmt.execute(params![
                    entry.path.to_string_lossy(), // Convert PathBuf to String for DB storage
                    entry.file_name,
                    entry.size,
                    entry.checksum,
                    entry.modified_at,
                    entry.created_at,
                ]).map_err(SanchayCoreError::DbInsert)?;
            }
        } // `stmt` is dropped here, releasing the borrow on `tx`

        tx.commit().map_err(SanchayCoreError::DbTransaction)?;
        Ok(())
    }

    /// Retrieves all files that have duplicate checksums.
    /// The results are ordered by checksum and then by path.
    pub fn get_duplicate_files(&self) -> Result<Vec<FileMetadata>, SanchayCoreError> {
        let mut stmt = self.conn.prepare(
            "SELECT f.path, f.file_name, f.size, f.checksum, f.modified_at, f.created_at
             FROM files f
             JOIN (
                 SELECT checksum
                 FROM files
                 GROUP BY checksum
                 HAVING COUNT(*) > 1
             ) AS duplicates ON f.checksum = duplicates.checksum
             ORDER BY f.checksum, f.path",
        ).map_err(SanchayCoreError::DbStatement)?;

        let metadata_iter = stmt.query_map(params![], |row| {
            Ok(FileMetadata {
                path: PathBuf::from(row.get::<_, String>(0)?),
                file_name: row.get(1)?,
                size: row.get(2)?,
                checksum: row.get(3)?,
                modified_at: row.get(4)?,
                created_at: row.get(5)?,
            })
        }).map_err(SanchayCoreError::DbQuery)?;

        let mut results = Vec::new();
        for metadata_result in metadata_iter {
            results.push(metadata_result.map_err(SanchayCoreError::DbRowConversion)?);
        }
        Ok(results)
    }

    // Add other database interaction methods here as needed, e.g.,
    // pub fn get_file_metadata_by_path(&self, path: &Path) -> Result<Option<FileMetadata>, SanchayCoreError> { ... }
    // pub fn delete_file_metadata(&self, path: &Path) -> Result<(), SanchayCoreError> { ... }
}

#[cfg(test)]
mod tests {
    use super::*;
    use tempfile::NamedTempFile; // To create temporary database files for tests
    use std::fs;
    use std::time::{SystemTime, UNIX_EPOCH};

    // Helper to get current Unix timestamp for test data
    fn now_as_unix_seconds() -> u64 {
        SystemTime::now().duration_since(UNIX_EPOCH).expect("Time went backwards").as_secs()
    }

    #[test]
    fn test_database_manager_new_and_schema() -> RusqliteResult<()> {
        let temp_db_file = NamedTempFile::new()?;
        let db_path = temp_db_file.path();

        // Check if the file exists before creation (it shouldn't yet)
        assert!(!db_path.exists());

        let manager = DatabaseManager::new(db_path).expect("Failed to create database manager");

        // Check if the database file was created
        assert!(db_path.exists());

        // Check if the 'files' table exists in the database
        let mut stmt = manager.conn.prepare("SELECT name FROM sqlite_master WHERE type='table' AND name='files'")?;
        let table_name: String = stmt.query_row(params![], |row| row.get(0))?;
        assert_eq!(table_name, "files");

        Ok(())
    }

    #[test]
    fn test_insert_and_retrieve_file_metadata() -> RusqliteResult<()> {
        let temp_db_file = NamedTempFile::new()?;
        let db_path = temp_db_file.path();
        let manager = DatabaseManager::new(db_path).expect("Failed to create database manager");

        let now = now_as_unix_seconds();

        let metadata = vec![
            FileMetadata {
                path: PathBuf::from("/a/b/file1.txt"),
                file_name: "file1.txt".to_string(),
                size: 100,
                checksum: "hash1".to_string(),
                modified_at: now - 100,
                created_at: now - 200,
            },
            FileMetadata {
                path: PathBuf::from("/x/y/file2.txt"),
                file_name: "file2.txt".to_string(),
                size: 200,
                checksum: "hash2".to_string(),
                modified_at: now - 50,
                created_at: now - 150,
            },
            FileMetadata {
                path: PathBuf::from("/c/d/file3.txt"),
                file_name: "file3.txt".to_string(),
                size: 300,
                checksum: "hash1".to_string(), // This is a duplicate hash of file1.txt
                modified_at: now - 20,
                created_at: now - 120,
            },
        ];

        manager.insert_file_metadata(&metadata).expect("Failed to insert metadata");

        // Verify total count of files
        let count: i64 = manager.conn.query_row("SELECT COUNT(*) FROM files", params![], |row| row.get(0))?;
        assert_eq!(count, 3, "Expected 3 files after initial insert");

        // Retrieve duplicate files
        let mut duplicates = manager.get_duplicate_files().expect("Failed to get duplicate files");
        assert_eq!(duplicates.len(), 2, "Expected 2 duplicate files (file1.txt, file3.txt)");

        // Sort by path for consistent assertion
        duplicates.sort_by(|a, b| a.path.cmp(&b.path));
        assert_eq!(duplicates[0].file_name, "file1.txt");
        assert_eq!(duplicates[1].file_name, "file3.txt");
        assert_eq!(duplicates[0].checksum, "hash1");
        assert_eq!(duplicates[1].checksum, "hash1");


        // Test `INSERT OR REPLACE` behavior for updates
        let updated_metadata = vec![
            FileMetadata {
                path: PathBuf::from("/a/b/file1.txt"), // Same path as existing entry
                file_name: "file1_renamed.txt".to_string(), // Renamed
                size: 101, // Updated size
                checksum: "new_hash1".to_string(), // Updated checksum
                modified_at: now + 10,
                created_at: now - 200, // Created time might remain the same
            },
        ];
        manager.insert_file_metadata(&updated_metadata).expect("Failed to update metadata");

        // Verify count: should still be 3 as one was updated, not added
        let updated_count: i64 = manager.conn.query_row("SELECT COUNT(*) FROM files", params![], |row| row.get(0))?;
        assert_eq!(updated_count, 3, "Expected count to remain 3 after update");

        // Retrieve the updated file and verify its new details
        let updated_file: FileMetadata = manager.conn.query_row(
            "SELECT path, file_name, size, checksum, modified_at, created_at FROM files WHERE path = ?",
            params!["/a/b/file1.txt"],
            |row| Ok(FileMetadata {
                path: PathBuf::from(row.get::<_, String>(0)?),
                file_name: row.get(1)?,
                size: row.get(2)?,
                checksum: row.get(3)?,
                modified_at: row.get(4)?,
                created_at: row.get(5)?,
            }),
        )?;
        assert_eq!(updated_file.file_name, "file1_renamed.txt");
        assert_eq!(updated_file.size, 101);
        assert_eq!(updated_file.checksum, "new_hash1");
        assert_eq!(updated_file.modified_at, now + 10);

        // After updating file1.txt's checksum to "new_hash1", it should no longer be a duplicate with file3.txt ("hash1")
        let duplicates_after_update = manager.get_duplicate_files().expect("Failed to get duplicate files after update");
        assert_eq!(duplicates_after_update.len(), 0, "Expected no duplicates after updating file1.txt's checksum");

        Ok(())
    }
}