import {
  MessageSquare,
  Webhook,
  BookOpen,
  FileSearch,
  Brain,
  GitBranch,
  Wrench,
  Send,
} from 'lucide-react'

export const ICON_MAP: Record<string, any> = {
  MessageSquare,
  Webhook,
  BookOpen,
  FileSearch,
  Brain,
  GitBranch,
  Wrench,
  Send,
}

export const COLOR_CLASSES = {
  purple: {
    border: 'border-purple-500',
    bg: 'bg-purple-500',
    text: 'text-purple-600',
    bgLight: 'bg-purple-50 dark:bg-purple-500/10',
    badge: 'bg-purple-50 text-purple-600 dark:bg-purple-500/10 border-purple-200 dark:border-purple-500/20'
  },
  amber: {
    border: 'border-amber-500',
    bg: 'bg-amber-500',
    text: 'text-amber-600',
    bgLight: 'bg-amber-50 dark:bg-amber-500/10',
    badge: 'bg-amber-50 text-amber-600 dark:bg-amber-500/10 border-amber-200 dark:border-amber-500/20'
  },
  blue: {
    border: 'border-primary',
    bg: 'bg-primary',
    text: 'text-primary',
    bgLight: 'bg-blue-50 dark:bg-blue-500/10',
    badge: 'bg-blue-50 text-blue-600 dark:bg-blue-500/10 border-blue-200 dark:border-blue-500/20'
  },
  green: {
    border: 'border-green-500',
    bg: 'bg-green-500',
    text: 'text-green-600',
    bgLight: 'bg-green-50 dark:bg-green-500/10',
    badge: 'bg-green-50 text-green-600 dark:bg-green-500/10 border-green-200 dark:border-green-500/20'
  },
}
