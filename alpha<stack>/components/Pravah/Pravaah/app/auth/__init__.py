from .dependencies import (
    get_current_user,
    get_current_active_user,
    get_current_active_admin_user,
)
from .jwt import create_access_token, verify_token

# This __init__.py makes the 'auth' directory a Python package.
# It also serves to expose key functions and dependencies from its submodules
# directly under the 'app.auth' namespace for easier import elsewhere in the application.