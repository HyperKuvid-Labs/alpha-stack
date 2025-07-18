use aws_sdk_s3::{
    config::{self, Region},
    primitives::ByteStream,
    Client,
};
use aws_smithy_http::endpoint::Endpoint;
use tracing::{info, debug};
use url::Url;

use crate::utils::error::{KaryakshamError, Result};

/// Configuration for the object storage client.
#[derive(Debug, Clone)]
pub struct ObjectStorageConfig {
    pub endpoint_url: Option<String>,
    pub region: String,
    pub access_key_id: String,
    pub secret_access_key: String,
    pub bucket_name: String,
}

/// A client for interacting with S3-compatible object storage.
/// It wraps the AWS SDK S3 client and provides simplified methods for common operations.
#[derive(Debug, Clone)]
pub struct ObjectStorageHandler {
    client: Client,
    bucket_name: String,
}

impl ObjectStorageHandler {
    /// Creates a new `ObjectStorageHandler` instance.
    ///
    /// Initializes the AWS SDK S3 client with provided configuration.
    /// This allows connection to AWS S3 or compatible services like MinIO.
    ///
    /// # Arguments
    /// * `config` - An `ObjectStorageConfig` containing endpoint, region, and credentials.
    ///
    /// # Returns
    /// A `Result` which is `Ok(Self)` on success, or an `Err(KaryakshamError)` if
    /// the client cannot be initialized (e.g., invalid endpoint URL).
    pub async fn new(config: ObjectStorageConfig) -> Result<Self> {
        let mut sdk_config_builder = config::SdkConfig::builder();

        // Set credentials using static provider
        sdk_config_builder = sdk_config_builder.credentials_provider(
            aws_sdk_s3::config::Credentials::new(
                &config.access_key_id,
                &config.secret_access_key,
                None, // Session token
                None, // Expiration
                "karyaksham_static_credentials", // Provider name for tracing
            ),
        );

        // Set AWS region
        sdk_config_builder = sdk_config_builder.region(Region::new(config.region.clone()));

        // If an explicit endpoint URL is provided, configure the client to use it.
        // This is crucial for local MinIO setups or other S3-compatible services.
        if let Some(endpoint_url) = &config.endpoint_url {
            let url = Url::parse(endpoint_url)
                .map_err(|e| KaryakshamError::ConfigurationError(format!("Invalid endpoint URL: {}", e)))?;
            sdk_config_builder = sdk_config_builder.endpoint_resolver(
                Endpoint::immutable(url.into_url())
            );
            info!("Configuring S3 client with custom endpoint: {}", endpoint_url);
        } else {
            info!("Configuring S3 client with default AWS endpoint for region: {}", config.region);
        }

        let sdk_config = sdk_config_builder.build();
        let client = Client::new(&sdk_config);

        debug!(
            "ObjectStorageHandler initialized for bucket: {}, endpoint: {:?}",
            config.bucket_name, config.endpoint_url
        );

        Ok(Self {
            client,
            bucket_name: config.bucket_name,
        })
    }

    /// Downloads a file from the configured S3 bucket as an asynchronous byte stream.
    ///
    /// This method is suitable for large files as it avoids loading the entire file
    /// into memory at once. The returned `ByteStream` implements `tokio::io::AsyncRead`.
    ///
    /// # Arguments
    /// * `key` - The object key (path) within the bucket to download.
    ///
    /// # Returns
    /// A `Result` containing the `ByteStream` on success, or `KaryakshamError` on failure
    /// (e.g., file not found, network issues, S3 errors).
    pub async fn download_file(&self, key: &str) -> Result<ByteStream> {
        info!("Attempting to download file from s3://{}/{}", self.bucket_name, key);

        let output = self
            .client
            .get_object()
            .bucket(&self.bucket_name)
            .key(key)
            .send()
            .await
            .map_err(|e| KaryakshamError::IoError(format!("Failed to download {}: {}", key, e)))?;

        info!("Successfully initiated download for s3://{}/{}", self.bucket_name, key);
        Ok(output.body)
    }

    /// Uploads a byte stream to a specified key in the configured S3 bucket.
    ///
    /// This method enables efficient uploading of data, especially for large files,
    /// by streaming the data directly to S3.
    ///
    /// # Arguments
    /// * `key` - The object key (path) within the bucket where the data will be stored.
    /// * `data` - The `ByteStream` representing the data to upload.
    ///
    /// # Returns
    /// A `Result` indicating success (`Ok(())`) or `KaryakshamError` on failure
    /// (e.g., network issues, S3 errors).
    pub async fn upload_file(&self, key: &str, data: ByteStream) -> Result<()> {
        info!("Attempting to upload file to s3://{}/{}", self.bucket_name, key);

        self.client
            .put_object()
            .bucket(&self.bucket_name)
            .key(key)
            .body(data)
            .send()
            .await
            .map_err(|e| KaryakshamError::IoError(format!("Failed to upload {}: {}", key, e)))?;

        info!("Successfully uploaded file to s3://{}/{}", self.bucket_name, key);
        Ok(())
    }

    /// Deletes a file from the configured S3 bucket.
    ///
    /// # Arguments
    /// * `key` - The object key (path) within the bucket to delete.
    ///
    /// # Returns
    /// A `Result` indicating success (`Ok(())`) or `KaryakshamError` on failure.
    pub async fn delete_file(&self, key: &str) -> Result<()> {
        info!("Attempting to delete file from s3://{}/{}", self.bucket_name, key);

        self.client
            .delete_object()
            .bucket(&self.bucket_name)
            .key(key)
            .send()
            .await
            .map_err(|e| KaryakshamError::IoError(format!("Failed to delete {}: {}", key, e)))?;

        info!("Successfully deleted file s3://{}/{}", self.bucket_name, key);
        Ok(())
    }

    /// Parses a full S3 path string (e.g., "s3://my-bucket/path/to/file.csv")
    /// into its constituent bucket name and object key.
    ///
    /// This utility function is useful when the S3 path is received as a single URL string
    /// from external sources (e.g., from the Python API).
    ///
    /// # Arguments
    /// * `s3_path` - The full S3 path string.
    ///
    /// # Returns
    /// A `Result` containing a tuple `(bucket_name, object_key)` on success, or
    /// `KaryakshamError::InputError` if the path is not a valid S3 URL or is malformed.
    pub fn parse_s3_path(s3_path: &str) -> Result<(String, String)> {
        let url = Url::parse(s3_path)
            .map_err(|e| KaryakshamError::InputError(format!("Invalid S3 path URL: {}", e)))?;

        if url.scheme() != "s3" {
            return Err(KaryakshamError::InputError(format!("Invalid S3 path scheme: expected 's3', got '{}'", url.scheme())));
        }

        let bucket = url.host_str()
            .ok_or_else(|| KaryakshamError::InputError("S3 path missing bucket name".into()))?
            .to_string();

        let key = url.path().trim_start_matches('/').to_string();

        if key.is_empty() {
            return Err(KaryakshamError::InputError("S3 path missing object key".into()));
        }

        Ok((bucket, key))
    }
}