"""Common schemas for API responses."""

from typing import Any, Generic, List, Optional, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    """Unified API response wrapper."""

    code: int = Field(default=0, description="状态码: 0=成功")
    message: str = Field(default="success", description="消息")
    data: Optional[T] = Field(default=None, description="数据")


class PaginatedData(BaseModel, Generic[T]):
    """Paginated data wrapper."""

    items: List[T] = Field(default_factory=list, description="数据列表")
    page: int = Field(description="当前页码")
    page_size: int = Field(description="每页数量")
    total: int = Field(description="总记录数")


class PaginationParams(BaseModel):
    """Pagination query parameters."""

    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=20, ge=1, le=100, description="每页数量")


class MessageResponse(BaseModel):
    """Simple message response."""

    message: str = Field(description="消息内容")


class IdResponse(BaseModel):
    """Response with a single ID."""

    id: int = Field(description="资源ID")


# data 恒为 null 的接口（登出、清空映射、部分删除等）专用标记类型。
# 取 type(None)（NoneType）使 OpenAPI 中 data 严格渲染为 {"type": "null"}，
# 与运行时 data 恒为 null 完全一致，不允许空对象 {}。
# （此前为空 BaseModel，会渲染成 anyOf[object, null]，错误地允许 {}。）
# "data 无载荷（null）"的具体说明见各接口 description。
DataNull = type(None)


class ApiErrorResponse(BaseModel):
    """统一业务/HTTP 错误响应文档形状（仅用于 OpenAPI responses 文档，不影响 200 成功响应）。

    所有非 2xx 响应均遵循 {code, message, data} 信封：
    - code：业务错误码（40000 业务 / 40001 参数校验 / 40101 未认证 / 40301 无权限 /
      40401 资源不存在 / 40901 冲突 / 42201 参数验证失败 / 50000 内部错误）。
    - message：人类可读的错误原因。
    - data：绝大多数错误为 null；个别错误（如库存不足）携带结构化补充信息，
      详见各接口在 responses 中单独声明的模型。
    """

    code: int = Field(description="业务错误码，非 0，见接口说明")
    message: str = Field(description="错误原因描述")
    data: Optional[Any] = Field(default=None, description="补充信息，多数错误为 null")


class RootInfoResponse(BaseModel):
    """根路径 `GET /` 的响应（非统一信封，返回应用基本信息）。

    供前端/运维快速确认服务身份与版本，字段直接平铺于顶层（无 code/message/data 信封）。
    """

    status: str = Field(description="服务状态标识，恒为 ok 表示进程正常")
    app: str = Field(description="应用名称，取自配置 APP_NAME")
    version: str = Field(description="应用版本号")


class HealthResponse(BaseModel):
    """健康检查 `GET /health` 的响应（非统一信封，返回存活状态）。

    供负载均衡/容器编排探活使用，字段直接平铺于顶层。
    """

    status: str = Field(description="健康状态，healthy 表示服务存活可用")
