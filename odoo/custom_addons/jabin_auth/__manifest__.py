{
    "name": "JABIN Auth",
    "version": "17.0.1.0.0",
    "category": "Services/JABIN",
    "summary": "JABIN ERP - Authentication: JWT login, logout, refresh, verify, profile",
    "description": """
JABIN Auth
==========

Authentication gateway for the JABIN ERP platform.

Provides:
    * JWT-based login / logout / refresh / verify endpoints.
    * Authenticated profile retrieval and update.
    * Refresh-token revocation registry.
    * Password hashing and verification (passlib).
    """,
    "author": "JABIN Engineering",
    "website": "https://github.com/Gaber65/JABIN",
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
