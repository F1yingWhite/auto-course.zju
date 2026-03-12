"""
Grading configuration module.
Contains prompt templates and grading criteria for automated assignment grading.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class GradingCriteria:
    """Grading criteria for assignments."""
    total_points: int = 100
    dimensions: list[str] = None
    
    def __post_init__(self):
        if self.dimensions is None:
            self.dimensions = [
                "correctness",
                "completeness", 
                "creativity",
                "formatting"
            ]


@dataclass
class GradingPrompt:
    """Prompt configuration for LLM-based grading."""
    
    # System prompt that sets up the grading role and rules
    system_prompt: str = """你是一位大学课程的助教，负责批改学生作业。请根据作业要求和评分标准，客观、公正地为学生作业打分。

评分原则：
1. 严格按照作业要求进行评分
2. 关注学生是否完成了所有要求的任务
3. 评估答案的正确性和完整性
4. 考虑学生的创新性和独特见解
5. 给出具体、有建设性的反馈意见

输出格式要求：
请严格按照以下 JSON 格式输出评分结果：
{
    "total_score": <总分，整数>,
    "dimensions": {
        "<维度 1>": {"score": <分数>, "comment": "<评语>"},
        "<维度 2>": {"score": <分数>, "comment": "<评语>"},
        ...
    },
    "overall_comment": "<总体评价和建议>",
    "strengths": ["<优点 1>", "<优点 2>", ...],
    "improvements": ["<改进建议 1>", "<改进建议 2>", ...]
}"""

    # User prompt template - {assignment_requirements} and {submission_content} will be filled in
    user_prompt_template: str = """## 作业要求
{assignment_requirements}

## 评分标准
总分：{total_points}分
评分维度：{dimensions}

## 学生提交内容
{submission_content}

## 评分任务
请根据上述作业要求和评分标准，对该学生作业进行评分。
请严格按照 JSON 格式输出评分结果，不要包含其他多余内容。"""


class GradingConfig:
    """Main configuration class for grading."""
    
    def __init__(
        self,
        openai_api_key: Optional[str] = None,
        openai_base_url: Optional[str] = None,
        model_name: str = "gpt-4o-mini",
        max_tokens: int = 2000,
        temperature: float = 0.3,
        criteria: Optional[GradingCriteria] = None,
        prompt: Optional[GradingPrompt] = None,
    ):
        self.openai_api_key = openai_api_key
        self.openai_base_url = openai_base_url
        self.model_name = model_name
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.criteria = criteria or GradingCriteria()
        self.prompt = prompt or GradingPrompt()
    
    def build_user_prompt(
        self, 
        assignment_requirements: str, 
        submission_content: str
    ) -> str:
        """Build the user prompt with assignment and submission content."""
        return self.prompt.user_prompt_template.format(
            assignment_requirements=assignment_requirements,
            total_points=self.criteria.total_points,
            dimensions=", ".join(self.criteria.dimensions),
            submission_content=submission_content
        )
    
    @classmethod
    def from_dict(cls, config_dict: dict) -> "GradingConfig":
        """Create GradingConfig from a dictionary."""
        grading_config = config_dict.get("grading", {})
        
        criteria_data = grading_config.get("criteria", {})
        criteria = GradingCriteria(
            total_points=criteria_data.get("total_points", 100),
            dimensions=criteria_data.get("dimensions")
        )
        
        prompt_data = grading_config.get("prompt", {})
        prompt = GradingPrompt(
            system_prompt=prompt_data.get("system_prompt", GradingPrompt.system_prompt),
            user_prompt_template=prompt_data.get("user_prompt_template", GradingPrompt.user_prompt_template)
        )
        
        return cls(
            openai_api_key=grading_config.get("openai_api_key"),
            openai_base_url=grading_config.get("openai_base_url"),
            model_name=grading_config.get("model_name", "gpt-4o-mini"),
            max_tokens=grading_config.get("max_tokens", 2000),
            temperature=grading_config.get("temperature", 0.3),
            criteria=criteria,
            prompt=prompt
        )
