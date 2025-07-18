use crate::core::file_handler::{FileFormat, ObjectStorageFileHandler};
use crate::utils::error::{KaryakshamError, Result};
use arrow::{
    csv::Reader as ArrowCsvReader,
    compute,
    record_batch::RecordBatch,
};
use csv::{ReaderBuilder, WriterBuilder};
use futures::{StreamExt, SinkExt}; // Needed for AsyncArrowWriter
use parquet::{
    basic::{Compression},
};
use parquet_arrow::AsyncArrowWriter;
use rayon::prelude::*;
use serde::{Deserialize, Serialize};
use std::io::Cursor;
use std::sync::Arc;
use tokio::io::{AsyncBufReadExt, AsyncWriteExt, BufReader};
use tokio_util::compat::TokioAsyncReadCompatExt; // For .compat()

/// Defines the parameters for various data processing jobs.
/// This enum will be serialized/deserialized when passed from Python.
#[derive(Debug, Serialize, Deserialize)]
pub enum ProcessingJobParams {
    /// Parameters for filtering a CSV file based on a column's value.
    CsvFilter {
        filter_column: String,
        filter_value: String,
        output_format: FileFormat, // The desired output format (e.g., CSV, Parquet)
    },
    /// Parameters for converting a CSV file to Parquet format.
    CsvToParquet,
    // Add other job types as needed, e.g., ColumnAggregation, DataJoin, etc.
}

/// The core data processing engine, responsible for executing transformations.
pub struct DataProcessor {
    /// A shared reference to the file handler for interacting with object storage.
    file_handler: Arc<ObjectStorageFileHandler>,
}

impl DataProcessor {
    /// Creates a new `DataProcessor` instance.
    pub fn new(file_handler: Arc<ObjectStorageFileHandler>) -> Self {
        DataProcessor { file_handler }
    }

    /// Dispatches the data processing task based on the provided parameters.
    pub async fn process_data(
        &self,
        input_path: &str,
        output_path: &str,
        params: ProcessingJobParams,
    ) -> Result<()> {
        log::info!(
            "Starting data processing: input='{}', output='{}', params='{:?}'",
            input_path,
            output_path,
            params
        );

        match params {
            ProcessingJobParams::CsvFilter {
                filter_column,
                filter_value,
                output_format,
            } => {
                self.process_csv_filter(
                    input_path,
                    output_path,
                    &filter_column,
                    &filter_value,
                    output_format,
                )
                .await
            }
            ProcessingJobParams::CsvToParquet => {
                self.process_csv_to_parquet(input_path, output_path).await
            }
        }
    }

