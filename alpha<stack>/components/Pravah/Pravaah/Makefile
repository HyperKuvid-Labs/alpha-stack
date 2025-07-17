PYTHON := python3
PIP := $(PYTHON) -m pip
UVICORN := $(PYTHON) -m uvicorn
MATURIN := $(PYTHON) -m maturin
PYTEST := $(PYTHON) -m pytest
RUFF := $(PYTHON) -m ruff
BLACK := $(PYTHON) -m black
ALEMBIC := $(PYTHON) -m alembic

# Rust commands, typically directly in PATH or cargo calls
CLIPPY := cargo clippy --workspace -- -D warnings
RUST_TEST := cargo test --workspace
RUST_FMT := cargo fmt --all

APP_DIR := app
CORE_ENGINE_DIR := pravah_core
TESTS_DIR := tests
DOCKER_COMPOSE_FILE := docker-compose.yml

.PHONY: help install build-rust develop-rust lint test check start format clean docker-build docker-run db-up db-down db-migrate db-new-migration

# --- Help Target ---
help:
	@echo "Makefile for Pravah Project"
	@echo ""
	@echo "Usage:"
	@echo "  make <target>"
	@echo ""
	@echo "Targets:"
	@echo "  help              - Display this help message."
	@echo "  install           - Install Python dependencies (from pyproject.toml) and set up Rust core for dev."
	@echo "  build-rust        - Build the Rust core into a Python wheel (release mode)."
	@echo "  develop-rust      - Install/Re-install the Rust core in editable (development) mode."
	@echo "  lint              - Run linters (ruff for Python, clippy for Rust)."
	@echo "  test              - Run all tests (pytest for Python, cargo test for Rust)."
	@echo "  check             - Run linting and testing."
	@echo "  start             - Start the FastAPI application locally (requires 'develop-rust' and 'db-up')."
	@echo "  format            - Run formatters (black for Python, rustfmt for Rust)."
	@echo "  clean             - Clean up build artifacts."
	@echo "  docker-build      - Build the Pravah Docker image."
	@echo "  docker-run        - Run the Pravah application using Docker Compose (with DB)."
	@echo "  db-up             - Start the PostgreSQL database using Docker Compose."
	@echo "  db-down           - Stop and remove the PostgreSQL database container."
	@echo "  db-migrate        - Apply database migrations (requires 'db-up')."
	@echo "  db-new-migration  - Generate a new Alembic migration script. Usage: make db-new-migration MESSAGE=\"Your message\""

# --- Development Environment Setup ---
install:
	@echo "Installing Python dependencies and setting up Pravah project..."
	$(PIP) install --upgrade pip
	# Install project dependencies, including editable Rust core if specified in pyproject.toml
	$(PIP) install -e .
	# Ensure the editable Rust core is built and linked
	$(MAKE) develop-rust

build-rust:
	@echo "Building Rust core engine in release mode..."
	cd $(CORE_ENGINE_DIR) && $(MATURIN) build --release --out ../target/wheels

develop-rust:
	@echo "Installing Rust core engine in editable (development) mode..."
	cd $(CORE_ENGINE_DIR) && $(MATURIN) develop

# --- Code Quality ---
lint:
	@echo "Running Python linter (ruff)..."
	$(RUFF) check $(APP_DIR) $(TESTS_DIR) .
	@echo "Running Rust linter (clippy)..."
	$(CLIPPY)

format:
	@echo "Running Python formatter (black)..."
	$(BLACK) $(APP_DIR) $(TESTS_DIR) .
	@echo "Running Rust formatter (rustfmt)..."
	$(RUST_FMT)

# --- Testing ---
test:
	@echo "Running Python tests (pytest)..."
	$(PYTEST) $(TESTS_DIR)
	@echo "Running Rust tests (cargo test)..."
	$(RUST_TEST)

check: lint test

# --- Application Run ---
start: develop-rust
	@echo "Starting FastAPI application..."
	# Make sure DATABASE_URL and other settings are available in the environment (e.g., via .env file or export)
	$(UVICORN) $(APP_DIR).main:app --host 0.0.0.0 --port 8000 --reload

# --- Database Management ---
db-up:
	@echo "Starting PostgreSQL database container..."
	docker-compose -f $(DOCKER_COMPOSE_FILE) up -d pravah-db

db-down:
	@echo "Stopping and removing PostgreSQL database container..."
	docker-compose -f $(DOCKER_COMPOSE_FILE) stop pravah-db
	docker-compose -f $(DOCKER_COMPOSE_FILE) rm -f pravah-db

db-migrate: db-up
	@echo "Running Alembic migrations..."
	# Ensure alembic configuration path is correct for the current environment
	$(ALEMBIC) -c $(APP_DIR)/db/migrations/alembic.ini upgrade head

db-new-migration:
	@echo "Generating new Alembic migration..."
	@if [ -z "$(MESSAGE)" ]; then \
		echo "Usage: make db-new-migration MESSAGE=\"Your migration message\""; \
		exit 1; \
	fi
	$(ALEMBIC) -c $(APP_DIR)/db/migrations/alembic.ini revision --autogenerate -m "$(MESSAGE)"

# --- Docker ---
docker-build:
	@echo "Building Pravah Docker image..."
	docker build -t pravah:latest .

docker-run: docker-build db-up
	@echo "Running Pravah application via Docker Compose..."
	# This assumes 'app' service in docker-compose.yml is configured to run the FastAPI app
	docker-compose -f $(DOCKER_COMPOSE_FILE) up -d app

# --- Clean ---
clean:
	@echo "Cleaning up build artifacts..."
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	# Clean Rust build artifacts
	rm -rf target/
	rm -rf $(CORE_ENGINE_DIR)/target/
	rm -rf $(CORE_ENGINE_DIR)/*.egg-info
	# Remove compiled Python modules from Rust
	rm -f $(CORE_ENGINE_DIR)/src/*.so
	rm -f $(CORE_ENGINE_DIR)/src/*.pyd
	rm -f $(CORE_ENGINE_DIR)/src/*.dylib