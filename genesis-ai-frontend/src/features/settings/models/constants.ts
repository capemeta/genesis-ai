import baiduCloudLogo from '@/assets/provider-logos/baidu-cloud.svg'
import anthropicLogo from '@/assets/provider-logos/anthropic.png'
import dashscopeLogo from '@/assets/provider-logos/dashscope.png'
import deepseekLogo from '@/assets/provider-logos/deepseek.png'
import doubaoLogo from '@/assets/provider-logos/doubao.png'
import fireworksLogo from '@/assets/provider-logos/fireworks.png'
import geminiLogo from '@/assets/provider-logos/gemini.png'
import grokLogo from '@/assets/provider-logos/grok.png'
import groqLogo from '@/assets/provider-logos/groq.png'
import lmStudioLogo from '@/assets/provider-logos/lmstudio.png'
import localAiLogo from '@/assets/provider-logos/localai.svg'
import minimaxLogo from '@/assets/provider-logos/minimax.png'
import moonshotLogo from '@/assets/provider-logos/moonshot.webp'
import newApiLogo from '@/assets/provider-logos/newapi.png'
import nvidiaLogo from '@/assets/provider-logos/nvidia.png'
import ollamaLogo from '@/assets/provider-logos/ollama.png'
import openAiLogo from '@/assets/provider-logos/openai.png'
import openRouterLogo from '@/assets/provider-logos/openrouter.png'
import ppioLogo from '@/assets/provider-logos/ppio.png'
import siliconLogo from '@/assets/provider-logos/silicon.png'
import togetherLogo from '@/assets/provider-logos/together.png'
import zhipuLogo from '@/assets/provider-logos/zhipu.png'
import { AudioLines, Bot, BrainCircuit, Eye, Image, Layers3, Mic, Video } from 'lucide-react'
import type { CapabilityType } from '@/lib/api/model-platform'
import type { ManualModelForm, ProviderDraft, ProviderEndpointType, CustomProviderForm } from './types'

export type CustomProviderProtocolType = CustomProviderForm['protocolType']

export const hiddenProviderCodes = new Set(['mineru'])

export const providerCapabilityFilterOptions: Array<{ value: 'all' | CapabilityType; label: string }> = [
  { value: 'all', label: 'All' },
  { value: 'chat', label: 'LLM' },
  { value: 'embedding', label: 'Embedding' },
  { value: 'rerank', label: 'Rerank' },
  { value: 'tts', label: 'TTS' },
  { value: 'asr', label: 'ASR' },
  { value: 'vision', label: '视觉理解' },
  { value: 'ocr', label: 'OCR' },
  { value: 'document_parse', label: 'Parse' },
]

export const capabilityMeta: Record<CapabilityType, { label: string; icon: typeof Bot; tone: string }> = {
  chat: { label: 'LLM 对话', icon: Bot, tone: 'bg-sky-500/12 text-sky-700 border-sky-500/20' },
  vision: { label: '视觉理解 / VLM', icon: Eye, tone: 'bg-fuchsia-500/12 text-fuchsia-700 border-fuchsia-500/20' },
  embedding: { label: '向量嵌入', icon: BrainCircuit, tone: 'bg-emerald-500/12 text-emerald-700 border-emerald-500/20' },
  rerank: { label: '重排序', icon: Layers3, tone: 'bg-amber-500/12 text-amber-700 border-amber-500/20' },
  asr: { label: '语音识别', icon: Mic, tone: 'bg-orange-500/12 text-orange-700 border-orange-500/20' },
  tts: { label: '语音播报', icon: AudioLines, tone: 'bg-violet-500/12 text-violet-700 border-violet-500/20' },
  image: { label: '文生图', icon: Image, tone: 'bg-rose-500/12 text-rose-700 border-rose-500/20' },
  video: { label: '文生视频', icon: Video, tone: 'bg-cyan-500/12 text-cyan-700 border-cyan-500/20' },
  ocr: { label: 'OCR 识别', icon: Eye, tone: 'bg-teal-500/12 text-teal-700 border-teal-500/20' },
  document_parse: { label: '文档解析', icon: Layers3, tone: 'bg-stone-500/12 text-stone-700 border-stone-500/20' },
}

export const capabilityUrlOverrideCandidates: CapabilityType[] = ['embedding', 'rerank', 'vision', 'asr', 'tts']

export const customProviderRuntimeCapabilityMap: Record<CustomProviderProtocolType, CapabilityType[]> = {
  openai: ['chat', 'vision', 'embedding', 'rerank', 'asr', 'tts'],
  openai_compatible: ['chat', 'vision', 'embedding', 'rerank', 'asr', 'tts'],
  azure_openai: ['chat', 'vision', 'embedding', 'rerank', 'asr', 'tts'],
  ollama: ['chat', 'vision', 'embedding'],
  vllm: ['chat', 'vision', 'embedding'],
  anthropic_native: ['chat', 'vision'],
  gemini_native: ['chat', 'vision'],
  bedrock: ['chat', 'vision'],
  custom: [],
}

export function getRuntimeCapabilitiesForProtocol(protocolType: CustomProviderProtocolType): CapabilityType[] {
  return customProviderRuntimeCapabilityMap[protocolType] ?? []
}

export const capabilityOverridePlaceholders: Partial<
  Record<
    CapabilityType,
    {
      requestSchema: string
      endpointPath: string
      implementationKey: string
      helperText: string
    }
  >
