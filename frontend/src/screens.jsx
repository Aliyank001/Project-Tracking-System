import React, {createContext, useContext, useEffect, useState} from 'react'
import {API, save} from './api'
import {useLoad} from './main'
import {Icon} from './icons'

const statusOptions = ['proposed', 'planned', 'active', 'on_hold', 'completed', 'cancelled']
const label = value => String(value ?? '—').replaceAll('_', ' ')
export const StatusContext = createContext([])
const statusCaption = (options, value) => options.find(option => option.value === value)?.label ?? label(value)
const money = (value, currency) => value == null ? '—' :
  new Intl.NumberFormat('en', {style: 'currency', currency}).format(Number(value))
const permitted = (user, codename) => user.is_superuser || user.permissions.includes('projects.' + codename)
const accountName = account => [account.first_name, account.last_name].filter(Boolean).join(' ') || account.username
const accountChoices = accounts => accounts.map(account => ({value: account.id, label: accountName(account) + ' · ' + account.username}))
const progressValue = row => row.progress_summary?.percent ?? row.progress

function ProjectCards({rows}) {
  const statuses = useContext(StatusContext)
  if (!rows.length) return <div className="panel empty">No matching projects.</div>
  return <div className="project-grid">{rows.map(row => <article className="project-card panel" key={row.id}>
    <div className="project-card-top"><span className="tile-icon"><Icon name="projects" /></span>
      <span className={'pill ' + row.status}>{statusCaption(statuses, row.status)}</span></div>
    <h2><a href={'#/projects/' + row.id}>{row.title}</a></h2>
    <p>{row.department}</p>
    <div className="project-card-progress"><span>{progressValue(row) == null ? 'Progress unavailable' : label(row.progress_summary?.source ?? row.progress_source)}</span>
      <strong>{progressValue(row) == null ? '—' : progressValue(row) + '%'}</strong></div>
    {progressValue(row) != null && <progress aria-label={row.title + ' progress'} value={progressValue(row)} max="100" />}
    <div className="project-card-footer"><span><Icon name="clock" size={15} />{row.planned_end}</span>
      <a aria-label={'Open ' + row.title} href={'#/projects/' + row.id}><Icon name="arrow" size={16} /></a></div>
  </article>)}</div>
}

function Heading({tag, title, subtitle, action}) {
  return <div className="heading"><div><p className="eyebrow">{tag}</p><h1>{title}</h1><p>{subtitle}</p></div>{action}</div>
}

function Load({state, children}) {
  if (state.loading) return <div className="panel" role="status">Loading…</div>
  if (state.error) return <div className="panel error" role="alert">{state.error.message}</div>
  return children(state.data)
}

function ProjectTable({rows, compact = false}) {
  const statuses = useContext(StatusContext)
  return <div className="table-wrap"><table><thead><tr>
    <th>Project</th>{!compact && <th>Department</th>}<th>Status</th><th>Progress</th><th>Due date</th>
    {!compact && <><th>Approved budget</th><th>Recorded spend</th></>}
  </tr></thead><tbody>{rows.map(row => <tr key={row.id}>
    <td><a href={'#/projects/' + row.id}><strong>{row.title}</strong></a></td>
    {!compact && <td>{row.department}</td>}<td><span className={'pill ' + row.status}>{statusCaption(statuses, row.status)}</span></td>
    <td>{progressValue(row) == null ? '—' :
      <div className="table-progress"><progress aria-label={row.title + ' progress'} value={progressValue(row)} max="100" />
        <span>{progressValue(row)}%</span></div>}</td>
    <td className="date-cell">{row.planned_end}</td>
    {!compact && <><td>{money(row.approved_budget, row.currency)}</td><td>{money(row.recorded_expenditure, row.currency)}</td></>}
  </tr>)}</tbody></table>{!rows.length && <p className="empty">No matching projects.</p>}</div>
}

