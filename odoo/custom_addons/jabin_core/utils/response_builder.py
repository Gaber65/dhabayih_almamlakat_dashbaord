from __future__ import annotations
from typing import Any, Dict, List, Optional, Union
import json
from odoo.http import request


class ApiError:
    __slots__ = ('field', 'message')

    def __init__(self, message: str, field: Optional[str] = None) -> None:
        if not message or not isinstance(message, str):
            raise ValueError("ApiError requires a non-empty 'message' string.")
        self.field: Optional[str] = field
        self.message: str = message

    def to_dict(self) -> Dict[str, Optional[str]]:
        return {'field': self.field, 'message': self.message}

    def __repr__(self) -> str:
        return f'ApiError(field={self.field!r}, message={self.message!r})'

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, ApiError):
            return NotImplemented
        return self.field == other.field and self.message == other.message


class ResponseBuilder:
    _DEFAULT_MESSAGES: Dict[int, str] = {
        200: 'Success',
        201: 'Created',
        202: 'Accepted',
        204: 'No Content',
        400: 'Validation Error',
        401: 'Unauthorized',
        403: 'Forbidden',
        404: 'Not Found',
        405: 'Method Not Allowed',
        409: 'Conflict',
        422: 'Unprocessable Entity',
        429: 'Too Many Requests',
        500: 'Internal Server Error',
        501: 'Not Implemented',
        502: 'Bad Gateway',
        503: 'Service Unavailable'
    }

    @classmethod
    def _message_for(cls, code: int, message: Optional[str]) -> str:
        if message:
            return message
        return cls._DEFAULT_MESSAGES.get(code, 'Error')

    @classmethod
    def _envelope(
            cls,
            *,
            success: bool,
            code: int,
            message: Optional[str],
            data: Optional[Any],
            meta: Optional[Dict[str, Any]],
            errors: Optional[List[Union[ApiError, Dict[str, Any]]]]
    ) -> Dict[str, Any]:
        normalised_errors: List[Dict[str, Optional[str]]] = []
        if errors:
            for err in errors:
                if isinstance(err, ApiError):
                    normalised_errors.append(err.to_dict())
                elif isinstance(err, dict):
                    normalised_errors.append({
                        'field': err.get('field'),
                        'message': err.get('message', '')
                    })
                else:
                    raise TypeError(f'Unsupported error entry type: {type(err).__name__}')

        return {
            'success': success,
            'message': cls._message_for(code, message),
            'code': code,
            'data': data if data is not None else ({} if success else None),
            'meta': meta if meta is not None else {},
            'errors': normalised_errors
        }

    @classmethod
    def _make_http_response(
            cls,
            data: Dict[str, Any],
            status_code: int = 200
    ):
        """Create an HTTP response with proper status code and headers."""
        response = request.make_response(
            json.dumps(data),
            headers=[('Content-Type', 'application/json')]
        )
        response.status_code = status_code
        return response

    @staticmethod
    def success(
            data: Any = None,
            message: Optional[str] = None,
            code: int = 200,
            meta: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        return ResponseBuilder._envelope(
            success=True,
            code=code,
            message=message,
            data=data,
            meta=meta,
            errors=None
        )

    @staticmethod
    def created(
            data: Any = None,
            message: Optional[str] = None,
            meta: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        return ResponseBuilder.success(data=data, message=message, code=201, meta=meta)

    @staticmethod
    def accepted(
            data: Any = None,
            message: Optional[str] = None,
            meta: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        return ResponseBuilder.success(data=data, message=message, code=202, meta=meta)

    @staticmethod
    def error(
            message: Optional[str] = None,
            code: int = 400,
            errors: Optional[List[Union[ApiError, Dict[str, Any]]]] = None,
            data: Any = None,
            meta: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        return ResponseBuilder._envelope(
            success=False,
            code=code,
            message=message,
            data=data,
            meta=meta,
            errors=errors
        )

    @staticmethod
    def validation_error(
            errors: List[Union[ApiError, Dict[str, Any]]],
            message: str = 'Validation Error',
            meta: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        if not errors:
            raise ValueError("validation_error requires a non-empty 'errors' list.")
        return ResponseBuilder._envelope(
            success=False,
            code=400,
            message=message,
            data=None,
            meta=meta,
            errors=errors
        )

    @staticmethod
    def not_found(
            message: str = 'Resource not found',
            errors: Optional[List[Union[ApiError, Dict[str, Any]]]] = None
    ) -> Dict[str, Any]:
        return ResponseBuilder.error(message=message, code=404, errors=errors)

    @staticmethod
    def unauthorized(
            message: str = 'Authentication required',
            errors: Optional[List[Union[ApiError, Dict[str, Any]]]] = None
    ) -> Dict[str, Any]:
        return ResponseBuilder.error(message=message, code=401, errors=errors)

    @staticmethod
    def forbidden(
            message: str = 'Access denied',
            errors: Optional[List[Union[ApiError, Dict[str, Any]]]] = None
    ) -> Dict[str, Any]:
        return ResponseBuilder.error(message=message, code=403, errors=errors)

    @staticmethod
    def server_error(
            message: str = 'Internal Server Error',
            errors: Optional[List[Union[ApiError, Dict[str, Any]]]] = None
    ) -> Dict[str, Any]:
        return ResponseBuilder.error(message=message, code=500, errors=errors)

    @staticmethod
    def bad_request(
            message: str = "Validation Error",
            errors: Optional[List[Union[ApiError, Dict[str, Any]]]] = None,
    ) -> Dict[str, Any]:
        return ResponseBuilder.error(
            message=message,
            code=400,
            errors=errors,
        )

    @staticmethod
    def conflict(
            message: str = "Conflict",
            errors: Optional[List[Union[ApiError, Dict[str, Any]]]] = None,
    ) -> Dict[str, Any]:
        return ResponseBuilder.error(
            message=message,
            code=409,
            errors=errors,
        )

    @staticmethod
    def unprocessable_entity(
            message: str = "Unprocessable Entity",
            errors: Optional[List[Union[ApiError, Dict[str, Any]]]] = None,
    ) -> Dict[str, Any]:
        return ResponseBuilder.error(
            message=message,
            code=422,
            errors=errors,
        )

    # HTTP Response methods for use with type="http"
    @classmethod
    def http_success(
            cls,
            data: Any = None,
            message: Optional[str] = None,
            code: int = 200,
            meta: Optional[Dict[str, Any]] = None
    ):
        """Return HTTP response for success."""
        response_data = cls.success(data=data, message=message, code=code, meta=meta)
        return cls._make_http_response(response_data, status_code=code)

    @classmethod
    def http_error(
            cls,
            message: Optional[str] = None,
            code: int = 400,
            errors: Optional[List[Union[ApiError, Dict[str, Any]]]] = None,
            data: Any = None,
            meta: Optional[Dict[str, Any]] = None
    ):
        """Return HTTP response for error."""
        response_data = cls.error(message=message, code=code, errors=errors, data=data, meta=meta)
        return cls._make_http_response(response_data, status_code=code)

    @classmethod
    def http_bad_request(
            cls,
            message: str = "Validation Error",
            errors: Optional[List[Union[ApiError, Dict[str, Any]]]] = None,
    ):
        return cls.http_error(message=message, code=400, errors=errors)

    @classmethod
    def http_not_found(
            cls,
            message: str = 'Resource not found',
            errors: Optional[List[Union[ApiError, Dict[str, Any]]]] = None
    ):
        return cls.http_error(message=message, code=404, errors=errors)

    @classmethod
    def http_unauthorized(
            cls,
            message: str = 'Authentication required',
            errors: Optional[List[Union[ApiError, Dict[str, Any]]]] = None
    ):
        return cls.http_error(message=message, code=401, errors=errors)

    @classmethod
    def http_forbidden(
            cls,
            message: str = 'Access denied',
            errors: Optional[List[Union[ApiError, Dict[str, Any]]]] = None
    ):
        return cls.http_error(message=message, code=403, errors=errors)

    @classmethod
    def http_server_error(
            cls,
            message: str = 'Internal Server Error',
            errors: Optional[List[Union[ApiError, Dict[str, Any]]]] = None
    ):
        return cls.http_error(message=message, code=500, errors=errors)

    @classmethod
    def http_conflict(
            cls,
            message: str = "Conflict",
            errors: Optional[List[Union[ApiError, Dict[str, Any]]]] = None,
    ):
        return cls.http_error(message=message, code=409, errors=errors)

    @classmethod
    def http_unprocessable_entity(
            cls,
            message: str = "Unprocessable Entity",
            errors: Optional[List[Union[ApiError, Dict[str, Any]]]] = None,
    ):
        return cls.http_error(message=message, code=422, errors=errors)