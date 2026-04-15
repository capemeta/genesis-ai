import { useEffect, useMemo, useRef, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useNavigate, useParams, useSearch } from '@tanstack/react-router'
import { Bot, Database, Eraser, MessageSquareText, Plus, Settings2, SquarePen } from 'lucide-react'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from '@/components/ui/sheet'
import {
  chatQueryKeys,
  clearChatSessionMessages,
  createChatSession,
  createChatSessionCapability,
  deleteChatSessionCapability,
  fetchChatBootstrap,
  fetchChatMessages,
  fetchChatSession,
  fetchChatSessions,
  fetchChatSpace,
  updateChatSession,
  updateChatSessionCapability,
  updateChatSpace,
} from '@/features/chat/api/chat'
import { ChatConfigPanel } from '@/features/chat/components/detail/chat-config-panel'
import { ChatMessageInput } from '@/features/chat/components/detail/chat-message-input'
import { ChatMessageList } from '@/features/chat/components/detail/chat-message-list'
import {
  ChatSessionArchiveDialog,
  ChatSessionDeleteDialog,
  ChatSessionRenameDialog,
  ClearChatMessagesDialog,
} from '@/features/chat/components/detail/chat-session-management-dialogs'
import { ChatSessionSidebar } from '@/features/chat/components/detail/chat-session-sidebar'
import { EditChatSpaceDialog } from '@/features/chat/components/shared/edit-chat-space-dialog'
import { useChatStream } from '@/features/chat/hooks/use-chat-stream'
import type { ChatConfigDraft, ChatMessage, ChatSession } from '@/features/chat/types/chat'
import {
  buildAutoSessionTitle,
  buildConfigDraft,
  getSessionDisplayTitle,
  isFallbackSessionTitle,
  mergeMessages,
  normalizeKnowledgeBaseScopeDraft,
  sortChatMessages,
} from '@/features/chat/utils/chat-format'

/**
 * 将流式请求的“手动停止”归类为正常中断，避免误报错误提示。
 */
function isStreamAbortMessage(message?: string): boolean {
  if (!message) {
    return false
  }
  const normalized = message.toLowerCase()
  return normalized.includes('aborted') || normalized.includes('aborterror') || normalized.includes('bodystreambuffer was aborted')
}

