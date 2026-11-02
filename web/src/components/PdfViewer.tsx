import { useEffect, useRef, useState } from 'react'
import { Document, Page, pdfjs } from 'react-pdf'
import 'react-pdf/dist/Page/TextLayer.css'
import type { Rect } from '../api'

pdfjs.GlobalWorkerOptions.workerSrc = new URL('pdfjs-dist/build/pdf.worker.min.mjs', import.meta.url).toString()

const WIDTH = 620

/** Renders the ORIGINAL PDF and draws citation rectangles (PDF points, top-left origin) over it. */
export default function PdfViewer({ url, rects, focusPage }: { url: string; rects: Rect[]; focusPage: number | null }) {
  const [pages, setPages] = useState(0)
  const [size, setSize] = useState<Record<number, { w: number; h: number }>>({})
  const refs = useRef<Record<number, HTMLDivElement | null>>({})

  // Scroll so the first highlight sits about a third of the way down the viewer. Measured relative
  // to the scroll container (not the page), and only once every page up to the target has its size.
  const ready = focusPage != null && pages > 0 && Array.from({ length: focusPage + 1 }, (_, i) => size[i]).every(Boolean)
  useEffect(() => {
    if (!ready || focusPage == null) return
    const t = setTimeout(() => {
      const el = refs.current[focusPage]
      const box = el?.closest('.viewer-scroll') as HTMLElement | null
      if (!el || !box) return
      const first = rects.find(r => r.page === focusPage)
      const scale = WIDTH / size[focusPage].w
      const pageTop = el.getBoundingClientRect().top - box.getBoundingClientRect().top + box.scrollTop
      box.scrollTo({ top: pageTop + (first ? first.y0 * scale - box.clientHeight / 3 : 0), behavior: 'smooth' })
    }, 50)
    return () => clearTimeout(t)
  }, [url, focusPage, rects, ready])  // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <Document file={url} onLoadSuccess={({ numPages }) => setPages(numPages)} loading={<p className="muted">Loading PDF…</p>}>
      {Array.from({ length: pages }, (_, i) => {
        const s = size[i] ?? { w: 612, h: 792 }  // US Letter until the real size is known
        const scale = WIDTH / s.w
        return (
          // Fixed height up front so pages don't change height while rendering and shift the scroll target.
          <div key={i} className="pdfpage" style={{ height: s.h * scale }} ref={el => { refs.current[i] = el }}>
            <Page pageNumber={i + 1} width={WIDTH} renderAnnotationLayer={false}
              onLoadSuccess={p => setSize(m => ({ ...m, [i]: { w: p.originalWidth, h: p.originalHeight } }))} />
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
