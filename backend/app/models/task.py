"""
任务状态管理
用于跟踪长时间运行的任务（如图谱构建）
"""

import uuid
import threading
import os
import json
import shutil
from datetime import datetime
from enum import Enum
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field

from ..config import Config
from ..utils.locale import t


class TaskStatus(str, Enum):
    """任务状态枚举"""
    PENDING = "pending"          # 等待中
    PROCESSING = "processing"    # 处理中
    COMPLETED = "completed"      # 已完成
    FAILED = "failed"            # 失败


@dataclass
class Task:
    """任务数据类"""
    task_id: str
    task_type: str
    status: TaskStatus
    created_at: datetime
    updated_at: datetime
    progress: int = 0              # 总进度百分比 0-100
    message: str = ""              # 状态消息
    result: Optional[Dict] = None  # 任务结果
    error: Optional[str] = None    # 错误信息
    metadata: Dict = field(default_factory=dict)  # 额外元数据
    progress_detail: Dict = field(default_factory=dict)  # 详细进度信息
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "task_id": self.task_id,
            "task_type": self.task_type,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "progress": self.progress,
            "message": self.message,
            "progress_detail": self.progress_detail,
            "result": self.result,
            "error": self.error,
            "metadata": self.metadata,
        }


class TaskManager:
    """
    任务管理器
    线程安全的任务状态管理 + 文件持久化（支持重启恢复、K8s友好）
    """
    
    _instance = None
    _lock = threading.Lock()
    
    # 持久化目录 (与 projects 类似，使用 uploads)
    TASKS_DIR = os.path.join(Config.UPLOAD_FOLDER, 'tasks')
    
    def __new__(cls):
        """单例模式"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._tasks: Dict[str, Task] = {}
                    cls._instance._task_lock = threading.Lock()
                    cls._instance._ensure_tasks_dir()
                    cls._instance._load_all_tasks()
        return cls._instance
    
    @classmethod
    def _ensure_tasks_dir(cls):
        os.makedirs(cls.TASKS_DIR, exist_ok=True)
    
    @classmethod
    def _get_task_path(cls, task_id: str) -> str:
        return os.path.join(cls.TASKS_DIR, f"{task_id}.json")
    
    def _save_task_to_disk(self, task: Task):
        """将单个任务持久化到JSON"""
        try:
            self._ensure_tasks_dir()
            path = self._get_task_path(task.task_id)
            data = task.to_dict()
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception:
            # 持久化失败不阻断（低资源下磁盘问题不致命）
            pass
    
    def _load_task_from_disk(self, task_id: str) -> Optional[Task]:
        path = self._get_task_path(task_id)
        if not os.path.exists(path):
            return None
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            # 重建 Task
            created = datetime.fromisoformat(data['created_at'])
            updated = datetime.fromisoformat(data['updated_at'])
            task = Task(
                task_id=data['task_id'],
                task_type=data['task_type'],
                status=TaskStatus(data['status']),
                created_at=created,
                updated_at=updated,
                progress=data.get('progress', 0),
                message=data.get('message', ''),
                result=data.get('result'),
                error=data.get('error'),
                metadata=data.get('metadata', {}),
                progress_detail=data.get('progress_detail', {}),
            )
            return task
        except Exception:
            return None
    
    def _load_all_tasks(self):
        """启动时从磁盘恢复任务状态"""
        self._ensure_tasks_dir()
        try:
            for fname in os.listdir(self.TASKS_DIR):
                if fname.endswith('.json'):
                    tid = fname[:-5]
                    task = self._load_task_from_disk(tid)
                    if task:
                        self._tasks[tid] = task
        except Exception:
            pass
    
    def create_task(self, task_type: str, metadata: Optional[Dict] = None) -> str:
        """
        创建新任务
        
        Args:
            task_type: 任务类型
            metadata: 额外元数据
            
        Returns:
            任务ID
        """
        task_id = str(uuid.uuid4())
        now = datetime.now()
        
        task = Task(
            task_id=task_id,
            task_type=task_type,
            status=TaskStatus.PENDING,
            created_at=now,
            updated_at=now,
            metadata=metadata or {}
        )
        
        with self._task_lock:
            self._tasks[task_id] = task
        
        self._save_task_to_disk(task)
        return task_id
    
    def get_task(self, task_id: str) -> Optional[Task]:
        """获取任务"""
        with self._task_lock:
            return self._tasks.get(task_id)
    
    def update_task(
        self,
        task_id: str,
        status: Optional[TaskStatus] = None,
        progress: Optional[int] = None,
        message: Optional[str] = None,
        result: Optional[Dict] = None,
        error: Optional[str] = None,
        progress_detail: Optional[Dict] = None
    ):
        """
        更新任务状态
        
        Args:
            task_id: 任务ID
            status: 新状态
            progress: 进度
            message: 消息
            result: 结果
            error: 错误信息
            progress_detail: 详细进度信息
        """
        with self._task_lock:
            task = self._tasks.get(task_id)
            if task:
                task.updated_at = datetime.now()
                if status is not None:
                    task.status = status
                if progress is not None:
                    task.progress = progress
                if message is not None:
                    task.message = message
                if result is not None:
                    task.result = result
                if error is not None:
                    task.error = error
                if progress_detail is not None:
                    task.progress_detail = progress_detail
                self._save_task_to_disk(task)
    
    def complete_task(self, task_id: str, result: Dict):
        """标记任务完成"""
        self.update_task(
            task_id,
            status=TaskStatus.COMPLETED,
            progress=100,
            message=t('progress.taskComplete'),
            result=result
        )
    
    def fail_task(self, task_id: str, error: str):
        """标记任务失败"""
        self.update_task(
            task_id,
            status=TaskStatus.FAILED,
            message=t('progress.taskFailed'),
            error=error
        )
    
    def list_tasks(self, task_type: Optional[str] = None) -> list:
        """列出任务"""
        with self._task_lock:
            tasks = list(self._tasks.values())
            if task_type:
                tasks = [t for t in tasks if t.task_type == task_type]
            return [t.to_dict() for t in sorted(tasks, key=lambda x: x.created_at, reverse=True)]
    
    def cleanup_old_tasks(self, max_age_hours: int = 24):
        """清理旧任务（内存+磁盘）"""
        from datetime import timedelta
        cutoff = datetime.now() - timedelta(hours=max_age_hours)
        
        with self._task_lock:
            old_ids = [
                tid for tid, task in self._tasks.items()
                if task.created_at < cutoff and task.status in [TaskStatus.COMPLETED, TaskStatus.FAILED]
            ]
            for tid in old_ids:
                del self._tasks[tid]
                try:
                    p = self._get_task_path(tid)
                    if os.path.exists(p):
                        os.remove(p)
                except Exception:
                    pass

