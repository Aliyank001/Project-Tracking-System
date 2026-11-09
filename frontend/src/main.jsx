import React, {useEffect, useState} from 'react'
import {createRoot} from 'react-dom/client'
import {get, save} from './api'
import {Dashboard, ProjectList, ProjectDetail, Reports, Notifications, StatusContext} from './screens'
import {Icon} from './icons'
import './style.css'

const readRoute = () => location.hash.slice(1) || '/'
const initials = name => name.split(/[^a-z0-9]+/i).map(part => part[0]).join('').slice(0, 2).toUpperCase()

function Brand() {
  return <span className="brand"><span className="brand-mark"><Icon name="logo" /></span>ProjectTrack</span>
}

function roleName(user) {
  if (user.is_superuser) return 'Workspace administrator'
  if (user.is_staff) return 'Administration staff'
  if (user.permissions.includes('projects.change_project')) return 'Project manager'
  if (user.permissions.includes('projects.add_progressreview')) return 'Reviewer'
  if (user.permissions.includes('projects.view_projectauditevent')) return 'Auditor'
  return 'Project contributor'
}

export function useLoad(path, version = 0) {
  const [state, setState] = useState({loading: true})
  useEffect(() => {
    if (!path) return
    let current = true
    setState({loading: true})
    get(path).then(data => {
      if (current) setState({data})
    }).catch(error => {
      if (current) setState({error})
    })
    return () => {current = false}
  }, [path, version])
  return state
}

function SignIn({onLogin}) {
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  async function submit(event) {
    event.preventDefault()
    setBusy(true)
    setError('')
    try {
      await save('auth/login/', Object.fromEntries(new FormData(event.currentTarget)))
      onLogin(await get('auth/me/'))
    } catch (error) {
      setError(error.message)
    } finally {
      setBusy(false)
    }
  }
  return <main className="signin">
    <section className="signin-intro">
      <Brand />
      <div className="signin-story"><p className="eyebrow">PROJECT WORKSPACE</p><h1>Clear plans.<br />Visible progress.</h1>
        <p>See who owns each task, what’s due next, and where projects need attention.</p></div>
      <div className="signin-preview">
        <div className="signin-preview-heading"><span className="signin-tile-icon"><Icon name="projects" /></span>
          <div><strong>Project delivery</strong><small>From assignment to handover</small></div></div>
        <div className="signin-preview-grid">
          {[['team', 'Assign', 'Give each person clear ownership.'], ['clock', 'Track', 'See tasks and milestone dates.'],
            ['check', 'Review', 'Check progress before handover.']].map(([icon, title, text]) =>
            <div key={title}><Icon name={icon} /><strong>{title}</strong><small>{text}</small></div>)}
        </div>
      </div>
      <p className="caption">ProjectTrack · Project management workspace</p>
    </section>
    <section className="signin-form">
      <form onSubmit={submit}>
        <p className="eyebrow">PROJECTTRACK WORKSPACE</p><h2>Welcome back.</h2>
        <p>Sign in with the account provided by your administrator.</p>
        <label>Username<input name="username" autoComplete="username" required /></label>
        <label>Password<input name="password" type="password" autoComplete="current-password" required /></label>
        {error && <p className="error" role="alert">{error}</p>}
        <button className="primary" disabled={busy}>{busy ? 'Signing in…' : 'Sign in'}<Icon name="arrow" size={16} /></button>
      </form>
    </section>
  </main>
}

function NotificationNav({active}) {
  const [count, setCount] = useState(0)
  useEffect(() => {
    let mounted = true
    async function refresh() {
      try {
        const data = await get('notifications/count/')
        if (mounted) setCount(data.unread_count)
      } catch {
        // The inbox shows request errors and offers a retry.
      }
    }
    refresh()
    const timer = window.setInterval(refresh, 30000)
    window.addEventListener('notifications:changed', refresh)
    return () => {
      mounted = false
      window.clearInterval(timer)
      window.removeEventListener('notifications:changed', refresh)
    }
  }, [])
  return <a href="#/notifications" aria-current={active ? 'page' : undefined}>
    <Icon name="notifications" /> Notifications
    {count > 0 && <small className="notification-count" aria-label={count + ' unread'}>{count}</small>}
  </a>
}

function Administration({user}) {
  if (!user.is_staff) return <section className="panel"><h1>Administration</h1><p>This area requires a staff account.</p></section>
  const allowed = permission => user.is_superuser || user.permissions.includes('auth.' + permission)
  const actions = [
    ...(allowed('view_user') || allowed('change_user') ? [
      ['team', 'People', 'Open user accounts and manage staff details.', '/admin/auth/user/', 'Manage users'],
    ] : []),
    ...(allowed('add_user') ? [
      ['team', 'New employee', 'Create a sign-in account for someone joining the company.', '/admin/auth/user/add/', 'Add employee'],
    ] : []),
    ...(allowed('view_group') || allowed('change_group') ? [
      ['admin', 'Roles & permissions', 'Manage the groups that determine what each employee can do.', '/admin/auth/group/', 'Manage roles'],
    ] : []),
    ...(user.is_superuser ? [
      ['projects', 'Project managers', 'Open the project register to appoint a manager or change ownership.', '#/projects', 'Open projects'],
    ] : []),
  ]
  return <>
    <div className="heading"><div><p className="eyebrow">WORKSPACE SETTINGS</p><h1>Administration</h1>
      <p>Manage employee accounts, roles and project ownership.</p></div>
      <a className="button primary" href="/admin/">Open admin console <Icon name="external" size={16} /></a></div>
    <section className="admin-profile panel">
      <span className="avatar">{initials(user.username)}</span>
      <div><strong>{user.username}</strong><small>{roleName(user)}</small></div>
      <span className="pill"><Icon name="admin" size={13} /> Admin access</span>
    </section>
    <div className="project-grid admin-grid">{actions.map(([icon, title, text, link, action]) =>
      <article key={title} className="panel admin-action">
        <span className="tile-icon"><Icon name={icon} /></span><h2>{title}</h2><p>{text}</p>
        <a href={link}>{action} <Icon name="arrow" size={15} /></a>
      </article>)}</div>
  </>
}

