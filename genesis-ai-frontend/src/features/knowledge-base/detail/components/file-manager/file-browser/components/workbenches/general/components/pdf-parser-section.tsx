import { Label } from '@/components/ui/label'
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group'
import { Badge } from '@/components/ui/badge'
import { FileText, Zap, Layout, ScanEye, Languages } from 'lucide-react'
import type { ReactNode } from 'react'
import type { ConfigState } from '@/features/knowledge-base/detail/components/shared-config/types'
import { cn } from '@/lib/utils'

interface PdfParserSectionProps {
  config: ConfigState
  onConfigChange: (config: ConfigState) => void
}

type SupportedParser = 'native' | 'mineru'

const DEFAULT_PDF_CONFIG = {
  parser: 'native' as SupportedParser,
  enable_ocr: true,
  ocr_engine: 'tesseract' as const,
  ocr_languages: ['ch', 'en'],
  extract_images: true,
  extract_tables: true,
}

const PARSER_INFO: Record<SupportedParser, { title: string; desc: ReactNode }> = {
  native: {
    title: 'Native（原生解析）',
    desc: '速度快，适合常规文本型 PDF。遇到扫描页时可配合 Tesseract OCR 补充识别。',
  },
  mineru: {
    title: 'MinerU（高精度解析）',
    desc: (
      <>
        适合复杂版面、公式和结构化内容，内置更完整的文档解析能力。{' '}
        <span className='font-medium text-red-500'>需要私有化部署 MinerU</span>
      </>
    ),
  },
}

