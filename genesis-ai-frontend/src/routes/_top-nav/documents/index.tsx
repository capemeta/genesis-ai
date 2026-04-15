import { createFileRoute } from '@tanstack/react-router'
import { useState } from 'react'
import { 
  FileText, 
  Upload, 
  Search, 
  Filter,
  FolderOpen,
  Clock,
  User,
  MoreVertical,
  Download,
  Trash2,
  Eye,
  ChevronRight,
  Folder,
  File,
  Database,
  PanelLeftClose,
  PanelLeft,
} from 'lucide-react'
import { Card, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Separator } from '@/components/ui/separator'
import { cn } from '@/lib/utils'

export const Route = createFileRoute('/_top-nav/documents/')({
  component: DocumentsPage,
})

// 文件夹树节点类型
interface FolderNode {
  id: string
  name: string
  level: number
  children?: FolderNode[]
  documentCount: number
}

// 文档类型
interface Document {
  id: string
  name: string
  type: 'PDF' | 'DOCX' | 'TXT' | 'Markdown' | 'Excel' | 'PPT'
  size: string
  folderId: string
  folderPath: string
  uploadedBy: string
  uploadedAt: string
  status: '已完成' | '处理中' | '失败'
  tags: string[]
  kbReferences: Array<{ id: string; name: string }>  // 被哪些知识库引用
}

