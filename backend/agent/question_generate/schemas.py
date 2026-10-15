"""QuestionGenerateAgent 的 Pydantic Schema。"""

from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class GeneratedOption(BaseModel):
    """生成的选项。"""

    option_key: str = Field(description="选项标识 A/B/C/D")
    option_content: str = Field(description="选项内容")
    is_correct: int = Field(description="是否正确: 1=对, 0=错")


class GeneratedQuestion(BaseModel):
    """生成的单个题目。"""

    question_type: str = Field(description="题型")
    content: str = Field(description="题干")
    answer: str = Field(description="标准答案")
    analysis: Optional[str] = Field(default=None, description="解析")
    difficulty: int = Field(ge=1, le=3, description="难度")
    options: List[GeneratedOption] = Field(default_factory=list, description="选项列表")
    knowledge_id: int = Field(description="关联知识点 ID")


class QuestionGenerateOutput(BaseModel):
    """LLM 结构化输出。"""

    questions: List[GeneratedQuestion] = Field(
        default_factory=list,
        description="生成的题目列表"
    )


class QuestionGenerateRequest(BaseModel):
    """生成请求。"""

    knowledge_id: int = Field(description="知识点 ID")
    question_bank_id: int = Field(description="题库 ID")
    question_type: str = Field(description="题型")
    difficulty: int = Field(ge=1, le=3, description="难度")
    count: int = Field(ge=1, le=20, description="生成数量")
    generate_explanation: bool = Field(default=False, description="是否生成解析")