export function Dashboard({user}) {
  const [version, setVersion] = useState(0)
  const [responseFlag, setResponseFlag] = useState(null)
  const state = useLoad('dashboard/', version)
  const portfolio = permitted(user, 'change_project') || permitted(user, 'view_projectauditevent')
  return <><Heading tag="OVERVIEW" title={portfolio ? 'A clear view of your projects.' : 'Your work, in focus.'}
    subtitle={portfolio ? 'See project progress, deadlines and where your team needs attention.' : 'See your assignments and keep progress up to date.'}
    action={<a className="button primary" href="#/projects"><Icon name="projects" size={16} /> View projects</a>} />
    <Load state={state}>{data => <>
      {(!portfolio || data.my_work?.length > 0) && <section className="panel"><h2>My assigned work</h2>
        <Records records={data.my_work ?? []} empty="You have no open assignments." render={item =>
          <div><a href={'#/projects/' + item.project_id}><strong>{item.title}</strong></a>
            <small>{item.project__title} · Due {item.planned_end} · {item.percent_complete}%</small></div>} />
      </section>}
      {portfolio && <>
      <div className="metrics">
        {[['Total projects', data.project_count, 'projects', 'Across your portfolio'], ['Active projects', data.status_counts.active || 0, 'check', 'Work in progress'],
          ['Overdue milestones', data.overdue_count, 'clock', 'Past their planned date'], ['Projects at risk', data.at_risk_count, 'risk', 'Flagged for review']].map(([name, value, icon, text]) =>
          <article className="panel metric" key={name}><div className="metric-label"><span>{name}</span><Icon name={icon} size={16} /></div>
            <strong>{value}</strong><small>{text}</small></article>)}
      </div>
      {data.flags.length > 0 && <div className="attention-banner">
        <span className="tile-icon"><Icon name="risk" /></span><div><strong>{data.at_risk_count === 1 ? '1 project needs attention' : data.at_risk_count + ' projects need attention'}</strong>
          <small>{data.flags[0].reason}</small></div>
        <a className="button primary" href={'#/projects/' + data.flags[0].project_id}>Review project <Icon name="arrow" size={15} /></a>
      </div>}
      <div className="columns">
        <section className="panel"><div className="section-title"><h2>Portfolio health</h2>
          <a className="caption" href="#/projects">View all projects ↗</a></div><ProjectTable rows={data.projects} compact /></section>
        <section className="panel"><h2>Upcoming milestones</h2>
          {data.upcoming.length ? <ul className="records">{data.upcoming.map((row, index) =>
            <li key={index}><a href={'#/projects/' + row.project_id}>{row.title}</a><small>{row.due_date}</small></li>)}</ul> :
            <p className="empty">No incomplete milestones due in the next {data.lookahead_days} days.</p>}
        </section>
        <section className="panel"><h2>Recorded expenditure</h2>
          {Object.entries(data.spending).map(([currency, amounts]) => <div className="chart-row" key={currency}>
            <p>{money(amounts.recorded, currency)} recorded / {money(amounts.budget, currency)} approved</p>
            <progress aria-label={currency + ' budget utilization'} value={Number(amounts.recorded)} max={Math.max(1, Number(amounts.budget))} />
          </div>)}
        </section>
        <section className="panel"><h2>Risk flags</h2>
          {responseFlag && <Editor key={responseFlag.signature} title="Respond to risk flag"
            fields={[
              ['dismiss', 'Action', [{value: 'false', label: 'Save feedback'}, {value: 'true', label: 'Dismiss from my view'}]],
              ['reason', 'Reason', 'textarea'],
            ]} values={{dismiss: 'false'}} extra={{signature: responseFlag.signature}}
            path={'projects/' + responseFlag.project_id + '/risk-response/'}
            onCancel={() => setResponseFlag(null)} onSaved={() => {
              setResponseFlag(null); setVersion(value => value + 1)
            }} />}
          {data.flags.length ? <ul className="records">{data.flags.map((flag, index) =>
            <li key={flag.signature ?? index}><div><a href={'#/projects/' + flag.project_id}>{flag.title}</a>
              <small>{flag.reason}</small><small>Rule-based · {new Date(flag.generated_at).toLocaleString()}</small>
              {flag.type === 'schedule' && <small>Planned progress assumes even progress across the schedule.</small>}</div>
              {flag.can_respond && <button onClick={() => setResponseFlag(flag)}>Respond</button>}</li>)}</ul> :
            <p className="empty">No current risk flags.</p>}
        </section>
      </div>
      <p className="caption">Last checked {new Date(data.as_of).toLocaleString()} · Rule-based indicators</p>
      </>}
    </>}</Load>
  </>
}

function Field({field, values}) {
  const [name, caption, type = 'text', required = true] = field
  const value = values[name] ?? ''
  return <label>{caption}{required && <span aria-hidden="true"> *</span>}
    {Array.isArray(type) ? <select name={name} defaultValue={value} required={required}>
      <option value="">Select…</option>{type.map(item => {
        const value = typeof item === 'object' ? item.value : item
        return <option key={value} value={value}>{typeof item === 'object' ? item.label : label(item)}</option>
      })}
    </select> : type === 'textarea' ? <textarea name={name} defaultValue={value} required={required} /> :
      type === 'file' ? <input name={name} type="file" accept=".pdf,.png,.jpg,.jpeg" /> :
      <input name={name} type={type === 'money' || type === 'integer' ? 'number' : type}
        defaultValue={value} required={required} min={['money', 'integer'].includes(type) ? 0 : undefined}
        max={name === 'percent_complete' ? 100 : undefined} step={type === 'money' ? '0.01' : undefined} />}
  </label>
}

