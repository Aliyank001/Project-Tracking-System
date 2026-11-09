import React from 'react'

const paths = {
  logo: 'M4 12 12 4l8 8-8 8-8-8Zm4 0 4-4 4 4-4 4-4-4Z',
  dashboard: 'M3 3h7v7H3z M14 3h7v7h-7z M3 14h7v7H3z M14 14h7v7h-7z',
  projects: 'M3 7a2 2 0 0 1 2-2h5l2 2h7a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2Z',
  reports: 'M4 20h16 M7 16v-4m5 4V7m5 9v-7',
  notifications: 'M18 8a6 6 0 0 0-12 0c0 6-3 7-3 8h18c0-1-3-2-3-8m-8 11a2 2 0 0 0 4 0',
  admin: 'M12 22s7-3 7-9V5l-7-3-7 3v8c0 6 7 9 7 9Zm-3-10 2 2 4-4',
  search: 'M15 15l5 5m-3-9a6 6 0 1 1-12 0 6 6 0 0 1 12 0Z',
  team: 'M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2m20 0v-2a4 4 0 0 0-3-4m-6-7a4 4 0 1 1-8 0 4 4 0 0 1 8 0Zm4-4a4 4 0 0 1 0 8',
  arrow: 'M5 12h14m-6-6 6 6-6 6',
  external: 'M7 17 17 7M7 7h10v10',
  clock: 'M12 8v4l3 2m6-2a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z',
  risk: 'M12 9v4m0 3h.01M10 4a2 2 0 0 1 4 0l7 14a1 1 0 0 1-1 2H4a1 1 0 0 1-1-2Z',
  check: 'm5 12 4 4L19 6',
  logout: 'M10 17l5-5-5-5m5 5H3m11-8h5a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2h-5',
}

export function Icon({name, size = 18}) {
  return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor"
    strokeWidth="1.65" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <path d={paths[name]} />
  </svg>
}