function DocumentsPage() {
  const [isFolderTreeCollapsed, setIsFolderTreeCollapsed] = useState(false)
  const [selectedFolderId, setSelectedFolderId] = useState<string | null>(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedDocument, setSelectedDocument] = useState<Document | null>(null)
  const [showKBReferencesDialog, setShowKBReferencesDialog] = useState(false)

  // 切换文件夹树显示/隐藏
  const toggleFolderTree = () => {
    setIsFolderTreeCollapsed(!isFolderTreeCollapsed)
  }

  // 选择文件夹
  const handleSelectFolder = (folderId: string | null) => {
    setSelectedFolderId(folderId)
  }

  // 查看知识库引用
  const handleViewKBReferences = (doc: Document) => {
    setSelectedDocument(doc)
    setShowKBReferencesDialog(true)
  }

  // 获取当前文件夹路径
  const getCurrentFolderPath = () => {
    if (!selectedFolderId) return '全部文档'
    const folder = findFolderById(mockFolders, selectedFolderId)
    return folder?.name || '全部文档'
  }

  // 过滤文档
  const filteredDocuments = mockDocuments.filter(doc => {
    // 文件夹过滤
    if (selectedFolderId && doc.folderId !== selectedFolderId) {
      return false
    }
    // 搜索过滤
    if (searchQuery && !doc.name.toLowerCase().includes(searchQuery.toLowerCase())) {
      return false
    }
    return true
  })

  return (
    <div className='flex h-[calc(100vh-4rem)] overflow-hidden'>
      {/* 左侧文件夹树 */}
      <div
        className={cn(
          'border-r bg-muted/30 transition-all duration-300',
          isFolderTreeCollapsed ? 'w-0' : 'w-64'
        )}
      >
        {!isFolderTreeCollapsed && (
          <div className='flex h-full flex-col'>
            <div className='flex items-center justify-between border-b px-4 py-3'>
              <h3 className='font-semibold'>文件夹</h3>
              <Button
                variant='ghost'
                size='icon'
                className='h-7 w-7'
                onClick={toggleFolderTree}
              >
                <PanelLeftClose className='h-4 w-4' />
              </Button>
            </div>
            <ScrollArea className='flex-1'>
              <div className='p-2'>
                {/* 全部文档 */}
                <div
                  className={cn(
                    'flex items-center gap-2 rounded-md px-3 py-2 text-sm cursor-pointer hover:bg-accent',
                    !selectedFolderId && 'bg-accent'
                  )}
                  onClick={() => handleSelectFolder(null)}
                >
                  <FolderOpen className='h-4 w-4 text-muted-foreground' />
                  <span className='flex-1'>全部文档</span>
                  <Badge variant='secondary' className='text-xs'>
                    {mockDocuments.length}
                  </Badge>
                </div>

                <Separator className='my-2' />

                {/* 文件夹树 */}
                <FolderTree
                  folders={mockFolders}
                  selectedFolderId={selectedFolderId}
                  onSelectFolder={handleSelectFolder}
                />
              </div>
            </ScrollArea>
          </div>
        )}
      </div>

      {/* 右侧主内容区 */}
      <div className='flex flex-1 flex-col overflow-hidden'>
        {/* 顶部工具栏 */}
        <div className='border-b bg-background px-6 py-4'>
          <div className='flex items-center justify-between mb-4'>
            <div className='flex items-center gap-3'>
              {isFolderTreeCollapsed && (
                <Button
                  variant='outline'
                  size='icon'
                  onClick={toggleFolderTree}
                >
                  <PanelLeft className='h-4 w-4' />
                </Button>
              )}
              <div>
                <h1 className='text-2xl font-bold flex items-center gap-2'>
                  <FileText className='h-6 w-6 text-primary' />
                  {getCurrentFolderPath()}
                </h1>
                <p className='text-sm text-muted-foreground mt-1'>
                  共 {filteredDocuments.length} 个文档
                </p>
              </div>
            </div>
            <Button size='lg' className='gap-2'>
              <Upload className='h-4 w-4' />
              上传文档
            </Button>
          </div>

          {/* 搜索和筛选 */}
          <div className='flex items-center gap-3'>
            <div className='relative flex-1'>
              <Search className='absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground' />
              <Input
                placeholder='搜索文档名称...'
                className='pl-10'
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
              />
            </div>
            <Button variant='outline' className='gap-2'>
              <Filter className='h-4 w-4' />
              筛选
            </Button>
          </div>
        </div>

        {/* 文档列表 */}
        <ScrollArea className='flex-1'>
          <div className='p-6'>
            <Card>
              <CardContent className='p-0'>
                {/* 表头 */}
                <div className='grid grid-cols-12 gap-4 border-b bg-muted/50 px-4 py-3 text-sm font-medium text-muted-foreground'>
                  <div className='col-span-4'>文档名称</div>
                  <div className='col-span-2'>所在文件夹</div>
                  <div className='col-span-1'>大小</div>
                  <div className='col-span-1 text-center'>引用数</div>
                  <div className='col-span-2'>上传信息</div>
                  <div className='col-span-1'>状态</div>
                  <div className='col-span-1 text-right'>操作</div>
                </div>

                {/* 文档列表 */}
                <div className='divide-y'>
                  {filteredDocuments.length === 0 ? (
                    <div className='flex flex-col items-center justify-center py-12 text-muted-foreground'>
                      <FileText className='h-12 w-12 mb-3 opacity-50' />
                      <p>暂无文档</p>
                    </div>
                  ) : (
                    filteredDocuments.map((doc) => (
                      <div
                        key={doc.id}
                        className='grid grid-cols-12 gap-4 px-4 py-3 hover:bg-muted/50 transition-colors items-center'
                      >
                        {/* 文档名称 */}
                        <div className='col-span-4 flex items-center gap-3'>
                          <div className={cn(
                            'flex h-10 w-10 items-center justify-center rounded-lg flex-shrink-0',
                            getFileIconBg(doc.type)
                          )}>
                            {getFileIcon(doc.type)}
                          </div>
                          <div className='min-w-0 flex-1'>
                            <div className='font-medium truncate'>{doc.name}</div>
                            {doc.tags.length > 0 && (
                              <div className='flex gap-1 mt-1'>
                                {doc.tags.slice(0, 2).map((tag, index) => (
                                  <Badge key={index} variant='secondary' className='text-xs'>
                                    {tag}
                                  </Badge>
                                ))}
                                {doc.tags.length > 2 && (
                                  <Badge variant='secondary' className='text-xs'>
                                    +{doc.tags.length - 2}
                                  </Badge>
                                )}
                              </div>
                            )}
                          </div>
                        </div>

                        {/* 所在文件夹 */}
                        <div className='col-span-2 flex items-center gap-1 text-sm text-muted-foreground'>
                          <Folder className='h-3 w-3' />
                          <span className='truncate'>{doc.folderPath}</span>
                        </div>

                        {/* 大小 */}
                        <div className='col-span-1 text-sm text-muted-foreground'>
                          {doc.size}
                        </div>

                        {/* 引用数 */}
                        <div className='col-span-1 text-center'>
                          <Button
                            variant='ghost'
                            size='sm'
                            className='h-7 px-2 gap-1'
                            onClick={() => handleViewKBReferences(doc)}
                          >
                            <Database className='h-3 w-3' />
                            <span className='font-medium'>{doc.kbReferences.length}</span>
                          </Button>
                        </div>

                        {/* 上传信息 */}
                        <div className='col-span-2 text-sm text-muted-foreground'>
                          <div className='flex items-center gap-1'>
                            <User className='h-3 w-3' />
                            <span>{doc.uploadedBy}</span>
                          </div>
                          <div className='flex items-center gap-1 mt-0.5'>
                            <Clock className='h-3 w-3' />
                            <span>{doc.uploadedAt}</span>
                          </div>
                        </div>

                        {/* 状态 */}
                        <div className='col-span-1'>
                          <Badge
                            variant={
                              doc.status === '已完成'
                                ? 'default'
                                : doc.status === '处理中'
                                ? 'secondary'
                                : 'destructive'
                            }
                          >
                            {doc.status}
                          </Badge>
                        </div>

                        {/* 操作 */}
                        <div className='col-span-1 flex justify-end'>
                          <DropdownMenu>
                            <DropdownMenuTrigger asChild>
                              <Button variant='ghost' size='icon' className='h-8 w-8'>
                                <MoreVertical className='h-4 w-4' />
                              </Button>
                            </DropdownMenuTrigger>
                            <DropdownMenuContent align='end'>
                              <DropdownMenuItem className='gap-2'>
                                <Eye className='h-4 w-4' />
                                预览
                              </DropdownMenuItem>
                              <DropdownMenuItem className='gap-2'>
                                <Download className='h-4 w-4' />
                                下载
                              </DropdownMenuItem>
                              <DropdownMenuItem 
                                className='gap-2'
                                onClick={() => handleViewKBReferences(doc)}
                              >
                                <Database className='h-4 w-4' />
                                查看引用
                              </DropdownMenuItem>
                              <DropdownMenuSeparator />
                              <DropdownMenuItem className='gap-2 text-destructive focus:text-destructive'>
                                <Trash2 className='h-4 w-4' />
                                删除
                              </DropdownMenuItem>
                            </DropdownMenuContent>
                          </DropdownMenu>
                        </div>
                      </div>
                    ))
                  )}
                </div>
              </CardContent>
            </Card>

            {/* 功能说明 */}
            <div className='mt-6'>
              <Card className='border-dashed'>
                <CardContent className='pt-6'>
                  <div className='text-center text-muted-foreground'>
                    <p className='text-sm'>
                      💡 <strong>功能开发中</strong>：文档上传、预览、批量操作、高级搜索等功能即将上线
                    </p>
                  </div>
                </CardContent>
              </Card>
            </div>
          </div>
        </ScrollArea>
      </div>

      {/* 知识库引用对话框 */}
      <Dialog open={showKBReferencesDialog} onOpenChange={setShowKBReferencesDialog}>
        <DialogContent className='max-w-2xl'>
          <DialogHeader>
            <DialogTitle>知识库引用</DialogTitle>
            <DialogDescription>
              文档 "{selectedDocument?.name}" 被以下知识库引用
            </DialogDescription>
          </DialogHeader>
          <div className='mt-4'>
            {selectedDocument && selectedDocument.kbReferences.length === 0 ? (
              <div className='text-center py-8 text-muted-foreground'>
                <Database className='h-12 w-12 mx-auto mb-3 opacity-50' />
                <p>该文档未被任何知识库引用</p>
              </div>
            ) : (
              <div className='space-y-2'>
                {selectedDocument?.kbReferences.map((kb) => (
                  <div
                    key={kb.id}
                    className='flex items-center justify-between p-3 rounded-lg border hover:bg-muted/50 transition-colors'
                  >
                    <div className='flex items-center gap-3'>
                      <div className='flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10'>
                        <Database className='h-5 w-5 text-primary' />
                      </div>
                      <div>
                        <div className='font-medium'>{kb.name}</div>
                        <div className='text-sm text-muted-foreground'>知识库</div>
                      </div>
                    </div>
                    <Button variant='outline' size='sm'>
                      查看详情
                    </Button>
                  </div>
                ))}
              </div>
            )}
          </div>
        </DialogContent>
      </Dialog>
    </div>
  )
}

