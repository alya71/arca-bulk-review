import { useEffect, useRef, useState } from 'react'
import { Document, Page, pdfjs } from 'react-pdf'
import 'react-pdf/dist/Page/TextLayer.css'
import type { Rect } from '../api'

pdfjs.GlobalWorkerOptions.workerSrc = new URL('pdfjs-dist/build/pdf.worker.min.mjs', import.meta.url).toString()

const WIDTH = 620

/** Renders the ORIGINAL PDF and draws citation rectangles (PDF points, top-left origin) over it. */
export default function PdfViewer({ url, rects, focusPage }: { url: string; rects: Rect[]; focusPage: number | null }) {
  const [pages, setPages] = useState(0)
  const [pageW, setPageW] = useState<Record<number, number>>({})
  const refs = useRef<Record<number, HTMLDivElement | null>>({})

  useEffect(() => {
    if (focusPage == null || !pages) return
    const t = setTimeout(() => {
      const first = rects.find(r => r.page === focusPage)
      const el = refs.current[focusPage]
      if (!el) return
      const scale = WIDTH / (pageW[focusPage] ?? 612)
      el.parentElement?.parentElement?.scrollTo({ top: el.offsetTop + (first ? first.y0 * scale - 160 : 0), behavior: 'smooth' })
    }, 150)
    return () => clearTimeout(t)
  }, [url, focusPage, pages, rects, pageW])

  return (
    <Document file={url} onLoadSuccess={({ numPages }) => setPages(numPages)} loading={<p className="muted">Loading PDF…</p>}>
      {Array.from({ length: pages }, (_, i) => {
        const scale = WIDTH / (pageW[i] ?? 612)
        return (
          <div key={i} className="pdfpage" ref={el => { refs.current[i] = el }}>
            <Page pageNumber={i + 1} width={WIDTH} renderAnnotationLayer={false}
              onLoadSuccess={p => setPageW(w => ({ ...w, [i]: p.originalWidth }))} />
            {rects.filter(r => r.page === i).map((r, j) => (
              <div key={j} className="hl" style={{
                left: r.x0 * scale - 2, top: r.y0 * scale - 1,
                width: (r.x1 - r.x0) * scale + 4, height: (r.y1 - r.y0) * scale + 2,
              }} />
            ))}
            <div className="pageno">page {i + 1} / {pages}</div>
          </div>
        )
      })}
    </Document>
  )
}