function Editor({title, fields, values = {}, extra = {}, path, method, onSaved, onCancel}) {
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  async function submit(event) {
    event.preventDefault()
    const form = new FormData(event.currentTarget)
    const evidence = form.get('evidence_file')
    if (evidence && !evidence.name) form.delete('evidence_file')
    const payload = {...Object.fromEntries(form), ...extra}
    for (const name of ['assignee', 'predecessor', 'weight']) {
      if (payload[name] === '') payload[name] = null
    }
    if (payload.currency) payload.currency = payload.currency.trim().toUpperCase()
    setBusy(true)
    setError('')
    try {
      onSaved(await save(path, evidence?.name ? form : payload, method))
    } catch (error) {
      setError(error.message)
    } finally {
      setBusy(false)
    }
  }
  return <form className="panel editor" onSubmit={submit}><h2>{title}</h2>
    <div className="form-grid">{fields.map(field => <Field key={field[0]} field={field} values={values} />)}</div>
    {error && <p className="error" role="alert">{error}</p>}
    <div className="actions"><button className="primary" disabled={busy}>{busy ? 'Saving…' : 'Save'}</button>
      <button type="button" onClick={onCancel}>Cancel</button></div>
  </form>
}

const projectFields = [
  ['title', 'Project title'], ['department', 'Department'], ['description', 'Description', 'textarea', false],
  ['planned_start', 'Planned start', 'date'], ['planned_end', 'Planned end', 'date'],
  ['status', 'Status', statusOptions], ['approved_budget', 'Approved budget', 'money'], ['currency', 'Currency code'],
]
function projectFormFields(statuses, currentStatus) {
  if (!statuses.length) return projectFields
  const allowed = statuses.filter(option => option.enabled || option.value === currentStatus)
  return projectFields.map(field => field[0] === 'status' ? ['status', 'Status', allowed] : field)
}
const itemFields = [
  ['kind', 'Type', ['task', 'milestone']], ['title', 'Title'], ['planned_start', 'Planned start', 'date'],
  ['planned_end', 'Due date', 'date'], ['assignee', 'Assignee user ID', 'integer', false],
  ['predecessor', 'Predecessor item ID', 'integer', false], ['percent_complete', 'Completion (%)', 'integer'],
  ['acceptance_note', 'Acceptance note', 'textarea', false], ['is_active', 'Active', ['true', 'false']],
  ['weight', 'Progress weight (1–1000)', 'integer', false],
]
const progressFields = [
  ['reporting_date', 'Reporting date', 'date'], ['percent_complete', 'Completion (%)', 'integer'],
  ['summary', 'Summary', 'textarea'], ['blockers', 'Blockers', 'textarea', false],
  ['next_steps', 'Next steps', 'textarea', false],
  ['evidence_url', 'Evidence link', 'url', false],
  ['evidence_file', 'Evidence file (PDF, PNG or JPEG, max 5 MB)', 'file', false],
]
const reviewFields = [
  ['decision', 'Decision', ['approved', 'correction_requested']],
  ['comment', 'Comment (required for correction)', 'textarea', false],
]
const expenditureFields = [
  ['date', 'Recorded date', 'date'], ['amount', 'Amount', 'money'], ['category', 'Category'],
  ['reference', 'Reference'], ['note', 'Note', 'textarea', false],
]

function queryString(fields) {
  return new URLSearchParams(Object.entries(fields).filter(([, value]) => value !== '')).toString()
}

function Pager({page, setPage, data}) {
  return <div className="actions"><button disabled={!data.previous} onClick={() => setPage(page - 1)}>Previous</button>
    <span>Page {page}</span><button disabled={!data.next} onClick={() => setPage(page + 1)}>Next</button></div>
}