// 文件夹树组件
interface FolderTreeProps {
  folders: FolderNode[]
  selectedFolderId: string | null
  onSelectFolder: (folderId: string | null) => void
  level?: number
}

function FolderTree({ folders, selectedFolderId, onSelectFolder, level = 0 }: FolderTreeProps) {
  const [expandedFolders, setExpandedFolders] = useState<Set<string>>(new Set())

  const toggleFolder = (folderId: string) => {
    const newExpanded = new Set(expandedFolders)
    if (newExpanded.has(folderId)) {
      newExpanded.delete(folderId)
    } else {
      newExpanded.add(folderId)
    }
    setExpandedFolders(newExpanded)
  }

  return (
    <div>
      {folders.map((folder) => (
        <div key={folder.id}>
          <div
            className={cn(
              'flex items-center gap-2 rounded-md px-3 py-2 text-sm cursor-pointer hover:bg-accent',
              selectedFolderId === folder.id && 'bg-accent',
              level > 0 && 'ml-4'
            )}
            onClick={() => onSelectFolder(folder.id)}
          >
            {folder.children && folder.children.length > 0 && (
              <ChevronRight
                className={cn(
                  'h-4 w-4 text-muted-foreground transition-transform',
                  expandedFolders.has(folder.id) && 'rotate-90'
                )}
                onClick={(e) => {
                  e.stopPropagation()
                  toggleFolder(folder.id)
                }}
              />
            )}
            {(!folder.children || folder.children.length === 0) && (
              <div className='w-4' />
            )}
            <Folder className='h-4 w-4 text-muted-foreground' />
            <span className='flex-1 truncate'>{folder.name}</span>
            <Badge variant='secondary' className='text-xs'>
              {folder.documentCount}
            </Badge>
          </div>
          {folder.children && expandedFolders.has(folder.id) && (
            <FolderTree
              folders={folder.children}
              selectedFolderId={selectedFolderId}
              onSelectFolder={onSelectFolder}
              level={level + 1}
            />
          )}
        </div>
      ))}
    </div>
  )
}

