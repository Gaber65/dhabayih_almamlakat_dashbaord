{
    "name": "Jabin API",
    "version": "17.0.1.0.0",
    "category": "Services/Jabin",
    "summary": "Jabin ERP - REST API gateway (controllers, versioning, base controller)",
    "description": """
Jabin API
=========

REST API gateway for the Jabin ERP platform.

Provides:
    * Base API controller with unified JSON response envelope
    * Centralised exception handling
    * API versioning rooted at /api/v1/
    * Discoverable API root endpoint

This module contains NO business endpoints (Sprint 1 only).
    """,
    "author": "Jabin Engineering",
    "website": "https://github.com/Gaber65/Jabin",
    "license": "Other proprietary",
    "depends": ["base", "jabin_core"],
    "data": [],
    "assets": {},
    "installable": True,
    "application": False,
    "auto_install": False,
}
