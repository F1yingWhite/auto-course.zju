import os
import shutil
import tempfile
import time
import traceback
from pathlib import Path

from google import genai


class LLMManager:
    def __init__(self, api_key: str, model_name: str = "gemini-3-flash-preview"):
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

        # 预处理：将 .docx/.doc 转换为 .pdf 并删除原文件
        processed_file_paths = []
        for path in file_paths:
            file_path = Path(path)
            if file_path.suffix.lower() in [".docx", ".doc"]:
                print(f"检测到 {file_path.name}，正在将其转换为 PDF 以保留格式和图片...")
                try:
                    from docx2pdf import convert
                    # 生成 PDF 路径：同名但后缀为 .pdf
                    pdf_path = file_path.with_suffix(".pdf")
                    # docx2pdf.convert(input, output)
                    # 注意：在 macOS 上，这会打开 Word 窗口
                    convert(str(file_path), str(pdf_path))
                    
                    if pdf_path.exists():
                        print(f"转换成功: {pdf_path.name}")
                        # 转换成功后删除原始 docx
                        if file_path.exists():
                            os.remove(file_path)
                            print(f"已删除原始文件: {file_path.name}")
                        processed_file_paths.append(str(pdf_path))
                    else:
                        print(f"警告: 转换后未找到 PDF 文件 {pdf_path.name}，将继续尝试处理原文件。")
                        processed_file_paths.append(path)
                except Exception as e:
                    print(f"转换 {file_path.name} 失败 (请确保已安装 Word 并授权): {e}")
                    processed_file_paths.append(path)
            else:
                processed_file_paths.append(path)
        
        # 使用处理后的路径列表
        file_paths = processed_file_paths

        # 检查本地实验文档是否存在并加入待分析列表
        assignment_ref = "./实验1 AI认识初步和DeepSeek大模型部署应用.pdf"
        if os.path.exists(assignment_ref):
            file_paths.append(assignment_ref)

        prompt = '请你根据文件`实验1 AI认识初步和DeepSeek大模型部署应用.pdf`对学生的作业进行打分，输出格式为json:\n{\n  "分数": int,  # 0-100分\n  "评语": "str"  # 针对作业的具体反馈\n}\n\n请根据以下文件内容进行评分：'

        # 准备内容列表
        contents = [prompt]
        temp_dir = tempfile.mkdtemp()

        try:
            for i, path in enumerate(file_paths):
                file_path = Path(path)
                suffix = file_path.suffix.lower()

                # 处理多媒体文件和 Office 文档
                if suffix in [
                    ".png",
                    ".jpg",
                    ".jpeg",
                    ".webp",
                    ".pdf",
                    ".mp4",
                    ".docx",
                    ".doc",
                    ".pptx",
                    ".ppt",
                    ".xlsx",
                    ".xls",
                ]:
                    # 为避免文件名包含非 ASCII 字符导致的编码错误，创建一个临时 ASCII 文件名的副本
                    temp_file_path = Path(temp_dir) / f"upload_{i}{suffix}"
                    shutil.copy2(file_path, temp_file_path)

                    print(f"正在上传文件到 Gemini: {file_path.name}")
                    try:
                        # 使用 display_name 保持原始文件名，但上传时使用临时 ASCII 路径避开编码问题
                        uploaded_file = self.client.files.upload(
                            file=str(temp_file_path), config={"display_name": file_path.name}
                        )

                        # 等待文件进入 ACTIVE 状态
                        print(f"等待文件 {file_path.name} 处理中...")
                        start_wait = time.time()
                        while uploaded_file.state != "ACTIVE":
                            if uploaded_file.state == "FAILED":
                                raise Exception(f"文件 {file_path.name} 处理失败 (FAILED 状态)")

                            if time.time() - start_wait > 60:  # 1分钟超时
                                raise Exception(f"等待文件 {file_path.name} 处理超时")

                            time.sleep(2)
                            uploaded_file = self.client.files.get(name=uploaded_file.name)

                        print(f"文件 {file_path.name} 已就绪 (ACTIVE)")
                        contents.append(uploaded_file)
                    except Exception as e:
                        print(f"上传或处理文件 {file_path.name} 失败: {e}")
                        # 如果上传失败，尝试以文本描述形式添加（虽然对于视频/PDF可能没用）
                        contents.append(f"\n[文件 {file_path.name} 上传或处理失败，无法分析该附件: {e}]")

            print(f"正在调用 {self.model_name} 进行打分...")
            response = self.client.models.generate_content(model=self.model_name, contents=contents)

            return response.text
        except Exception as e:
            err_msg = f"调用 Gemini 时发生错误: {e}\n{traceback.format_exc()}"
            print(err_msg)
            return f"调用 Gemini 时发生错误: {e}"
        finally:
            # 清理临时目录
            shutil.rmtree(temp_dir, ignore_errors=True)
