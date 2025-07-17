from app.utils.logging import configure_logging

# Configure structured logging for the entire application.
# This ensures that all modules within the 'app' package and its sub-packages
# use the defined logging configuration from the start.
configure_logging()

# This __init__.py file primarily serves to mark the 'app' directory as a Python package.
# Additional package-level imports or setup could be placed here if necessary,
# but for Pravah, specific modules (e.g., app.main, app.api.v1.endpoints) are
# designed to be imported directly as needed, maintaining modularity.