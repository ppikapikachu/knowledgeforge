"""Custom exception classes for the application."""

from typing import Any, Optional


class BusinessException(Exception):
    """Base business exception."""

    def __init__(self, code: int = 40000, message: str = "业务错误"):
        self.code = code
        self.message = message
        super().__init__(message)


class ResourceNotFoundException(BusinessException):
    """Resource not found exception."""

    def __init__(self, resource: str = "资源", resource_id: Any = None):
        message = f"{resource}不存在"
        if resource_id is not None:
            message = f"{resource}不存在: {resource_id}"
        super().__init__(code=40401, message=message)


class ValidationException(BusinessException):
    """Validation error exception."""

    def __init__(self, message: str = "数据验证失败"):
        super().__init__(code=40001, message=message)


class AuthenticationException(BusinessException):
    """Authentication failed exception."""

    def __init__(self, message: str = "认证失败"):
        super().__init__(code=40101, message=message)


class PermissionException(BusinessException):
    """Permission denied exception."""

    def __init__(self, message: str = "权限不足"):
        super().__init__(code=40301, message=message)


class DuplicateException(BusinessException):
    """Duplicate resource exception."""

    def __init__(self, message: str = "数据已存在"):
        super().__init__(code=40901, message=message)
