{
    "name": "JABIN Security",
    "version": "17.0.1.0.0",
    "category": "Services/JABIN",
    "summary": "JABIN ERP - RBAC, JWT utilities, audit logging, and security decorators",
    "description": """
JABIN Security
==============

Security infrastructure for the JABIN ERP platform.

Provides:
    * JWT encoding / decoding utilities (PyJWT-based).
    * Security context for request-scoped user / roles.
    * Role-based access control (jabin.role, jabin.permission).
    * Immutable audit log (jabin.audit.log).
    * Authorization services (PermissionService, AuthorizationService, AuditService).
    * Controller decorators (auth_required, permission_required).
    """,
    "author": "JABIN Engineering",
    "website": "https://github.com/Gaber65/JABIN",
    "license": "Other proprietary",
    "depends": ["base", "jabin_core", "jabin_users"],
    "data": [
        "security/jabin_security_security.xml",
        "security/jabin_security_data.xml",
        
    ],
    "assets": {},
    "installable": True,
    "application": False,
    "auto_install": False,
}