    /// Processes a CSV file by filtering rows based on a column's value.
    /// Supports outputting to CSV or Parquet format.
    ///
    /// This method attempts to read CSV data in chunks, parallelize the filtering
    /// of these in-memory chunks using Rayon for CPU-bound tasks, and then write
    /// the filtered data to the specified output format.
    async fn process_csv_filter(
        &self,
        input_path: &str,
        output_path: &str,
        filter_column: &str,
        filter_value: &str,
        output_format: FileFormat,
    ) -> Result<()> {
        log::info!(
            "Processing CSV filter: column='{}', value='{}', output_format='{:?}'",
            filter_column,
            filter_value,
            output_format
        );

        let input_stream = self.file_handler.read_file(input_path).await?;
        let mut reader = BufReader::new(input_stream).lines();

        // Read headers line
        let headers_line = reader
            .next_line()
            .await?
            .ok_or_else(|| KaryakshamError::ProcessingError("CSV file is empty, no headers found.".to_string()))?;

        // Parse headers using csv crate
        let headers: Vec<String> = ReaderBuilder::new()
            .has_headers(false) // We already read the line
            .from_reader(Cursor::new(headers_line.as_bytes()))
            .headers()
            .map_err(|e| KaryakshamError::ProcessingError(format!("Failed to parse CSV headers: {}", e)))?
            .iter()
            .map(|s| s.to_string())
            .collect();

        let filter_col_index = headers
            .iter()
            .position(|h| h == filter_column)
            .ok_or_else(|| {
                KaryakshamError::ProcessingError(format!(
                    "Filter column '{}' not found in CSV headers",
                    filter_column
                ))
            })?;

        let output_sink = self.file_handler.create_file(output_path).await?;

        match output_format {
            FileFormat::Csv => {
                let mut csv_writer = WriterBuilder::new()
                    .has_headers(false) // We'll write headers explicitly
                    .from_writer(output_sink.compat());

                // Write headers to output CSV
                csv_writer
                    .write_record(&headers)
                    .map_err(|e| KaryakshamError::ProcessingError(format!("Failed to write headers to output CSV: {}", e)))?;
                csv_writer
                    .flush()
                    .map_err(|e| KaryakshamError::ProcessingError(format!("Failed to flush headers: {}", e)))?;

                const BATCH_SIZE: usize = 10_000; // Process records in batches for parallelism
                let mut record_batch: Vec<csv::StringRecord> = Vec::with_capacity(BATCH_SIZE);

                while let Some(line_result) = reader.next_line().await {
                    let line = line_result?
                        .ok_or_else(|| KaryakshamError::ProcessingError("Unexpected end of CSV file during line read".to_string()))?;

                    // Parse the line into a single StringRecord
                    let record = ReaderBuilder::new()
                        .has_headers(false)
                        .from_reader(Cursor::new(line.as_bytes()))
                        .records()
                        .next() // Get the single record from this line
                        .ok_or_else(|| KaryakshamError::ProcessingError(format!("Failed to parse CSV record from line: {}", line)))??; // Handle Option and Result

                    record_batch.push(record);

                    if record_batch.len() >= BATCH_SIZE {
                        // Process this batch in parallel using Rayon
                        let filtered_batch: Vec<csv::StringRecord> = record_batch
                            .par_iter()
                            .filter(|record| {
                                record
                                    .get(filter_col_index)
                                    .map_or(false, |col_val| col_val == filter_value)
                            })
                            .cloned() // Clone to move ownership out of the parallel iterator
                            .collect();

                        // Write filtered batch (sequential write to the async stream)
                        for record in filtered_batch {
                            csv_writer
                                .write_record(&record)
                                .map_err(|e| KaryakshamError::ProcessingError(format!("Failed to write record to output CSV: {}", e)))?;
                        }
                        csv_writer
                            .flush()
                            .map_err(|e| KaryakshamError::ProcessingError(format!("Failed to flush CSV writer: {}", e)))?;

                        record_batch.clear(); // Clear for the next batch
                    }
                }

                // Process any remaining records in the last batch
                if !record_batch.is_empty() {
                    let filtered_batch: Vec<csv::StringRecord> = record_batch
                        .par_iter()
                        .filter(|record| {
                            record
                                .get(filter_col_index)
                                .map_or(false, |col_val| col_val == filter_value)
                        })
                        .cloned()
                        .collect();

                    for record in filtered_batch {
                        csv_writer
                            .write_record(&record)
                            .map_err(|e| KaryakshamError::ProcessingError(format!("Failed to write record to output CSV: {}", e)))?;
                    }
                    csv_writer
                        .flush()
                        .map_err(|e| KaryakshamError::ProcessingError(format!("Failed to flush CSV writer: {}", e)))?;
                }
            }
            FileFormat::Parquet => {
                // For Parquet output, it's more efficient to use Arrow's CSV reader
                // to parse into RecordBatches, then filter these batches, and finally
                // write the filtered batches to Parquet.
                let mut arrow_csv_reader = ArrowCsvReader::Builder::new()
                    .has_headers(true)
                    .build(BufReader::new(
                        self.file_handler.read_file(input_path).await?,
                    ).compat()) // Re-read the stream for Arrow-CSV parser
                    .map_err(|e| KaryakshamError::ProcessingError(format!("Failed to create Arrow CSV reader: {}", e)))?;

                let schema = arrow_csv_reader.schema();
                let filter_col_idx = schema
                    .index_of(filter_column)
                    .ok_or_else(|| {
                        KaryakshamError::ProcessingError(format!(
                            "Filter column '{}' not found in Arrow schema for Parquet output",
                            filter_column
                        ))
                    })?;

                let props = Some(Arc::new(
                    parquet::file::writer::Properties::builder()
                        .set_compression(Compression::SNAPPY)
                        .build(),
                ));

                let mut arrow_parquet_writer = AsyncArrowWriter::try_new(
                    output_sink,
                    schema.clone(),
                    props,
                )
                .map_err(|e| KaryakshamError::ProcessingError(format!("Failed to create Parquet Arrow writer: {}", e)))?;

                while let Some(batch_result) = arrow_csv_reader.next() {
                    let batch = batch_result.map_err(|e| KaryakshamError::ProcessingError(format!("Failed to read Arrow record batch from CSV: {}", e)))?;

                    // Apply filter using Arrow compute functions
                    let filter_array = compute::eq(
                        batch.column(filter_col_idx),
                        &arrow::array::StringArray::from(vec![filter_value]),
                    )
                    .map_err(|e| KaryakshamError::ProcessingError(format!("Failed to apply Arrow filter: {}", e)))?;

                    let filtered_batch = compute::filter_record_batch(&batch, &filter_array.into())
                        .map_err(|e| KaryakshamError::ProcessingError(format!("Failed to filter Arrow record batch: {}", e)))?;

                    arrow_parquet_writer
                        .write(&filtered_batch)
                        .await
                        .map_err(|e| KaryakshamError::ProcessingError(format!("Failed to write filtered Arrow batch to Parquet: {}", e)))?;
                }

                arrow_parquet_writer
                    .close()
                    .await
                    .map_err(|e| KaryakshamError::ProcessingError(format!("Failed to close Parquet writer: {}", e)))?;
            }
            _ => {
                return Err(KaryakshamError::NotImplemented(format!(
                    "Output format {:?} not supported for CSV filter.",
                    output_format
                )))
            }
        }
        log::info!("CSV filter processing complete for '{}'", input_path);
        Ok(())
    }

