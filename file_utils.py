import shutil
import time
from pathlib import Path


def clear_downloads(download_path: str):
    """
    清空指定的下载目录。
    """
    path = Path(download_path).expanduser()
    if not path.exists():
        print(f"下载目录 {path} 不存在，无需清理。")
        return

    print(f"正在清理下载目录: {path}")
    for item in path.iterdir():
        try:
            if item.is_file() or item.is_symlink():
                item.unlink()
            elif item.is_dir():
                shutil.rmtree(item)
        except Exception as e:
            print(f"清理 {item} 失败: {e}")
    print("下载目录清理完毕。")


def wait_for_downloads(download_path: str, timeout: int = 60):
    """
    等待下载目录中所有浏览器临时文件消失。
    """
    path = Path(download_path).expanduser()
    end_time = time.time() + timeout
    temp_suffixes = {".crdownload", ".part", ".download", ".tmp"}

    print("正在等待文件下载完成...")
    while time.time() < end_time:
        temp_files = [f for f in path.iterdir() if f.suffix.lower() in temp_suffixes]
        if not temp_files:
            # 额外等待一小会儿，确保文件写入完成并释放
            time.sleep(1)
            # 再次确认是否有新文件产生（有时候浏览器会先创建一个空文件再重命名）
            if not [f for f in path.iterdir() if f.suffix.lower() in temp_suffixes]:
                print("所有文件下载完成。")
                return True
        time.sleep(1)

    print(f"等待下载超时 ({timeout}s)。")
    return False


def get_latest_files(download_path: str):
    """
    获取下载目录中的所有文件。
    """
    path = Path(download_path).expanduser()
    # 过滤掉可能的临时文件
    temp_suffixes = {".crdownload", ".part", ".download", ".tmp"}
    return [str(f) for f in path.iterdir() if f.is_file() and f.suffix.lower() not in temp_suffixes]
