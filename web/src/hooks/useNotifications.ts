import { useEffect, useRef, useCallback } from 'react'

export function useNotifications() {
  const permissionRef = useRef(Notification.permission)

  useEffect(() => {
    if ('Notification' in window && Notification.permission === 'default') {
      Notification.requestPermission().then((perm) => {
        permissionRef.current = perm
      })
    }
  }, [])

  const notify = useCallback((title: string, body?: string) => {
    if (document.hasFocus()) return
    if (permissionRef.current !== 'granted') return

    const n = new Notification(title, {
      body,
      icon: '/favicon.ico',
      tag: 'wt-web',
    })
    setTimeout(() => n.close(), 5000)
  }, [])

  return { notify }
}
