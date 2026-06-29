const PROVIDERS = {
  openai: {
    label: 'OpenAI',
    base_url: 'https://api.openai.com/v1',
    models: ['gpt-4o-mini', 'gpt-4o', 'gpt-4.1-mini', 'gpt-4.1', 'o4-mini', 'o3-mini', 'o3'],
    default_model: 'gpt-4o-mini',
  },
  anthropic: {
    label: 'Claude / Anthropic',
    base_url: 'https://api.anthropic.com/v1',
    models: [
      'claude-opus-4-8',
      'claude-sonnet-4-6',
      'claude-haiku-4-5-20251001',
      'claude-3-5-sonnet-latest',
      'claude-3-5-haiku-latest',
      'claude-3-opus-latest',
    ],
    default_model: 'claude-sonnet-4-6',
  },
  qwen: {
    label: 'Qwen / DashScope',
    base_url: 'https://dashscope.aliyuncs.com/compatible-mode/v1',
    models: ['qwen-plus', 'qwen-max', 'qwen-turbo', 'qwen3-235b-a22b', 'qwen3-30b-a3b', 'qwen-long'],
    default_model: 'qwen-plus',
  },
  deepseek: {
    label: 'DeepSeek',
    base_url: 'https://api.deepseek.com/v1',
    models: ['deepseek-v4-pro', 'deepseek-v4-flash', 'deepseek-chat', 'deepseek-reasoner'],
    default_model: 'deepseek-v4-pro',
  },
  kimi: {
    label: 'Kimi / Moonshot AI',
    base_url: 'https://api.moonshot.cn/v1',
    models: [
      'kimi-k2-0711-preview',
      'kimi-k2-6-preview',
      'moonshot-v1-128k',
      'moonshot-v1-32k',
      'moonshot-v1-8k',
    ],
    default_model: 'kimi-k2-0711-preview',
  },
  glm: {
    label: 'GLM / Zhipu AI',
    base_url: 'https://open.bigmodel.cn/api/paas/v4',
    models: ['glm-4-plus', 'glm-4-air', 'glm-4-flash', 'glm-z1-plus', 'glm-z1-air', 'glm-z1-flash'],
    default_model: 'glm-4-plus',
  },
  minimax: {
    label: 'MiniMax',
    base_url: 'https://api.minimaxi.chat/v1',
    models: ['minimax-m3', 'minimax-m2.7'],
    default_model: 'minimax-m3',
  },
  nvidia: {
    label: 'NVIDIA NIM (Nemotron)',
    base_url: 'https://integrate.api.nvidia.com/v1',
    models: [
      'nvidia/nemotron-4-340b-instruct',
      'nvidia/llama-3.1-nemotron-70b-instruct',
      'nvidia/llama-3.1-nemotron-nano-8b-v1',
      'nvidia/nemotron-mini-4b-instruct',
    ],
    default_model: 'nvidia/nemotron-4-340b-instruct',
  },
  gemini: {
    label: 'Google Gemini',
    base_url: 'https://generativelanguage.googleapis.com/v1beta/openai/',
    models: [
      'gemini-3.5-flash',
      'gemini-3.1-pro',
      'gemini-2.5-pro',
      'gemini-2.5-flash',
      'gemini-2.5-flash-lite',
    ],
    default_model: 'gemini-2.5-flash',
  },
  mistral: {
    label: 'Mistral AI',
    base_url: 'https://api.mistral.ai/v1',
    models: [
      'mistral-large-latest',
      'mistral-small-latest',
      'mistral-nemo',
      'open-mixtral-8x22b',
      'open-mixtral-8x7b',
      'codestral-latest',
    ],
    default_model: 'mistral-large-latest',
  },
}

export default PROVIDERS
