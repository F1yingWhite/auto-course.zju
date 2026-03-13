import shutil
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


def get_latest_files(download_path: str):
    """
    获取下载目录中的所有文件。
    """
    path = Path(download_path).expanduser()
    return [str(f) for f in path.iterdir() if f.is_file()]
