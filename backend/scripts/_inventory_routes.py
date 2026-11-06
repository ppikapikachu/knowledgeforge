# 一次性盘点/审计脚本（openapi 驱动）：逐操作检测成功响应 data 的 schema 可展开性。
# 只读，不改代码。输出 TSV：方法\t路径\tdata状态\tdata引用名
#   data状态: OK(具体$ref或对象) | STRING(bad) | MISSING(bad) | NULL(合法null) | DICT(需人工)
import sys
sys.path.insert(0, ".")
from app.main import app  # noqa: E402

spec = app.openapi()
schemas = spec.get("components", {}).get("schemas", {})


def resolve(ref):
    name = ref.split("/")[-1]
    return name, schemas.get(name, {})


def data_state(op):
    resp = op.get("responses", {}).get("200", {})
    content = resp.get("content", {}).get("application/json", {})
    schema = content.get("schema", {})
    if not schema:
        return "NO200SCHEMA", "-"
    # ApiResponse 引用
    if "$ref" in schema:
        name, sch = resolve(schema["$ref"])
    else:
        name, sch = "(inline)", schema
    props = sch.get("properties", {})
    if "data" not in props:
        # 可能是裸 data（非信封）
        return f"NO_DATA_FIELD({name})", "-"
    d = props["data"]
    # 展开 allOf/anyOf
    target = d
    for k in ("allOf", "anyOf", "oneOf"):
        if k in target and isinstance(target[k], list) and target[k]:
            target = target[k][0]
    if "$ref" in target:
        n, _ = resolve(target["$ref"])
        return "OK", n
    t = target.get("type")
    if t == "string":
        return "STRING", "-"
    if t == "object":
        if target.get("properties") or target.get("additionalProperties"):
            return "OBJECT_INLINE", "inline"
        return "EMPTY_OBJECT", "-"
    if t == "array":
        return "ARRAY", target.get("items", {})
    if t is None and not target:
        return "EMPTY", "-"
    return f"TYPE_{t}", str(target)[:40]


rows = []
for path, ops in spec.get("paths", {}).items():
    for method, op in ops.items():
        if method not in ("get", "post", "put", "patch", "delete"):
            continue
        st, ref = data_state(op)
        rows.append((method.upper(), path, st, str(ref)))

print(f"TOTAL_OPERATIONS={len(rows)}")
from collections import Counter
print("STATE_COUNTS=", dict(Counter(r[2] for r in rows)))
print("---")
for m, p, st, ref in rows:
    print(f"{m}\t{p}\t{st}\t{ref}")
