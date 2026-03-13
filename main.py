import os
import time
import tomllib

from browser_manager import BrowserManager
from file_utils import clear_downloads, get_latest_files
from llm_manager import LLMManager


def load_config(file_path="config.toml"):
    with open(file_path, "rb") as f:
        return tomllib.load(f)


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
        print("\n开始检查待批改作业...")
        while True:
            try:
                icons = browser.get_ungraded_assignments()
            except Exception as e:
                print(f"获取待批改列表失败: {e}")
                break

            if not icons:
                print("所有作业已处理完毕。")
                break

            print(f"发现 {len(icons)} 份待批改作业，处理第一份...")
            first_icon = icons[0]

            try:
                # 进入批改页
                try:
                    browser.open_assignment_detail(first_icon)
                except Exception:
                    pass

                browser.download_current_assignment()

                # 获取下载后的文件列表
                files = get_latest_files(download_dir)

                # 调用 Gemini 进行评分
                if files:
                    result = llm.grade_assignment(files)
                    print("\n--- Gemini 评分结果 ---")
                    print(result)
                    print("----------------------\n")
                else:
                    print("⚠️ 该作业未检测到已下载的文件，跳过 LLM 评分。")

                # 评分完成后清空下载目录
                clear_downloads(download_dir)

                # 返回作业列表页
                print("返回作业列表...")
                browser.driver.back()
                time.sleep(3)

                # 重新应用筛选（返回后可能状态丢失）
                browser.filter_ungraded()

            except Exception as e:
                print(f"处理当前作业时发生错误: {e}")
                # 尝试强制返回列表页，以便继续下一个
                print("尝试返回作业列表以继续...")
                browser.driver.get(config["course"]["url"])
                time.sleep(3)
                browser.enter_course_grading(config["course"]["url"])
                browser.filter_ungraded()
                continue

        input("\n所有作业处理完成，按回车键退出浏览器...")

    except Exception as e:
        print(f"\n❌ 主程序发生严重错误: {e}")
        import traceback

        traceback.print_exc()
    finally:
        browser.quit()


if __name__ == "__main__":
    main()
