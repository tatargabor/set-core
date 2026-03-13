import { useState, useEffect } from 'react'

const MOBILE_BREAKPOINT = 768

export default function useIsMobile(): boolean {
  const [isMobile, setIsMobile] = useState(() => window.innerWidth < MOBILE_BREAKPOINT)

  useEffect(() => {
    let timeout: ReturnType<typeof setTimeout> | null = null

    const handleResize = () => {
      if (timeout) clearTimeout(timeout)
      timeout = setTimeout(() => {
        const mobile = window.innerWidth < MOBILE_BREAKPOINT
        setIsMobile(prev => prev !== mobile ? mobile : prev)
      }, 150)
    }

    window.addEventListener('resize', handleResize)
    return () => {
      window.removeEventListener('resize', handleResize)
      if (timeout) clearTimeout(timeout)
    }
  }, [])

  return isMobile
}