> = {
  embedding: {
    requestSchema: '如 openai_embedding',
    endpointPath: '通常留空，默认继承 base URL',
    implementationKey: '如 openai_embedding',
    helperText: 'Embedding 大多数场景只需单独 base URL；协议特殊时再补请求协议或实现键。',
  },
  rerank: {
    requestSchema: '如 openai_rerank / dashscope_text_rerank_v1',
    endpointPath: '如 /compatible-api/v1/reranks',
    implementationKey: '如 dashscope_multimodal_rerank_v1',
    helperText: 'Tongyi 这类 rerank 模型协议不一致时，可以在这里覆盖请求协议、endpoint 和实现键。',
  },
  vision: {
    requestSchema: '如 openai_vision',
    endpointPath: '通常留空，默认继承聊天入口',
    implementationKey: '如 openai_vision',
    helperText: '多模态对话模型通常主类型仍是 chat，只是额外具备 vision 能力；这里只保留给专用视觉理解入口或网关特殊的厂商使用。',
  },
  asr: {
    requestSchema: '如 openai_audio_transcription',
    endpointPath: '如 /audio/transcriptions',
    implementationKey: '如 openai_audio_transcription',
    helperText: '语音识别未来会统一走能力级路由，这里先把高级覆盖入口预留好。',
  },
  tts: {
    requestSchema: '如 openai_audio_speech',
    endpointPath: '如 /audio/speech',
    implementationKey: '如 openai_audio_speech',
    helperText: '语音合成优先走统一协议；只有网关不兼容时，才需要模型或能力级覆盖。',
  },
}

export const endpointTypeLabelMap: Record<ProviderEndpointType, string> = {
  official: '官方服务',
  openai_compatible: '兼容网关',
  local: '本地部署',
  proxy: '平台代理',
}

export const providerThemeMap: Record<string, string> = {
  OpenAI: 'bg-black text-white',
  Anthropic: 'bg-neutral-800 text-white',
  Gemini: 'bg-gradient-to-br from-blue-500 via-violet-500 to-amber-400 text-white',
  DeepSeek: 'bg-blue-600 text-white',
  Moonshot: 'bg-zinc-900 text-white',
  'ZHIPU-AI': 'bg-sky-100 text-sky-700',
  xAI: 'bg-neutral-900 text-white',
  BaiduYiyan: 'bg-red-100 text-red-700',
  'OpenAI-API-Compatible': 'bg-slate-100 text-slate-700',
  OpenRouter: 'bg-zinc-100 text-zinc-800',
  Groq: 'bg-orange-100 text-orange-700',
  'Tongyi-Qianwen': 'bg-amber-100 text-amber-700',
  Doubao: 'bg-rose-100 text-rose-700',
  PPIO: 'bg-indigo-100 text-indigo-700',
  Ollama: 'bg-emerald-100 text-emerald-700',
  'Azure-OpenAI': 'bg-cyan-100 text-cyan-700',
  MiniMax: 'bg-orange-100 text-orange-700',
  TogetherAI: 'bg-violet-100 text-violet-700',
  Fireworks: 'bg-red-100 text-red-700',
  NVIDIA: 'bg-lime-100 text-lime-700',
  SILICONFLOW: 'bg-fuchsia-100 text-fuchsia-700',
  vLLM: 'bg-indigo-100 text-indigo-700',
  'LM Studio': 'bg-sky-100 text-sky-700',
  LocalAI: 'bg-emerald-100 text-emerald-700',
}

export const providerLogoMap: Partial<Record<string, string>> = {
  OpenAI: openAiLogo,
  Anthropic: anthropicLogo,
  Gemini: geminiLogo,
  DeepSeek: deepseekLogo,
  Moonshot: moonshotLogo,
  'ZHIPU-AI': zhipuLogo,
  xAI: grokLogo,
  BaiduYiyan: baiduCloudLogo,
  'OpenAI-API-Compatible': newApiLogo,
  OpenRouter: openRouterLogo,
  Groq: groqLogo,
  'Tongyi-Qianwen': dashscopeLogo,
  Doubao: doubaoLogo,
  PPIO: ppioLogo,
  Ollama: ollamaLogo,
  'Azure-OpenAI': openAiLogo,
  MiniMax: minimaxLogo,
  TogetherAI: togetherLogo,
  Fireworks: fireworksLogo,
  NVIDIA: nvidiaLogo,
  SILICONFLOW: siliconLogo,
  'LM Studio': lmStudioLogo,
  LocalAI: localAiLogo,
}

export const emptyDraft: ProviderDraft = {
  baseUrl: '',
  apiKey: '',
  endpointType: 'official',
  isEnabled: false,
  isVisibleInUI: false,
  capabilityBaseUrls: {},
  capabilityOverrides: {},
}

export const emptyCustomProviderForm: CustomProviderForm = {
  displayName: '',
  providerCode: '',
  protocolType: 'openai_compatible',
  endpointType: 'openai_compatible',
  baseUrl: '',
  apiKey: '',
  description: '',
  capabilities: ['chat'],
  isEnabled: true,
  isVisibleInUI: true,
}

export const emptyManualModelForm: ManualModelForm = {
  modelKey: '',
  rawModelName: '',
  displayName: '',
  modelType: 'chat',
  capabilities: ['chat'],
  groupName: '',
  contextWindow: '',
  maxOutputTokens: '',
  embeddingDimension: '',
  adapterOverrideType: '',
  implementationKeyOverride: '',
  requestSchemaOverride: '',
  endpointPathOverride: '',
  runtimeBaseUrlOverride: '',
  supportsMultimodalInput: false,
  concurrencyLimit: '',
}
