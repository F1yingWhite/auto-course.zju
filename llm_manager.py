import os
from pathlib import Path

from google import genai


class LLMManager:
    def __init__(self, api_key: str, model_name: str = "gemini-1.5-flash"):
        # 临时记录原始代理（如果有的话）
        old_http_proxy = os.environ.get("HTTP_PROXY")
        old_https_proxy = os.environ.get("HTTPS_PROXY")

        try:
            # 仅在初始化客户端时设置代理
            os.environ["HTTP_PROXY"] = "http://127.0.0.1:7890"
            os.environ["HTTPS_PROXY"] = "http://127.0.0.1:7890"

            # 初始化客户端，它会读取当前的环境变量
            self.client = genai.Client(api_key=api_key)
            self.model_name = model_name
            print("LLM 客户端已初始化，代理设置为 127.0.0.1:7890")

        finally:
            # 初始化完成后，立即恢复/清除环境变量，以免影响浏览器
            if old_http_proxy:
                os.environ["HTTP_PROXY"] = old_http_proxy
            else:
                os.environ.pop("HTTP_PROXY", None)

            if old_https_proxy:
                os.environ["HTTPS_PROXY"] = old_https_proxy
            else:
                os.environ.pop("HTTPS_PROXY", None)

    def grade_assignment(self, file_paths: list[str]):
        """
        调用 Gemini 对作业进行打分。
        """
        if not file_paths:
            print("没有找到作业文件，无法评分。")
            return

        # 构造提示词
        prompt = "你是一名助教。请对以下附件中的学生作业进行批改和打分。请给出具体的评分理由和最终分数（百分制）。"

        # 准备内容列表
        contents = [prompt]

        try:
            for path in file_paths:
                file_path = Path(path)
                suffix = file_path.suffix.lower()

                # 处理多媒体文件
                if suffix in [".png", ".jpg", ".jpeg", ".webp", ".pdf", ".mp4"]:
                    print(f"正在上传文件到 Gemini: {path}")
                    uploaded_file = self.client.files.upload(path=str(file_path))
                    contents.append(uploaded_file)
                else:
                    # 处理文本文件
                    try:
                        with open(path, "r", encoding="utf-8") as f:
                            contents.append(f"\n文件 {file_path.name} 的内容:\n{f.read()}")
                    except Exception as e:
                        print(f"无法读取文件 {file_path.name}: {e}")

            print(f"正在调用 {self.model_name} 进行打分...")
            response = self.client.models.generate_content(model=self.model_name, contents=contents)

            return response.text
        except Exception as e:
            return f"调用 Gemini 时发生错误: {e}"
