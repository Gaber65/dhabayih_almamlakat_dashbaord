{
    "name": "JABIN API",
    "version": "17.0.1.0.0",
    "category": "Services/JABIN",
    "summary": "JABIN ERP - REST API gateway (controllers, versioning, base controller)",
    "description": """
JABIN API
=========

REST API gateway for the JABIN ERP platform.

Provides:
    * Base API controller with unified JSON response envelope
    * Centralised exception handling
    * API versioning rooted at /api/v1/
    * Discoverable API root endpoint

This module contains NO business endpoints (Sprint 1 only).
    """,
    "author": "JABIN Engineering",
    "website": "https://github.com/Gaber65/JABIN",
    "license": "Other proprietary",
    "depends": ["base", "jabin_core"],
    "data": [],
    "assets": {},
    "installable": True,
    "application": False,
    "auto_install": False,
}
