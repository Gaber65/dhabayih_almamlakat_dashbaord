{
    "name": "JABIN Highlight",
    "version": "17.0.1.0.0",
    "category": "Services/JABIN",
    "summary": "JABIN ERP – Highlights (Stories): temporary image/video posts that expire after 24 hours",
    "description": """
JABIN Highlight
===============

Temporary media stories feature for the JABIN ERP platform.

Provides:
    * Highlights model (jabin.highlight) backed by ir.attachment.
    * REST APIs under /api/v1/highlights:
        - POST   /api/v1/highlights               Upload a new highlight (image/video).
        - GET    /api/v1/highlights               Feed: active highlights grouped by user.
        - GET    /api/v1/highlights/<user_id>     Active highlights for a single user.
        - DELETE /api/v1/highlights/<highlight_id> Delete a highlight (owner or admin).
    * Scheduled cron that deletes expired records and attachments every hour.
    * System parameters for expiry hours, max file sizes, and max video duration.
    * Odoo backend views for administrator management.
    """,
    "author": "JABIN Engineering",
    "website": "https://github.com/Gaber65/JABIN",
    "license": "Other proprietary",
    "depends": ["base", "jabin_core", "jabin_users", "jabin_security", "jabin_api"],
    "data": [
        # Security must load before models are usable
        "security/ir.model.access.csv",
        "security/highlight_security.xml",
        # Default configuration values
        "data/highlight_data.xml",
        # Scheduled cleanup job
        "data/highlight_cron.xml",
        # Backend views
        "views/highlight_views.xml",
        "views/actions.xml",
        "views/menus.xml",
    ],
    "assets": {},
    "installable": True,
    "application": False,
    "auto_install": False,
}
