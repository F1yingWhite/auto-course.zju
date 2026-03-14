import os
import shutil
import subprocess
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

    def _convert_to_pdf_libreoffice(self, file_path: Path) -> Path | None:
        """
        使用 LibreOffice (soffice --headless) 将文件转换为 PDF。
        """
        libreoffice_paths = [
            "/Applications/LibreOffice.app/Contents/MacOS/soffice",
            "/usr/local/bin/soffice",
            "soffice",
        ]

        soffice_bin = None
        for p in libreoffice_paths:
            if shutil.which(p) or os.path.exists(p):
                soffice_bin = p
                break

        if not soffice_bin:
            print("未找到 LibreOffice (soffice)，请确保已安装并加入 PATH。")
            return None

        output_dir = file_path.parent
        pdf_path = file_path.with_suffix(".pdf")

        try:
            print(f"调用 LibreOffice 转换 {file_path.name}...")
            # --headless: 无界面运行
            # --convert-to pdf: 目标格式
            # --outdir: 输出目录
            cmd = [
                soffice_bin,
                "--headless",
                "--convert-to",
                "pdf",
                "--outdir",
                str(output_dir),
                str(file_path),
            ]

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)

            if result.returncode == 0 and pdf_path.exists():
                return pdf_path
            else:
                print(f"LibreOffice 转换失败 (退出码 {result.returncode}): {result.stderr}")
                return None
        except Exception as e:
            print(f"执行 LibreOffice 转换时发生异常: {e}")
            return None

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

                pdf_path = self._convert_to_pdf_libreoffice(file_path)

                if pdf_path and pdf_path.exists():
                    print(f"转换成功: {pdf_path.name}")
                    # 转换成功后删除原始 docx
                    if file_path.exists():
                        os.remove(file_path)
                        print(f"已删除原始文件: {file_path.name}")
                    processed_file_paths.append(str(pdf_path))
                else:
                    print(f"警告: 转换失败，将继续尝试处理原文件 {file_path.name}。")
                    processed_file_paths.append(path)
            else:
                processed_file_paths.append(path)

        # 使用处理后的路径列表
        file_paths = processed_file_paths

        # 检查本地实验文档是否存在并加入待分析列表
        assignment_ref = "./实验1 AI认识初步和DeepSeek大模型部署应用.pdf"
        if os.path.exists(assignment_ref):
            file_paths.append(assignment_ref)

        prompt = '请你根据文件`实验1 AI认识初步和DeepSeek大模型部署应用.pdf`对学生的作业进行打分，不需要关注视频长度，因为上传给你看可能会出现问题，输出格式为json:\n{\n  "分数": int,  # 0-100分\n  "评语": "str"  # 针对作业的具体反馈\n}\n\n请根据以下文件内容进行评分：'

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
                else:
                    # 处理文本文件，尝试多种编码
                    content = None
                    for encoding in ["utf-8", "gbk", "gb18030", "latin-1"]:
                        try:
                            with open(path, "r", encoding=encoding) as f:
                                content = f.read()
                                break
                        except Exception:
                            continue

                    if content is not None:
                        contents.append(f"\n文件 {file_path.name} 的内容:\n{content}")
                    else:
                        print(f"无法以任何已知编码读取文件 {file_path.name}")
                        contents.append(f"\n[无法读取文件 {file_path.name}]")

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