function App() {
  const [route, setRoute] = useState(readRoute)
  const [user, setUser] = useState(undefined)
  const statuses = useLoad(user ? 'project-statuses/' : null)
  const [error, setError] = useState('')
  useEffect(() => {
    const onHash = () => setRoute(readRoute())
    window.addEventListener('hashchange', onHash)
    get('auth/me/').then(setUser).catch(error => {
      if (![401, 403].includes(error.status)) setError(error.message)
      setUser(null)
    })
    return () => window.removeEventListener('hashchange', onHash)
  }, [])
  if (user === undefined) return <main className="startup">Opening ProjectTrack…</main>
  if (!user) return <>{error && <div className="error banner" role="alert">{error}</div>}<SignIn onLogin={value => {setUser(value); setError('')}} /></>

  const detail = route.match(/^\/projects\/([a-f0-9-]+)$/i)
  const projects = route.startsWith('/projects')
  const archived = route.split('?')[0] === '/projects/archived'
  const search = new URLSearchParams(route.split('?')[1]).get('search') ?? ''
  const section = detail ? 'Project details' : projects ? 'Projects' : ({
    '/reports': 'Reports', '/notifications': 'Notifications', '/administration': 'Administration',
  }[route] ?? 'Overview')
  async function signOut() {
    try {
      await save('auth/logout/', {})
      setUser(null)
      setError('')
    } catch (error) {
      setError(error.message)
    }
  }
  return <div className="shell">
    <aside className="sidebar">
      <a className="brand-link" href="#/"><Brand /></a>
      <div className="workspace-card"><span className="workspace-symbol"><Icon name="projects" size={16} /></span>
        <div><strong>Company workspace</strong><small>Project portfolio</small></div></div>
      <p className="nav-label">WORKSPACE</p>
      <nav aria-label="Main navigation">
        <a href="#/" aria-current={route === '/' ? 'page' : undefined}><Icon name="dashboard" /> Overview</a>
        <a href="#/projects" aria-current={projects ? 'page' : undefined}><Icon name="projects" /> Projects</a>
        {(user.is_superuser || user.permissions.some(permission =>
          ['projects.change_project', 'projects.view_projectauditevent'].includes(permission))) &&
          <a href="#/reports" aria-current={route === '/reports' ? 'page' : undefined}><Icon name="reports" /> Reports</a>}
        <NotificationNav active={route === '/notifications'} />
        {user.is_staff && <a href="#/administration" aria-current={route === '/administration' ? 'page' : undefined}><Icon name="admin" /> Administration</a>}
      </nav>
      <div className="sidebar-foot">
        <span className="avatar">{initials(user.username)}</span>
        <div><strong>{user.username}</strong><small>{roleName(user)}</small></div>
        <button type="button" className="icon-button" onClick={signOut} aria-label="Sign out" title="Sign out"><Icon name="logout" size={16} /></button>
      </div>
    </aside>
    <div className="workspace">
      <header className="topbar"><div className="breadcrumbs"><span>Workspace</span><span aria-hidden="true">/</span><strong>{section}</strong></div>
        <div className="topbar-tools">
          <form key={route} className="quick-search" onSubmit={event => {
            event.preventDefault()
            const query = new FormData(event.currentTarget).get('search').trim()
            location.hash = '/projects' + (query ? '?search=' + encodeURIComponent(query) : '')
          }}>
            <Icon name="search" size={16} /><input name="search" aria-label="Quick project search" placeholder="Search projects…" defaultValue={search} />
          </form>
          {user.is_staff ? <a className="avatar" href="#/administration" title={roleName(user)} aria-label={roleName(user)}>{initials(user.username)}</a> :
            <span className="avatar" title={roleName(user)}>{initials(user.username)}</span>}
          <button type="button" className="icon-button mobile-signout" onClick={signOut} aria-label="Sign out"><Icon name="logout" size={17} /></button>
        </div>
      </header>
      <main className="content"><StatusContext.Provider value={statuses.data ?? []}>
        {error && <p className="error" role="alert">{error}</p>}
        {detail ? <ProjectDetail key={detail[1]} id={detail[1]} user={user} /> :
          projects ? <ProjectList key={route} user={user} archived={archived} initialSearch={search} /> :
          route === '/administration' ? <Administration user={user} /> :
          route === '/reports' ? <Reports /> :
          route === '/notifications' ? <Notifications /> : <Dashboard user={user} />}
      </StatusContext.Provider></main>
    </div>
  </div>
}

createRoot(document.getElementById('root')).render(<App />)

