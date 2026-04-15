/**
 * 文件夹树组件 - 主入口
 * 
 * 功能：
 * - 显示文件夹树形结构
 * - 创建、编辑、删除文件夹
 * - 添加标签和摘要
 * - 展开/折叠节点
 */
import React, { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Folder, FolderPlus } from 'lucide-react'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import {
  fetchFolderTree,
  createFolder,
  updateFolder,
  deleteFolder,
  fetchFolderTags,
} from '@/lib/api/folder'
import type { Tag, TagTargetType } from '@/lib/api/folder.types'
import { createTag, updateTag } from '@/lib/api/tag'
import { useFolderAvailableTags } from '@/hooks/use-available-tags'
import { FolderTreeNode } from './folder-tree-node'
import { FolderTreeDialog } from './folder-tree-dialog'
import { TagDetailSheet } from './tag-detail-sheet'
import { FolderTreeViewDialog } from './folder-tree-view-dialog'
import { FolderTreeDeleteDialog } from './folder-tree-delete-dialog'
import type {
  FolderTreeProps,
  FolderFormData,
  TagFormData,
  TagDefinition,
} from './folder-tree-types'
import type { FolderTreeNode as FolderTreeNodeType } from '@/lib/api/folder.types'

export function FolderTree({
  kbId,
  selectedFolderId,
  onSelectFolder,
  canCreate = true,
  canEdit = true,
  canDelete = true,
}: FolderTreeProps) {
  const queryClient = useQueryClient()
  const [expandedFolders, setExpandedFolders] = useState<Set<string>>(new Set())
  const [createDialogOpen, setCreateDialogOpen] = useState(false)
  const [editDialogOpen, setEditDialogOpen] = useState(false)
  const [tagDetailSheetOpen, setTagDetailSheetOpen] = useState(false)
  const [viewDialogOpen, setViewDialogOpen] = useState(false)
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false)
  const [currentFolder, setCurrentFolder] = useState<FolderTreeNodeType | null>(null)
  const [parentFolder, setParentFolder] = useState<FolderTreeNodeType | null>(null)

  // 文件夹表单数据
  const [folderForm, setFolderForm] = useState<FolderFormData>({
    name: '',
    summary: '',
    tags: [],
  })

  // 标签表单数据
  const [tagForm, setTagForm] = useState<TagFormData>({
    name: '',
    description: '',
    synonyms: [],
    color: 'blue',
    allowedTargetTypes: ['folder'],
  })

  // 正在编辑的标签
  const [editingTag, setEditingTag] = useState<TagDefinition | null>(null)

  // 当前文件夹的完整标签数据（包含颜色、描述等）
  const [currentFolderTags, setCurrentFolderTags] = useState<Tag[]>([])

  // 标签输入
  const [newTag, setNewTag] = useState('')
  const [newSynonym, setNewSynonym] = useState('')

  // 获取文件夹树
  const { data: folderTree = [], isLoading } = useQuery({
    queryKey: ['folders', 'tree', kbId],
    queryFn: () => fetchFolderTree(kbId),
    enabled: !!kbId,
  })

  // 获取文件夹可选标签（用于标签选择）
  const { data: folderTags = [] } = useFolderAvailableTags(kbId, { limit: 200 })

  // 转换标签数据格式
  const tagDefinitions: TagDefinition[] = React.useMemo(() => {
    if (!folderTags || !Array.isArray(folderTags)) return []
    return folderTags.map((tag: Tag) => ({
      id: tag.id,
      name: tag.name,
      description: tag.description,
      color: tag.color || 'blue', // 使用后端返回的颜色，如果没有则默认蓝色
      synonyms: tag.aliases,
      allowedTargetTypes: tag.allowed_target_types,
    }))
  }, [folderTags])

  // 创建文件夹
  const { mutate: handleCreate, isPending: isCreating } = useMutation({
    mutationFn: createFolder,
    onSuccess: async (newFolder) => {
      queryClient.invalidateQueries({ queryKey: ['folders', 'tree', kbId] })
      
      // 刷新文档查询缓存，因为文档包含文件夹信息
      queryClient.invalidateQueries({ 
        queryKey: ['kb-documents', kbId], 
        exact: false
      })
      
      toast.success('文件夹创建成功')
      setCreateDialogOpen(false)
      resetForm()

      if (parentFolder) {
        setExpandedFolders((prev) => new Set([...prev, parentFolder.id]))
      }
      setExpandedFolders((prev) => new Set([...prev, newFolder.id]))
      onSelectFolder?.(newFolder.id)
      setParentFolder(null)
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || '创建失败')
    },
  })

  // 更新文件夹
  const { mutateAsync: updateFolderAsync, isPending: isUpdating } = useMutation({
    mutationFn: ({ id, data }: { id: string; data: any }) => updateFolder(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['folders', 'tree', kbId] })
      
      // 刷新文档查询缓存，因为文档包含文件夹信息
      queryClient.invalidateQueries({ 
        queryKey: ['kb-documents', kbId], 
        exact: false
      })
      
      toast.success('文件夹更新成功')
      setEditDialogOpen(false)
      resetForm()
      setCurrentFolder(null)
    },
    onError: (error: any) => {
      console.error('更新失败:', error)
      toast.error(error.response?.data?.detail || '更新失败，请重试')
    },
  })

  // 删除文件夹
  const { mutate: handleDelete, isPending: isDeleting } = useMutation({
    mutationFn: deleteFolder,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['folders', 'tree', kbId] })
      
      // 刷新文档查询缓存，因为文档包含文件夹信息
      queryClient.invalidateQueries({ 
        queryKey: ['kb-documents', kbId], 
        exact: false
      })
      
      toast.success('文件夹删除成功')
      setDeleteDialogOpen(false)
      setCurrentFolder(null)
      if (selectedFolderId === currentFolder?.id) {
        onSelectFolder?.(null)
      }
    },
    onError: (error: any) => {
      const errorMsg = error.response?.data?.detail || '删除失败'
      if (errorMsg.includes('包含文档')) {
        toast.error(errorMsg, {
          duration: 6000,
          style: { whiteSpace: 'pre-line' },
        })
      } else {
        toast.error(errorMsg)
      }
    },
  })

  // 创建标签
  const { mutate: handleCreateTag, isPending: isCreatingTag } = useMutation({
    mutationFn: createTag,
    onSuccess: async (tag) => {
      await queryClient.invalidateQueries({ queryKey: ['tags', 'list', kbId] })
      await queryClient.invalidateQueries({ queryKey: ['tags', 'available', kbId] })
      
      // 强制刷新文档查询缓存，确保标签更新后界面同步
      await queryClient.invalidateQueries({ 
        queryKey: ['kb-documents', kbId], 
        exact: false  // 匹配所有以此开头的查询键
      })
      
      toast.success('标签创建成功')
      setTagDetailSheetOpen(false)

      // 确保新标签名在文件夹表单中（如果之前没在的话）
      setFolderForm((prev) => {
        if (!prev.tags.includes(tag.name)) {
          return { ...prev, tags: [...prev.tags, tag.name] }
        }
        return prev
      })

      // 确保标签完整数据在当前文件夹标签列表中
      setCurrentFolderTags((prev) => {
        const exists = prev.some((t) => t.id === tag.id || t.name === tag.name)
        if (exists) {
          return prev.map((t) => (t.id === tag.id || t.name === tag.name ? tag : t))
        }
        return [...prev, tag]
      })

      resetTagForm()
    },
    onError: (error: any) => {
      console.error('创建标签失败:', error)
      // toast.error(error.response?.data?.detail || '创建标签失败')  不要展示，因为已经全局处理了
    },
  })

  // 更新标签
  const { mutate: handleUpdateTag, isPending: isUpdatingTag } = useMutation({
    mutationFn: ({ id, data }: { id: string; data: any }) => updateTag(id, data),
    onSuccess: (updatedTag) => {
      queryClient.invalidateQueries({ queryKey: ['tags', 'list', kbId] })
      queryClient.invalidateQueries({ queryKey: ['tags', 'available', kbId] })
      
      // 强制刷新文档查询缓存，确保标签更新后界面同步
      queryClient.invalidateQueries({ 
        queryKey: ['kb-documents', kbId], 
        exact: false  // 匹配所有以此开头的查询键
      })
      
      toast.success('标签更新成功')
      setTagDetailSheetOpen(false)

      // 更新当前文件夹完整标签列表中的对应项
      setCurrentFolderTags((prev) => {
        const index = prev.findIndex((t) => t.id === updatedTag.id)
        if (index > -1) {
          const next = [...prev]
          next[index] = updatedTag
          return next
        }
        // 如果原本不在列表中（比如刚通过名称快速添加），则补全完整数据
        return [...prev, updatedTag]
      })

      resetTagForm()
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || '更新标签失败')
    },
  })

  // 切换展开/折叠
  const toggleExpand = (folderId: string) => {
    setExpandedFolders((prev) => {
      const next = new Set(prev)
      if (next.has(folderId)) {
        next.delete(folderId)
      } else {
        next.add(folderId)
      }
      return next
    })
  }

  // 重置表单
  const resetForm = () => {
    setFolderForm({
      name: '',
      summary: '',
      tags: [],
    })
    setNewTag('')
    setCurrentFolderTags([])
  }

  // 重置标签表单
  const resetTagForm = (defaultTargetType: TagTargetType = 'folder') => {
    setTagForm({
      name: '',
      description: '',
      synonyms: [],
      color: 'blue',
      allowedTargetTypes: [defaultTargetType],
    })
    setNewSynonym('')
    setEditingTag(null)
  }

  // 打开创建对话框
  const openCreateDialog = (parent?: FolderTreeNodeType) => {
    if (!parent && selectedFolderId) {
      const findFolder = (
        folders: FolderTreeNodeType[],
        id: string
      ): FolderTreeNodeType | null => {
        for (const folder of folders) {
          if (folder.id === id) return folder
          if (folder.children) {
            const found = findFolder(folder.children, id)
            if (found) return found
          }
        }
        return null
      }
      const selectedFolder = findFolder(folderTree, selectedFolderId)
      setParentFolder(selectedFolder || null)
    } else {
      setParentFolder(parent || null)
    }
    resetForm()
    setCreateDialogOpen(true)
  }

  // 打开编辑对话框
  const openEditDialog = async (folder: FolderTreeNodeType) => {
    setCurrentFolder(folder)
    try {
      const tagsData = await fetchFolderTags(folder.id)
      setCurrentFolderTags(tagsData.tags)
      setFolderForm({
        name: folder.name,
        summary: folder.summary || '',
        tags: tagsData.tags.map((t) => t.name),
      })
    } catch (error) {
      console.error('获取文件夹标签失败:', error)
      setCurrentFolderTags([])
      setFolderForm({
        name: folder.name,
        summary: folder.summary || '',
        tags: [],
      })
    }
    setEditDialogOpen(true)
  }

  // 打开查看对话框
  const openViewDialog = async (folder: FolderTreeNodeType) => {
    setCurrentFolder(folder)
    try {
      const tagsData = await fetchFolderTags(folder.id)
      setCurrentFolderTags(tagsData.tags)
      setFolderForm({
        name: folder.name,
        summary: folder.summary || '',
        tags: tagsData.tags.map((t) => t.name),
      })
    } catch (error) {
      console.error('获取文件夹标签失败:', error)
      setCurrentFolderTags([])
      setFolderForm({
        name: folder.name,
        summary: folder.summary || '',
        tags: [],
      })
    }
    setViewDialogOpen(true)
  }

  // 打开删除对话框
  const openDeleteDialog = (folder: FolderTreeNodeType) => {
    setCurrentFolder(folder)
    setDeleteDialogOpen(true)
  }

  // 添加标签（快速添加）
  const handleAddTag = () => {
    if (!newTag.trim()) {
      toast.error('请输入标签名称')
      return
    }

    const tagName = newTag.trim()

    // 检查是否已在当前文件夹的标签列表中
    if (folderForm.tags.includes(tagName)) {
      toast.info('标签已添加到当前文件夹')
      setNewTag('')
      return
    }

    // 检查标签是否在知识库中已存在
    const existingTag = tagDefinitions.find((t) => t.name === tagName)

    // 直接添加标签（无论是否已存在）
    setFolderForm((prev) => ({
      ...prev,
      tags: [...prev.tags, tagName],
    }))

    // 如果是已知标签，同时更新完整数据列表以保持颜色显示
    if (existingTag) {
      const fullTag: Tag = {
        id: existingTag.id,
        tenant_id: '', // 这些字段在前端展示中不常用，可以填空
        name: existingTag.name,
        aliases: existingTag.synonyms,
        description: existingTag.description,
        color: existingTag.color,
        allowed_target_types: existingTag.allowedTargetTypes ?? ['folder'],
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      }
      setCurrentFolderTags((prev) => [...prev, fullTag])
    }

    setNewTag('')

    // 显示不同的提示信息
    if (existingTag) {
      toast.success('已添加标签')
    } else {
      toast.success('已添加新标签')
    }
  }

  // 移除标签
  const handleRemoveTag = (tag: string) => {
    setFolderForm((prev) => ({
      ...prev,
      tags: prev.tags.filter((t) => t !== tag),
    }))
    // 同时从完整数据列表中移除
    setCurrentFolderTags((prev) => prev.filter((t) => t.name !== tag))
  }

  // 添加同义词
  const handleAddSynonym = () => {
    if (!newSynonym.trim()) {
      toast.error('请输入同义词')
      return
    }
    if (tagForm.synonyms.includes(newSynonym.trim())) {
      toast.error('同义词已存在')
      return
    }
    setTagForm((prev) => ({
      ...prev,
      synonyms: [...prev.synonyms, newSynonym.trim()],
    }))
    setNewSynonym('')
  }

  // 移除同义词
  const handleRemoveSynonym = (synonym: string) => {
    setTagForm((prev) => ({
      ...prev,
      synonyms: prev.synonyms.filter((s) => s !== synonym),
    }))
  }

  // 打开标签详细设置
  const handleOpenTagDetail = async (tag?: TagDefinition, tagName?: string) => {
    // 如果传入了 tag 对象，说明是点击已存在的标签
    if (tag) {
      // 先打开侧边栏，显示基本信息
      setEditingTag(tag)
      setTagForm({
        name: tag.name || '',
        description: tag.description || '',
        synonyms: tag.synonyms || [],
        color: tag.color || 'blue',
        allowedTargetTypes: tag.allowedTargetTypes?.length ? tag.allowedTargetTypes : ['folder'],
      })
      setTagDetailSheetOpen(true)

      try {
        // 从后端查询完整的标签数据
        const { fetchTag } = await import('@/lib/api/tag')
        const fullTagData = await fetchTag(tag.id)

        // 使用后端返回的完整数据更新表单
        setEditingTag({
          id: fullTagData.id,
          name: fullTagData.name,
          description: fullTagData.description,
          color: fullTagData.color || 'blue', // 使用后端返回的颜色
          synonyms: fullTagData.aliases || [],
        })
          setTagForm({
            name: fullTagData.name,
            description: fullTagData.description || '',
            synonyms: fullTagData.aliases || [],
            color: fullTagData.color || 'blue', // 使用后端返回的颜色
            allowedTargetTypes: fullTagData.allowed_target_types?.length ? fullTagData.allowed_target_types : ['folder'],
          })
      } catch (error) {
        console.error('获取标签详情失败:', error)
        toast.error('获取标签详情失败，显示的可能不是最新数据')
      }
    } else if (tagName) {
      // 如果只传入了标签名称，检查是否已存在（忽略大小写）
      const tagNameTrimmed = tagName.trim()
      let existingTag = tagDefinitions.find(
        (t) => t.name.toLowerCase() === tagNameTrimmed.toLowerCase()
      )

      if (existingTag) {
        // 如果已存在，则作为编辑模式打开
        return handleOpenTagDetail(existingTag)
      }

      // 如果本地列表没找到（可能是分页或刚从外部新增），调用后端接口精确核对
      try {
        const { checkTagDuplicate } = await import('@/lib/api/tag')
        const result = await checkTagDuplicate(kbId, tagNameTrimmed)
        if (result.exists && result.tag) {
          const matchedTag: TagDefinition = {
            id: result.tag.id,
            name: result.tag.name,
            description: result.tag.description,
            color: result.tag.color || 'blue', // 使用后端返回的颜色
            synonyms: result.tag.aliases || [],
          }
          return handleOpenTagDetail(matchedTag)
        }
      } catch (error) {
        console.error('检查标签重复失败:', error)
      }

      // 如果确实不存在，则是新建标签且带有名
      setTagForm({
        name: tagNameTrimmed,
        description: '',
        synonyms: [],
        color: 'blue',
        allowedTargetTypes: ['folder'],
      })
      setNewSynonym('')
      setEditingTag(null)
      setTagDetailSheetOpen(true)
    } else {
      // 完全新建标签
      resetTagForm()
      setTagDetailSheetOpen(true)
    }
  }

  // 保存标签定义
  const handleSaveTagDefinition = async () => {
    const tagName = tagForm.name.trim()
    if (!tagName) {
      toast.error('请输入标签名称')
      return
    }

    if (editingTag) {
      // 编辑模式 - 调用更新 API
        handleUpdateTag({
          id: editingTag.id,
          data: {
            name: tagName,
            description: tagForm.description.trim() || undefined,
            aliases: tagForm.synonyms.length > 0 ? tagForm.synonyms : undefined,
            color: tagForm.color,
            allowed_target_types: tagForm.allowedTargetTypes,
          },
        })

      // 更新文件夹中的标签列表
      setFolderForm((prev) => {
        // 如果改了名字，且旧名字在列表里，则替换；否则确保新名字在列表里
        const hasOldTag = prev.tags.includes(editingTag.name)
        const hasNewTag = prev.tags.includes(tagName)

        let newTags = [...prev.tags]
        if (hasOldTag) {
          newTags = newTags.map((t) => (t === editingTag.name ? tagName : t))
        } else if (!hasNewTag) {
          newTags.push(tagName)
        }

        // 去重
        return {
          ...prev,
          tags: Array.from(new Set(newTags)),
        }
      })
    } else {
      // 创建模式 - 先检测是否已存在（忽略大小写）
      const tagNameLower = tagName.toLowerCase()
      let existingTag = tagDefinitions.find((t) => t.name.toLowerCase() === tagNameLower)

      // 如果本地没有，为了保险起见，再次核对后端（防止并发或分页遗漏）
      if (!existingTag) {
        try {
          const { checkTagDuplicate } = await import('@/lib/api/tag')
          const result = await checkTagDuplicate(kbId, tagName)
          if (result.exists && result.tag) {
            existingTag = {
              id: result.tag.id,
              name: result.tag.name,
              description: result.tag.description,
              color: result.tag.color || 'blue',
              synonyms: result.tag.aliases || [],
            }
          }
        } catch (error) {
          console.error('保存前校验重复失败:', error)
        }
      }

      if (existingTag) {
        // 如果已存在，直接转为“更新并使用”机制
          handleUpdateTag({
            id: existingTag.id,
            data: {
              name: tagName,
              description: tagForm.description.trim() || undefined,
              aliases: tagForm.synonyms.length > 0 ? tagForm.synonyms : undefined,
              color: tagForm.color,
              allowed_target_types: tagForm.allowedTargetTypes,
            },
          })

        if (!folderForm.tags.includes(existingTag.name) && !folderForm.tags.includes(tagName)) {
          setFolderForm((prev) => ({
            ...prev,
            tags: [...prev.tags, tagName],
          }))
        }
        return
      }

      // 真正的新标签
        handleCreateTag({
          name: tagName,
          description: tagForm.description.trim() || undefined,
          aliases: tagForm.synonyms.length > 0 ? tagForm.synonyms : undefined,
          color: tagForm.color,
          allowed_target_types: tagForm.allowedTargetTypes,
          kb_id: kbId,
        })
    }
  }

  // 计算标签保存的加载状态
  const isTagSaving = isCreatingTag || isUpdatingTag

  // 提交创建文件夹
  const submitCreate = async () => {
    if (!folderForm.name.trim()) {
      toast.error('请输入文件夹名称')
      return
    }
    handleCreate({
      name: folderForm.name.trim(),
      summary: folderForm.summary.trim() || undefined,
      kb_id: kbId,
      parent_id: parentFolder?.id,
      tags: folderForm.tags,
    })
  }

  // 提交更新文件夹
  const submitUpdate = async () => {
    if (!currentFolder || !folderForm.name.trim()) {
      toast.error('请输入文件夹名称')
      return
    }
    
    updateFolderAsync({
      id: currentFolder.id,
      data: {
        name: folderForm.name.trim(),
        summary: folderForm.summary.trim() || undefined,
        tags: folderForm.tags,
      },
    })
  }

  // 提交删除
  const submitDelete = () => {
    if (!currentFolder) return
    handleDelete(currentFolder.id)
  }

  if (isLoading) {
    return <div className="p-4 text-sm text-muted-foreground">加载中...</div>
  }

  return (
    <div className="flex flex-col h-full">
      {/* 头部 */}
      <div className="flex items-center justify-between px-4 py-3 border-b bg-muted/30">
        <h3 className="text-sm font-semibold">文件夹</h3>
        {canCreate && (
          <Button
            variant="ghost"
            size="icon"
            className="h-7 w-7 hover:bg-background"
            onClick={() => openCreateDialog()}
            title="新建文件夹"
          >
            <FolderPlus className="h-4 w-4" />
          </Button>
        )}
      </div>

      {/* 文件夹树 */}
      <div className="flex-1 overflow-y-auto p-2">
        {/* 根目录 */}
        <div
          className={cn(
            'flex items-center gap-2 px-3 py-2 rounded-md cursor-pointer mb-1 transition-colors',
            !selectedFolderId
              ? 'bg-blue-50 dark:bg-blue-950/30 border border-blue-200 dark:border-blue-800 font-semibold'
              : 'hover:bg-accent/50 font-medium'
          )}
          onClick={() => onSelectFolder?.(null)}
        >
          <Folder
            className={cn(
              'h-4 w-4 transition-colors',
              !selectedFolderId
                ? 'text-blue-600 dark:text-blue-400'
                : 'text-muted-foreground'
            )}
          />
          <span className={cn(
            'text-sm',
            !selectedFolderId && 'text-blue-700 dark:text-blue-300'
          )}>根目录</span>
        </div>

        {/* 分隔线 */}
        {folderTree.length > 0 && <div className="my-2 border-t" />}

        {/* 文件夹列表 */}
        {folderTree.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-12 text-muted-foreground">
            <Folder className="h-12 w-12 mb-3 opacity-20" />
            <p className="text-sm">暂无文件夹</p>
            {canCreate && (
              <Button
                variant="outline"
                size="sm"
                className="mt-3 gap-2"
                onClick={() => openCreateDialog()}
              >
                <FolderPlus className="h-4 w-4" />
                创建第一个文件夹
              </Button>
            )}
          </div>
        ) : (
          folderTree.map((folder) => (
            <FolderTreeNode
              key={folder.id}
              folder={folder}
              level={0}
              selectedFolderId={selectedFolderId}
              expandedFolders={expandedFolders}
              canCreate={canCreate}
              canEdit={canEdit}
              canDelete={canDelete}
              onToggleExpand={toggleExpand}
              onSelectFolder={onSelectFolder!}
              onCreateChild={openCreateDialog}
              onEdit={openEditDialog}
              onView={openViewDialog}
              onDelete={openDeleteDialog}
            />
          ))
        )}
      </div>

      {/* 创建文件夹对话框 */}
      <FolderTreeDialog
        open={createDialogOpen}
        mode="create"
        folderForm={folderForm}
        newTag={newTag}
        tagDefinitions={tagDefinitions}
        currentFolderTags={currentFolderTags}
        parentFolderName={parentFolder?.name}
        isSubmitting={isCreating}
        onOpenChange={setCreateDialogOpen}
        onFolderFormChange={setFolderForm}
        onNewTagChange={setNewTag}
        onAddTag={handleAddTag}
        onRemoveTag={handleRemoveTag}
        onSelectTag={(tag) => {
          if (!folderForm.tags.includes(tag.name)) {
            // 注意：onFolderFormChange 在 FolderTreeDialog 内部已经调用过一次了，
            // 但这里我们要确保 currentFolderTags 也能更新
            const fullTag: Tag = {
              id: tag.id,
              tenant_id: '',
              name: tag.name,
              aliases: tag.synonyms,
              description: tag.description,
              color: tag.color,
              allowed_target_types: tag.allowedTargetTypes ?? ['folder'],
              created_at: new Date().toISOString(),
              updated_at: new Date().toISOString(),
            }
            setCurrentFolderTags((prev) => [...prev, fullTag])
          }
        }}
        onOpenTagDetail={handleOpenTagDetail}
        onSubmit={submitCreate}
      />

      {/* 编辑文件夹对话框 */}
      <FolderTreeDialog
        open={editDialogOpen}
        mode="edit"
        folderForm={folderForm}
        newTag={newTag}
        tagDefinitions={tagDefinitions}
        currentFolderTags={currentFolderTags}
        isSubmitting={isUpdating}
        onOpenChange={setEditDialogOpen}
        onFolderFormChange={setFolderForm}
        onNewTagChange={setNewTag}
        onAddTag={handleAddTag}
        onRemoveTag={handleRemoveTag}
        onSelectTag={(tag) => {
          if (!folderForm.tags.includes(tag.name)) {
            const fullTag: Tag = {
              id: tag.id,
              tenant_id: '',
              name: tag.name,
              aliases: tag.synonyms,
              description: tag.description,
              color: tag.color,
              allowed_target_types: tag.allowedTargetTypes ?? ['folder'],
              created_at: new Date().toISOString(),
              updated_at: new Date().toISOString(),
            }
            setCurrentFolderTags((prev) => [...prev, fullTag])
          }
        }}
        onOpenTagDetail={handleOpenTagDetail}
        onSubmit={submitUpdate}
      />

      {/* 标签详细设置侧边栏 */}
      <TagDetailSheet
        open={tagDetailSheetOpen}
        tagForm={tagForm}
        newSynonym={newSynonym}
        editingTag={editingTag}
        defaultTargetType='folder'
        onOpenChange={setTagDetailSheetOpen}
        onTagFormChange={setTagForm}
        onNewSynonymChange={setNewSynonym}
        onAddSynonym={handleAddSynonym}
        onRemoveSynonym={handleRemoveSynonym}
        onSaveTagDefinition={handleSaveTagDefinition}
        isLoading={isTagSaving}
      />

      {/* 查看详情 Dialog */}
      <FolderTreeViewDialog
        open={viewDialogOpen}
        folder={currentFolder}
        tags={currentFolderTags}
        tagDefinitions={tagDefinitions}
        canEdit={canEdit}
        onOpenChange={setViewDialogOpen}
        onEdit={() => {
          setViewDialogOpen(false)
          openEditDialog(currentFolder!)
        }}
      />

      {/* 删除确认 Dialog */}
      <FolderTreeDeleteDialog
        open={deleteDialogOpen}
        folder={currentFolder}
        isDeleting={isDeleting}
        onOpenChange={setDeleteDialogOpen}
        onConfirm={submitDelete}
      />
    </div>
  )
}
