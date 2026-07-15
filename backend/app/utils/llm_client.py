"""
LLM客户端封装
统一使用OpenAI格式调用
"""

import json
import os
import random
import re
import time
import urllib.error
import urllib.request
from typing import Optional, Dict, Any, List
from openai import OpenAI, NotFoundError, APIStatusError

from ..config import Config
from .logger import get_logger

logger = get_logger('futuresreport.llm_client')

# 429 错误 body 中 Gemini RetryInfo 的 retryDelay 字段，形如 "40s"
_RETRY_DELAY_PATTERN = re.compile(r'"retryDelay"\s*:\s*"(\d+(?:\.\d+)?)s"')
# 429 错误 body 中标识每日配额耗尽的 quotaId，形如 "GenerateContentPerDayPerProjectPerModel..."
_PER_DAY_QUOTA_PATTERN = re.compile(r'"quotaId"\s*:\s*"[^"]*PerDay[^"]*"')

# Providers whose APIs accept OpenAI-style response_format JSON mode.
# Providers not listed here (e.g. nvidia) may reject the parameter,
# so we skip it and rely on prompt instructions + post-processing instead.
_JSON_MODE_PROVIDERS = frozenset({
    "openai", "qwen", "deepseek", "kimi", "glm", "minimax", "mistral", "gemini",
})


class LLMClient:
    """LLM客户端"""
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        provider: Optional[str] = None
    ):
        self.provider = (provider or Config.LLM_PROVIDER or "openai").lower()
        self.api_key = api_key or Config.LLM_API_KEY
        self.base_url = base_url or Config.LLM_BASE_URL
        self.model = model or Config.LLM_MODEL_NAME
        
        if not self.api_key:
            raise ValueError("LLM_API_KEY 未配置")
        
        self.client = None
        if self.provider != "anthropic":
            self.client = OpenAI(
                api_key=self.api_key,
                base_url=self.base_url
            )
    
    def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 4096,
        response_format: Optional[Dict] = None
    ) -> str:
        """
        发送聊天请求
        
        Args:
            messages: 消息列表
            temperature: 温度参数
            max_tokens: 最大token数
            response_format: 响应格式（如JSON模式）
            
        Returns:
            模型响应文本
        """
        if self.provider == "anthropic":
            content = self._chat_anthropic(
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens
            )
            return re.sub(r'<think>[\s\S]*?</think>', '', content).strip()

        kwargs = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        
        if response_format:
            kwargs["response_format"] = response_format

        max_retries = int(os.environ.get('LLM_MAX_RETRIES', '5'))
        base_delay = float(os.environ.get('LLM_RETRY_BASE_DELAY', '5'))

        attempt = 0
        while True:
            try:
                response = self.client.chat.completions.create(**kwargs)
                break
            except NotFoundError as exc:
                raise ValueError(
                    f"模型 '{self.model}' 在 {self.provider} 上找不到。"
                    f"請至 AI Studio 確認可用模型，或在設定中更換模型名稱。"
                    f"（原始錯誤：{exc}）"
                ) from exc
            except APIStatusError as exc:
                if exc.status_code != 429:
                    raise

                self._raise_if_daily_quota_exhausted(exc)

                attempt += 1
                if attempt > max_retries:
                    raise

                delay = self._compute_retry_delay(exc, attempt, base_delay)
                logger.warning(
                    f"LLM 請求觸發速率限制 (429)，第 {attempt}/{max_retries} 次重試，"
                    f"等待 {delay:.1f} 秒後繼續..."
                )
                time.sleep(delay)

        content = response.choices[0].message.content
        # 部分模型（如MiniMax M2.5）会在content中包含<think>思考内容，需要移除
        content = re.sub(r'<think>[\s\S]*?</think>', '', content).strip()
        return content

    @staticmethod
    def _error_body_text(exc: APIStatusError) -> str:
        """将异常的 body（可能是 dict/list/str/None）统一转成可正则匹配的文本"""
        body = getattr(exc, 'body', None)
        if isinstance(body, (dict, list)):
            return json.dumps(body, ensure_ascii=False)
        if body is not None:
            return str(body)
        return str(exc)

    def _raise_if_daily_quota_exhausted(self, exc: APIStatusError) -> None:
        """若 429 错误是每日配额耗尽（而非短期限流），重试无意义，直接抛出明确提示"""
        text = self._error_body_text(exc)
        if _PER_DAY_QUOTA_PATTERN.search(text):
            raise RuntimeError(
                "每日免費配額已用盡，請升級方案、更換 API key，或改用其他模型。"
            ) from exc

    def _compute_retry_delay(self, exc: APIStatusError, attempt: int, base_delay: float) -> float:
        """优先使用服务端返回的 RetryInfo.retryDelay，否则使用指数退避 + jitter"""
        text = self._error_body_text(exc)
        match = _RETRY_DELAY_PATTERN.search(text)
        if match:
            return float(match.group(1)) + 2

        return base_delay * (2 ** (attempt - 1)) + random.uniform(0, 1)

    def _chat_anthropic(
        self,
        messages: List[Dict[str, str]],
        temperature: float,
        max_tokens: int
    ) -> str:
        system_parts = []
        anthropic_messages = []

        for message in messages:
            role = message.get("role", "user")
            content = message.get("content", "")
            if role == "system":
                system_parts.append(content)
            elif role == "assistant":
                anthropic_messages.append({"role": "assistant", "content": content})
            else:
                anthropic_messages.append({"role": "user", "content": content})

        payload = {
            "model": self.model,
            "messages": anthropic_messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if system_parts:
            payload["system"] = "\n\n".join(system_parts)

        endpoint = f"{self.base_url.rstrip('/')}/messages"
        request = urllib.request.Request(
            endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "content-type": "application/json",
                "anthropic-version": "2023-06-01",
                "x-api-key": self.api_key,
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                raw = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Anthropic API request failed: {exc.code} {body}") from exc

        data = json.loads(raw)
        blocks = data.get("content", [])
        return "".join(block.get("text", "") for block in blocks if block.get("type") == "text")
    
    def chat_json(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.3,
        max_tokens: int = 4096
    ) -> Dict[str, Any]:
        """
        发送聊天请求并返回JSON

        Args:
            messages: 消息列表
            temperature: 温度参数
            max_tokens: 最大token数

        Returns:
            解析后的JSON对象
        """
        use_json_mode = self.provider in _JSON_MODE_PROVIDERS
        response = self.chat(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format={"type": "json_object"} if use_json_mode else None
        )
        # 清理markdown代码块标记
        cleaned_response = response.strip()
        cleaned_response = re.sub(r'^```(?:json)?\s*\n?', '', cleaned_response, flags=re.IGNORECASE)
        cleaned_response = re.sub(r'\n?```\s*$', '', cleaned_response)
        cleaned_response = cleaned_response.strip()

        try:
            return json.loads(cleaned_response)
        except json.JSONDecodeError:
            raise ValueError(f"LLM返回的JSON格式无效: {cleaned_response}")

