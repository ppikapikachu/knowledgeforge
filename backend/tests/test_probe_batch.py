# 一次性探针（已中和）：曾用于实证 skipped 项 claim_key 被列默认值误置 'active' 的根因。
# 该文件删除被 Windows 文件权限阻止（文件自身无当前用户显式条目且无 WRITE_OWNER），
# 故以空模块中和，不影响测试收集。根因修复见 app/models/question_review_batch.py claim_key default=None。