export function ChatSpaceDetailPage() {
  const navigate = useNavigate()
  const params = useParams({ from: '/_top-nav/chat/$chatId' })
  const search = useSearch({ from: '/_top-nav/chat/$chatId' }) as { sessionId?: string }
  const queryClient = useQueryClient()
  const spaceId = params.chatId
  const selectedSessionId = search.sessionId
  const [renameSession, setRenameSession] = useState<ChatSession | null>(null)
  const [archiveSession, setArchiveSession] = useState<ChatSession | null>(null)
  const [deleteSession, setDeleteSession] = useState<ChatSession | null>(null)
  const [isMobileSessionSheetOpen, setIsMobileSessionSheetOpen] = useState(false)
  const [isEditSpaceDialogOpen, setIsEditSpaceDialogOpen] = useState(false)
  const [clearMessagesOpen, setClearMessagesOpen] = useState(false)
  const [optimisticRemovedSessionId, setOptimisticRemovedSessionId] = useState<string | null>(null)
  const [chatConfigDraft, setChatConfigDraft] = useState<ChatConfigDraft | null>(null)
  const autoRenamedSessionIdsRef = useRef<Set<string>>(new Set())
  const initializedDraftSessionIdRef = useRef<string | null>(null)

  const bootstrapQuery = useQuery({
    queryKey: chatQueryKeys.bootstrap(),
    queryFn: fetchChatBootstrap,
  })

  const spaceQuery = useQuery({
    queryKey: chatQueryKeys.space(spaceId),
    queryFn: () => fetchChatSpace(spaceId),
  })

  const activeSessionsQuery = useQuery({
    queryKey: chatQueryKeys.sessions(spaceId, { page: 1, pageSize: 100, status: 'active' }),
    queryFn: () => fetchChatSessions(spaceId, { page: 1, pageSize: 100, status: 'active' }),
  })

  const archivedSessionsQuery = useQuery({
    queryKey: chatQueryKeys.sessions(spaceId, { page: 1, pageSize: 100, status: 'archived' }),
    queryFn: () => fetchChatSessions(spaceId, { page: 1, pageSize: 100, status: 'archived' }),
  })

  // 详情页需要同时感知活跃与归档会话，才能保证会话操作后的切换体验一致。
  const sessions = useMemo(
    () => [
      ...(activeSessionsQuery.data?.data || []),
      ...(archivedSessionsQuery.data?.data || []),
    ],
    [activeSessionsQuery.data?.data, archivedSessionsQuery.data?.data]
  )
  const visibleSessions = useMemo(
    () =>
      optimisticRemovedSessionId
        ? sessions.filter((session) => session.id !== optimisticRemovedSessionId)
        : sessions,
    [optimisticRemovedSessionId, sessions]
  )
  const visibleActiveSessions = useMemo(
    () => visibleSessions.filter((session) => session.status === 'active'),
    [visibleSessions]
  )
  const visibleArchivedSessions = useMemo(
    () => visibleSessions.filter((session) => session.status === 'archived'),
    [visibleSessions]
  )
  const effectiveSelectedSessionId =
    selectedSessionId && selectedSessionId !== optimisticRemovedSessionId
      ? selectedSessionId
      : undefined

  const activeSessionId =
    effectiveSelectedSessionId || visibleActiveSessions[0]?.id || visibleArchivedSessions[0]?.id
  const hasAnySession = visibleSessions.length > 0
  const activeSessionsQueryKey = chatQueryKeys.sessions(spaceId, {
    page: 1,
    pageSize: 100,
    status: 'active',
  })
  const archivedSessionsQueryKey = chatQueryKeys.sessions(spaceId, {
    page: 1,
    pageSize: 100,
    status: 'archived',
  })
  const sortSessionsForSidebar = (items: ChatSession[]) =>
    [...items].sort((left, right) => {
      if (left.is_pinned !== right.is_pinned) {
        return left.is_pinned ? -1 : 1
      }
      if (left.display_order !== right.display_order) {
        return left.display_order - right.display_order
      }
      return new Date(right.updated_at).getTime() - new Date(left.updated_at).getTime()
    })

  const sessionQuery = useQuery({
    queryKey: activeSessionId ? chatQueryKeys.session(activeSessionId) : [...chatQueryKeys.all, 'empty-session'],
    queryFn: () => fetchChatSession(activeSessionId!),
    enabled: Boolean(activeSessionId),
    staleTime: 30_000,
    refetchOnMount: false,
  })

  useEffect(() => {
    setChatConfigDraft(null)
    initializedDraftSessionIdRef.current = null
  }, [activeSessionId])

  useEffect(() => {
    if (!activeSessionId || !sessionQuery.data || sessionQuery.data.id !== activeSessionId) {
      return
    }
    if (initializedDraftSessionIdRef.current === activeSessionId && chatConfigDraft) {
      return
    }

    const selectedKnowledgeBaseIds = (sessionQuery.data.capabilities || [])
      .filter((binding) => binding.capability_type === 'knowledge_base' && binding.is_enabled)
      .map((binding) => binding.capability_id)

    setChatConfigDraft(buildConfigDraft(undefined, sessionQuery.data, selectedKnowledgeBaseIds))
    initializedDraftSessionIdRef.current = activeSessionId
  }, [activeSessionId, chatConfigDraft, sessionQuery.data])

  const messagesQuery = useQuery({
    queryKey: activeSessionId ? chatQueryKeys.messages(activeSessionId) : [...chatQueryKeys.all, 'empty-messages'],
    queryFn: () => fetchChatMessages(activeSessionId!),
    enabled: Boolean(activeSessionId),
    staleTime: 30_000,
    refetchOnMount: false,
  })

  const createSessionMutation = useMutation({
    mutationFn: async () =>
      createChatSession(spaceId, {
        title: `新会话 ${Date.now().toString().slice(-4)}`,
        title_source: 'fallback',
        channel: 'ui',
        visibility: 'user_visible',
        persistence_mode: 'persistent',
        config_override: {},
      }),
    onSuccess: async (session) => {
      // 新建会话后直接写入活跃列表和详情缓存，避免再补拉归档列表或立即回查空消息。
      queryClient.setQueryData(chatQueryKeys.session(session.id), session)
      queryClient.setQueryData(chatQueryKeys.messages(session.id), [])
      queryClient.setQueryData(
        activeSessionsQueryKey,
        (current?: { data: ChatSession[]; total: number }) => {
          if (!current) {
            return {
              data: [session],
              total: 1,
            }
          }

          const remainingSessions = current.data.filter((item) => item.id !== session.id)
          return {
            ...current,
            data: sortSessionsForSidebar([session, ...remainingSessions]),
            total: current.total + (remainingSessions.length === current.data.length ? 1 : 0),
          }
        }
      )
      navigate({
        to: '/chat/$chatId',
        params: { chatId: spaceId },
        search: { sessionId: session.id },
      })
      toast.success('已创建新会话')
    },
  })

  useEffect(() => {
    if (activeSessionsQuery.isLoading || archivedSessionsQuery.isLoading) {
      return
    }

    if (!selectedSessionId && activeSessionsQuery.data?.data[0]?.id) {
      navigate({
        to: '/chat/$chatId',
        params: { chatId: spaceId },
        search: { sessionId: activeSessionsQuery.data.data[0].id },
        replace: true,
      })
    }
  }, [
    activeSessionsQuery.data,
    activeSessionsQuery.isLoading,
    archivedSessionsQuery.isLoading,
    navigate,
    selectedSessionId,
    spaceId,
  ])

  useEffect(() => {
    // 只有在路由已经切离被乐观移除的会话后，才清理该标记，避免删除成功瞬间又对旧会话发起查询。
    if (!optimisticRemovedSessionId) {
      return
    }

    if (selectedSessionId !== optimisticRemovedSessionId) {
      setOptimisticRemovedSessionId(null)
    }
  }, [optimisticRemovedSessionId, selectedSessionId])

  const updateSessionMutation = useMutation({
    mutationFn: async ({
      sessionId,
      payload,
    }: {
      sessionId: string
      payload: Parameters<typeof updateChatSession>[1]
      currentStatus?: ChatSession['status']
    }) => updateChatSession(sessionId, payload),
    onSuccess: async (updatedSession, variables) => {
      const invalidateTasks: Array<Promise<unknown>> = []
      const hasStatusChange = typeof variables.payload.status === 'string'

      if (!hasStatusChange) {
        const targetQueryKey =
          variables.currentStatus === 'archived' ? archivedSessionsQueryKey : activeSessionsQueryKey

        queryClient.setQueryData(chatQueryKeys.session(updatedSession.id), updatedSession)
        queryClient.setQueryData(
          targetQueryKey,
          (current?: { data: ChatSession[]; total: number }) => {
            if (!current) {
              return current
            }

            const nextItems = current.data.map((item) =>
              item.id === updatedSession.id ? { ...item, ...updatedSession } : item
            )

            return {
              ...current,
              data: sortSessionsForSidebar(nextItems),
            }
          }
        )
        return
      }

      if (variables.payload.status === 'deleted') {
        const targetQueryKey =
          variables.currentStatus === 'archived' ? archivedSessionsQueryKey : activeSessionsQueryKey
        invalidateTasks.push(queryClient.invalidateQueries({ queryKey: targetQueryKey }))
      } else if (
        variables.payload.status === 'archived' ||
        (variables.payload.status === 'active' && variables.currentStatus === 'archived')
      ) {
        invalidateTasks.push(
          queryClient.invalidateQueries({ queryKey: activeSessionsQueryKey }),
          queryClient.invalidateQueries({ queryKey: archivedSessionsQueryKey })
        )
      } else {
        const targetQueryKey =
          variables.currentStatus === 'archived' ? archivedSessionsQueryKey : activeSessionsQueryKey
        invalidateTasks.push(queryClient.invalidateQueries({ queryKey: targetQueryKey }))
      }

      // 删除后会话详情接口会按不存在处理，此时不应再主动回拉当前 session。
      if (variables.payload.status !== 'deleted') {
        invalidateTasks.push(
          queryClient.invalidateQueries({ queryKey: chatQueryKeys.session(variables.sessionId) })
        )
      }

      await Promise.all(invalidateTasks)
    },
  })

  useEffect(() => {
    const session = sessionQuery.data
    if (!activeSessionId || !session || updateSessionMutation.isPending) {
      return
    }

    if (session.title_source !== 'fallback' || !isFallbackSessionTitle(session.title)) {
      return
    }

    if (autoRenamedSessionIdsRef.current.has(session.id)) {
      return
    }

    const firstUserMessage = (messagesQuery.data || []).find(
      (message) => message.role === 'user' && message.content?.trim()
    )

    if (!firstUserMessage?.content) {
      return
    }

    const nextTitle = buildAutoSessionTitle(firstUserMessage.content)
    if (!nextTitle || nextTitle === session.title?.trim()) {
      autoRenamedSessionIdsRef.current.add(session.id)
      return
    }

    autoRenamedSessionIdsRef.current.add(session.id)
    updateSessionMutation.mutate(
      {
        sessionId: session.id,
        payload: {
          title: nextTitle,
          title_source: 'auto',
        },
      },
      {
        onError: () => {
          autoRenamedSessionIdsRef.current.delete(session.id)
        },
      }
    )
  }, [
    activeSessionId,
    messagesQuery.data,
    sessionQuery.data,
    updateSessionMutation,
    updateSessionMutation.isPending,
  ])

  const saveConfigMutation = useMutation({
    mutationFn: async (draft: ChatConfigDraft) => {
      if (!activeSessionId) {
        throw new Error('当前没有可用会话')
      }
      validateKnowledgeBaseScopeExpressions(
        draft,
        (bootstrapQuery.data?.knowledge_bases || []).map((item) => ({
          id: item.id,
          name: item.name,
        }))
      )

      const updatedSession = await updateChatSession(activeSessionId, {
        config_override: buildPersistedChatConfigOverride(draft),
      })

      const bindings = sessionQuery.data?.capabilities || []
      const existingKnowledgeBaseBindings = bindings.filter(
        (binding) => binding.capability_type === 'knowledge_base'
      )
      const selectedIds = new Set(draft.selectedKnowledgeBaseIds)
      const toDelete = existingKnowledgeBaseBindings.filter(
        (binding) => !selectedIds.has(binding.capability_id)
      )
      const existingIds = new Set(existingKnowledgeBaseBindings.map((binding) => binding.capability_id))
      const toCreate = draft.selectedKnowledgeBaseIds.filter((id) => !existingIds.has(id))
      const toUpdate = existingKnowledgeBaseBindings.filter((binding) =>
        selectedIds.has(binding.capability_id)
      )

      await Promise.all(toDelete.map((binding) => deleteChatSessionCapability(activeSessionId, binding.id)))
      const createdBindings = await Promise.all(
        toCreate.map((knowledgeBaseId, index) =>
          createChatSessionCapability(activeSessionId, {
            capability_type: 'knowledge_base',
            capability_id: knowledgeBaseId,
            binding_role: index === 0 ? 'primary' : 'secondary',
            is_enabled: true,
            priority: 100 + index,
            config: buildKnowledgeBaseBindingConfig(
              draft.knowledgeBaseScopes[knowledgeBaseId] || {
                kbDocIds: [],
                folderIds: [],
                folderTagIds: [],
                includeDescendantFolders: true,
                tagIds: [],
                metadata: {},
                filterExpressionText: '',
              }
            ),
          })
        )
      )
      const updatedBindings = await Promise.all(
        toUpdate.map(async (binding) => {
          const nextConfig = buildKnowledgeBaseBindingConfig(
            draft.knowledgeBaseScopes[binding.capability_id] || {
              kbDocIds: [],
              folderIds: [],
              folderTagIds: [],
              includeDescendantFolders: true,
              tagIds: [],
              metadata: {},
              filterExpressionText: '',
            },
            binding.config
          )
          const currentScope = normalizeKnowledgeBaseScopeDraft(binding)
          const nextScope = draft.knowledgeBaseScopes[binding.capability_id] || {
            kbDocIds: [],
            folderIds: [],
            folderTagIds: [],
            includeDescendantFolders: true,
            tagIds: [],
            metadata: {},
            filterExpressionText: '',
          }
          if (
            JSON.stringify({
              kbDocIds: [...currentScope.kbDocIds].sort(),
              folderIds: [...currentScope.folderIds].sort(),
              folderTagIds: [...currentScope.folderTagIds].sort(),
              includeDescendantFolders: currentScope.includeDescendantFolders,
              tagIds: [...currentScope.tagIds].sort(),
              metadata: currentScope.metadata,
              filterExpressionText: String(currentScope.filterExpressionText || '').trim(),
            }) ===
            JSON.stringify({
              kbDocIds: [...nextScope.kbDocIds].sort(),
              folderIds: [...nextScope.folderIds].sort(),
              folderTagIds: [...nextScope.folderTagIds].sort(),
              includeDescendantFolders: nextScope.includeDescendantFolders,
              tagIds: [...nextScope.tagIds].sort(),
              metadata: nextScope.metadata,
              filterExpressionText: String(nextScope.filterExpressionText || '').trim(),
            })
          ) {
            return binding
          }

          return updateChatSessionCapability(activeSessionId, binding.id, {
            config: nextConfig,
          })
        })
      )

      const deletedBindingIds = new Set(toDelete.map((binding) => binding.id))
      const nextCapabilities = [
        ...bindings
          .filter((binding) => !deletedBindingIds.has(binding.id))
          .map((binding) => updatedBindings.find((item) => item.id === binding.id) || binding),
        ...createdBindings,
      ]

      return {
        updatedSession,
        nextCapabilities,
      }
    },
    onSuccess: ({ updatedSession, nextCapabilities }) => {
      queryClient.setQueryData(chatQueryKeys.session(updatedSession.id), {
        ...updatedSession,
        capabilities: nextCapabilities,
      })
      toast.success('配置已保存')
    },
  })

  const updateSpaceMutation = useMutation({
    mutationFn: async (values: { name: string; description: string }) =>
      updateChatSpace(spaceId, {
        name: values.name,
        description: values.description || undefined,
      }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: chatQueryKeys.space(spaceId) })
      await queryClient.invalidateQueries({ queryKey: [...chatQueryKeys.all, 'spaces'] })
      toast.success('聊天空间信息已更新')
      setIsEditSpaceDialogOpen(false)
    },
  })

  const { isStreaming, sendStreamMessage, stopStream } = useChatStream()

  const sendMessageMutation = useMutation({
    mutationFn: async (content: string) => {
      if (!activeSessionId) {
        throw new Error('当前没有可用会话')
      }
      if (!chatConfigDraft) {
        throw new Error('当前配置尚未初始化完成，请稍后再试')
      }

      validateKnowledgeBaseScopeExpressions(
        chatConfigDraft,
        (bootstrapQuery.data?.knowledge_bases || []).map((item) => ({
          id: item.id,
          name: item.name,
        }))
      )

      await sendStreamMessage(
        activeSessionId,
        {
          content,
          source_channel: 'ui',
          content_blocks: [],
          config_override: buildRuntimeChatConfigOverride(chatConfigDraft),
          metadata_info: {},
        },
        {
          onTurnCreated: ({ session, user_message, assistant_message }) => {
            queryClient.setQueryData<ChatMessage[]>(
              chatQueryKeys.messages(activeSessionId),
              (current = []) => mergeMessages(current, [user_message, assistant_message])
            )
            queryClient.setQueryData(chatQueryKeys.session(activeSessionId), session)
          },
          onAssistantStatus: ({ message_id, status }) => {
            queryClient.setQueryData<ChatMessage[]>(
              chatQueryKeys.messages(activeSessionId),
              (current = []) =>
                current.map((message) =>
                  message.id === message_id ? { ...message, status } : message
                )
            )
          },
          onAssistantDelta: ({ message_id, delta }) => {
            queryClient.setQueryData<ChatMessage[]>(
              chatQueryKeys.messages(activeSessionId),
              (current = []) =>
                current.map((message) =>
                  message.id === message_id
                    ? {
                        ...message,
                        status: 'streaming',
                        content: `${message.content || ''}${delta}`,
                        display_content: `${message.display_content || message.content || ''}${delta}`,
                      }
                    : message
                )
            )
          },
          onAssistantCompleted: async ({ session, assistant_message }) => {
            queryClient.setQueryData<ChatMessage[]>(
              chatQueryKeys.messages(activeSessionId),
              (current = []) => mergeMessages(current, [assistant_message])
            )
            queryClient.setQueryData(chatQueryKeys.session(activeSessionId), session)
            await Promise.all([
              queryClient.invalidateQueries({ queryKey: chatQueryKeys.messages(activeSessionId) }),
              queryClient.invalidateQueries({ queryKey: chatQueryKeys.sessionLists(spaceId) }),
              queryClient.invalidateQueries({ queryKey: chatQueryKeys.session(activeSessionId) }),
              queryClient.invalidateQueries({ queryKey: chatQueryKeys.space(spaceId) }),
            ])
          },
          onAssistantFailed: ({ message_id, error }) => {
            const isAborted = isStreamAbortMessage(error)
            queryClient.setQueryData<ChatMessage[]>(
              chatQueryKeys.messages(activeSessionId),
              (current = []) =>
                current.map((message) =>
                  message.id === message_id
                    ? {
                        ...message,
                        status: isAborted ? 'completed' : 'failed',
                        error_message: isAborted ? undefined : error,
                      }
                    : message
                )
            )
            if (isAborted) {
              toast.info('已停止生成')
              return
            }
            toast.error(error || '消息发送失败')
          },
        }
      )
    },
  })

  const clearMessagesMutation = useMutation({
    mutationFn: async () => {
      if (!activeSessionId) {
        throw new Error('当前没有可用会话')
      }
      await clearChatSessionMessages(activeSessionId)
    },
    onSuccess: async () => {
      if (activeSessionId) {
        queryClient.setQueryData(chatQueryKeys.messages(activeSessionId), [])
      }
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: chatQueryKeys.session(activeSessionId!) }),
        queryClient.invalidateQueries({ queryKey: chatQueryKeys.sessionLists(spaceId) }),
      ])
      toast.success('聊天记录已清空')
      setClearMessagesOpen(false)
    },
    onError: (error: unknown) => {
      toast.error(error instanceof Error ? error.message : '清空失败')
    },
  })

  const handleSendMessage = async (content: string) => {
    try {
      await sendMessageMutation.mutateAsync(content)
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : String(error || '')
      if (isStreamAbortMessage(errorMessage)) {
        toast.info('已停止生成')
        return
      }
      toast.error(error instanceof Error ? error.message : '发送消息失败')
    }
  }

  const handleRetryMessage = async (failedMessage: ChatMessage) => {
    const retrySourceMessages = messages
      .filter((message) => message.turn_id === failedMessage.turn_id && message.role === 'user')
    const retrySourceMessage = retrySourceMessages[retrySourceMessages.length - 1]

    if (!retrySourceMessage?.content?.trim()) {
      toast.error('未找到可重发的原始提问')
      return
    }

    await handleSendMessage(retrySourceMessage.content)
  }

  const handleSelectSession = (sessionId: string) => {
    navigate({
      to: '/chat/$chatId',
      params: { chatId: spaceId },
      search: { sessionId },
    })
    setIsMobileSessionSheetOpen(false)
  }

  const handleCreateSession = () => {
    createSessionMutation.mutate()
    setIsMobileSessionSheetOpen(false)
  }

  const resolveNextSessionId = (currentSessionId: string) => {
    // 删除当前会话后优先回落到剩余活跃会话，再回落到归档会话。
    const remainingActiveIds = (activeSessionsQuery.data?.data || [])
      .filter((session) => session.id !== currentSessionId)
      .map((session) => session.id)
    const remainingArchivedIds = (archivedSessionsQuery.data?.data || [])
      .filter((session) => session.id !== currentSessionId)
      .map((session) => session.id)

    return remainingActiveIds[0] || remainingArchivedIds[0]
  }

  const handleRenameSession = async (title: string) => {
    if (!renameSession) {
      return
    }

    try {
      await updateSessionMutation.mutateAsync({
        sessionId: renameSession.id,
        payload: {
          title,
          title_source: 'manual',
        },
        currentStatus: renameSession.status,
      })
      toast.success('会话名称已更新')
      setRenameSession(null)
    } catch (error) {
      toast.error(error instanceof Error ? error.message : '会话重命名失败')
    }
  }

  const handleArchiveSession = async () => {
    if (!archiveSession) {
      return
    }

    const nextStatus = archiveSession.status === 'archived' ? 'active' : 'archived'

    try {
      await updateSessionMutation.mutateAsync({
        sessionId: archiveSession.id,
        payload: { status: nextStatus },
        currentStatus: archiveSession.status,
      })
      toast.success(nextStatus === 'archived' ? '会话已归档' : '会话已恢复')
      setArchiveSession(null)
    } catch (error) {
      toast.error(error instanceof Error ? error.message : '会话状态更新失败')
    }
  }

  const handleTogglePinSession = async (session: ChatSession) => {
    try {
      await updateSessionMutation.mutateAsync({
        sessionId: session.id,
        payload: { is_pinned: !session.is_pinned },
        currentStatus: session.status,
      })
      toast.success(session.is_pinned ? '已取消置顶' : '会话已置顶')
    } catch (error) {
      toast.error(error instanceof Error ? error.message : '会话置顶状态更新失败')
    }
  }

  const handleDeleteSession = async () => {
    if (!deleteSession) {
      return
    }

    const deletingSessionId = deleteSession.id
    const isDeletingCurrentSession = selectedSessionId === deletingSessionId
    const nextSessionId = isDeletingCurrentSession
      ? resolveNextSessionId(deletingSessionId)
      : undefined

    try {
      if (isDeletingCurrentSession) {
        // 先把当前会话从视图上下文摘掉，避免删除成功前后又对旧 sessionId 发详情/消息请求。
        setOptimisticRemovedSessionId(deletingSessionId)
        await Promise.all([
          queryClient.cancelQueries({ queryKey: chatQueryKeys.session(deletingSessionId) }),
          queryClient.cancelQueries({ queryKey: chatQueryKeys.messages(deletingSessionId) }),
        ])
      }

      await updateSessionMutation.mutateAsync({
        sessionId: deletingSessionId,
        payload: { status: 'deleted' },
        currentStatus: deleteSession.status,
      })

      navigate({
        to: '/chat/$chatId',
        params: { chatId: spaceId },
        search: nextSessionId ? { sessionId: nextSessionId } : { sessionId: undefined },
        replace: isDeletingCurrentSession,
      })

      queryClient.removeQueries({ queryKey: chatQueryKeys.session(deletingSessionId) })
      queryClient.removeQueries({ queryKey: chatQueryKeys.messages(deletingSessionId) })

      toast.success('会话已删除')
      setDeleteSession(null)
    } catch (error) {
      setOptimisticRemovedSessionId(null)
      toast.error(error instanceof Error ? error.message : '会话删除失败')
    }
  }

  const savedConfigDraft = useMemo(() => {
    const session = sessionQuery.data
    if (!session) {
      return null
    }
    const selectedKnowledgeBaseIds = (session.capabilities || [])
      .filter((binding) => binding.capability_type === 'knowledge_base' && binding.is_enabled)
      .map((binding) => binding.capability_id)
    return buildConfigDraft(undefined, session, selectedKnowledgeBaseIds)
  }, [sessionQuery.data])

  const currentConfigDraft = chatConfigDraft || savedConfigDraft
  const hasUnsavedConfigChanges =
    Boolean(savedConfigDraft && currentConfigDraft) &&
    serializeChatConfigDraft(savedConfigDraft!) !== serializeChatConfigDraft(currentConfigDraft!)

  const messages = useMemo(
    () => sortChatMessages(messagesQuery.data || []),
    [messagesQuery.data]
  )
  const linkedKnowledgeBaseCount = (sessionQuery.data?.capabilities || []).filter(
    (binding) => binding.capability_type === 'knowledge_base' && binding.is_enabled
  ).length

  const sessionHeaderTitle = useMemo(() => {
    const session = sessionQuery.data
    if (!session) {
      return hasAnySession ? '请选择左侧会话' : '暂无会话'
    }
    const orderIndex = sessions.findIndex((s) => s.id === session.id)
    return getSessionDisplayTitle(session, orderIndex >= 0 ? orderIndex : 0)
  }, [sessionQuery.data, sessions, hasAnySession])

  return (
    <div className='flex h-full min-h-0 w-full overflow-hidden bg-white'>
      <div className='hidden h-full min-h-0 shrink-0 lg:flex'>
        <ChatSessionSidebar
          space={spaceQuery.data}
          sessions={visibleSessions}
          activeSessionId={activeSessionId}
          onCreateSession={handleCreateSession}
          onRefreshActiveSessions={() => activeSessionsQuery.refetch()}
          onRefreshArchivedSessions={() => archivedSessionsQuery.refetch()}
          isRefreshingActiveSessions={activeSessionsQuery.isFetching}
          isRefreshingArchivedSessions={archivedSessionsQuery.isFetching}
          onSelectSession={handleSelectSession}
          onRenameSession={setRenameSession}
          onTogglePinSession={handleTogglePinSession}
          onArchiveSession={setArchiveSession}
          onDeleteSession={setDeleteSession}
          onEditSpace={() => setIsEditSpaceDialogOpen(true)}
        />
      </div>

      <main className='flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden'>
        <header className='flex items-center justify-between border-b border-blue-200 bg-white px-6 py-4 backdrop-blur md:px-8'>
          <div className='min-w-0 space-y-1'>
            <div className='flex items-center gap-3'>
              <div className='hidden h-2 w-2 rounded-full bg-emerald-500 animate-pulse md:block' />
              <div className='truncate text-xl font-bold tracking-tight text-foreground' title={sessionHeaderTitle}>
                {sessionHeaderTitle}
              </div>
            </div>
            <div className='flex items-center gap-2 text-[11px] text-blue-700/80 transition-colors hover:text-blue-700'>
              <Database className='h-3 w-3' />
              <span>{linkedKnowledgeBaseCount} 个关联知识库</span>
            </div>
          </div>

          <div className='flex items-center gap-2'>
            <Button
              type='button'
              variant='outline'
              size='sm'
              className='shrink-0'
              title='清空当前会话的聊天记录'
              disabled={
                !hasAnySession ||
                !activeSessionId ||
                messages.length === 0 ||
                isStreaming ||
                clearMessagesMutation.isPending
              }
              onClick={() => setClearMessagesOpen(true)}
            >
              <Eraser className='h-3.5 w-3.5 sm:mr-1.5' />
              <span className='hidden sm:inline'>清空记录</span>
            </Button>
            <div className='lg:hidden'>
              <Sheet open={isMobileSessionSheetOpen} onOpenChange={setIsMobileSessionSheetOpen}>
                <SheetTrigger asChild>
                  <Button variant='outline' size='icon'>
                    <MessageSquareText className='h-4 w-4' />
                  </Button>
                </SheetTrigger>
                <SheetContent side='left' className='w-full max-w-none p-0 sm:max-w-sm'>
                  <SheetHeader className='border-b pb-4 pr-12'>
                    <SheetTitle>会话列表</SheetTitle>
                    <SheetDescription>
                      小屏幕下在这里切换、新建或管理本空间里的各条对话。
                    </SheetDescription>
                  </SheetHeader>
                  <ChatSessionSidebar
                    className='max-w-none border-r-0'
                    space={spaceQuery.data}
                    sessions={visibleSessions}
                    activeSessionId={activeSessionId}
                    onCreateSession={handleCreateSession}
                    onRefreshActiveSessions={() => activeSessionsQuery.refetch()}
                    onRefreshArchivedSessions={() => archivedSessionsQuery.refetch()}
                    isRefreshingActiveSessions={activeSessionsQuery.isFetching}
                    isRefreshingArchivedSessions={archivedSessionsQuery.isFetching}
                    onSelectSession={handleSelectSession}
                    onRenameSession={(session) => {
                      setRenameSession(session)
                      setIsMobileSessionSheetOpen(false)
                    }}
                    onTogglePinSession={async (session) => {
                      await handleTogglePinSession(session)
                      setIsMobileSessionSheetOpen(false)
                    }}
                    onArchiveSession={(session) => {
                      setArchiveSession(session)
                      setIsMobileSessionSheetOpen(false)
                    }}
                    onDeleteSession={(session) => {
                      setDeleteSession(session)
                      setIsMobileSessionSheetOpen(false)
                    }}
                    onEditSpace={() => {
                      setIsEditSpaceDialogOpen(true)
                      setIsMobileSessionSheetOpen(false)
                    }}
                  />
                </SheetContent>
              </Sheet>
            </div>

            <div className='xl:hidden'>
              <Sheet>
                <SheetTrigger asChild>
                  <Button variant='outline' size='icon'>
                    <Settings2 className='h-4 w-4' />
                  </Button>
                </SheetTrigger>
                <SheetContent className='w-full sm:max-w-md'>
                  <SheetHeader>
                    <SheetTitle>会话配置</SheetTitle>
                  </SheetHeader>
                  <div className='mt-4'>
                    <ChatConfigPanel
                      className='w-full max-w-none border-l-0'
                      bootstrap={bootstrapQuery.data}
                      session={sessionQuery.data}
                      draft={currentConfigDraft || buildConfigDraft(undefined, sessionQuery.data, [])}
                      onDraftChange={(updater) => {
                        setChatConfigDraft((current) => updater(current || buildConfigDraft(undefined, sessionQuery.data, [])))
                      }}
                      onSave={async (draft) => {
                        await saveConfigMutation.mutateAsync(draft)
                        return
                      }}
                      hasUnsavedChanges={hasUnsavedConfigChanges}
                      isSaving={saveConfigMutation.isPending}
                    />
                  </div>
                </SheetContent>
              </Sheet>
            </div>
          </div>
        </header>

        {activeSessionsQuery.isLoading || archivedSessionsQuery.isLoading ? (
          <div className='flex flex-1 items-center justify-center bg-background/50'>
             <div className='flex flex-col items-center gap-4'>
                <div className='relative flex h-16 w-16 items-center justify-center'>
                  <div className='absolute inset-0 animate-ping rounded-full bg-primary/20' />
                  <div className='relative flex h-12 w-12 items-center justify-center rounded-2xl bg-primary/10 text-primary'>
                    <Bot className='h-6 w-6 animate-bounce' />
                  </div>
                </div>
                <div className='text-[10px] font-bold uppercase tracking-widest text-muted-foreground/40'>
                  正在初始化空间...
                </div>
             </div>
          </div>
        ) : hasAnySession ? (
          <>
            <ChatMessageList
              messages={messages}
              isLoading={messagesQuery.isLoading}
              isStreaming={isStreaming}
              isRetrying={sendMessageMutation.isPending}
              onRetryMessage={handleRetryMessage}
            />

            <ChatMessageInput
              isSending={isStreaming || sendMessageMutation.isPending}
              onSend={handleSendMessage}
              onStop={stopStream}
            />
          </>
        ) : (
          <div className='flex flex-1 items-center justify-center px-6 py-10'>
            <div className='w-full max-w-2xl rounded-3xl border border-dashed bg-card/80 p-8 text-center shadow-sm'>
              <div className='mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-primary/10 text-primary'>
                <MessageSquareText className='h-7 w-7' />
              </div>
              <div className='mt-5 text-2xl font-semibold'>这个聊天空间里还没有会话</div>
              <div className='mt-3 text-sm leading-6 text-muted-foreground'>
                进入空间后先按需要调整模型、知识库和检索参数；准备好了，再手动新建一条会话开始聊。
              </div>
              <div className='mt-6 flex items-center justify-center gap-3'>
                <Button onClick={handleCreateSession} disabled={createSessionMutation.isPending}>
                  <Plus className='mr-2 h-4 w-4' />
                  {createSessionMutation.isPending ? '创建中...' : '新建会话'}
                </Button>
                <Button variant='outline' onClick={() => setIsEditSpaceDialogOpen(true)}>
                  <SquarePen className='mr-2 h-4 w-4' />
                  编辑空间
                </Button>
              </div>
              <div className='mt-6 text-xs text-muted-foreground'>
                当前已关联 {linkedKnowledgeBaseCount} 个资料库。
              </div>
            </div>
          </div>
        )}
      </main>

      <ChatConfigPanel
        className='hidden xl:flex'
        bootstrap={bootstrapQuery.data}
        session={sessionQuery.data}
        draft={currentConfigDraft || buildConfigDraft(undefined, sessionQuery.data, [])}
        onDraftChange={(updater) => {
          setChatConfigDraft((current) => updater(current || buildConfigDraft(undefined, sessionQuery.data, [])))
        }}
        onSave={async (draft) => {
          await saveConfigMutation.mutateAsync(draft)
          return
        }}
        hasUnsavedChanges={hasUnsavedConfigChanges}
        isSaving={saveConfigMutation.isPending}
      />

      <ChatSessionRenameDialog
        open={Boolean(renameSession)}
        session={renameSession}
        isSubmitting={updateSessionMutation.isPending}
        onOpenChange={(open) => {
          if (!open) {
            setRenameSession(null)
          }
        }}
        onConfirm={handleRenameSession}
      />

      <ChatSessionArchiveDialog
        open={Boolean(archiveSession)}
        session={archiveSession}
        isSubmitting={updateSessionMutation.isPending}
        onOpenChange={(open) => {
          if (!open) {
            setArchiveSession(null)
          }
        }}
        onConfirm={handleArchiveSession}
      />

      <ChatSessionDeleteDialog
        open={Boolean(deleteSession)}
        session={deleteSession}
        isSubmitting={updateSessionMutation.isPending}
        onOpenChange={(open) => {
          if (!open) {
            setDeleteSession(null)
          }
        }}
        onConfirm={handleDeleteSession}
      />

      <ClearChatMessagesDialog
        open={clearMessagesOpen}
        session={sessionQuery.data}
        isSubmitting={clearMessagesMutation.isPending}
        onOpenChange={setClearMessagesOpen}
        onConfirm={() => clearMessagesMutation.mutate()}
      />

      <EditChatSpaceDialog
        open={isEditSpaceDialogOpen}
        space={spaceQuery.data}
        isSubmitting={updateSpaceMutation.isPending}
        onOpenChange={setIsEditSpaceDialogOpen}
        onSubmit={async (values) => {
          await updateSpaceMutation.mutateAsync(values)
        }}
      />
    </div>
  )
}

