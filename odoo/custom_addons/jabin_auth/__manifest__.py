{
    "name": "Jabin Auth",
    "version": "17.0.1.0.0",
    "category": "Services/Jabin",
    "summary": "Jabin ERP - Authentication: JWT login, logout, refresh, verify, profile",
    "description": """
Jabin Auth
==========

Authentication gateway for the Jabin ERP platform.

Provides:
    * JWT-based login / logout / refresh / verify endpoints.
    * Authenticated profile retrieval and update.
    * Refresh-token revocation registry.
    * Password hashing and verification (passlib).
    """,
    "author": "Jabin Engineering",
    "website": "https://github.com/Gaber65/Jabin",
    "license": "Other proprietary",
    "depends": ["base", "jabin_core", "jabin_users", "jabin_security"],
    "data": [
        "security/jabin_auth_security.xml",
        'data/internal_config.xml',

    ],
    "assets": {},
    "installable": True,
    "application": False,
    "auto_install": False,
}
