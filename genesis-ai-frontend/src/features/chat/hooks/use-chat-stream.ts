import { useCallback, useEffect, useRef, useState } from 'react'
import { streamChatMessage } from '@/features/chat/api/chat'
import type {
  ChatSendMessageRequest,
  ChatStreamEvent,
  ChatStreamCompletedEvent,
  ChatStreamDeltaEvent,
  ChatStreamFailedEvent,
  ChatStreamStatusEvent,
  ChatStreamTurnCreatedEvent,
} from '@/features/chat/types/chat'

interface UseChatStreamHandlers {
  onTurnCreated?: (payload: ChatStreamTurnCreatedEvent) => void
  onAssistantStatus?: (payload: ChatStreamStatusEvent) => void
  onAssistantDelta?: (payload: ChatStreamDeltaEvent) => void
  onAssistantCompleted?: (payload: ChatStreamCompletedEvent) => void
  onAssistantFailed?: (payload: ChatStreamFailedEvent) => void
}

/**
 * 统一封装聊天流式发送逻辑，避免页面里堆叠 SSE 解析细节。
 */
export function useChatStream() {
  const controllerRef = useRef<AbortController | null>(null)
  const [isStreaming, setIsStreaming] = useState(false)

  const stopStream = useCallback(() => {
    controllerRef.current?.abort()
    controllerRef.current = null
    setIsStreaming(false)
  }, [])

  const handleStreamEvent = useCallback(
    (event: ChatStreamEvent, handlers: UseChatStreamHandlers) => {
      switch (event.event) {
        case 'turn.created':
          handlers.onTurnCreated?.(event.data as ChatStreamTurnCreatedEvent)
          break
        case 'assistant.status':
          handlers.onAssistantStatus?.(event.data as ChatStreamStatusEvent)
          break
        case 'assistant.delta':
          handlers.onAssistantDelta?.(event.data as ChatStreamDeltaEvent)
          break
        case 'assistant.completed':
          handlers.onAssistantCompleted?.(event.data as ChatStreamCompletedEvent)
          break
        case 'assistant.failed':
          handlers.onAssistantFailed?.(event.data as ChatStreamFailedEvent)
          break
        default:
          break
      }
    },
    []
  )

  const sendStreamMessage = useCallback(
    async (
      sessionId: string,
      payload: ChatSendMessageRequest,
      handlers: UseChatStreamHandlers = {}
    ) => {
      stopStream()

      const controller = new AbortController()
      controllerRef.current = controller
      setIsStreaming(true)

      try {
        await streamChatMessage(sessionId, payload, {
          signal: controller.signal,
          onEvent: (event) => handleStreamEvent(event, handlers),
        })
      } finally {
        if (controllerRef.current === controller) {
          controllerRef.current = null
          setIsStreaming(false)
        }
      }
    },
    [handleStreamEvent, stopStream]
  )

  useEffect(() => stopStream, [stopStream])

  return {
    isStreaming,
    sendStreamMessage,
    stopStream,
  }
}
