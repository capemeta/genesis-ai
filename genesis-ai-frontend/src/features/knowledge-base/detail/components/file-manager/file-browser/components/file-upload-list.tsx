/**
 * 上传文件列表
 */
import { FileUploadItem } from './file-upload-item'
import type { UploadFileItem } from '../hooks/use-file-upload'

interface FileUploadListProps {
  files: UploadFileItem[]
  onRemove: (fileId: string) => void
  onCancel: (fileId: string) => void
}

export function FileUploadList({ files, onRemove, onCancel }: FileUploadListProps) {
  return (
    <div className="space-y-2">
      {files.map((file) => (
        <FileUploadItem
          key={file.id}
          file={file}
          onRemove={() => onRemove(file.id)}
          onCancel={() => onCancel(file.id)}
        />
      ))}
    </div>
  )
}
