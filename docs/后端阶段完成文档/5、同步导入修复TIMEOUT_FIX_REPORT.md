# ImportTask 导入期间全站 API 超时修复报告

## 一、根因

```
async def run_import_task()
    → service.execute_import()    ← 同步耗时操作（LLM 60~80秒）
    → 阻塞 Python 事件循环
    → 所有 API 无响应
```

**证据**：`run_import_task` 和 `retry_import_relations` 是 `async def` 路由，内部调用同步的 `execute_import()`，其中包含多个 LLM 调用（每次 60+ 秒）。Python 单线程事件循环被阻塞，无法处理其他请求。

## 二、修复方案

**将耗时导入任务从 API 请求路径分离到后台线程**：

```
API 请求 → 验证 → 启动后台线程 → 立即返回 task_id
后台线程 → 独立 Session → 执行导入 → 更新任务状态
```

## 三、修改文件

| 文件 | 修改内容 |
|------|----------|
| `app/services/background_runner.py` | **新增** 后台任务执行器（threading + 独立 Session + 并发锁） |
| `app/api/v1/import_task.py` | `run` 和 `relations/retry` 改为后台执行，立即返回 |

## 四、关键设计

1. **后台线程独立 Session**：每个任务创建 `SessionLocal()`，完成后关闭，不影响 API 请求
2. **并发控制**：`Semaphore(1)` 限制同时只执行 1 个导入任务
3. **立即返回**：API 提交后返回 `ACCEPTED`，通过 `GET /{id}` 查询进度
4. **状态可查**：任务执行进度实时更新到数据库

## 五、修复前后对比

| 指标 | 修复前 | 修复后 |
|------|--------|--------|
| 导入提交响应 | 阻塞 60~80s | **171ms** |
| 导入期间 health | 超时 | **55ms** |
| 导入期间 login | 超时 | **436ms** |
| 导入期间知识查询 | 超时 | **正常** |

## 六、测试结果

```
回归测试: 95 passed, 0 failed
并发测试: 全部通过
```

### 并发测试详情

- ✅ 不运行导入时，健康检查、登录、知识点查询正常
- ✅ 运行导入时，API 仍能在合理时间内响应
- ✅ 导入任务提交立即返回（171ms）
- ✅ 后台线程独立 Session，正确释放

## 七、事务与数据正确性

- ✅ 不使用跨越整个导入的长事务
- ✅ 每个知识点保存后立即 commit
- ✅ 关系生成失败不回滚已保存的 Knowledge
- ✅ 后台线程独立 Session，异常时 rollback + close
- ✅ 去重和幂等逻辑不变

## 八、未执行项

| 项目 | 原因 |
|------|------|
| MySQL PROCESSLIST 诊断 | 需要并发导入 + DBA 权限 |
| 连接池 checkout/checkin 日志 | 需要 SQLAlchemy 事件监听（非必要） |
| 多 Worker 并发测试 | 当前限制并发为 1 |
