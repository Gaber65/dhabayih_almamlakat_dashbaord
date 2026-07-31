from __future__ import annotations

import logging
from typing import Any, Dict, Optional

AUDIT_LEVEL = 35
AUDIT_LEVEL_NAME = "AUDIT"


class JabinAuditLogger(logging.Logger):
    """Custom logger with support for the AUDIT level."""

    def audit(self, msg: str, *args: Any, **kwargs: Any) -> None:
        if self.isEnabledFor(AUDIT_LEVEL):
            self._log(AUDIT_LEVEL, msg, args, **kwargs)


class JabinAuditLoggerAdapter(logging.LoggerAdapter):
    """LoggerAdapter that also exposes audit()."""

    def audit(self, msg: str, *args: Any, **kwargs: Any) -> None:
        self.logger.audit(msg, *args, **kwargs)


logging.setLoggerClass(JabinAuditLogger)
logging.addLevelName(AUDIT_LEVEL, AUDIT_LEVEL_NAME)


class JabinLogger:
    """Factory for JABIN loggers."""

    _ROOT_PREFIX = "jabin"
    _configured = False

    @classmethod
    def get(
        cls,
        name: str,
        context: Optional[Dict[str, Any]] = None,
        level: Optional[int] = None,
    ) -> JabinAuditLogger | JabinAuditLoggerAdapter:

        clean_name = name.removeprefix(f"{cls._ROOT_PREFIX}.").strip(".")
        full_name = (
            f"{cls._ROOT_PREFIX}.{clean_name}"
            if clean_name
            else cls._ROOT_PREFIX
        )

        cls._ensure_configured()

        logger: JabinAuditLogger = logging.getLogger(full_name)

        if level is not None:
            logger.setLevel(level)

        if context:
            return JabinAuditLoggerAdapter(logger, context)

        return logger

    @classmethod
    def _ensure_configured(cls) -> None:
        if cls._configured:
            return

        root: JabinAuditLogger = logging.getLogger(cls._ROOT_PREFIX)

        if not root.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(
                logging.Formatter(
                    "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
                    "%Y-%m-%d %H:%M:%S",
                )
            )
            root.addHandler(handler)

        if root.level == logging.NOTSET:
            root.setLevel(logging.INFO)

        root.propagate = False
        cls._configured = True

    DEBUG = logging.DEBUG
    INFO = logging.INFO
    WARNING = logging.WARNING
    AUDIT = AUDIT_LEVEL
    ERROR = logging.ERROR
    CRITICAL = logging.CRITICAL