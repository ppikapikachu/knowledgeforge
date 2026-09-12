"""Unified API response utilities."""

import json
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi.responses import JSONResponse


def _json_serializer(obj: Any) -> Any:
    """Custom JSON serializer for datetime objects."""
    if isinstance(obj, datetime):
        if obj.tzinfo is None:
            obj = obj.replace(tzinfo=timezone.utc)
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


def success_response(
    data: Any = None,
    message: str = "success",
    code: int = 0,
) -> JSONResponse:
    """Create a successful API response."""
    content = {
        "code": code,
        "message": message,
        "data": data,
    }
    return JSONResponse(
        status_code=200,
        content=content,
    )


def error_response(
    code: int = 40000,
    message: str = "业务错误",
    status_code: int = 400,
) -> JSONResponse:
    """Create an error API response."""
    return JSONResponse(
        status_code=status_code,
        content={
            "code": code,
            "message": message,
            "data": None,
        },
    )


def paginated_response(
    items: list,
    total: int,
    page: int,
    page_size: int,
    message: str = "success",
) -> JSONResponse:
    """Create a paginated API response."""
    content = {
        "code": 0,
        "message": message,
        "data": {
            "items": items,
            "page": page,
            "page_size": page_size,
            "total": total,
        },
    }
    # Use custom serializer for datetime objects
    body = json.dumps(content, default=_json_serializer, ensure_ascii=False)
    return JSONResponse(
        status_code=200,
        content=content,
    )