export function ProjectList({user, archived, initialSearch}) {
  const statuses = useContext(StatusContext)
  const [filters, setFilters] = useState({search: initialSearch})
  const [page, setPage] = useState(1)
  const [create, setCreate] = useState(false)
  const [layout, setLayout] = useState('cards')
  const state = useLoad('projects/?' + queryString({...filters, page, archived}))
  const managers = useLoad(create && user.is_superuser ? 'manager-directory/' : null)
  const defaultStatus = statuses.find(option => option.value === 'proposed' && option.enabled)?.value
    ?? statuses.find(option => option.enabled)?.value ?? 'proposed'
  return <><Heading tag="REGISTER" title={archived ? 'Archived projects' : 'Projects'}
    subtitle={archived ? 'Browse archived projects and their history.' : 'Search and track the projects you can access.'}
    action={!archived && permitted(user, 'add_project') && <button className="primary" onClick={() => setCreate(true)}>+ New project</button>} />
    <nav className="tabs" aria-label="Project register views">
      <a className="button" href="#/projects" aria-current={!archived ? 'page' : undefined}>Current</a>
      <a className="button" href="#/projects/archived" aria-current={archived ? 'page' : undefined}>Archived</a>
    </nav>
    {create && (user.is_superuser ? <Load state={managers}>{accounts => accounts.length ?
      <Editor title="Register a project" fields={[...projectFormFields(statuses), ['manager_id', 'Project manager', accountChoices(accounts)]]}
        values={{status: defaultStatus, currency: 'NGN'}} path="projects/"
        onSaved={project => {location.hash = '/projects/' + project.id}} onCancel={() => setCreate(false)} /> :
      <p className="panel">Create an account in the Project Managers group in Administration first.</p>
    }</Load> : <Editor title="Register a project" fields={projectFormFields(statuses)} values={{status: defaultStatus, currency: 'NGN'}}
      path="projects/" onSaved={project => {location.hash = '/projects/' + project.id}} onCancel={() => setCreate(false)} />)}
    <section className="panel">
      <form className="filters" onSubmit={event => {
        event.preventDefault(); setPage(1); setFilters(Object.fromEntries(new FormData(event.currentTarget)))
      }}>
        <Field field={['search', 'Search title or department', 'search', false]} values={{search: initialSearch}} />
        <Field field={['project_id', 'Project ID', 'text', false]} values={{}} />
        <Field field={['owner', 'Owner username', 'text', false]} values={{}} />
        <Field field={['department', 'Department', 'text', false]} values={{}} />
        <Field field={['status', 'Status', statuses.length ? statuses : statusOptions, false]} values={{}} />
        <Field field={['start', 'Planned from', 'date', false]} values={{}} />
        <Field field={['end', 'Planned to', 'date', false]} values={{}} /><button>Apply filters</button>
      </form>
    </section>
    <div className="register-layout" aria-label="Project display">
      <button aria-pressed={layout === 'cards'} onClick={() => setLayout('cards')}><Icon name="dashboard" size={16} /> Cards</button>
      <button aria-pressed={layout === 'table'} onClick={() => setLayout('table')}><Icon name="reports" size={16} /> Table</button>
    </div>
    <Load state={state}>{data => <>
      {layout === 'cards' ? <ProjectCards rows={data.results} /> : <section className="panel"><ProjectTable rows={data.results} /></section>}
      <Pager page={page} setPage={setPage} data={data} />
    </>}</Load>
  </>
}

function Records({records, render, empty}) {
  return records.length ? <ul className="records">{records.map(record => <li key={record.id}>{render(record)}</li>)}</ul> :
    <p className="empty">{empty}</p>
}

