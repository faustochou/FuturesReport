"""
配置管理
统一从项目根目录的 .env 文件加载配置
"""

import os
from dotenv import load_dotenv

# 加载项目根目录的 .env 文件
# 路径: FuturesReport/.env (相对于 backend/app/config.py)
project_root_env = os.path.join(os.path.dirname(__file__), '../../.env')

if os.path.exists(project_root_env):
    load_dotenv(project_root_env, override=True)
else:
    # 如果根目录没有 .env，尝试加载环境变量（用于生产环境）
    load_dotenv(override=True)


class Config:
    """Flask配置类"""
    
    # Flask配置
    SECRET_KEY = os.environ.get('SECRET_KEY', 'futuresreport-secret-key')
    DEBUG = os.environ.get('FLASK_DEBUG', 'True').lower() == 'true'
    
    # JSON配置 - 禁用ASCII转义，让中文直接显示（而不是 \uXXXX 格式）
    JSON_AS_ASCII = False
    
    # LLM配置（统一使用OpenAI格式）
    LLM_PROVIDER = os.environ.get('LLM_PROVIDER', 'openai')
    LLM_API_KEY = os.environ.get('LLM_API_KEY')
    LLM_BASE_URL = os.environ.get('LLM_BASE_URL', 'https://api.openai.com/v1')
    LLM_MODEL_NAME = os.environ.get('LLM_MODEL_NAME', 'gpt-4o-mini')

    # Report Agent 专用 LLM 配置（可选）
    # 未设置时回退到上方通用 LLM_* 配置，用于将报告生成与模拟的 LLM 配额分开，减轻限流压力
    REPORT_LLM_API_KEY = os.environ.get('REPORT_LLM_API_KEY') or LLM_API_KEY
    REPORT_LLM_BASE_URL = os.environ.get('REPORT_LLM_BASE_URL') or LLM_BASE_URL
    REPORT_LLM_MODEL_NAME = os.environ.get('REPORT_LLM_MODEL_NAME') or LLM_MODEL_NAME
    
    # Zep配置
    ZEP_API_KEY = os.environ.get('ZEP_API_KEY')
    
    # 数据库配置
    # Production:  DATABASE_URL=postgresql://user:pass@host:5432/dbname
    # Development: leave empty → SQLite under USER_DATA_DIR
    DATABASE_URL = os.environ.get('DATABASE_URL', '')

    # 文件上传配置
    MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # 50MB
    UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), '../uploads')
    DATA_FOLDER = os.environ.get('USER_DATA_DIR', UPLOAD_FOLDER)
    # Kept for the JSON→DB migration script; no longer the primary user store
    USER_DATA_FILE = os.environ.get(
        'USER_DATA_FILE',
        os.path.join(DATA_FOLDER, 'users.json')
    )
    LEGACY_USER_DATA_FILE = os.path.join(UPLOAD_FOLDER, 'users.json')
    ALLOWED_EXTENSIONS = {'pdf', 'md', 'txt', 'markdown'}
    
    # 文本处理配置
    DEFAULT_CHUNK_SIZE = 500  # 默认切块大小
    DEFAULT_CHUNK_OVERLAP = 50  # 默认重叠大小
    
    # OASIS模拟配置
    OASIS_DEFAULT_MAX_ROUNDS = int(os.environ.get('OASIS_DEFAULT_MAX_ROUNDS', '10'))
    OASIS_SIMULATION_DATA_DIR = os.path.join(os.path.dirname(__file__), '../uploads/simulations')
    
    # OASIS平台可用动作配置
    OASIS_TWITTER_ACTIONS = [
        'CREATE_POST', 'LIKE_POST', 'REPOST', 'FOLLOW', 'DO_NOTHING', 'QUOTE_POST'
    ]
    OASIS_REDDIT_ACTIONS = [
        'LIKE_POST', 'DISLIKE_POST', 'CREATE_POST', 'CREATE_COMMENT',
        'LIKE_COMMENT', 'DISLIKE_COMMENT', 'SEARCH_POSTS', 'SEARCH_USER',
        'TREND', 'REFRESH', 'DO_NOTHING', 'FOLLOW', 'MUTE'
    ]
    
    # Report Agent配置
    REPORT_AGENT_MAX_TOOL_CALLS = int(os.environ.get('REPORT_AGENT_MAX_TOOL_CALLS', '5'))
    REPORT_AGENT_MAX_REFLECTION_ROUNDS = int(os.environ.get('REPORT_AGENT_MAX_REFLECTION_ROUNDS', '2'))
    REPORT_AGENT_TEMPERATURE = float(os.environ.get('REPORT_AGENT_TEMPERATURE', '0.5'))
    
    # 低资源环境下的模拟保护配置 (K3s 2vCPU/4GB 友好)
    SIM_MAX_AGENTS = int(os.environ.get('SIM_MAX_AGENTS', '120'))
    SIM_MAX_ROUNDS = int(os.environ.get('SIM_MAX_ROUNDS', '30'))
    LLM_CONCURRENCY_LIMIT = int(os.environ.get('LLM_CONCURRENCY_LIMIT', '8'))  # 降低并发防OOM
    SIM_CHECKPOINT_INTERVAL = int(os.environ.get('SIM_CHECKPOINT_INTERVAL', '5'))  # 每N轮保存checkpoint
    SIM_WARN_AGENTS = int(os.environ.get('SIM_WARN_AGENTS', '80'))  # 超过此数前端提示高资源
    SIM_WARN_ROUNDS = int(os.environ.get('SIM_WARN_ROUNDS', '20'))
    
    @classmethod
    def validate(cls) -> list[str]:
        """验证必要配置"""
        errors: list[str] = []
        if not cls.ZEP_API_KEY:
            errors.append("ZEP_API_KEY 未配置")
        return errors