/**
 * 组装知识库绑定配置，只覆盖会话级范围设置，不影响其他绑定字段。
 */
function buildPersistedChatConfigOverride(draft: ChatConfigDraft): Record<string, any> {
  return {
    default_model_id: draft.defaultModelId || null,
    temperature: draft.temperature,
    top_p: draft.topP,
    presence_penalty: draft.presencePenalty,
    frequency_penalty: draft.frequencyPenalty,
    max_tokens: draft.maxTokens,
    reasoning_effort: draft.reasoningEffort,
    search_depth_k: draft.searchDepthK,
    rerank_top_n: draft.rerankTopN,
    min_score: draft.minScore,
    vector_weight: draft.vectorWeight,
    vector_similarity_threshold: draft.vectorSimilarityThreshold,
    keyword_relevance_threshold: draft.keywordRelevanceThreshold,
    vector_top_k: draft.vectorTopK,
    keyword_top_k: draft.keywordTopK,
    enable_rerank: draft.enableRerank,
    rerank_model: draft.enableRerank ? draft.rerankModelId || null : null,
    reasoning_mode: draft.reasoningMode,
    enable_persistent_context: draft.persistentContextEnabled,
    ...(draft.queryRewriteMode === 'inherit'
      ? {}
      : { enable_query_rewrite: draft.queryRewriteMode === 'enabled' }),
    enable_synonym_rewrite: draft.synonymRewriteEnabled,
    auto_filter_mode: draft.autoFilterMode,
    enable_llm_filter_expression: draft.enableLlmFilterExpression,
    llm_candidate_min_confidence: draft.llmCandidateMinConfidence,
    llm_upgrade_confidence_threshold: draft.llmUpgradeConfidenceThreshold,
    llm_max_upgrade_count: draft.llmMaxUpgradeCount,
    hierarchical_retrieval_mode: draft.hierarchicalRetrievalMode,
    neighbor_window_size: draft.neighborWindowSize,
    enable_parent_context: draft.enableParentContext,
    group_by_content_group: draft.groupByContentGroup,
    enable_filter_inheritance: draft.filterInheritanceEnabled,
    enable_filter_inheritance_evaluation: draft.filterInheritanceEvaluationEnabled,
    query_rewrite_context: draft.queryRewriteContext
      .map((item) => ({
        role: item.role,
        content: String(item.content || '').trim(),
      }))
      .filter((item) => item.content.length > 0),
  }
}

