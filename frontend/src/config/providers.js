// Keep in sync with LLM_PROVIDER_DEFAULTS in backend/app/models/user.py
// (enforced by backend/tests/test_provider_catalog.py).
const PROVIDERS = {
  openai: {
    label: 'OpenAI',
    base_url: 'https://api.openai.com/v1',
    models: [
      'gpt-6-astra',
      'gpt-6.1-sol',
      'gpt-6.1-terra',
      'gpt-6-luna',
      'gpt-5.5',
      'gpt-5.4-mini',
    ],
    default_model: 'gpt-6-luna',
  },
  anthropic: {
    label: 'Claude / Anthropic',
    base_url: 'https://api.anthropic.com/v1',
    models: [
      'claude-fable-5-1',
      'claude-opus-5-5',
      'claude-sonnet-5-5',
      'claude-haiku-5-5',
      'claude-opus-4-8',
      'claude-sonnet-4-6',
      'claude-haiku-4-5',
    ],
    default_model: 'claude-sonnet-5-5',
  },
  qwen: {
    label: 'Qwen / DashScope',
    base_url: 'https://dashscope.aliyuncs.com/compatible-mode/v1',
    models: [
      'qwen3.8-max',
      'qwen3.7-plus',
      'qwen3.8-flash',
      'qwen-plus',
      'qwen-max',
    ],
    default_model: 'qwen3.7-plus',
  },
  deepseek: {
    label: 'DeepSeek',
    base_url: 'https://api.deepseek.com/v1',
    models: [
      'deepseek-v4-pro',
      'deepseek-flash',
    ],
    default_model: 'deepseek-v4-pro',
  },
  kimi: {
    label: 'Kimi / Moonshot AI',
    base_url: 'https://api.moonshot.cn/v1',
    models: [
      'kimi-k3.1-pro',
      'kimi-k3.1-pro-highspeed',
      'kimi-k3',
      'kimi-k2.7-code',
      'kimi-k2.6',
    ],
    default_model: 'kimi-k3.1-pro',
  },
  glm: {
    label: 'GLM / Zhipu AI',
    base_url: 'https://open.bigmodel.cn/api/paas/v4',
    models: [
      'glm-5.3',
      'glm-5.2',
      'glm-5.1',
      'glm-5',
    ],
    default_model: 'glm-5.3',
  },
  minimax: {
    label: 'MiniMax',
    base_url: 'https://api.minimax.io/v1',
    models: [
      'MiniMax-M3',
      'MiniMax-M2.7',
      'MiniMax-M2.5',
    ],
    default_model: 'MiniMax-M3',
  },
  nvidia: {
    label: 'NVIDIA NIM (Nemotron)',
    base_url: 'https://integrate.api.nvidia.com/v1',
    models: [
      'nvidia/nemotron-3-ultra-550b-a55b',
      'nvidia/nemotron-3-super-120b-a12b',
      'nvidia/nemotron-3.5-lightning-30b-a3b',
      'nvidia/nemotron-nano-3-30b-a3b',
      'nvidia/llama-3.1-nemotron-ultra-253b-v1',
    ],
    default_model: 'nvidia/nemotron-3-ultra-550b-a55b',
  },
  gemini: {
    label: 'Google Gemini',
    base_url: 'https://generativelanguage.googleapis.com/v1beta/openai/',
    models: [
      'gemini-4-argon',
      'gemini-3.8-flash',
      'gemini-3.6-flash',
      'gemini-3.5-flash-lite',
      'gemini-3.1-pro-preview',
      'gemini-3.1-flash-lite',
    ],
    default_model: 'gemini-3.8-flash',
  },
  mistral: {
    label: 'Mistral AI',
    base_url: 'https://api.mistral.ai/v1',
    models: [
      'mistral-large-latest',
      'mistral-medium-latest',
      'mistral-small-latest',
    ],
    default_model: 'mistral-large-latest',
  },
}

export default PROVIDERS
