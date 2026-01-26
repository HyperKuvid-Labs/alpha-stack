FROM rust:1.80.0-alpine

RUN useradd -m -u 1000 appuser
WORKDIR /app
COPY . .
RUN cargo build --release
USER appuser
CMD ["target/release/rust-cli-calculator"]