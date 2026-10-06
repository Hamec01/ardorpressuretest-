"""Route-level access for business APIs (ADR-005 §3/§10, docs/ACCESS_PLAN_R4-R7.md stage 3).

Every business route depends on exactly one of these. Reading (logs, files, records,
plans) is for every employee role; changing data is for admin and foreman. Unknown,
inactive or unauthenticated callers get 401, insufficient role 403 (require_role is
fail-closed and enforces CSRF on unsafe browser requests).
"""
from services.api.auth import require_role

READ_ROLES = ["admin", "foreman", "viewer"]
WRITE_ROLES = ["admin", "foreman"]

require_reader = require_role(READ_ROLES)
require_writer = require_role(WRITE_ROLES)
