{
    "name": "Jabin Security",
    "version": "17.0.1.0.0",
    "category": "Services/Jabin",
    "summary": "Jabin ERP - RBAC, JWT utilities, audit logging, and security decorators",
    "description": """
Jabin Security
==============

Security infrastructure for the Jabin ERP platform.

Provides:
    * JWT encoding / decoding utilities (PyJWT-based).
    * Security context for request-scoped user / roles.
    * Role-based access control (jabin.role, jabin.permission).
    * Immutable audit log (jabin.audit.log).
    * Authorization services (PermissionService, AuthorizationService, AuditService).
    * Controller decorators (auth_required, permission_required).
    """,
    "author": "Jabin Engineering",
    "website": "https://github.com/Gaber65/Jabin",
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
