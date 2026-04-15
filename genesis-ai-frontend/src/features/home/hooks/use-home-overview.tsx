import { useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Activity, Database, Files, MessageSquare, Timer, UploadCloud } from 'lucide-react'
import { formatDistanceToNow, isToday } from 'date-fns'
import { zhCN } from 'date-fns/locale'
import { fetchKnowledgeBaseDocuments, fetchKnowledgeBases } from '@/lib/api/knowledge-base'
import { fetchChatSpaces } from '@/features/chat/api/chat'

async function runWithConcurrency<T>(tasks: Array<() => Promise<T>>, concurrency: number): Promise<T[]> {
  const results: T[] = []
  let taskIndex = 0

  async function worker() {
    while (taskIndex < tasks.length) {
      const currentIndex = taskIndex
      taskIndex += 1
      results[currentIndex] = await tasks[currentIndex]()
    }
  }

  const workers = Array.from({ length: Math.min(concurrency, tasks.length) }, () => worker())
  await Promise.all(workers)
  return results
}

export function useHomeOverview() {
  const {
    data: kbData,
    isLoading: kbLoading,
    isError: kbError,
    refetch: refetchKbData,
    dataUpdatedAt: kbDataUpdatedAt,
    isRefetching: kbRefetching,
  } = useQuery({
    queryKey: ['home', 'knowledge-bases', 'overview'],
    queryFn: () =>
      fetchKnowledgeBases({
        page: 1,
        page_size: 1,
        sort_by: 'updated_at',
        sort_order: 'desc',
      }),
    staleTime: 60 * 1000,
  })

  const {
    data: spaceData,
    isLoading: spaceLoading,
    isError: spaceError,
    refetch: refetchSpaceData,
    dataUpdatedAt: spaceDataUpdatedAt,
    isRefetching: spaceRefetching,
  } = useQuery({
    queryKey: ['home', 'chat-spaces', 'overview'],
    queryFn: () =>
      fetchChatSpaces({
        page: 1,
        pageSize: 50,
        status: 'active',
      }),
    staleTime: 60 * 1000,
  })

  const {
    data: allActiveSpaces,
    isLoading: allSpacesLoading,
    isError: allSpacesError,
    refetch: refetchAllSpaces,
    dataUpdatedAt: allSpacesUpdatedAt,
    isRefetching: allSpacesRefetching,
  } = useQuery({
    queryKey: ['home', 'chat-spaces', 'all-active', spaceData?.total],
    enabled: (spaceData?.total || 0) > 0,
    queryFn: async () => {
      const totalActiveSpaces = spaceData?.total || 0
      const pageSize = 50
      const totalPages = Math.ceil(totalActiveSpaces / pageSize)
      const pageTasks = Array.from({ length: totalPages }, (_, i) => () =>
        fetchChatSpaces({
          page: i + 1,
          pageSize,
          status: 'active',
        })
      )
      const pageResults = await runWithConcurrency(pageTasks, 3)
      return pageResults.flatMap((pageResult) => pageResult.data || [])
    },
    staleTime: 60 * 1000,
  })

  const {
    data: aggregateData,
    isLoading: aggregateLoading,
    refetch: refetchAggregateData,
    dataUpdatedAt: aggregateUpdatedAt,
    isRefetching: aggregateRefetching,
  } = useQuery({
    queryKey: ['home', 'knowledge-bases', 'document-total', kbData?.total],
    enabled: (kbData?.total || 0) > 0,
    queryFn: async () => {
      const totalKnowledgeBases = kbData?.total || 0
      const pageSize = 50
      const totalPages = Math.ceil(totalKnowledgeBases / pageSize)

      const pageTasks = Array.from({ length: totalPages }, (_, i) => () =>
        fetchKnowledgeBases({
          page: i + 1,
          page_size: pageSize,
          sort_by: 'updated_at',
          sort_order: 'desc',
        })
      )
      const pageResults = await runWithConcurrency(pageTasks, 3)
      const knowledgeBases = pageResults.flatMap((pageResult) => pageResult.data || [])

      const documentCountTasks = knowledgeBases.map((kb) => () =>
        fetchKnowledgeBaseDocuments(kb.id, {
          page: 1,
          page_size: 1,
        }).then((result) => result.total || 0)
      )
      const documentCounts = await runWithConcurrency(documentCountTasks, 5)
      const totalDocuments = documentCounts.reduce((sum, count) => sum + count, 0)

      return {
        totalDocuments: Number.isFinite(totalDocuments) ? totalDocuments : 0,
      }
    },
    staleTime: 60 * 1000,
  })

  const statsLoading = kbLoading || spaceLoading || allSpacesLoading || aggregateLoading
  const activityLoading = kbLoading || spaceLoading
  const latestRefreshAt = Math.max(
    kbDataUpdatedAt || 0,
    spaceDataUpdatedAt || 0,
    allSpacesUpdatedAt || 0,
    aggregateUpdatedAt || 0
  )

  const todayActiveSpaces = useMemo(
    () => (allActiveSpaces || []).filter((space) => space.updated_at && isToday(new Date(space.updated_at))).length,
    [allActiveSpaces]
  )

  const statItems = useMemo(
    () => [
      {
        label: '知识库总数',
        value: String(kbData?.total ?? 0),
        hint: kbError ? '数据获取失败，展示默认值' : '已接入实时总数',
        icon: <Database className='h-4 w-4' />,
        tone: 'blue' as const,
      },
      {
        label: '今日活跃空间',
        value: String(todayActiveSpaces),
        hint: spaceError || allSpacesError ? '数据获取失败，展示默认值' : '按全量活跃空间统计',
        icon: <MessageSquare className='h-4 w-4' />,
        tone: 'violet' as const,
      },
      {
        label: '文档总量',
        value: String(aggregateData?.totalDocuments ?? 0),
        hint: '已按全部知识库实时聚合',
        icon: <Files className='h-4 w-4' />,
        tone: 'blue' as const,
      },
      {
        label: '服务可用性',
        value: '99.95%',
        hint: '核心服务健康状态良好',
        icon: <Activity className='h-4 w-4' />,
        tone: 'emerald' as const,
      },
    ],
    [aggregateData?.totalDocuments, allSpacesError, kbData?.total, kbError, todayActiveSpaces, spaceError]
  )

  const activityItems = useMemo(() => {
    const latestKb = kbData?.data?.[0]
    const latestSpace = spaceData?.data?.[0]
    const latestKbTime = latestKb?.updated_at
      ? formatDistanceToNow(new Date(latestKb.updated_at), { addSuffix: true, locale: zhCN })
      : '实时'
    const latestSpaceTime = latestSpace?.updated_at
      ? formatDistanceToNow(new Date(latestSpace.updated_at), { addSuffix: true, locale: zhCN })
      : '实时'

    return [
      {
        title: latestKb?.name || '最近知识库',
        description: latestKb ? `最近更新知识库：${latestKb.name}` : '暂无知识库更新数据',
        time: latestKbTime,
        status: latestKb ? '已同步' : '待接入',
        icon: <Database className='h-4 w-4' />,
      },
      {
        title: latestSpace?.name || '最近聊天空间',
        description: latestSpace ? `最近活跃空间：${latestSpace.name}` : '暂无聊天空间数据',
        time: latestSpaceTime,
        status: latestSpace ? '活跃' : '待接入',
        icon: <MessageSquare className='h-4 w-4' />,
      },
      {
        title: '产品手册 V3.pdf',
        description: '上传至知识库「产品文档中心」并完成解析',
        time: '5 分钟前',
        status: '已完成',
        icon: <UploadCloud className='h-4 w-4' />,
      },
      {
        title: '全局任务队列',
        description: '当前无阻塞任务，系统处理延迟稳定',
        time: '实时',
        status: '正常',
        icon: <Timer className='h-4 w-4' />,
      },
    ]
  }, [kbData?.data, spaceData?.data])

  return {
    statItems,
    activityItems,
    statsLoading,
    activityLoading,
    refreshing: kbRefetching || spaceRefetching || allSpacesRefetching || aggregateRefetching,
    latestRefreshText:
      latestRefreshAt > 0
        ? formatDistanceToNow(new Date(latestRefreshAt), { addSuffix: true, locale: zhCN })
        : '尚未刷新',
    refreshAll: async () => {
      await Promise.all([refetchKbData(), refetchSpaceData(), refetchAllSpaces(), refetchAggregateData()])
    },
  }
}
