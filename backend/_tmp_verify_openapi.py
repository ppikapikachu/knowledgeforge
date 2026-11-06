# 一次性 OpenAPI 校验脚本（用后即删）
import sys

from app.main import app

spec = app.openapi()

OPS = [
    ("post", "/api/v1/question-generation/tasks"),
    ("get", "/api/v1/question-generation/tasks"),
    ("get", "/api/v1/question-generation/tasks/{task_id}"),
    ("post", "/api/v1/question-generation/questions/{question_id}/review"),
    ("get", "/api/v1/question-generation/policies/effective"),
    ("put", "/api/v1/question-generation/policies/global"),
    ("put", "/api/v1/question-generation/policies/question-banks/{question_bank_id}"),
    ("delete", "/api/v1/question-generation/policies/question-banks/{question_bank_id}"),
    ("post", "/api/v1/question-generation/allocations/preview"),
    ("post", "/api/v1/import-tasks"),
    ("get", "/api/v1/import-tasks"),
    ("get", "/api/v1/import-tasks/{task_id}"),
    ("post", "/api/v1/import-tasks/{task_id}/run"),
    ("post", "/api/v1/import-tasks/{task_id}/relations/retry"),
    ("post", "/api/v1/import-tasks/{task_id}/simulate"),
    ("get", "/api/v1/dashboard/overview"),
    ("post", "/api/v1/agent/knowledge-extract/test"),
    ("post", "/api/v1/agent/knowledge-deduplicate/test"),
    ("get", "/api/v1/question-dedup/status"),
    ("get", "/api/v1/question-dedup/records"),
    ("post", "/api/v1/question-dedup/records/{record_id}/resolve"),
    ("get", "/api/v1/question-dedup/stats/{task_id}"),
    ("post", "/api/v1/question-dedup/index/rebuild"),
    ("get", "/api/v1/question-reviews/records"),
    ("get", "/api/v1/question-reviews/stats/{task_id}"),
    ("post", "/api/v1/question-reviews/questions/{question_id}/reopen"),
    ("post", "/api/v1/question-reviews/batches/preview"),
    ("post", "/api/v1/question-reviews/batches"),
    ("get", "/api/v1/question-reviews/batches"),
    ("get", "/api/v1/question-reviews/batches/{batch_id}"),
]


def data_schema(schema):
    if "$ref" in schema:
        name = schema["$ref"].rsplit("/", 1)[-1]
        schema = spec.get("components", {}).get("schemas", {}).get(name, {})
    return schema.get("properties", {}).get("data")


def is_rich(ds):
    if not isinstance(ds, dict):
        return False
    if "$ref" in ds:
        return True
    if ds.get("properties"):
        return True
    for k in ("allOf", "anyOf", "oneOf"):
        for sub in ds.get(k, []) or []:
            if is_rich(sub):
                return True
    return False


failed = []
for method, path in OPS:
    op = spec.get("paths", {}).get(path, {}).get(method)
    if op is None:
        failed.append((method, path, "OP NOT FOUND"))
        continue
    resp200 = op.get("responses", {}).get("200") or op.get("responses", {}).get("201")
    if not resp200:
        failed.append((method, path, "NO 200 RESPONSE"))
        continue
    content = (resp200.get("content") or {}).get("application/json") or {}
    schema = content.get("schema") or {}
    if "$ref" in schema:
        name = schema["$ref"].rsplit("/", 1)[-1]
        schema = spec.get("components", {}).get("schemas", {}).get(name, {})
    if "properties" not in schema:
        failed.append((method, path, f"200 schema no properties: {schema}"))
        continue
    ds = data_schema(schema)
    if not is_rich(ds):
        failed.append((method, path, f"data not expandable: {ds}"))
        continue
    print(f"OK  {method.upper():6s} {path}")

print("-" * 60)
if failed:
    for f in failed:
        print("FAIL", f)
    sys.exit(1)
print(f"ALL {len(OPS)} OPS PASSED")
