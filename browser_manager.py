import time
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


class BrowserManager:
    def __init__(self, download_path: str):
        self.download_path = str(Path(download_path).expanduser())
        options = webdriver.ChromeOptions()
        # 设置默认下载路径
        prefs = {"download.default_directory": self.download_path}
        options.add_experimental_option("prefs", prefs)
        self.driver = webdriver.Chrome(options=options)
        self.wait = WebDriverWait(self.driver, 15)  # 默认等待 15 秒

    def login(self, username, password):
        """
        处理统一身份认证登录。
        """
        print("正在打开登录页面...")
        self.driver.get("https://course.zju.edu.cn/learninginzju?locale=zh-CN")

        login_btn = self.wait.until(
            EC.element_to_be_clickable(
                (By.XPATH, "//a[contains(text(), '统一身份认证')] | //button[contains(text(), '统一身份认证')]")
            )
        )
        login_btn.click()

        user_input = self.wait.until(EC.presence_of_element_located((By.ID, "username")))
        pass_input = self.driver.find_element(By.ID, "password")
        submit_btn = self.driver.find_element(By.ID, "dl")

        user_input.send_keys(username)
        pass_input.send_keys(password)
        submit_btn.click()

        self.wait.until(EC.url_contains("course.zju.edu.cn"))
        print("登录成功。")

    def enter_course_grading(self, course_url):
        """
        进入课程页面并切换到作业批改。
        """
        print(f"跳转到课程主页: {course_url}")
        self.driver.get(course_url)
        time.sleep(3)

        grading_tab = self.wait.until(
            EC.element_to_be_clickable((By.XPATH, "//span[@ng-click=\"ui.view = 'scores'\"]"))
        )
        if "active" not in grading_tab.get_attribute("class"):
            grading_tab.click()
            print("已进入【作业批改】标签页")
            time.sleep(2)

    def filter_ungraded(self):
        """
        筛选【已交】且【未批改】的作业。
        """
        print("设置筛选条件：已交 + 未批改...")
        try:
            # 设置【状态】为【已交】
            status_btn = self.wait.until(EC.element_to_be_clickable((By.ID, "status-select_ms")))
            if "已交" not in status_btn.text.strip():
                status_btn.click()
                time.sleep(1)
                status_option = self.wait.until(EC.element_to_be_clickable((By.XPATH, "//label[contains(., '已交')]")))
                status_option.click()
                time.sleep(1)

            # 设置【批改状态】为【未批改】
            grading_btn = self.wait.until(EC.element_to_be_clickable((By.ID, "status-mark_ms")))
            if "未批改" not in grading_btn.text.strip():
                grading_btn.click()
                time.sleep(1)
                ungraded_option = self.wait.until(
                    EC.element_to_be_clickable((By.XPATH, "//input[@value='unmarked']/parent::label"))
                )
                ungraded_option.click()
                grading_btn.click()
                time.sleep(2)
        except Exception as e:
            print(f"筛选作业时发生错误（可能已设置过）: {e}")

    def get_ungraded_assignments(self):
        """
        获取当前页面所有待批改图标。
        """
        try:
            # 缩短这里的等待，如果没有就是没有了
            local_wait = WebDriverWait(self.driver, 5)
            return local_wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, "i.font.font-correcting")))
        except:
            return []

    def open_assignment_detail(self, icon_element):
        """
        点击图标进入作业详情页。
        """
        current_url = self.driver.current_url
        self.driver.execute_script("arguments[0].scrollIntoView(true);", icon_element)
        time.sleep(0.5)
        self.driver.execute_script("arguments[0].click();", icon_element)

        # 等待 URL 变化
        WebDriverWait(self.driver, 10).until(EC.url_changes(current_url))
        print("已进入作业详情页，等待内容加载...")
        time.sleep(3)

    def download_current_assignment(self):
        """
        进入作业详情页，并下载所有文件。
        """
        try:
            # 增加显式等待时间，详情页可能加载较慢
            print("正在定位作业文件列表...")
            file_items = WebDriverWait(self.driver, 20).until(
                EC.presence_of_all_elements_located((By.CSS_SELECTOR, "div.tab-body div.upload"))
            )
            print(f"发现提交的文件数量: {len(file_items)}")

            for index, item in enumerate(file_items):
                file_name = "未知文件"
                try:
                    name_element = item.find_element(By.CSS_SELECTOR, "span.upload-name")
                    file_name = name_element.text.strip()
                    print(f"正在处理文件 ({index + 1}/{len(file_items)}): {file_name}")

                    self.driver.execute_script("arguments[0].scrollIntoView(true);", item)
                    time.sleep(1)
                    self.driver.execute_script("arguments[0].click();", item)

                    print("等待预览界面加载...")
                    time.sleep(4)

                    if len(self.driver.find_elements(By.TAG_NAME, "iframe")) > 0:
                        try:
                            self.wait.until(EC.frame_to_be_available_and_switch_to_it((By.TAG_NAME, "iframe")))

                            download_selectors = [
                                "div.tool.download i.font-pdf-editor-download-btn",
                                "i.icon-file-preview-download",
                                ".download-btn",
                                "i.font-download",
                            ]

                            download_btn = None
                            for selector in download_selectors:
                                try:
                                    btns = self.driver.find_elements(By.CSS_SELECTOR, selector)
                                    if btns and btns[0].is_displayed():
                                        download_btn = btns[0]
                                        break
                                except:
                                    continue

                            if download_btn:
                                ActionChains(self.driver).move_to_element(download_btn).click().perform()
                                print(f"已点击下载: {file_name}")
                                wait_time = 10 if ".pdf" in file_name.lower() else 5
                                time.sleep(wait_time)
                            else:
                                print("未找到下载按钮，可能此文件类型不支持预览下载。")

                            self.driver.switch_to.default_content()
                        except Exception as iframe_err:
                            print(f"iframe 内操作失败: {iframe_err}")
                            self.driver.switch_to.default_content()
                    else:
                        print("未发现预览 iframe。")

                except Exception as e:
                    print(f"处理文件 {file_name} 失败: {e}")
                    try:
                        self.driver.switch_to.default_content()
                    except:
                        pass
                    continue
        except Exception as e:
            print(f"获取详情页文件列表失败，可能是页面加载超时: {e}")
            raise

    def quit(self):
        self.driver.quit()