function ProgressTab({project, user}) {
  const root = 'projects/' + project.id + '/progress-updates/'
  const [page, setPage] = useState(1)
  const [version, setVersion] = useState(0)
  const [pending, setPending] = useState(false)
  const [edit, setEdit] = useState(null)
  const canSubmit = !project.archived_at && permitted(user, 'add_progressupdate')
  const canReview = !project.archived_at && permitted(user, 'add_progressreview')
  const state = useLoad(root + '?' + queryString({page, review: pending ? 'pending' : ''}), version)
  const reviewing = edit?.mode === 'review'
  const resubmitting = edit?.mode === 'resubmit'

  function finish() {
    setEdit(null)
    setPage(1)
    setVersion(value => value + 1)
  }

  return <section className="panel">
    <div className="section-title"><h2>{pending ? 'Review queue' : 'Progress updates'}</h2>
      <div className="actions">
        {canReview && <button onClick={() => {setPending(!pending); setPage(1); setEdit(null)}}>
          {pending ? 'All updates' : 'Review queue'}
        </button>}
        {canSubmit && !pending && <button className="primary" onClick={() => setEdit({mode: 'new'})}>
          Submit progress
        </button>}
      </div>
    </div>
    {edit && <Editor key={edit.mode + (edit.record?.id ?? '')}
      title={reviewing ? 'Review progress update' : resubmitting ? 'Resubmit corrected progress' : 'Submit progress'}
      fields={reviewing ? reviewFields : progressFields}
      values={resubmitting ? edit.record : {}}
      path={reviewing || resubmitting ? root + edit.record.id + '/' + edit.mode + '/' : root}
      onCancel={() => setEdit(null)} onSaved={finish} />}
    <Load state={state}>{data => <>
      <Records records={data.results} empty={pending ? 'No updates awaiting your review.' : 'No progress updates yet.'}
        render={record => <><div>
          <strong>{record.percent_complete}% reported · {record.reporting_date}</strong>
          <small>Update #{record.id} · User #{record.author}{record.replaces && ' · Revises #' + record.replaces}</small>
          <p>{record.summary}</p>
          {record.blockers && <small>Blockers: {record.blockers}</small>}
          {record.next_steps && <small>Next steps: {record.next_steps}</small>}
          {record.evidence_url && <small><a href={record.evidence_url} target="_blank" rel="noreferrer">Open evidence link</a></small>}
          {record.evidence_name && <small><a href={API + root + record.id + '/evidence/'}>Download {record.evidence_name}</a></small>}
          <p><span className="pill">{label(record.review?.decision ?? 'pending review')}</span>
            {record.replaced && ' · Revised'}</p>
          {record.review && <small>Reviewed by user #{record.review.reviewer} · {new Date(record.review.created_at).toLocaleString()}</small>}
          {record.review?.comment && <p>{record.review.comment}</p>}
        </div>
        {canReview && !record.review && record.author !== user.id &&
          <button onClick={() => setEdit({mode: 'review', record})}>Review</button>}
        {canSubmit && record.author === user.id && record.review?.decision === 'correction_requested' && !record.replaced &&
          <button onClick={() => setEdit({mode: 'resubmit', record})}>Resubmit</button>}
        </>} />
      <Pager page={page} setPage={setPage} data={data} />
    </>}</Load>
  </section>
}

function ProjectTab({tab, project, user}) {
  const root = 'projects/' + project.id + '/'
  const [page, setPage] = useState(1)
  const [version, setVersion] = useState(0)
  const [edit, setEdit] = useState(null)
  const [scenario, setScenario] = useState({})
  const state = useLoad(root + tab + '/?' + queryString({...scenario, page}), version)
  const manage = user.is_superuser || project.owner === user.id
  const team = useLoad(edit && manage && tab === 'work-items' ? root + 'team/' : null)
  const choices = team.data ? accountChoices([team.data.owner, ...team.data.members]) : []
  if (edit?.assignee && !choices.some(choice => choice.value === edit.assignee)) {
    choices.push({value: edit.assignee, label: 'Previous assignee (access removed)'})
  }
  const canWrite = !project.archived_at && {
    'work-items': manage && permitted(user, 'add_workitem'),
    expenditure: manage && permitted(user, 'add_expenditure'),
  }[tab]
  const forms = {'work-items': itemFields.map(field => field[0] === 'assignee'
    ? ['assignee', 'Assignee', choices, false] : field), expenditure: expenditureFields}
  const headings = {'work-items': 'Tasks and milestones',
    expenditure: 'Budget and expenditure', audit: 'Audit history', analytics: 'Analytics and scenarios'}
  const actions = {'work-items': 'Add work item', expenditure: 'Record expenditure'}
  if (tab === 'analytics') return <section className="panel"><h2>{headings[tab]}</h2>
    <form className="filters" onSubmit={event => {event.preventDefault(); setScenario(Object.fromEntries(new FormData(event.currentTarget)))}}>
      {[['budget_cut', 'Budget cut (%)'], ['extra_days', 'Additional delay (days)'],
        ['price_increase', 'Price increase (%)'], ['resource_loss', 'Resource loss (%)']].map(([name, caption]) =>
        <Field key={name} field={[name, caption, 'integer']} values={{[name]: 0}} />)}
      <button className="primary">Run scenario</button>
    </form>
    <Load state={state}>{data => <Analytics data={data} />}</Load>
  </section>
  return <section className="panel">
    <div className="section-title"><h2>{headings[tab]}</h2>
      {canWrite && <button className="primary" onClick={() => setEdit({})}>{actions[tab]}</button>}
    </div>
    {edit && manage && tab === 'work-items' && team.error && <p className="error" role="alert">{team.error.message}</p>}
    {edit && (!manage || tab !== 'work-items' || team.data) && <Editor key={edit.id ?? 'new'} title={edit.id ? 'Update work item' : actions[tab]}
      fields={edit.progressOnly ? [itemFields[6]] : forms[tab]}
      values={{kind: 'task', percent_complete: 0, is_active: true, ...edit}}
      path={root + tab + '/' + (edit.id ? edit.id + '/' : '')} method={edit.id ? 'PATCH' : 'POST'}
      onCancel={() => setEdit(null)} onSaved={() => {setEdit(null); setPage(1); setVersion(v => v + 1)}} />}
    <Load state={state}>{data => <>
      {data.summary && <Budget summary={data.summary} />}
      <Records records={data.results} empty="No records yet." render={record => {
        if (tab === 'work-items') {
          const canEdit = !project.archived_at && permitted(user, 'change_workitem') && (manage || (record.assignee === user.id && record.is_active))
          return <><div><strong>{record.title}</strong><small>{label(record.kind)} · #{record.id} · Due {record.planned_end} · {label(record.status)} · {record.percent_complete}%</small>
            {record.weight != null && <small>Progress weight {record.weight}</small>}
            {record.assignee && <small>Assigned to user #{record.assignee}</small>}
            {record.predecessor && <small>Depends on #{record.predecessor}</small>}</div>
            {canEdit && <button onClick={() => setEdit({...record, progressOnly: !manage})}>Edit</button>}</>
        }
        if (tab === 'expenditure') return <div><strong>{money(record.amount, project.currency)} · {record.category}</strong>
          <small>{record.date} · {record.reference}</small>{record.note && <p>{record.note}</p>}</div>
        return <div><strong>{label(record.action)}</strong><small>User #{record.actor} · {new Date(record.created_at).toLocaleString()}</small>
          {Object.keys(record.changes).length > 0 && <pre>{JSON.stringify(record.changes, null, 2)}</pre>}</div>
      }} /><Pager page={page} setPage={setPage} data={data} />
    </>}</Load>
  </section>
}

function ProjectTeam({project, user, onManagerChange}) {
  const root = 'projects/' + project.id + '/'
  const [version, setVersion] = useState(0)
  const [edit, setEdit] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const team = useLoad(root + 'team/', version)
  const managers = useLoad(edit === 'manager' ? 'manager-directory/' : null)
  function refresh() {
    setEdit('')
    setVersion(value => value + 1)
  }
  async function remove(member) {
    setBusy(true)
    setError('')
    try {
      await save(root + 'team/', {user_id: member.id}, 'DELETE')
      refresh()
    } catch (error) {
      setError(error.message)
    } finally {
      setBusy(false)
    }
  }
  return <section className="panel">
    <div className="section-title"><h2>Project team</h2>
      {!project.archived_at && <div className="actions">
        <button onClick={() => setEdit('member')}>Add employee</button>
        {user.is_superuser && <button onClick={() => setEdit('manager')}>Assign manager</button>}
      </div>}
    </div>
    {error && <p className="error" role="alert">{error}</p>}
    <Load state={team}>{data => <>
      <p>Project manager <strong>{accountName(data.owner)}</strong></p>
      {edit === 'member' && (data.candidates.length ?
        <Editor title="Give project access" fields={[[ 'user_id', 'Employee', accountChoices(data.candidates) ]]}
          path={root + 'team/'} onSaved={refresh} onCancel={() => setEdit('')} /> :
        <p>No eligible accounts are available. Ask an administrator to create an employee account.</p>)}
      {edit === 'manager' && <Load state={managers}>{accounts =>
        <Editor title="Appoint project manager" fields={[[ 'user_id', 'Manager', accountChoices(accounts) ]]}
          values={{user_id: data.owner.id}} path={root + 'manager/'}
          onSaved={() => {refresh(); onManagerChange()}} onCancel={() => setEdit('')} />
      }</Load>}
      <Records records={data.members} empty="No employees have been added." render={member => <>
        <div><strong>{accountName(member)}</strong><small>{member.username}</small></div>
        {!project.archived_at && <button disabled={busy} onClick={() => remove(member)}>Remove access</button>}
      </>} />
    </>}</Load>
  </section>
}

function Budget({summary}) {
  return <div className="metrics">{[['Approved budget', summary.approved_budget], ['Recorded expenditure', summary.recorded_expenditure],
    ['Remaining', summary.remaining], ['Variance (spent − budget)', summary.variance]].map(([name, value]) =>
    <div className="panel metric" key={name}><span>{name}</span><strong>{money(value, summary.currency)}</strong></div>)}</div>
}

function Analytics({data}) {
  const {evm, forecast, currency} = data
  return <><div className="metrics">
    {[['Schedule index', evm.spi], ['Cost index', evm.cpi], ['Estimated at completion', money(evm.eac, currency)]].map(([name, value]) =>
      <div className="panel metric" key={name}><span>{name}</span><strong>{value ?? '—'}</strong></div>)}
    </div><p className="caption">{evm.method}</p>
    {(evm.schedule_status || evm.cost_status) && <p>Schedule: {evm.schedule_status || 'insufficient data'} · Cost: {evm.cost_status || 'insufficient data'}</p>}
    <h3>Synthetic forecast</h3>
    {forecast.status === 'available' ? <><p>Delay probability <strong>{Math.round(forecast.delay_probability * 100)}%</strong> · Estimated delay <strong>{forecast.days_late} days</strong> · Estimated final cost <strong>{money(forecast.final_cost, currency)}</strong></p>
      <p className="caption">{forecast.limitation} Method {forecast.method}. Reporting date {forecast.data_date}.</p></> :
      <p className="empty">Insufficient data. Add a milestone, budget and progress report to an underway project.</p>}
    {data.forest_evaluation && <p className="caption">
      Random Forest evaluation on {data.forest_evaluation.held_out_projects} synthetic projects ·
      {' '}{(data.forest_evaluation.delay_accuracy * 100).toFixed(1)}% delay accuracy ·
      {' '}{data.forest_evaluation.days_late_mae.toFixed(2)} days mean absolute error ·
      {' '}{(data.forest_evaluation.final_cost_ratio_mae * 100).toFixed(2)} percentage points cost-ratio error.
    </p>}
    <h3>Scenario comparison</h3><p className="caption">{data.scenario_basis}</p>
    <div className="table-wrap"><table><thead><tr><th>Case</th><th>Budget</th><th>Est. cost</th><th>Budget gap</th><th>Projected date</th></tr></thead>
      <tbody>{data.scenarios.map(row => <tr key={row.case}><td>{label(row.case)}</td><td>{money(row.budget, currency)}</td>
        <td>{money(row.estimated_cost, currency)}</td><td>{money(row.budget_gap, currency)}</td><td>{row.finish_date}</td></tr>)}</tbody>
    </table></div>
  </>
}

export function ProjectDetail({id, user}) {
  const statuses = useContext(StatusContext)
  const [tab, setTab] = useState('overview')
  const [edit, setEdit] = useState(false)
  const [version, setVersion] = useState(0)
  const [archiveError, setArchiveError] = useState('')
  const [archiveBusy, setArchiveBusy] = useState(false)
  const state = useLoad('projects/' + id + '/', version)
  const reload = () => setVersion(v => v + 1)
  async function changeArchive(archived) {
    setArchiveBusy(true)
    setArchiveError('')
    try {
      await save('projects/' + id + '/archive/', {archived})
      setEdit(false)
      reload()
    } catch (error) {
      setArchiveError(error.message)
    } finally {
      setArchiveBusy(false)
    }
  }
  return <>
    <Load state={state}>{project => {
      const owner = user.is_superuser || user.id === project.owner
      const canManage = owner && permitted(user, 'change_project')
      const portfolio = owner || permitted(user, 'view_projectauditevent')
      const archived = Boolean(project.archived_at)
      const tabs = [['overview', 'Overview'], ['work-items', portfolio ? 'Tasks & milestones' : 'My tasks'], ['progress-updates', 'Progress']]
      if (portfolio) tabs.push(['expenditure', 'Budget'], ['analytics', 'Analytics'], ['audit', 'History'])
      if (canManage) tabs.push(['team', 'Team'])
      return <><a className="back" href={archived ? '#/projects/archived' : '#/projects'}>
        ← {archived ? 'Archived projects' : 'Project register'}
      </a><Heading tag={project.department} title={project.title}
        subtitle={'Due ' + project.planned_end + ' · ' + statusCaption(statuses, project.status) + (archived ? ' · Archived' : '')}
        action={canManage && <div className="actions">
          {!archived && <button onClick={() => setEdit(true)}>Edit project</button>}
          {(archived || ['completed', 'cancelled'].includes(project.status)) &&
            <button disabled={archiveBusy} onClick={() => changeArchive(!archived)}>
              {archived ? 'Restore project' : 'Archive project'}
            </button>}
        </div>} />
        {archiveError && <p className="error" role="alert">{archiveError}</p>}
        <div className="tabs" aria-label="Project sections">{tabs.map(([key, text]) =>
          <button key={key} aria-pressed={tab === key} onClick={() => {
            setTab(key)
            if (key === 'overview' && tab !== key) reload()
          }}>{text}</button>)}</div>
        {edit && <Editor title="Edit project" fields={[...projectFormFields(statuses, project.status), ['budget_revision_reason', 'Reason if revising budget', 'textarea', false]]} values={project} path={'projects/' + id + '/'}
          method="PATCH" onCancel={() => setEdit(false)} onSaved={() => {setEdit(false); reload()}} />}
        {tab === 'overview' ? <><section className="panel project-overview"><h2>Project overview</h2>
          <p>{project.description || 'No description provided.'}</p>
          {portfolio && project.progress_summary?.percent != null && <div className="overview-progress">
            <small>Project progress</small><strong>{project.progress_summary.percent}%</strong>
            <progress aria-label="Project progress" value={project.progress_summary.percent} max="100" />
          </div>}
          <dl><dt>Project ID</dt><dd>{project.id}</dd><dt>Department</dt><dd>{project.department}</dd>
            <dt>Planned start</dt><dd>{project.planned_start}</dd>
            {portfolio && <><dt>Owner</dt><dd>User #{project.owner}</dd>
              <dt>Approved budget</dt><dd>{money(project.approved_budget, project.currency)}</dd>
              <dt>Progress</dt><dd>{project.progress_summary?.percent == null ? 'Unavailable' :
                project.progress_summary.percent + '% · ' + label(project.progress_summary.source)}</dd></>}</dl></section></> :
          tab === 'progress-updates' ? <ProgressTab project={project} user={user} /> :
          tab === 'team' && canManage ? <ProjectTeam project={project} user={user} onManagerChange={reload} /> :
          <ProjectTab key={tab} tab={tab} project={project} user={user} />}
      </>
    }}</Load>
  </>
}

export function Notifications() {
  const [page, setPage] = useState(1)
  const [unread, setUnread] = useState(false)
  const [version, setVersion] = useState(0)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const state = useLoad('notifications/?' + queryString({page, unread: unread ? '1' : ''}), version)

  async function refresh(path) {
    setBusy(true)
    setError('')
    try {
      await save(path, {})
      setPage(1)
      setVersion(value => value + 1)
      window.dispatchEvent(new Event('notifications:changed'))
    } catch (error) {
      setError(error.message)
    } finally {
      setBusy(false)
    }
  }

  useEffect(() => {
    refresh('notifications/sync/')
  }, [])

  return <><Heading tag="INBOX" title="Notifications" subtitle="Task assignments, milestone deadlines and progress review decisions."
    action={<button onClick={() => refresh('notifications/sync/')} disabled={busy}>Refresh inbox</button>} />
    <section className="panel">
      <div className="tabs" aria-label="Notification filters">
        <button aria-pressed={!unread} onClick={() => {setUnread(false); setPage(1)}}>All</button>
        <button aria-pressed={unread} onClick={() => {setUnread(true); setPage(1)}}>Unread</button>
      </div>
      {error && <p className="error" role="alert">{error}</p>}
      <Load state={state}>{data => <>
        <Records records={data.results} empty={unread ? 'No unread notifications.' : 'Your inbox is empty.'}
          render={notice => <><div>
            <span className="pill">{notice.read_at ? 'Read' : 'Unread'}</span>
            <p><strong>{notice.message}</strong></p>
            <small><a href={'#/projects/' + notice.project}>{notice.project_title}</a>
              {' · ' + new Date(notice.created_at).toLocaleString()}</small>
          </div>
          {!notice.read_at && <button disabled={busy} onClick={() => refresh('notifications/' + notice.id + '/read/')}>
            Mark as read
          </button>}
          </>} />
        <Pager page={page} setPage={setPage} data={data} />
      </>}</Load>
    </section>
  </>
}

function ReportBars({rows, format}) {
  const max = Math.max(1, ...rows.map(row => Number(row.value)))
  return <ul className="report-bars">{rows.map(({name, value, tone}) => <li key={name}>
    <div className="report-bar-label"><span>{name}</span><strong>{format(value)}</strong></div>
    <div className="report-bar-track" aria-hidden="true">
      <div className={'report-bar-fill ' + (tone ?? '')} style={{width: 100 * Number(value) / max + '%'}} />
    </div>
  </li>)}</ul>
}

function ReportCharts({charts}) {
  const statuses = useContext(StatusContext)
  if (!Object.keys(charts.status_counts).length) return null
  return <div className="report-chart-grid">
    <section className="panel report-chart">
      <div className="report-chart-title"><span className="tile-icon"><Icon name="dashboard" /></span>
        <div><h2>Projects by status</h2><small>Count across the filtered portfolio</small></div></div>
      <ReportBars rows={Object.entries(charts.status_counts).map(([status, value]) => ({
        name: statusCaption(statuses, status).replace(/^./, char => char.toUpperCase()), value,
      }))} format={value => value.toLocaleString()} />
    </section>
    <section className="panel report-chart">
      <div className="report-chart-title"><span className="tile-icon"><Icon name="reports" /></span>
        <div><h2>Budget vs recorded spending</h2><small>Each currency has its own scale</small></div></div>
      {Object.entries(charts.spending).map(([currency, totals]) => <div className="report-currency" key={currency}>
        <h3>{currency}</h3>
        <ReportBars rows={[
          {name: 'Approved budget', value: totals.budget},
          {name: 'Recorded spending', value: totals.recorded, tone: 'spending'},
        ]} format={value => money(value, currency)} />
      </div>)}
    </section>
  </div>
}

export function Reports() {
  const statuses = useContext(StatusContext)
  const [filters, setFilters] = useState({})
  const query = queryString(filters)
  const state = useLoad('reports/?' + query)
  return <><Heading tag="REPORTING" title="Portfolio reports" subtitle="Filter by department, project status and planned date range."
    action={<div className="actions">
      <a className="button" href={API + 'reports/?export=csv&' + query}>Download CSV</a>
      <a className="button" href={API + 'reports/?export=xlsx&' + query}>Download Excel</a>
      <a className="button primary" href={API + 'reports/?export=pdf&' + query}>Download PDF</a>
    </div>} />
    <section className="panel"><form className="filters" onSubmit={event => {
      event.preventDefault(); setFilters(Object.fromEntries(new FormData(event.currentTarget)))
    }}>
      {[['project_id', 'Project ID', 'text', false], ['department', 'Department', 'text', false], ['status', 'Status', statuses.length ? statuses : statusOptions, false],
        ['start', 'From', 'date', false], ['end', 'To', 'date', false]].map(field =>
        <Field key={field[0]} field={field} values={{}} />)}
      <button>Apply filters</button>
    </form>
    </section>
    <Load state={state}>{data => <>
      <ReportCharts charts={data.charts} />
      <section className="panel"><h2>Project details</h2>
        <p>{data.count} matching projects{data.count > data.results.length ? ' · Table preview limited to 200' : ''}</p>
        <ProjectTable rows={data.results} />
      </section>
    </>}</Load>
  </>
}

