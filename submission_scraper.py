"""
Submission scraper module.
Extracts student submissions from the course website using Selenium.
"""

import logging
import time
from dataclasses import dataclass
from typing import Optional

from selenium.webdriver import Chrome
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

logger = logging.getLogger(__name__)


@dataclass
class StudentSubmission:
    """Represents a student's assignment submission."""
    student_id: str
    student_name: str
    submission_content: str
    submission_time: Optional[str] = None
    attachments: list[str] = None
    
    def __post_init__(self):
        if self.attachments is None:
            self.attachments = []


class SubmissionScraper:
    """Scraper for extracting student submissions from course website."""
    
    # CSS selectors for 学在浙大 course platform
    SUBMISSION_ROW_SELECTORS = [
        ".submission-item.list-item",
        ".homework-row.single-homework",
        "tr.submission-item",
        "[ng-repeat*='submission']",
    ]
    
    STUDENT_ID_SELECTORS = [
        ".truncate-text span[ng-bind*='user_no']",
        ".user-no span",
        "td:nth-child(2)",
    ]
    
    STUDENT_NAME_SELECTORS = [
        ".student-name",
        ".user-name span",
        "td:nth-child(3)",
    ]
    
    SUBMISSION_CONTENT_SELECTORS = [
        ".homework-content .comment-area",
        ".submission-content",
        ".answer-content",
        "[ng-bind-html*='comment']",
        "[ng-bind-html*='content']",
    ]
    
    SUBMISSION_TIME_SELECTORS = [
        ".submission-time",
        ".time span",
        "[ng-bind*='created_at']",
    ]
    
    ATTACHMENT_SELECTORS = [
        ".attachment-list a",
        ".file-list a",
        "[ng-repeat*='upload']",
    ]
    
    def __init__(self, driver: Chrome, timeout: int = 15):
        """
        Initialize the submission scraper.
        
        Args:
            driver: Selenium Chrome driver instance.
            timeout: Default timeout for WebDriverWait.
        """
        self.driver = driver
        self.wait = WebDriverWait(driver, timeout)
    
    def navigate_to_assignment(self, assignment_url: str) -> bool:
        """
        Navigate to the assignment page.
        
        Args:
            assignment_url: URL of the assignment page.
            
        Returns:
            True if navigation successful, False otherwise.
        """
        try:
            logger.info(f"Navigating to assignment: {assignment_url}")
            self.driver.get(assignment_url)
            
            # Wait for page to load - look for common assignment page elements
            self.wait.until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, "[ng-controller], .homework-detail, .assignment-content")
                )
            )
            logger.info("Assignment page loaded successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to navigate to assignment: {e}")
            return False
    
    def get_assignment_requirements(self) -> str:
        """
        Extract the assignment requirements from the current page.
        
        Returns:
            Assignment requirements text.
        """
        try:
            # Try multiple selectors for assignment description
            selectors = [
                ".homework-description",
                ".assignment-requirements",
                ".detail-content",
                ".content-plain",
                "[ng-bind-html*='description']",
            ]
            
            for selector in selectors:
                try:
                    element = self.driver.find_element(By.CSS_SELECTOR, selector)
                    text = element.text.strip()
                    if text:
                        logger.info(f"Extracted assignment requirements ({len(text)} chars)")
                        return text
                except:
                    continue
            
            # Fallback: try to find any content div with assignment-related text
            content_divs = self.driver.find_elements(By.CSS_SELECTOR, "div")
            for div in content_divs:
                text = div.text.strip()
                if len(text) > 100 and ("作业" in text or "要求" in text or "task" in text.lower()):
                    logger.info(f"Found assignment content in div ({len(text)} chars)")
                    return text
            
            logger.warning("Could not find assignment requirements")
            return ""
            
        except Exception as e:
            logger.error(f"Error extracting assignment requirements: {e}")
            return ""
    
    def get_all_submissions(self) -> list[StudentSubmission]:
        """
        Extract all student submissions from the assignment grading page.
        
        Returns:
            List of StudentSubmission objects.
        """
        try:
            submissions = []
            
            # Find submission rows using multiple selectors
            rows = self._find_elements_with_selectors(self.SUBMISSION_ROW_SELECTORS)
            
            if not rows:
                # Fallback: try to find any table rows
                rows = self.driver.find_elements(By.CSS_SELECTOR, "tbody tr")
                logger.info(f"Using fallback, found {len(rows)} table rows")
            
            logger.info(f"Found {len(rows)} submission rows")
            
            for i, row in enumerate(rows):
                try:
                    submission = self._parse_submission_row(row)
                    if submission and submission.submission_content:
                        submissions.append(submission)
                        logger.info(f"  Extracted submission {i+1}/{len(rows)}: {submission.student_name}")
                except Exception as e:
                    logger.warning(f"Failed to parse row {i}: {e}")
                    continue
            
            logger.info(f"Extracted {len(submissions)} submissions with content")
            return submissions
            
        except Exception as e:
            logger.error(f"Error extracting submissions: {e}")
            return []
    
    def _find_elements_with_selectors(self, selectors: list[str]) -> list:
        """Try multiple selectors and return the first non-empty result."""
        for selector in selectors:
            elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
            if elements:
                logger.debug(f"Found elements with selector: {selector}")
                return elements
        return []
    
    def _parse_submission_row(self, row) -> Optional[StudentSubmission]:
        """
        Parse a single submission row element.
        
        For 学在浙大 platform:
        1. First click the row to open submission details
        2. Then extract content from the opened view
        
        Args:
            row: Selenium WebElement representing a submission row.
            
        Returns:
            StudentSubmission object or None if parsing fails.
        """
        try:
            student_id = ""
            student_name = ""
            content = ""
            submission_time = None
            attachments = []
            
            # Step 1: Extract student info from the row
            student_id = self._extract_text_from_selectors(row, self.STUDENT_ID_SELECTORS)
            student_name = self._extract_text_from_selectors(row, self.STUDENT_NAME_SELECTORS)
            
            # Step 2: Click to view submission details (if needed)
            # The actual submission content is in .homework-content .comment-area
            # which may require clicking to expand
            try:
                # Try to click the row or a view button to expand content
                view_btn = row.find_element(By.CSS_SELECTOR, "a[href*='submissions'], .view-btn")
                if view_btn:
                    view_btn.click()
                    time.sleep(1)  # Wait for content to load
            except:
                pass  # Content might already be visible
            
            # Step 3: Extract submission content
            # Primary: .homework-content .comment-area (学在浙大 specific)
            content = self._extract_text_from_selectors(row, self.SUBMISSION_CONTENT_SELECTORS)
            
            # If no content found in row, try to get from page context
            if not content:
                # The content might be in a separate detail view
                # Try to find content in the current page context
                content_elements = self.driver.find_elements(
                    By.CSS_SELECTOR, ".homework-content .comment-area"
                )
                if content_elements:
                    content = content_elements[0].text.strip()
            
            # Step 4: Extract submission time
            submission_time = self._extract_text_from_selectors(row, self.SUBMISSION_TIME_SELECTORS)
            
            # Step 5: Extract attachments
            attachment_elements = row.find_elements(By.CSS_SELECTOR, ".attachment-list a, .file-list a")
            for elem in attachment_elements:
                try:
                    file_name = elem.text.strip()
                    if file_name:
                        attachments.append(file_name)
                except:
                    continue
            
            # If we have content and student info, create submission object
            if content and (student_id or student_name):
                return StudentSubmission(
                    student_id=student_id or "unknown",
                    student_name=student_name or "Unknown",
                    submission_content=content,
                    submission_time=submission_time,
                    attachments=attachments
                )
            
            # If we found student info but no content, mark for detail view
            if (student_id or student_name) and not content:
                logger.debug(f"Found student {student_name} but no content in row, need detail view")
                return StudentSubmission(
                    student_id=student_id or "unknown",
                    student_name=student_name or "Unknown",
                    submission_content="",  # Will be filled by detail view
                    submission_time=submission_time,
                    attachments=attachments
                )
            
            return None
            
        except Exception as e:
            logger.warning(f"Error parsing submission row: {e}")
            return None
    
    def _extract_text_from_selectors(self, parent, selectors: list[str]) -> str:
        """Try multiple selectors and return the first non-empty text."""
        for selector in selectors:
            try:
                elem = parent.find_element(By.CSS_SELECTOR, selector)
                text = elem.text.strip()
                if text:
                    return text
            except:
                continue
        return ""
    
    def get_submission_from_detail_view(self) -> Optional[StudentSubmission]:
        """
        Extract submission content from the current detail view page.
        This is used when viewing a single student's submission.
        
        Returns:
            StudentSubmission object or None.
        """
        try:
            # Look for student info
            student_name = self._extract_text_from_selectors(
                self.driver, 
                [".student-name", ".modal-title", "[ng-bind*='student.name']"]
            )
            
            student_id = self._extract_text_from_selectors(
                self.driver,
                [".student-id", "[ng-bind*='student.user_no']"]
            )
            
            # Look for submission content - primary selector for 学在浙大
            content = ""
            content_elements = self.driver.find_elements(
                By.CSS_SELECTOR, ".homework-content .comment-area"
            )
            if content_elements:
                content = content_elements[0].text.strip()
            
            # Fallback to other selectors
            if not content:
                content = self._extract_text_from_selectors(
                    self.driver,
                    self.SUBMISSION_CONTENT_SELECTORS
                )
            
            # Look for attachments
            attachments = []
            attachment_elements = self.driver.find_elements(
                By.CSS_SELECTOR, ".attachment-list a, .file-list a, [ng-repeat*='upload'] a"
            )
            for elem in attachment_elements:
                try:
                    file_name = elem.text.strip()
                    if file_name:
                        attachments.append(file_name)
                except:
                    continue
            
            if content:
                return StudentSubmission(
                    student_id=student_id or "unknown",
                    student_name=student_name or "Unknown",
                    submission_content=content,
                    attachments=attachments
                )
            
            return None
            
        except Exception as e:
            logger.error(f"Error extracting submission from detail view: {e}")
            return None
    
    def get_all_submissions_by_visiting_each(self, submission_urls: list[str]) -> list[StudentSubmission]:
        """
        Visit each submission URL individually to extract content.
        This is a fallback method when bulk extraction fails.
        
        Args:
            submission_urls: List of URLs for individual submission pages.
            
        Returns:
            List of StudentSubmission objects.
        """
        submissions = []
        
        for url in submission_urls:
            try:
                self.driver.get(url)
                time.sleep(1)  # Wait for page to load
                
                submission = self.get_submission_from_detail_view()
                if submission:
                    submissions.append(submission)
                    
            except Exception as e:
                logger.error(f"Failed to extract submission from {url}: {e}")
        
        return submissions