export function PdfParserSection({ config, onConfigChange }: PdfParserSectionProps) {
  const pdfConfig = (config.pdf_parser_config || DEFAULT_PDF_CONFIG) as typeof DEFAULT_PDF_CONFIG
  const currentParser: SupportedParser = pdfConfig.parser

  const updatePdfConfig = (updates: Partial<typeof pdfConfig>) => {
    const nextConfig = {
      ...pdfConfig,
      ...updates,
      ocr_engine: 'tesseract' as const,
      extract_images: true,
      extract_tables: true,
      enable_ocr:
        (updates.parser || currentParser) === 'native'
          ? (updates.enable_ocr ?? pdfConfig.enable_ocr)
          : false,
    }
    onConfigChange({ ...config, pdf_parser_config: nextConfig })
  }

  const toggleLanguage = (lang: string) => {
    const currentLangs = pdfConfig.ocr_languages || []
    const nextLanguages = currentLangs.includes(lang)
      ? currentLangs.filter((item) => item !== lang)
      : [...currentLangs, lang]
    updatePdfConfig({ ocr_languages: nextLanguages.length > 0 ? nextLanguages : ['ch'] })
  }

  return (
    <section className='space-y-4 text-left font-sans'>
      <div className='flex items-center gap-2'>
        <FileText className='h-4 w-4 text-primary' />
        <h3 className='text-[13px] font-semibold text-slate-700'>PDF 解析策略</h3>
      </div>

      <div className='grid gap-6 rounded-2xl border border-slate-100 bg-white p-6 shadow-sm'>
        <div className='space-y-3'>
          <Label className='text-[13px] font-semibold text-slate-700'>
            解析引擎
          </Label>
          <RadioGroup
            value={currentParser}
            onValueChange={(value: SupportedParser) => updatePdfConfig({ parser: value })}
            className='space-y-1.5'
          >
            <div
              className={cn(
                'flex cursor-pointer items-center gap-3 rounded-lg border-2 px-3 py-2.5 transition-all hover:bg-muted/50',
                currentParser === 'native'
                  ? 'border-amber-500 bg-amber-50/50 dark:bg-amber-950/20'
                  : 'border-muted-foreground/20 bg-card'
              )}
              onClick={() => updatePdfConfig({ parser: 'native' })}
            >
              <RadioGroupItem value='native' id='parser-native' className='shrink-0' />
              <Zap className='h-4 w-4 text-amber-500 shrink-0' />
              <div className='min-w-0'>
                <Label htmlFor='parser-native' className='block cursor-pointer text-[13px] font-semibold leading-none text-slate-700'>
                  Native
                </Label>
                <p className='mt-1 text-xs text-slate-500'>速度优先 · 适合文字型 PDF</p>
              </div>
            </div>

            <div
              className={cn(
                'flex cursor-pointer items-center gap-3 rounded-lg border-2 px-3 py-2.5 transition-all hover:bg-muted/50',
                currentParser === 'mineru'
                  ? 'border-blue-500 bg-blue-50/50 dark:bg-blue-950/20'
                  : 'border-muted-foreground/20 bg-card'
              )}
              onClick={() => updatePdfConfig({ parser: 'mineru' })}
            >
              <RadioGroupItem value='mineru' id='parser-mineru' className='shrink-0' />
              <Layout className='h-4 w-4 text-blue-500 shrink-0' />
              <div className='min-w-0'>
                <div className='flex items-center gap-1.5'>
                  <Label htmlFor='parser-mineru' className='cursor-pointer text-[13px] font-semibold leading-none text-slate-700'>
                    MinerU
                  </Label>
                  <Badge variant='secondary' className='h-4 px-1 text-[9px]'>
                    复杂文档
                  </Badge>
                </div>
                <p className='mt-1 text-xs text-slate-500'>精度优先 · 扫描件 / 复杂版面</p>
              </div>
            </div>
          </RadioGroup>

          <p className='px-0.5 pt-1 text-xs leading-relaxed text-slate-500'>
            {PARSER_INFO[currentParser].desc}
          </p>
        </div>

        {currentParser === 'native' && (
          <div className='animate-in space-y-4 fade-in slide-in-from-top-2 duration-300 border-t border-slate-100 pt-4'>
            <div className='flex items-center justify-between'>
              <div className='flex items-center gap-2'>
                <ScanEye className='h-4 w-4 shrink-0 text-primary' />
                <Label className='text-[13px] font-semibold leading-none text-slate-700'>启用 OCR</Label>
                <span className='text-xs text-slate-500'>（自动检测扫描页）</span>
              </div>
              <RadioGroup
                value={pdfConfig.enable_ocr ? 'enabled' : 'disabled'}
                onValueChange={(value) => updatePdfConfig({ enable_ocr: value === 'enabled' })}
                className='flex items-center gap-3'
              >
                <div className='flex items-center gap-1.5'>
                  <RadioGroupItem value='enabled' id='ocr-enabled' />
                  <Label htmlFor='ocr-enabled' className='cursor-pointer text-xs'>开启</Label>
                </div>
                <div className='flex items-center gap-1.5'>
                  <RadioGroupItem value='disabled' id='ocr-disabled' />
                  <Label htmlFor='ocr-disabled' className='cursor-pointer text-xs'>关闭</Label>
                </div>
              </RadioGroup>
            </div>

            {pdfConfig.enable_ocr && (
              <div className='animate-in space-y-3 fade-in slide-in-from-top-2 duration-200'>
                <div className='flex items-center gap-1.5'>
                  <Languages className='h-3.5 w-3.5 text-slate-500' />
                  <Label className='text-[13px] font-semibold text-slate-700'>
                    识别语言
                  </Label>
                </div>
                <div className='grid grid-cols-4 gap-2'>
                  {[
                    { value: 'ch', label: '中文' },
                    { value: 'en', label: '英文' },
                    { value: 'ja', label: '日文' },
                    { value: 'ko', label: '韩文' },
                  ].map((lang) => {
                    const selected = pdfConfig.ocr_languages?.includes(lang.value)
                    return (
                      <button
                        key={lang.value}
                        type='button'
                        className={cn(
                          'rounded-md border py-1.5 text-center text-xs font-medium transition-colors',
                          selected
                            ? 'border-primary bg-primary/5 text-foreground'
                            : 'border-muted-foreground/10 text-muted-foreground hover:bg-muted/30'
                        )}
                        onClick={() => toggleLanguage(lang.value)}
                      >
                        {lang.label}
                      </button>
                    )
                  })}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </section>
  )
}