function buildRuntimeKnowledgeBaseBindings(draft: ChatConfigDraft): Array<Record<string, any>> {
  return draft.selectedKnowledgeBaseIds.map((knowledgeBaseId, index) => ({
    kb_id: knowledgeBaseId,
    binding_role: index === 0 ? 'primary' : 'secondary',
    is_enabled: true,
    priority: 100 + index,
    config: buildKnowledgeBaseBindingConfig(
      draft.knowledgeBaseScopes[knowledgeBaseId] || {
        kbDocIds: [],
        folderIds: [],
        folderTagIds: [],
        includeDescendantFolders: true,
        tagIds: [],
        metadata: {},
        filterExpressionText: '',
      }
    ),
  }))
}

function buildRuntimeChatConfigOverride(draft: ChatConfigDraft): Record<string, any> {
  return {
    ...buildPersistedChatConfigOverride(draft),
    runtime_knowledge_base_bindings_enabled: true,
    runtime_knowledge_base_bindings: buildRuntimeKnowledgeBaseBindings(draft),
  }
}

function serializeChatConfigDraft(draft: ChatConfigDraft): string {
  return JSON.stringify({
    ...draft,
    queryRewriteContext: (draft.queryRewriteContext || []).map((item) => ({
      role: item.role,
      content: String(item.content || '').trim(),
    })),
    selectedKnowledgeBaseIds: [...draft.selectedKnowledgeBaseIds].sort(),
    knowledgeBaseScopes: Object.fromEntries(
      Object.entries(draft.knowledgeBaseScopes || {})
        .sort(([left], [right]) => left.localeCompare(right))
        .map(([kbId, scope]) => [
          kbId,
          {
            ...scope,
            kbDocIds: [...(scope.kbDocIds || [])].sort(),
            folderIds: [...(scope.folderIds || [])].sort(),
            folderTagIds: [...(scope.folderTagIds || [])].sort(),
            tagIds: [...(scope.tagIds || [])].sort(),
            metadata: Object.fromEntries(
              Object.entries(scope.metadata || {}).sort(([left], [right]) => left.localeCompare(right))
            ),
            filterExpressionText: String(scope.filterExpressionText || '').trim(),
          },
        ])
    ),
  })
}

