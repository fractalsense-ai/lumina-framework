import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest'

import App from '../app'

const DOMAIN_INFO_RESPONSE = {
  domain_id: 'domain/edu/algebra-level-1/v1',
  domain_version: '1.0.0',
  ui_manifest: {
    title: 'Lumina Test Domain',
    subtitle: 'Test subtitle',
    domain_label: 'Education',
    consent_heading: 'Consent Heading',
    consent_text: 'Consent text',
    consent_button_label: 'I Agree',
    placeholder_text: 'Type your message...',
  },
}

const AUTH_STATE = {
  token: 'test-token',
  userId: 'user1',
  username: 'testuser',
  role: 'student',
}

/** Route-aware fetch mock — resolves based on URL rather than call order. */
function makeFetchMock(overrides?: Record<string, () => Promise<unknown>>) {
  const routes: Record<string, () => Promise<unknown>> = {
    '/api/auth/me': () => Promise.resolve({ ok: true }),
    '/api/domain-info': () =>
      Promise.resolve({ ok: true, json: async () => DOMAIN_INFO_RESPONSE }),
    '/api/consent/accept': () => Promise.resolve({ ok: true }),
    ...overrides,
  }

  return vi.fn().mockImplementation((url: string) => {
    for (const [path, handler] of Object.entries(routes)) {
      if (url.includes(path)) return handler()
    }
    return Promise.resolve({ ok: false, text: async () => 'unmocked route' })
  })
}

describe('App', () => {
  beforeEach(() => {
    window.localStorage.clear()
    vi.restoreAllMocks()
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('shows consent screen then opens chat interface', async () => {
    window.localStorage.setItem('lumina.auth', JSON.stringify(AUTH_STATE))
    vi.stubGlobal('fetch', makeFetchMock())

    render(<App />)

    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'I Agree' })).toBeInTheDocument()
    })
    fireEvent.click(screen.getByRole('button', { name: 'I Agree' }))

    await waitFor(() => {
      expect(screen.getByRole('textbox')).toBeInTheDocument()
    })
  })

  it('shows api error message when chat request fails', async () => {
    window.localStorage.setItem('lumina.auth', JSON.stringify(AUTH_STATE))
    vi.stubGlobal(
      'fetch',
      makeFetchMock({
        '/api/chat': () =>
          Promise.resolve({ ok: false, text: async () => 'api down' }),
      }),
    )

    render(<App />)

    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'I Agree' })).toBeInTheDocument()
    })
    fireEvent.click(screen.getByRole('button', { name: 'I Agree' }))

    const input = await screen.findByRole('textbox')
    fireEvent.change(input, { target: { value: 'hello' } })
    fireEvent.click(screen.getByRole('button', { name: '' }))

    await waitFor(() => {
      expect(
        screen.getByText(/Sorry, the API request failed/i),
      ).toBeInTheDocument()
    })
  })

  it('routes a scoped first turn before sending chat', async () => {
    const scopedAuth = {
      ...AUTH_STATE,
      token: `header.${btoa(JSON.stringify({ organization_id: 'org-a', site_id: 'site-a', padding: 'x' })).replace(/=+$/, '').replace(/\+/g, '-').replace(/\//g, '_')}.signature`,
    }
    window.localStorage.setItem('lumina.auth', JSON.stringify(scopedAuth))
    const fetchMock = vi.fn().mockImplementation((url: string, options?: RequestInit) => {
      if (url.includes('/api/auth/me') || url.includes('/api/consent/accept')) return Promise.resolve({ ok: true })
      if (url.includes('/api/domain-info')) return Promise.resolve({ ok: true, json: async () => DOMAIN_INFO_RESPONSE })
      if (url.includes('/api/thread-routing/preflight')) {
        return Promise.resolve({ ok: true, json: async () => ({
          decision_id: 'decision-1', decision: 'create_new', thread_id: 'thread-1',
          operator_confirmation_required: false, candidates: [],
        }) })
      }
      if (url.includes('/api/thread-routing/decision-1/confirm')) {
        return Promise.resolve({ ok: true, json: async () => ({
          thread_id: 'thread-1', session_id: 'session-1', decision: 'create_new',
        }) })
      }
      if (url.includes('/api/chat')) {
        const payload = JSON.parse(String(options?.body))
        return Promise.resolve({ ok: true, json: async () => ({
          session_id: payload.session_id, response: 'Routed response', action: 'continue',
          prompt_type: 'standard', escalated: false,
        }) })
      }
      return Promise.resolve({ ok: false, text: async () => 'unmocked route' })
    })
    vi.stubGlobal('fetch', fetchMock)

    render(<App />)
    await screen.findByRole('button', { name: 'I Agree' })
    fireEvent.click(screen.getByRole('button', { name: 'I Agree' }))
    const input = await screen.findByRole('textbox')
    fireEvent.change(input, { target: { value: 'inventory review' } })
    fireEvent.click(screen.getByRole('button', { name: '' }))

    await waitFor(() => {
      const chatCall = fetchMock.mock.calls.find(([url]) => String(url).includes('/api/chat'))
      expect(chatCall).toBeDefined()
      expect(JSON.parse(String(chatCall?.[1]?.body))).toMatchObject({
        session_id: 'session-1', thread_id: 'thread-1', message: 'inventory review',
      })
    })
  })

  it('allows confirmation after a routing intercept', async () => {
    const scopedAuth = {
      ...AUTH_STATE,
      token: `header.${btoa(JSON.stringify({ organization_id: 'org-a', site_id: 'site-a' }))}.signature`,
    }
    window.localStorage.setItem('lumina.auth', JSON.stringify(scopedAuth))
    const fetchMock = vi.fn().mockImplementation((url: string, options?: RequestInit) => {
      if (url.includes('/api/auth/me') || url.includes('/api/consent/accept')) return Promise.resolve({ ok: true })
      if (url.includes('/api/domain-info')) return Promise.resolve({ ok: true, json: async () => DOMAIN_INFO_RESPONSE })
      if (url.includes('/api/thread-routing/preflight')) {
        return Promise.resolve({ ok: true, json: async () => ({
          decision_id: 'decision-2', decision: 'create_new', thread_id: 'thread-2',
          operator_confirmation_required: true, candidates: [],
        }) })
      }
      if (url.includes('/api/thread-routing/decision-2/confirm')) {
        expect(JSON.parse(String(options?.body))).toEqual({ action: 'create_new' })
        return Promise.resolve({ ok: true, json: async () => ({
          thread_id: 'thread-2', session_id: 'session-2', decision: 'create_new',
        }) })
      }
      if (url.includes('/api/chat')) return Promise.resolve({ ok: true, json: async () => ({
        session_id: 'session-2', response: 'Confirmed response', action: 'continue', prompt_type: 'standard', escalated: false,
      }) })
      return Promise.resolve({ ok: false, text: async () => 'unmocked route' })
    })
    vi.stubGlobal('fetch', fetchMock)

    render(<App />)
    await screen.findByRole('button', { name: 'I Agree' })
    fireEvent.click(screen.getByRole('button', { name: 'I Agree' }))
    const input = await screen.findByRole('textbox')
    fireEvent.change(input, { target: { value: 'new work order' } })
    fireEvent.click(screen.getByRole('button', { name: '' }))

    const newButton = await screen.findByRole('button', { name: 'New' })
    expect(newButton).toBeEnabled()
    fireEvent.click(newButton)

    await waitFor(() => {
      expect(screen.getByText('Confirmed response')).toBeInTheDocument()
    })
  })
})
