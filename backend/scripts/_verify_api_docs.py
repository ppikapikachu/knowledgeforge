# 一次性校验脚本：核对 FastAPI /docs 全部路由的接口描述完整性。
# 只读 openapi spec，不改任何代码。校验范围：
#   1) 每个 operation 的 description >= 20 字符（含返回 data 结构说明）
#   2) 每个 Path/Query/Header 参数的 description >= 20 字符
#   3) 每个请求体 Body 字段的 description >= 20 字符
# 响应 Schema 的字段简短标签不在校验范围（返回值含义统一写在路由 description 的"返回 data 结构"里）。
import sys

sys.path.insert(0, ".")
from app.main import app  # noqa: E402


def is_desc_ok(d):
    return isinstance(d, str) and len(d.strip()) >= 20


spec = app.openapi()
issues = []
checked_ops = 0
checked_params = 0

for path, ops in spec.get("paths", {}).items():
    for method, op in ops.items():
        if method not in ("get", "post", "put", "patch", "delete", "head", "options", "trace"):
            continue
        checked_ops += 1
        opid = f"{method.upper()} {path}"
        if not is_desc_ok(op.get("description")):
            issues.append(f"[ROUTE_DESC] {opid}")
        for p in op.get("parameters", []):
            checked_params += 1
            if not is_desc_ok(p.get("description")):
                issues.append(f"[PARAM:{p.get('in')}] {opid} :: {p.get('name')}")
        rb = op.get("requestBody")
        if rb:
            for _ctype, cobj in rb.get("content", {}).items():
                for pname, pobj in (cobj.get("schema", {}).get("properties") or {}).items():
                    checked_params += 1
                    if not is_desc_ok(pobj.get("description")):
                        issues.append(f"[BODY_FIELD] {opid} :: {pname}")

print(f"ROUTES_CHECKED={checked_ops}")
print(f"PARAMS_CHECKED={checked_params}")
print(f"ISSUES={len(issues)}")
for i in issues:
    print(i)
