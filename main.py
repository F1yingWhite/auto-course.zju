import time
import tomllib

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

import os
import time
def load_config(file_path="config.toml"):
    with open(file_path, "rb") as f:
        return tomllib.load(f)


def main():
    # 1. 加载配置
    config = load_config()
    username = config["account"]["username"]
    password = config["account"]["password"]
    course_url = config["course"]["url"]

    options = webdriver.ChromeOptions()
    driver = webdriver.Chrome(options=options)
    wait = WebDriverWait(driver, 15)

    try:
        # 1. 打开学在浙大首页
        print("正在打开学在浙大首页...")
        driver.get("https://course.zju.edu.cn/learninginzju?locale=zh-CN")

        # 2. 点击统一身份认证登录按钮
        # 根据页面特征寻找包含“统一身份认证”字样的链接或按钮
        print("寻找并点击登录按钮...")
        login_btn = wait.until(
            EC.element_to_be_clickable(
                (By.XPATH, "//a[contains(text(), '统一身份认证')] | //button[contains(text(), '统一身份认证')]")
            )
        )
        login_btn.click()

        # 3. 在浙大统一身份认证页面输入账号密码并登录
        print("正在输入统一身份认证账号密码...")
        # 等待账号输入框出现
        user_input = wait.until(EC.presence_of_element_located((By.ID, "username")))
        pass_input = driver.find_element(By.ID, "password")
        submit_btn = driver.find_element(By.ID, "dl")  # "dl" 是浙大登录按钮的常见 ID

        user_input.send_keys(username)
        pass_input.send_keys(password)
        submit_btn.click()

        print("等待登录验证...")
        wait.until(EC.url_contains("course.zju.edu.cn"))

        print(f"登录成功，正在跳转到课程主页: {course_url}")
        driver.get(course_url)
        print("成功进入目标课程！")

        # 等待页面基础元素加载完成
        time.sleep(2)

        grading_tab = wait.until(EC.element_to_be_clickable((By.XPATH, "//span[@ng-click=\"ui.view = 'scores'\"]")))

        if "active" not in grading_tab.get_attribute("class"):
            grading_tab.click()
            print("已点击【作业批改】")
            time.sleep(2)
        else:
            print("当前已经在【作业批改】标签页")

        time.sleep(2)

        print("正在检查【状态】下拉框...")
        try:
            status_btn = wait.until(EC.element_to_be_clickable((By.ID, "status-select_ms")))

            current_status = status_btn.text.strip()

            if "已交" not in current_status:
                print("当前状态不是【已交】，正在展开下拉框...")
                status_btn.click()
                time.sleep(1)

                status_option = wait.until(
                    EC.element_to_be_clickable(
                        (
                            By.XPATH,
                            "//div[contains(@class, 'ui-multiselect-menu') and contains(@style, 'display: block')]//label[contains(., '已交')] | //label[contains(., '已交')]",
                        )
                    )
                )
                status_option.click()
                print("已成功选择【已交】状态！")
                time.sleep(1)  # 等待表格数据按新状态刷新
            else:
                print("状态已经是【已交】，无需更改。")

        except Exception as e:
            print(f"设置【状态】下拉框时跳过，报错信息作调试参考: {e}")

        # 3. 筛选批改状态：未批改
        print("正在设置批改状态为【未批改】...")
        try:
            grading_btn = wait.until(EC.element_to_be_clickable((By.ID, "status-mark_ms")))
            current_grading_status = grading_btn.text.strip()

            if "未批改" not in current_grading_status:
                print(f"当前批改状态为【{current_grading_status}】，正在展开下拉框...")
                grading_btn.click()
                time.sleep(1)  # 等待下拉动画展开

                ungraded_option = wait.until(
                    EC.element_to_be_clickable(
                        (
                            By.XPATH,
                            "//div[contains(@class, 'ui-multiselect-menu') and contains(@style, 'display: block')]//input[@value='unmarked']/parent::label",
                        )
                    )
                )
                ungraded_option.click()
                print("已成功选中【未批改】！")

                grading_btn.click()
                time.sleep(2)
            else:
                print("批改状态已经是【未批改】，无需更改。")

        except Exception as e:
            print(f"设置【批改】下拉框时发生异常，请参考报错信息: {e}")
        # 4. 点击第一个待批改的作业进行批改（当前页面跳转）
        print("正在查找批改按钮...")
        correct_icons = wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, "i.font.font-correcting")))

        if len(correct_icons) > 0:
            try:
                print(f"太好了，当前页面找到了 {len(correct_icons)} 份待批改的作业！")
                print("正在点击第一个作业的批改图标...")
                first_icon = correct_icons[0]
                current_url = driver.current_url
                driver.execute_script("arguments[0].click();", first_icon)
                wait.until(EC.url_changes(current_url))
                print("正在加载批改详情页...")

                time.sleep(3)
                print("已成功进入批改详情页！")
            except Exception as e:
                print(f"点击批改图标时发生异常，请参考报错信息: {e}")
        else:
            print("列表中没有找到批改图标，太棒了，作业已经全部批改完了！")

        print("列表筛选完成！")
        print("成功进入目标课程！")
        # 5. 抓取并循环遍历学生提交的所有作业文件
        print("正在定位左侧的作业文件列表...")
        try:
            file_items = wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, "div.tab-body div.upload")))

            print(f"共找到 {len(file_items)} 个提交的文件，准备依次处理...")

            for index, item in enumerate(file_items):
                try:
                    name_element = item.find_element(By.CSS_SELECTOR, "span.upload-name")
                    file_name = name_element.text.strip()
                except Exception:
                    file_name = f"未知文件_{index + 1}"

                print("\n=================================")
                print(f"正在处理第 {index + 1} 个文件: {file_name}")

                driver.execute_script("arguments[0].click();", item)

                time.sleep(5)

                print(f"预览已加载，准备寻找 [{file_name}] 的下载按钮...")
                try:
                    download_btn = wait.until(
                        EC.element_to_be_clickable(
                            (By.CSS_SELECTOR, "i.font-pdf-editor-download-btn, i.icon-file-preview-download")
                        )
                    )

                    driver.execute_script("arguments[0].click();", download_btn)
                    print(f"成功触发 [{file_name}] 的下载！")

                    # 触发下载后多等一会儿，确保浏览器开始建立下载任务，防止立马点下一个文件导致下载中断
                    time.sleep(3)

                except Exception as e:
                    print(f"⚠️ 未找到 [{file_name}] 的下载按钮，可能该文件不支持下载，或者预览还在加载: {e}")

        except Exception as e:
            print(f"查找或遍历作业文件列表失败，请检查定位逻辑: {e}")

        except Exception as e:
            print(f"查找或遍历作业文件列表失败，请检查定位逻辑: {e}")
        input("按下回车键关闭浏览器并结束脚本...")

    except Exception as e:
        print(f"发生错误: {e}")
    finally:
        driver.quit()


if __name__ == "__main__":
    main()
