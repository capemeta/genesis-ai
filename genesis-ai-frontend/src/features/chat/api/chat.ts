import axiosInstance, { resolveApiUrl } from '@/lib/api/axios-instance'
import type { ApiResponse, PaginatedResponse } from '@/lib/api/types'
import { useAuthStore } from '@/stores/auth-store'
import type {
  ChatBootstrapData,
  ChatCapabilityBinding,
  ChatMessage,
  ChatSelectorOption,
  ChatSendMessageRequest,
  ChatSendMessageResponse,
  ChatSession,
  ChatSessionListResponse,
  ChatSessionPayload,
  ChatSpace,
  ChatSpaceListResponse,
  ChatSpacePayload,
  ChatSpacesQuery,
  ChatSessionsQuery,
  ChatStreamEvent,
  ChatStreamEventMap,
} from '@/features/chat/types/chat'

export const chatQueryKeys = {
  all: ['chat'] as const,
  bootstrap: () => [...chatQueryKeys.all, 'bootstrap'] as const,
  spaces: (query: ChatSpacesQuery) => [...chatQueryKeys.all, 'spaces', query] as const,
  space: (spaceId: string) => [...chatQueryKeys.all, 'space', spaceId] as const,
  sessionLists: (spaceId: string) => [...chatQueryKeys.all, 'space', spaceId, 'sessions'] as const,
  sessions: (spaceId: string, query: ChatSessionsQuery) =>
    [...chatQueryKeys.all, 'space', spaceId, 'sessions', query] as const,
  session: (sessionId: string) => [...chatQueryKeys.all, 'session', sessionId] as const,
  messages: (sessionId: string) =>
    [...chatQueryKeys.all, 'session', sessionId, 'messages'] as const,
} as const

function unwrapResponse<T>(response: { data: ApiResponse<T> }): T {
  return response.data.data
}

export async function fetchChatBootstrap(): Promise<ChatBootstrapData> {
  const response = await axiosInstance.get<ApiResponse<ChatBootstrapData>>('/api/v1/chat/bootstrap')
  return unwrapResponse(response)
}

/** 聊天挂载知识库选择器专用（排除已选 ID，与知识库主页 /knowledge-bases/list 无关） */
export async function fetchChatKnowledgeBasePickerList(params: {
  page: number
  page_size: number
  search?: string
  /** 已挂载到当前空间的知识库 ID，列表中排除 */
  exclude_ids: string[]
}): Promise<PaginatedResponse<ChatSelectorOption>> {
  const response = await axiosInstance.post<
    ApiResponse<PaginatedResponse<ChatSelectorOption>>
  >('/api/v1/chat/knowledge-base-picker/list', {
    ...params,
    exclude_ids: params.exclude_ids,
  })
  return unwrapResponse(response)
}

export async function fetchChatSpaces(query: ChatSpacesQuery): Promise<ChatSpaceListResponse> {
  const response = await axiosInstance.get<ApiResponse<ChatSpaceListResponse>>('/api/v1/chat/spaces', {
    params: {
      page: query.page,
      page_size: query.pageSize,
      search: query.search || undefined,
      status: query.status || 'active',
    },
  })
  return unwrapResponse(response)
}

export async function fetchChatSpace(spaceId: string): Promise<ChatSpace> {
  const response = await axiosInstance.get<ApiResponse<ChatSpace>>(`/api/v1/chat/spaces/${spaceId}`)
  return unwrapResponse(response)
}

export async function createChatSpace(payload: ChatSpacePayload): Promise<ChatSpace> {
  const response = await axiosInstance.post<ApiResponse<ChatSpace>>('/api/v1/chat/spaces', payload)
  return unwrapResponse(response)
}

export async function updateChatSpace(
  spaceId: string,
  payload: Partial<ChatSpacePayload> & { status?: ChatSpace['status'] }
): Promise<ChatSpace> {
  const response = await axiosInstance.put<ApiResponse<ChatSpace>>(
    `/api/v1/chat/spaces/${spaceId}`,
    payload
  )
  return unwrapResponse(response)
}

export async function deleteChatSpace(spaceId: string): Promise<void> {
  await axiosInstance.delete(`/api/v1/chat/spaces/${spaceId}`)
}

export async function createChatSessionCapability(
  sessionId: string,
  payload: Pick<
    ChatCapabilityBinding,
    'capability_type' | 'capability_id' | 'binding_role' | 'is_enabled' | 'priority' | 'config'
  >
): Promise<ChatCapabilityBinding> {
  const response = await axiosInstance.post<ApiResponse<ChatCapabilityBinding>>(
    `/api/v1/chat/sessions/${sessionId}/capabilities`,
    payload
  )
  return unwrapResponse(response)
}

export async function updateChatSessionCapability(
  sessionId: string,
  bindingId: string,
  payload: Partial<Pick<ChatCapabilityBinding, 'is_enabled' | 'priority' | 'config'>>
): Promise<ChatCapabilityBinding> {
  const response = await axiosInstance.put<ApiResponse<ChatCapabilityBinding>>(
    `/api/v1/chat/sessions/${sessionId}/capabilities/${bindingId}`,
    payload
  )
  return unwrapResponse(response)
}

export async function deleteChatSessionCapability(sessionId: string, bindingId: string): Promise<void> {
  await axiosInstance.delete(`/api/v1/chat/sessions/${sessionId}/capabilities/${bindingId}`)
}