// 辅助函数：根据文件类型获取图标
function getFileIcon(type: string) {
  const iconClass = 'h-5 w-5'
  switch (type) {
    case 'PDF':
      return <FileText className={cn(iconClass, 'text-red-500')} />
    case 'DOCX':
      return <FileText className={cn(iconClass, 'text-blue-500')} />
    case 'TXT':
    case 'Markdown':
      return <FileText className={cn(iconClass, 'text-purple-500')} />
    case 'Excel':
      return <FileText className={cn(iconClass, 'text-green-500')} />
    case 'PPT':
      return <FileText className={cn(iconClass, 'text-orange-500')} />
    default:
      return <File className={cn(iconClass, 'text-gray-500')} />
  }
}

// 辅助函数：根据文件类型获取背景色
function getFileIconBg(type: string) {
  switch (type) {
    case 'PDF':
      return 'bg-red-500/10'
    case 'DOCX':
      return 'bg-blue-500/10'
    case 'TXT':
    case 'Markdown':
      return 'bg-purple-500/10'
    case 'Excel':
      return 'bg-green-500/10'
    case 'PPT':
      return 'bg-orange-500/10'
    default:
      return 'bg-gray-500/10'
  }
}

// 辅助函数：根据 ID 查找文件夹
function findFolderById(folders: FolderNode[], id: string): FolderNode | null {
  for (const folder of folders) {
    if (folder.id === id) return folder
    if (folder.children) {
      const found = findFolderById(folder.children, id)
      if (found) return found
    }
  }
  return null
}

