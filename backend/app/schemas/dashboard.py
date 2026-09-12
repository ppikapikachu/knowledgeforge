"""Dashboard schemas."""

from pydantic import BaseModel, Field


class DashboardOverview(BaseModel):
    """Dashboard overview response schema."""

    knowledge_count: int = Field(description="知识点总数")
    question_count: int = Field(description="题目总数")
    single_choice_count: int = Field(description="单选题数量")
    multiple_choice_count: int = Field(description="多选题数量")
    true_false_count: int = Field(description="判断题数量")
    short_answer_count: int = Field(description="简答题数量")
    import_task_count: int = Field(description="导入任务总数")