function parseKnowledgeBaseFilterExpression(value?: string): Record<string, any> | null {
  const text = String(value || '').trim()
  if (!text) {
    return null
  }
  const parsed = JSON.parse(text)
  if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
    throw new Error('知识库过滤表达式必须是 JSON 对象')
  }
  return parsed as Record<string, any>
}

function validateKnowledgeBaseScopeExpressions(
  draft: ChatConfigDraft,
  knowledgeBaseOptions: Array<{ id: string; name: string }>
): void {
  if (draft.enableRerank && !String(draft.rerankModelId || '').trim()) {
    throw new Error('已开启重排序，请先选择一个 rerank 模型')
  }
  if (draft.llmCandidateMinConfidence < 0 || draft.llmCandidateMinConfidence > 1) {
    throw new Error('LLM 最小置信度必须在 0 到 1 之间')
  }
  if (draft.llmUpgradeConfidenceThreshold < 0 || draft.llmUpgradeConfidenceThreshold > 1) {
    throw new Error('硬过滤升级阈值必须在 0 到 1 之间')
  }
  if (draft.llmMaxUpgradeCount < 1 || draft.llmMaxUpgradeCount > 8) {
    throw new Error('最大升级数量必须在 1 到 8 之间')
  }
  const invalidContext = (draft.queryRewriteContext || []).find(
    (item) => String(item.content || '').trim().length === 0
  )
  if (invalidContext) {
    throw new Error('查询改写上下文中存在空内容，请补全或删除该条消息')
  }
  const nameMap = new Map(knowledgeBaseOptions.map((item) => [item.id, item.name]))
  for (const kbId of draft.selectedKnowledgeBaseIds) {
    const scope = draft.knowledgeBaseScopes?.[kbId]
    const text = String(scope?.filterExpressionText || '').trim()
    if (!text) {
      continue
    }
    try {
      parseKnowledgeBaseFilterExpression(text)
    }
    catch (error) {
      const kbName = nameMap.get(kbId) || kbId
      const message = error instanceof Error ? error.message : '过滤表达式配置无效'
      throw new Error(`知识库“${kbName}”的过滤表达式无效：${message}`)
    }
  }
}