export async function fetchChatSessions(
  spaceId: string,
  query: ChatSessionsQuery = {}
): Promise<ChatSessionListResponse> {
  const response = await axiosInstance.get<ApiResponse<ChatSessionListResponse>>(
    `/api/v1/chat/spaces/${spaceId}/sessions`,
    {
      params: {
        page: query.page || 1,
        page_size: query.pageSize || 50,
        status: query.status || 'active',
      },
    }
  )
  return unwrapResponse(response)
}

export async function createChatSession(
  spaceId: string,
  payload: ChatSessionPayload
): Promise<ChatSession> {
  const response = await axiosInstance.post<ApiResponse<ChatSession>>(
    `/api/v1/chat/spaces/${spaceId}/sessions`,
    payload
  )
  return unwrapResponse(response)
}

export async function fetchChatSession(sessionId: string): Promise<ChatSession> {
  const response = await axiosInstance.get<ApiResponse<ChatSession>>(`/api/v1/chat/sessions/${sessionId}`)
  return unwrapResponse(response)
}

export async function updateChatSession(
  sessionId: string,
  payload: Partial<ChatSessionPayload> & { status?: ChatSession['status'] }
): Promise<ChatSession> {
  const response = await axiosInstance.put<ApiResponse<ChatSession>>(
    `/api/v1/chat/sessions/${sessionId}`,
    payload
  )
  return unwrapResponse(response)
}

export async function fetchChatMessages(sessionId: string): Promise<ChatMessage[]> {
  const response = await axiosInstance.get<ApiResponse<ChatMessage[]>>(
    `/api/v1/chat/sessions/${sessionId}/messages`
  )
  return unwrapResponse(response)
}

/** 清空当前会话的全部聊天记录（会话本身保留） */
export async function clearChatSessionMessages(sessionId: string): Promise<void> {
  await axiosInstance.delete(`/api/v1/chat/sessions/${sessionId}/messages`)
}

export async function sendChatMessage(
  sessionId: string,
  payload: ChatSendMessageRequest
): Promise<ChatSendMessageResponse> {
  const response = await axiosInstance.post<ApiResponse<ChatSendMessageResponse>>(
    `/api/v1/chat/sessions/${sessionId}/messages`,
    payload
  )
  return unwrapResponse(response)
}

function buildStreamUrl(sessionId: string): string {
  // 统一复用 API URL 解析逻辑，兼容 Docker 子路径部署与本地源码启动。
  return resolveApiUrl(`/api/v1/chat/sessions/${sessionId}/messages/stream`)
}

function buildStreamHeaders(): HeadersInit {
  const accessToken = useAuthStore.getState().access_token
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  }

  // Cookie 是主认证方式；Authorization 作为 fetch 场景的兜底，避免绕过 axios 时丢失认证信息。
  if (accessToken) {
    headers.Authorization = `Bearer ${accessToken}`
  }

  return headers
}

let streamRefreshPromise: Promise<void> | null = null

async function refreshStreamAuthOnce(): Promise<void> {
  // 多个流式请求同时遇到 401 时，共用一次 refresh，避免 refresh token 并发轮换冲突。
  streamRefreshPromise ||= useAuthStore.getState().refreshToken().finally(() => {
    streamRefreshPromise = null
  })
  await streamRefreshPromise
}

function parseSseChunk(chunk: string): Array<ChatStreamEvent> {
  return chunk
    .split('\n\n')
    .map((block) => block.trim())
    .filter(Boolean)
    .flatMap((block) => {
      const lines = block.split('\n')
      const eventLine = lines.find((line) => line.startsWith('event:'))
      const dataLines = lines.filter((line) => line.startsWith('data:'))

      if (!eventLine || dataLines.length === 0) {
        return []
      }

      const event = eventLine.replace('event:', '').trim() as keyof ChatStreamEventMap
      const dataText = dataLines.map((line) => line.replace('data:', '').trim()).join('\n')

      return [
        {
          event,
          data: JSON.parse(dataText),
        } as ChatStreamEvent,
      ]
    })
}

export async function streamChatMessage(
  sessionId: string,
  payload: ChatSendMessageRequest,
  options: {
    signal?: AbortSignal
    onEvent: (event: ChatStreamEvent) => void
  }
): Promise<void> {
  const requestBody = JSON.stringify(payload)
  const requestUrl = buildStreamUrl(sessionId)
  const requestStream = () =>
    fetch(requestUrl, {
      method: 'POST',
      credentials: 'include',
      headers: buildStreamHeaders(),
      body: requestBody,
      signal: options.signal,
    })

  let response = await requestStream()

  if (response.status === 401) {
    await refreshStreamAuthOnce()
    response = await requestStream()
  }

  if (!response.ok) {
    throw new Error(`流式请求失败：${response.status}`)
  }

  if (!response.body) {
    throw new Error('流式响应体为空')
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder('utf-8')
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) {
      break
    }

    buffer += decoder.decode(value, { stream: true })
    const segments = buffer.split('\n\n')
    buffer = segments.pop() || ''

    for (const segment of segments) {
      for (const event of parseSseChunk(segment)) {
        options.onEvent(event)
      }
    }
  }

  if (buffer.trim()) {
    for (const event of parseSseChunk(buffer)) {
      options.onEvent(event)
    }
  }
}
