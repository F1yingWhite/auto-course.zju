"""
Course Auto Grader - Main entry point.
Automates login, submission extraction, and LLM-based grading.
"""

import json
import logging
import os
from datetime import datetime
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from grading_config import GradingConfig
from llm_grader import LLMGrader
from submission_scraper import SubmissionScraper

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("grading.log", encoding="utf-8")
    ]
)
logger = logging.getLogger(__name__)


def load_config(file_path: str = "config.toml") -> dict:
    """Load configuration from TOML file."""
    try:
        import tomllib
    except ImportError:
        import tomli as tomllib
    
    with open(file_path, "rb") as f:
        return tomllib.load(f)


def save_grading_results(
    results: dict,
    output_dir: str = "grading_results",
    assignment_name: str = "assignment"
) -> str:
    """
    Save grading results to JSON and CSV files.
    
    Args:
        results: Dictionary of grading results.
        output_dir: Directory to save results.
        assignment_name: Name of the assignment for file naming.
        
    Returns:
        Path to the output directory.
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Save detailed JSON results
    json_file = output_path / f"{assignment_name}_{timestamp}.json"
    serializable_results = {}
    for student_id, result in results.items():
        if result:
            serializable_results[student_id] = result.to_dict()
        else:
            serializable_results[student_id] = None
    
    with open(json_file, "w", encoding="utf-8") as f:
        json.dump(serializable_results, f, ensure_ascii=False, indent=2)
    logger.info(f"Saved detailed results to: {json_file}")
    
    # Save summary CSV
    csv_file = output_path / f"{assignment_name}_{timestamp}_summary.csv"
    with open(csv_file, "w", encoding="utf-8") as f:
        f.write("学号，姓名，总分，总体评价\n")
        for student_id, result in results.items():
            if result:
                comment = result.overall_comment.replace("\n", " ")
                f.write(f"{student_id},,{result.total_score},{comment}\n")
            else:
                f.write(f"{student_id},,,评分失败\n")
    logger.info(f"Saved summary CSV to: {csv_file}")
    
    return str(output_path)


def login_course(driver: webdriver.Chrome, wait: WebDriverWait, config: dict) -> bool:
    """
    Login to the course website.
    
    Args:
        driver: Selenium Chrome driver.
        wait: WebDriverWait instance.
        config: Configuration dictionary with credentials.
        
    Returns:
        True if login successful, False otherwise.
    """
    username = config["account"]["username"]
    password = config["account"]["password"]
    
    try:
        # 1. Open course homepage
        logger.info("Opening course website...")
        driver.get("https://course.zju.edu.cn/learninginzju?locale=zh-CN")

        # 2. Click login button
        logger.info("Finding and clicking login button...")
        login_btn = wait.until(EC.element_to_be_clickable(
            (By.XPATH, "//a[contains(text(), '统一身份认证')] | //button[contains(text(), '统一身份认证')]")
        ))
        login_btn.click()

        # 3. Enter credentials
        logger.info("Entering credentials...")
        user_input = wait.until(EC.presence_of_element_located((By.ID, "username")))
        pass_input = driver.find_element(By.ID, "password")
        submit_btn = driver.find_element(By.ID, "dl")

        user_input.send_keys(username)
        pass_input.send_keys(password)
        submit_btn.click()

        # 4. Wait for login
        logger.info("Waiting for authentication...")
        wait.until(EC.url_contains("course.zju.edu.cn"))
        
        logger.info("Login successful!")
        return True

    except Exception as e:
        logger.error(f"Login failed: {e}")
        return False


def run_grading_workflow(
    driver: webdriver.Chrome,
    wait: WebDriverWait,
    grading_config: GradingConfig,
    assignment_url: str,
    submissions_url: str = None
) -> dict:
    """
    Run the complete grading workflow.
    
    Args:
        driver: Selenium Chrome driver.
        wait: WebDriverWait instance.
        grading_config: Grading configuration.
        assignment_url: URL of the assignment page.
        submissions_url: URL of the submissions list (optional).
        
    Returns:
        Dictionary of grading results.
    """
    scraper = SubmissionScraper(driver, wait.timeout)
    grader = LLMGrader(grading_config)
    
    # Step 1: Navigate to assignment page and get requirements
    logger.info("=" * 50)
    logger.info("Step 1: Extracting assignment requirements")
    logger.info("=" * 50)
    
    if not scraper.navigate_to_assignment(assignment_url):
        raise ValueError(f"Failed to navigate to assignment: {assignment_url}")
    
    # Allow time for page to fully load
    driver.implicitly_wait(2)
    assignment_requirements = scraper.get_assignment_requirements()
    
    if not assignment_requirements:
        logger.warning("Could not extract assignment requirements. Using placeholder.")
        assignment_requirements = "请根据课程要求完成作业。"
    
    logger.info(f"Assignment requirements extracted ({len(assignment_requirements)} chars)")
    
    # Step 2: Navigate to submissions page and get all submissions
    logger.info("=" * 50)
    logger.info("Step 2: Extracting student submissions")
    logger.info("=" * 50)
    
    if submissions_url:
        scraper.navigate_to_assignment(submissions_url)
        driver.implicitly_wait(2)
    
    # Try to get submissions from the list page first
    submissions = scraper.get_all_submissions()
    
    # If no submissions found with content, try alternative method
    if not submissions:
        logger.info("Could not extract submissions from list view.")
        logger.info("Please navigate to the submissions list page...")
        input("Press Enter when you're on the submissions list page...")
        
        # Try again after user navigation
        submissions = scraper.get_all_submissions()
        
        # If still no submissions, try visiting each submission individually
        if not submissions:
            logger.info("Attempting to collect submission URLs for individual extraction...")
            # User needs to provide submission URLs or navigate manually
            submission_urls = []
            print("Please enter submission URLs one per line (empty line to finish):")
            while True:
                url = input().strip()
                if not url:
                    break
                submission_urls.append(url)
            
            if submission_urls:
                submissions = scraper.get_all_submissions_by_visiting_each(submission_urls)
    
    if not submissions:
        logger.warning("No submissions found. Please check the page structure.")
        return {}
    
    # Filter submissions that have content
    submissions_with_content = [s for s in submissions if s.submission_content]
    submissions_without_content = [s for s in submissions if not s.submission_content]
    
    logger.info(f"Found {len(submissions_with_content)} submissions with content")
    if submissions_without_content:
        logger.info(f"{len(submissions_without_content)} submissions need detail view extraction")
        
        # For submissions without content, try to extract from detail view
        for submission in submissions_without_content:
            logger.info(f"Extracting content for {submission.student_name}...")
            # The user may need to navigate to each submission detail page
            # This is handled by the detail view extraction method
    
    # Step 3: Grade each submission
    logger.info("=" * 50)
    logger.info("Step 3: Grading submissions with LLM")
    logger.info("=" * 50)
    
    results = {}
    for i, submission in enumerate(submissions_with_content, 1):
        logger.info(f"Grading submission {i}/{len(submissions_with_content)}: {submission.student_name} ({submission.student_id})")
        
        try:
            result = grader.grade_submission(
                assignment_requirements,
                submission.submission_content
            )
            results[submission.student_id] = result
            logger.info(f"  Score: {result.total_score}/{grading_config.criteria.total_points}")
        except Exception as e:
            logger.error(f"  Failed to grade: {e}")
            results[submission.student_id] = None
    
    return results


def main():
    """Main entry point for the auto grader."""
    # Load configuration
    config = load_config()
    grading_config = GradingConfig.from_dict(config)
    
    # Get OpenAI API key from environment or config
    api_key = os.environ.get("OPENAI_API_KEY", grading_config.openai_api_key)
    if not api_key:
        logger.error("OpenAI API key not found. Please set OPENAI_API_KEY environment variable or add to config.")
        return
    
    grading_config.openai_api_key = api_key
    
    # Initialize Selenium
    options = webdriver.ChromeOptions()
    # Add options for headless mode if needed
    # options.add_argument("--headless=new")
    driver = webdriver.Chrome(options=options)
    wait = WebDriverWait(driver, 15)
    
    try:
        # Login
        if not login_course(driver, wait, config):
            logger.error("Failed to login. Exiting.")
            return
        
        # Navigate to course page
        course_url = config["course"]["url"]
        logger.info(f"Navigating to course: {course_url}")
        driver.get(course_url)
        
        # Get assignment URLs from config or prompt user
        assignment_url = config.get("grading", {}).get("assignment_url")
        submissions_url = config.get("grading", {}).get("submissions_url")
        
        if not assignment_url:
            logger.info("Please navigate to the assignment page manually...")
            input("Press Enter when you're on the assignment page...")
            assignment_url = driver.current_url
        
        # Run grading workflow
        results = run_grading_workflow(
            driver, wait, grading_config,
            assignment_url, submissions_url
        )
        
        # Save results
        if results:
            output_path = save_grading_results(results)
            logger.info(f"Grading completed! Results saved to: {output_path}")
            
            # Print summary
            print("\n" + "=" * 50)
            print("GRADING SUMMARY")
            print("=" * 50)
            for student_id, result in results.items():
                if result:
                    print(f"{student_id}: {result.total_score}/{grading_config.criteria.total_points}")
                else:
                    print(f"{student_id}: 评分失败")
        else:
            logger.warning("No grading results to save.")
        
        # Keep browser open for review
        input("\nPress Enter to close browser and exit...")
        
    except Exception as e:
        logger.error(f"Error in grading workflow: {e}")
        raise
    finally:
        driver.quit()


if __name__ == "__main__":
    main()