function buildKnowledgeBaseBindingConfig(
  scope: ChatConfigDraft['knowledgeBaseScopes'][string],
  baseConfig: Record<string, any> = {}
): Record<string, any> {
  const nextConfig = { ...(baseConfig || {}) }
  const filters: Record<string, any> = {}
  const folderIds = Array.isArray(scope?.folderIds)
    ? scope.folderIds.filter((item) => typeof item === 'string' && item.trim().length > 0)
    : []
  const kbDocIds = Array.isArray(scope?.kbDocIds)
    ? scope.kbDocIds.filter((item) => typeof item === 'string' && item.trim().length > 0)
    : []
  const folderTagIds = Array.isArray(scope?.folderTagIds)
    ? scope.folderTagIds.filter((item) => typeof item === 'string' && item.trim().length > 0)
    : []
  const tagIds = Array.isArray(scope?.tagIds)
    ? scope.tagIds.filter((item) => typeof item === 'string' && item.trim().length > 0)
    : []
  const metadata =
    scope?.metadata && typeof scope.metadata === 'object'
      ? Object.fromEntries(
          Object.entries(scope.metadata)
            .map(([key, value]) => [key, String(value || '').trim()])
            .filter(([key, value]) => key.trim().length > 0 && value.length > 0)
        )
      : {}
  const filterExpression = parseKnowledgeBaseFilterExpression(scope?.filterExpressionText)

  if (kbDocIds.length > 0) {
    filters.kb_doc_ids = kbDocIds
  }
  if (folderIds.length > 0) {
    filters.folder_ids = folderIds
  }
  if (folderTagIds.length > 0) {
    filters.folder_tag_ids = folderTagIds
  }
  if (tagIds.length > 0) {
    filters.tag_ids = tagIds
  }
  if (Object.keys(metadata).length > 0) {
    filters.metadata = metadata
  }
  if (filterExpression) {
    filters.filter_expression = filterExpression
  }
  if (folderIds.length > 0 || folderTagIds.length > 0) {
    filters.include_descendant_folders = scope?.includeDescendantFolders !== false
  }

  if (Object.keys(filters).length > 0) {
    nextConfig.filters = filters
  } else {
    delete nextConfig.filters
  }
  return nextConfig
}