// 模拟文件夹数据
const mockFolders: FolderNode[] = [
  {
    id: 'folder-1',
    name: '财务文档',
    level: 1,
    documentCount: 15,
    children: [
      { id: 'folder-1-1', name: '2024年度', level: 2, documentCount: 8 },
      { id: 'folder-1-2', name: '2023年度', level: 2, documentCount: 7 },
    ],
  },
  {
    id: 'folder-2',
    name: '产品文档',
    level: 1,
    documentCount: 23,
    children: [
      { id: 'folder-2-1', name: 'PRD', level: 2, documentCount: 12 },
      { id: 'folder-2-2', name: '设计稿', level: 2, documentCount: 11 },
    ],
  },
  {
    id: 'folder-3',
    name: '技术文档',
    level: 1,
    documentCount: 18,
    children: [
      { id: 'folder-3-1', name: '架构设计', level: 2, documentCount: 6 },
      { id: 'folder-3-2', name: 'API文档', level: 2, documentCount: 12 },
    ],
  },
  {
    id: 'folder-4',
    name: '市场资料',
    level: 1,
    documentCount: 9,
  },
]

// 模拟文档数据
const mockDocuments: Document[] = [
  {
    id: '1',
    name: '2024年度财务报告.pdf',
    type: 'PDF',
    size: '2.4 MB',
    folderId: 'folder-1-1',
    folderPath: '财务文档/2024年度',
    uploadedBy: 'Alex',
    uploadedAt: '2 小时前',
    status: '已完成',
    tags: ['财务', '年度报告'],
    kbReferences: [
      { id: 'kb-1', name: '财务知识库' },
      { id: 'kb-2', name: '公司文档库' },
    ],
  },
  {
    id: '2',
    name: '产品需求文档_v3.docx',
    type: 'DOCX',
    size: '1.8 MB',
    folderId: 'folder-2-1',
    folderPath: '产品文档/PRD',
    uploadedBy: 'Sarah',
    uploadedAt: '5 小时前',
    status: '已完成',
    tags: ['产品', 'PRD'],
    kbReferences: [
      { id: 'kb-3', name: '产品知识库' },
    ],
  },
  {
    id: '3',
    name: '技术架构设计.md',
    type: 'Markdown',
    size: '156 KB',
    folderId: 'folder-3-1',
    folderPath: '技术文档/架构设计',
    uploadedBy: 'Mike',
    uploadedAt: '昨天',
    status: '已完成',
    tags: ['技术', '架构'],
    kbReferences: [
      { id: 'kb-4', name: '技术文档库' },
      { id: 'kb-2', name: '公司文档库' },
      { id: 'kb-5', name: '研发知识库' },
    ],
  },
  {
    id: '4',
    name: '客户数据分析.xlsx',
    type: 'Excel',
    size: '3.2 MB',
    folderId: 'folder-4',
    folderPath: '市场资料',
    uploadedBy: 'Emma',
    uploadedAt: '昨天',
    status: '处理中',
    tags: ['数据', '分析'],
    kbReferences: [],
  },
  {
    id: '5',
    name: '用户手册_v2.0.pdf',
    type: 'PDF',
    size: '5.6 MB',
    folderId: 'folder-2-2',
    folderPath: '产品文档/设计稿',
    uploadedBy: 'Alex',
    uploadedAt: '2 天前',
    status: '已完成',
    tags: ['用户手册', '帮助'],
    kbReferences: [
      { id: 'kb-3', name: '产品知识库' },
      { id: 'kb-6', name: '帮助文档库' },
    ],
  },
  {
    id: '6',
    name: 'API接口文档.md',
    type: 'Markdown',
    size: '234 KB',
    folderId: 'folder-3-2',
    folderPath: '技术文档/API文档',
    uploadedBy: 'Mike',
    uploadedAt: '3 天前',
    status: '已完成',
    tags: ['API', '接口'],
    kbReferences: [
      { id: 'kb-4', name: '技术文档库' },
    ],
  },
  {
    id: '7',
    name: '市场调研报告.pptx',
    type: 'PPT',
    size: '8.9 MB',
    folderId: 'folder-4',
    folderPath: '市场资料',
    uploadedBy: 'Emma',
    uploadedAt: '1 周前',
    status: '已完成',
    tags: ['市场', '调研'],
    kbReferences: [
      { id: 'kb-7', name: '市场资料库' },
      { id: 'kb-2', name: '公司文档库' },
    ],
  },
]
