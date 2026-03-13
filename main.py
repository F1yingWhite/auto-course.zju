import json
import os
import re
import time
import tomllib

from browser_manager import BrowserManager
from file_utils import clear_downloads, get_latest_files, wait_for_downloads
from llm_manager import LLMManager


def load_config(file_path="config.toml"):
    with open(file_path, "rb") as f:
        return tomllib.load(f)


def parse_llm_result(text):
    """
    解析 LLM 返回的 JSON 字符串，提取分数和评语。
    """
    try:
        # 尝试匹配 Markdown 块中的 JSON
        json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)
        else:
            # 如果没找到 Markdown 块，尝试匹配最外层的花括号
            json_match = re.search(r"(\{.*\})", text, re.DOTALL)
            json_str = json_match.group(1) if json_match else text

        data = json.loads(json_str)
        return data.get("分数"), data.get("评语")
    except Exception as e:
        print(f"解析 LLM 结果失败: {e}")
        return None, None


def clean_markdown(text):
    """
    去除评语中的 Markdown 语法，使其适合填入文本框。
    """
    if not text:
        return ""
    # 去除加粗/斜体
    text = re.sub(r"[*_]{1,3}", "", text)
    # 去除标题符号
    text = re.sub(r"^#+\s*", "", text, flags=re.MULTILINE)
    # 去除列表符号
    text = re.sub(r"^[-*+]\s+", "", text, flags=re.MULTILINE)
    # 去除数字列表前面的数字
    text = re.sub(r"^\d+\.\s+", "", text, flags=re.MULTILINE)
    # 去除代码块标记
    text = re.sub(r"```.*?```", "", text, flags=re.DOTALL)
    text = re.sub(r"`", "", text)
    return text.strip()


def main():
    # 1. 初始化配置
    config = load_config()
    download_dir = os.path.expanduser("~/Downloads")

    # 2. 准备工作：清空下载目录
    clear_downloads(download_dir)

    # 3. 初始化管理器
    browser = BrowserManager(download_dir)
    llm = LLMManager(config["llm"]["api"])

    try:
        # 4. 登录并进入课程
        browser.login(config["account"]["username"], config["account"]["password"])
        browser.enter_course_grading(config["course"]["url"])
        browser.filter_ungraded()

        # 5. 主循环：批改作业
        print("\n正在寻找首份待批改作业...")
        icons = browser.get_ungraded_assignments()
        if not icons:
            print("所有待批改作业已处理完毕。")
            return

        # 进入第一份作业
        browser.open_assignment_detail(icons[0])

        while True:
            try:
                print("\n--- 开始处理当前作业 ---")

                # 下载文件
                browser.download_current_assignment()

                # 等待下载完成
                wait_for_downloads(download_dir)

                # 获取下载后的文件列表
                files = get_latest_files(download_dir)

                # 调用 Gemini 进行评分
                if files:
                    result_text = llm.grade_assignment(files)
                    print("\n--- Gemini 原始回复 ---")
                    print(result_text)
                    print("----------------------\n")

                    score, comment = parse_llm_result(result_text)
                    if score is not None:
                        cleaned_comment = clean_markdown(comment)
                        print(f"解析成功 -> 分数: {score}")
                        print(f"清洗后的评语: {cleaned_comment[:50]}...")

                        # 填入评分和评语
                        browser.fill_grade(score, cleaned_comment)
                        print("已自动填入分数和评语。")
                    else:
                        print("解析失败，跳过填入步骤。")
                else:
                    print("⚠️ 该作业未检测到已下载的文件，跳过 LLM 评分。")

                # 评分完成后清空下载目录
                clear_downloads(download_dir)

                # 尝试切换到下一个学生
                print("尝试进入下一个学生...")
                if not browser.click_next_student():
                    print("无法进入下一个学生，可能已到列表末尾或全部批改完成。")
                    break

            except Exception as e:
                print(f"处理当前作业时发生错误: {e}")
                # 发生错误时，尝试返回列表重新开始
                print("尝试返回列表重置状态...")
                browser.driver.get(config["course"]["url"])
                time.sleep(3)
                browser.enter_course_grading(config["course"]["url"])
                browser.filter_ungraded()
                icons = browser.get_ungraded_assignments()
                if not icons:
                    break
                browser.open_assignment_detail(icons[0])
                continue

        print("\n🎉 所有作业已处理完成！")
        input("按回车键退出浏览器...")

    except Exception as e:
        print(f"\n❌ 主程序发生严重错误: {e}")
        import traceback

        traceback.print_exc()
    finally:
        browser.quit()


if __name__ == "__main__":
    main()
