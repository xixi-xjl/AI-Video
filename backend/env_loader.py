"""从项目根目录加载 .env（与 README.md 同级）"""

from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = PROJECT_ROOT / ".env"


def load_project_env() -> Path:
    """加载根目录 .env，返回实际使用的路径。"""
    if ENV_FILE.exists():
        load_dotenv(ENV_FILE)
        return ENV_FILE
    load_dotenv()
    return ENV_FILE
