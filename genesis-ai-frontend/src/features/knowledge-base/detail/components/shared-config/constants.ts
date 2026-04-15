import type {
  ChunkingConfig,
  EnhancementSettings,
  KnowledgeBaseIntelligenceConfig,
  KnowledgeGraphSettings,
  RaptorSettings,
  TableRetrievalSettings,
  TableSchemaColumn,
} from '@/lib/api/knowledge-base'

export const DEFAULT_CHUNKING_CONFIG: ChunkingConfig = {
  separator: '\\n\\n',
  split_rules: [{ pattern: '\\n\\n', is_regex: false }],
  chunk_size: 500,
  overlap: 50,
  pdf_chunk_strategy: 'markdown',
  max_heading_level: 3,
  heading_rules: [],
  fallback_separators: ['\n\n', '\n', '。', '；', ' '],
  preserve_headings: true,
}

export const DEFAULT_ENHANCEMENT_CONFIG: EnhancementSettings = {
  enabled: true,
  summary: {
    enabled: false,
  },
  keywords: {
    enabled: false,
    top_n: 3,
  },
  questions: {
    enabled: false,
    top_n: 3,
  },
}

export const DEFAULT_TABLE_SCHEMA_COLUMN: TableSchemaColumn = {
  name: '',
  type: 'text',
  nullable: true,
  role: 'content',
  filterable: false,
  aggregatable: false,
  searchable: true,
  aliases: [],
  enum_values: [],
}

export const DEFAULT_TABLE_RETRIEVAL_CONFIG: TableRetrievalSettings = {
  schema: {
    columns: [],
  },
  key_columns: [],
  field_map: {},
  include_sheets: [],
  text_prefix_template: '',
  overflow_strategy: 'key_columns_first',
  kb_term_mappings: {},
  schema_status: 'draft',
  schema_source_document_id: null,
}

export const DEFAULT_KNOWLEDGE_GRAPH_CONFIG: KnowledgeGraphSettings = {
  enabled: false,
  entity_types: ['organization', 'person', 'location', 'event', 'category'],
  method: 'light',
  entity_resolution: false,
  community_reports: false,
}

export const DEFAULT_RAPTOR_CONFIG: RaptorSettings = {
  enabled: false,
  scope: 'file',
  prompt:
    'Please summarize the following paragraphs. Be careful with the numbers, do not make things up. Paragraphs as following:\n{cluster_content}\nThe above is the content you need to summarize.',
  max_tokens: 256,
  threshold: 0.1,
  max_clusters: 64,
  random_seed: 0,
}

export const DEFAULT_INTELLIGENCE_CONFIG: KnowledgeBaseIntelligenceConfig = {
  enhancement: DEFAULT_ENHANCEMENT_CONFIG,
  knowledge_graph: DEFAULT_KNOWLEDGE_GRAPH_CONFIG,
  raptor: DEFAULT_RAPTOR_CONFIG,
}
