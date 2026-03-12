"""
LLM-based grading module.
Handles communication with OpenAI API for automated assignment grading.
"""

import json
import logging
from dataclasses import dataclass
from typing import Optional

from openai import OpenAI

from grading_config import GradingConfig

logger = logging.getLogger(__name__)


@dataclass
class GradingResult:
    """Represents the grading result for a submission."""
    total_score: int
    dimensions: dict
    overall_comment: str
    strengths: list[str]
    improvements: list[str]
    raw_response: str
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "total_score": self.total_score,
            "dimensions": self.dimensions,
            "overall_comment": self.overall_comment,
            "strengths": self.strengths,
            "improvements": self.improvements,
        }
    
    def __str__(self) -> str:
        """String representation of grading result."""
        lines = [
            f"总分：{self.total_score}",
            f"总体评价：{self.overall_comment}",
            "\n各维度评分:",
        ]
        for dim, data in self.dimensions.items():
            lines.append(f"  - {dim}: {data.get('score', 'N/A')} - {data.get('comment', '')}")
        lines.append("\n优点:")
        for s in self.strengths:
            lines.append(f"  + {s}")
        lines.append("\n改进建议:")
        for i in self.improvements:
            lines.append(f"  - {i}")
        return "\n".join(lines)


class LLMGrader:
    """LLM-based assignment grader using OpenAI API."""
    
    def __init__(self, config: GradingConfig):
        """
        Initialize the LLM grader.
        
        Args:
            config: Grading configuration with API settings and prompts.
        """
        self.config = config
        
        client_kwargs = {}
        if config.openai_api_key:
            client_kwargs["api_key"] = config.openai_api_key
        if config.openai_base_url:
            client_kwargs["base_url"] = config.openai_base_url
            
        self.client = OpenAI(**client_kwargs)
    
    def grade_submission(
        self, 
        assignment_requirements: str, 
        submission_content: str,
        max_retries: int = 3
    ) -> GradingResult:
        """
        Grade a student submission using LLM.
        
        Args:
            assignment_requirements: The assignment requirements/prompt text.
            submission_content: The student's submission content.
            max_retries: Maximum number of retry attempts on parsing failure.
            
        Returns:
            GradingResult with scores and feedback.
            
        Raises:
            ValueError: If grading fails after all retries.
        """
        user_prompt = self.config.build_user_prompt(
            assignment_requirements, 
            submission_content
        )
        
        logger.info(f"Sending grading request to LLM (model: {self.config.model_name})")
        
        for attempt in range(max_retries):
            try:
                response = self.client.chat.completions.create(
                    model=self.config.model_name,
                    messages=[
                        {"role": "system", "content": self.config.prompt.system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    max_tokens=self.config.max_tokens,
                    temperature=self.config.temperature,
                    response_format={"type": "json_object"}
                )
                
                raw_response = response.choices[0].message.content
                logger.debug(f"Raw LLM response: {raw_response[:200]}...")
                
                return self._parse_grading_response(raw_response)
                
            except json.JSONDecodeError as e:
                logger.warning(f"Attempt {attempt + 1}: Failed to parse JSON response: {e}")
                if attempt == max_retries - 1:
                    raise ValueError(f"Failed to parse grading response after {max_retries} attempts")
            except Exception as e:
                logger.error(f"Grading error: {e}")
                raise
        
        raise ValueError("Grading failed")
    
    def _parse_grading_response(self, raw_response: str) -> GradingResult:
        """
        Parse the raw LLM response into a GradingResult.
        
        Args:
            raw_response: Raw JSON string from LLM.
            
        Returns:
            Parsed GradingResult object.
            
        Raises:
            ValueError: If response format is invalid.
        """
        try:
            # Clean up the response (remove markdown code blocks if present)
            cleaned = raw_response.strip()
            if cleaned.startswith("```json"):
                cleaned = cleaned[7:]
            if cleaned.startswith("```"):
                cleaned = cleaned[3:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
            cleaned = cleaned.strip()
            
            data = json.loads(cleaned)
            
            # Validate required fields
            required_fields = ["total_score", "dimensions", "overall_comment"]
            for field in required_fields:
                if field not in data:
                    raise ValueError(f"Missing required field: {field}")
            
            return GradingResult(
                total_score=int(data["total_score"]),
                dimensions=data.get("dimensions", {}),
                overall_comment=data.get("overall_comment", ""),
                strengths=data.get("strengths", []),
                improvements=data.get("improvements", []),
                raw_response=raw_response
            )
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON parsing error: {e}")
            logger.error(f"Raw response: {raw_response}")
            raise ValueError(f"Invalid JSON response: {e}")
        except (KeyError, TypeError, ValueError) as e:
            logger.error(f"Response validation error: {e}")
            logger.error(f"Raw response: {raw_response}")
            raise ValueError(f"Invalid response format: {e}")
    
    def grade_batch(
        self,
        assignment_requirements: str,
        submissions: list[tuple[str, str]],  # List of (student_id, submission_content)
        delay_between_requests: float = 0.0
    ) -> dict[str, GradingResult]:
        """
        Grade multiple submissions in batch.
        
        Args:
            assignment_requirements: The assignment requirements text.
            submissions: List of (student_id, submission_content) tuples.
            delay_between_requests: Delay between API requests (seconds).
            
        Returns:
            Dictionary mapping student_id to GradingResult.
        """
        import time
        
        results = {}
        total = len(submissions)
        
        for i, (student_id, content) in enumerate(submissions, 1):
            logger.info(f"Grading submission {i}/{total} for student: {student_id}")
            try:
                result = self.grade_submission(assignment_requirements, content)
                results[student_id] = result
                logger.info(f"  -> Score: {result.total_score}/{self.config.criteria.total_points}")
            except Exception as e:
                logger.error(f"Failed to grade submission for {student_id}: {e}")
                results[student_id] = None
            
            if delay_between_requests > 0 and i < total:
                time.sleep(delay_between_requests)
        
        return results
