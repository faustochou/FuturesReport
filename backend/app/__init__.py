"""
Futures Report Backend - Flask应用工厂
"""

import os
import warnings

# 抑制 multiprocessing resource_tracker 的警告（来自第三方库如 transformers）
# 需要在所有其他导入之前设置
warnings.filterwarnings("ignore", message=".*resource_tracker.*")

from flask import Flask, request
from flask_cors import CORS

from .config import Config
from .utils.logger import setup_logger, get_logger


def _init_database(logger) -> None:
    """Initialise the database engine and seed reference data.

    Schema management strategy
    --------------------------
    Production (Zeabur + PostgreSQL):
        Alembic migrations run BEFORE this function is called — via the
        Dockerfile CMD (`alembic upgrade head && npm run dev`).
        create_tables() is a no-op here because all tables already exist.

    Local development (SQLite fallback, no Dockerfile):
        Alembic is NOT run automatically.  create_tables() acts as a safety
        net: it creates any missing tables so the app can start without a
        manual `alembic upgrade head`.
    """
    from .db.database import init_engine, create_tables, seed_subscription_tiers
    init_engine()
    create_tables()          # no-op when alembic already ran; safety net for local dev
    seed_subscription_tiers()
    logger.info("数据库初始化完成")


def create_app(config_class=Config):
    """Flask应用工厂函数"""
    app = Flask(__name__)
    app.config.from_object(config_class)

    # 设置JSON编码：确保中文直接显示（而不是 \uXXXX 格式）
    # Flask >= 2.3 使用 app.json.ensure_ascii，旧版本使用 JSON_AS_ASCII 配置
    if hasattr(app, 'json') and hasattr(app.json, 'ensure_ascii'):
        app.json.ensure_ascii = False

    # 设置日志
    logger = setup_logger('futuresreport')
    
    # 只在 reloader 子进程中打印启动信息（避免 debug 模式下打印两次）
    is_reloader_process = os.environ.get('WERKZEUG_RUN_MAIN') == 'true'
    debug_mode = app.config.get('DEBUG', False)
    should_log_startup = not debug_mode or is_reloader_process
    
    if should_log_startup:
        logger.info("=" * 50)
        logger.info("Futures Report Backend 启动中...")
        logger.info("=" * 50)

    # 初始化数据库（建表 / 检查连接）—— 无条件执行，create_all() 是幂等的
    _init_database(logger)

    # 启用CORS
    CORS(app, resources={r"/api/*": {"origins": "*"}})
    
    # 注册模拟进程清理函数（确保服务器关闭时终止所有模拟进程）
    from .services.simulation_runner import SimulationRunner
    SimulationRunner.register_cleanup()
    if should_log_startup:
        logger.info("已注册模拟进程清理函数")
    
    # 请求日志中间件
    @app.before_request
    def log_request():
        logger = get_logger('futuresreport.request')
        logger.debug(f"请求: {request.method} {request.path}")
        if request.content_type and 'json' in request.content_type:
            logger.debug(f"请求体: {request.get_json(silent=True)}")
    
    @app.after_request
    def log_response(response):
        logger = get_logger('futuresreport.request')
        logger.debug(f"响应: {response.status_code}")
        return response
    
    # 注册蓝图
    from .api import graph_bp, simulation_bp, report_bp, auth_bp, admin_bp, subscription_bp
    app.register_blueprint(auth_bp, url_prefix='/api/auth')
    app.register_blueprint(admin_bp, url_prefix='/api/admin')
    app.register_blueprint(subscription_bp, url_prefix='/api/subscription')
    app.register_blueprint(graph_bp, url_prefix='/api/graph')
    app.register_blueprint(simulation_bp, url_prefix='/api/simulation')
    app.register_blueprint(report_bp, url_prefix='/api/report')
    
    # 健康检查 (K8s / Zeabur 探针友好 + 资源报告)
    @app.route('/health')
    def health():
        from datetime import datetime
        data = {
            'status': 'ok',
            'service': 'Futures Report Backend',
            'time': datetime.now().isoformat(),
        }
        try:
            import psutil
            vm = psutil.virtual_memory()
            data['memory'] = {
                'total_mb': round(vm.total / 1024 / 1024, 1),
                'available_mb': round(vm.available / 1024 / 1024, 1),
                'percent': vm.percent,
            }
            data['cpu_percent'] = psutil.cpu_percent(interval=0.1)
        except Exception:
            data['memory'] = {'note': 'psutil not available'}
        return data
    
    if should_log_startup:
        logger.info("Futures Report Backend 启动完成")
    
    return app