    /// Converts a CSV file to Parquet format.
    ///
    /// This method uses the `arrow-csv` crate to read the CSV data into Arrow
    /// RecordBatches, and then the `parquet-arrow` crate to efficiently write
    /// these RecordBatches to a Parquet file, leveraging asynchronous I/O.
    async fn process_csv_to_parquet(&self, input_path: &str, output_path: &str) -> Result<()> {
        log::info!(
            "Converting CSV to Parquet: input='{}', output='{}'",
            input_path,
            output_path
        );

        let input_stream = self.file_handler.read_file(input_path).await?;
        let reader = BufReader::new(input_stream);

        let mut csv_reader = ArrowCsvReader::Builder::new()
            .has_headers(true)
            .build(reader.compat())
            .map_err(|e| KaryakshamError::ProcessingError(format!("Failed to create Arrow CSV reader: {}", e)))?;

        let output_sink = self.file_handler.create_file(output_path).await?;

        // Parquet writer properties (e.g., compression)
        let props = Some(Arc::new(
            parquet::file::writer::Properties::builder()
                .set_compression(Compression::SNAPPY) // SNAPPY is a good default for performance
                .build(),
        ));

        // Create an Arrow Parquet writer
        let mut arrow_parquet_writer = AsyncArrowWriter::try_new(
            output_sink,
            csv_reader.schema(),
            props,
        )
        .map_err(|e| KaryakshamError::ProcessingError(format!("Failed to create Parquet Arrow writer: {}", e)))?;

        // Read batches from CSV and write them to Parquet
        while let Some(batch_result) = csv_reader.next() {
            let batch = batch_result.map_err(|e| KaryakshamError::ProcessingError(format!("Failed to read Arrow record batch from CSV: {}", e)))?;
            arrow_parquet_writer
                .write(&batch)
                .await
                .map_err(|e| KaryakshamError::ProcessingError(format!("Failed to write Arrow batch to Parquet: {}", e)))?;
        }

        // Finalize and close the Parquet writer
        arrow_parquet_writer
            .close()
            .await
            .map_err(|e| KaryakshamError::ProcessingError(format!("Failed to close Parquet writer: {}", e)))?;

        log::info!("CSV to Parquet conversion complete for '{}'", input_path);
        Ok(())
    }
}