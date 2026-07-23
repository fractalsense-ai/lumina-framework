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

/** Create a scoped auth token with organization_id and site_id */
function makeScopedAuth() {
  return {
    ...AUTH_STATE,
    token: `header.${btoa(JSON.stringify({ organization_id: 'org-a', site_id: 'site-a', padding: 'x' })).replace(/=+$/, '').replace(/\+/g, '-').replace(/\//g, '_')}.signature`,
  }
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
      if (url.includes('/api/decision-precedent/preflight')) {
        return Promise.resolve({ ok: true, json: async () => ({
          confidence_record_id: 'conf-1', organization_id: 'org-a', site_id: 'site-a',
          actor_id: 'user1', policy_version: 1, risk_class: 'operational', final_score: 0.8,
          tier: 'suggest_only', rationale_codes: ['high_confidence'], confirmation_required: false,
          escalation_record_id: null,
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

  it('scoped turn performs routing then decision preflight then chat for suggest_only', async () => {
    const scopedAuth = makeScopedAuth()
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
      if (url.includes('/api/decision-precedent/preflight')) {
        return Promise.resolve({ ok: true, json: async () => ({
          confidence_record_id: 'conf-1', organization_id: 'org-a', site_id: 'site-a',
          actor_id: 'user1', policy_version: 1, risk_class: 'operational', final_score: 0.8,
          tier: 'suggest_only', rationale_codes: ['high_confidence'], confirmation_required: false,
          escalation_record_id: null,
        }) })
      }
      if (url.includes('/api/chat')) {
        const payload = JSON.parse(String(options?.body))
        return Promise.resolve({ ok: true, json: async () => ({
          session_id: payload.session_id, response: 'Suggest only response', action: 'continue',
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
    fireEvent.change(input, { target: { value: 'test message' } })
    fireEvent.click(screen.getByRole('button', { name: '' }))

    await waitFor(() => {
      expect(screen.getByText('Suggest only response')).toBeInTheDocument()
    })

    // Assert call ordering: routing preflight → routing confirm → decision preflight → chat
    const callUrls = fetchMock.mock.calls.map((call: unknown[]) => String(call[0]))
    const routingPreflightIdx = callUrls.findIndex((u: string) => u.includes('/api/thread-routing/preflight'))
    const routingConfirmIdx = callUrls.findIndex((u: string) => u.includes('/api/thread-routing/decision-1/confirm'))
    const decisionPreflightIdx = callUrls.findIndex((u: string) => u.includes('/api/decision-precedent/preflight'))
    const chatIdx = callUrls.findIndex((u: string) => u.includes('/api/chat'))
    expect(routingPreflightIdx).toBeGreaterThanOrEqual(0)
    expect(routingConfirmIdx).toBeGreaterThan(routingPreflightIdx)
    expect(decisionPreflightIdx).toBeGreaterThan(routingConfirmIdx)
    expect(chatIdx).toBeGreaterThan(decisionPreflightIdx)
  })

  it('require_confirmation blocks chat until user clicks Continue', async () => {
    const scopedAuth = makeScopedAuth()
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
      if (url.includes('/api/decision-precedent/preflight')) {
        return Promise.resolve({ ok: true, json: async () => ({
          confidence_record_id: 'conf-2', organization_id: 'org-a', site_id: 'site-a',
          actor_id: 'user1', policy_version: 1, risk_class: 'operational', final_score: 0.5,
          tier: 'require_confirmation', rationale_codes: ['medium_confidence'], confirmation_required: true,
          escalation_record_id: null,
        }) })
      }
      if (url.includes('/api/decision-precedent/conf-2/confirm')) {
        return Promise.resolve({ ok: true, json: async () => ({
          confirmation_id: 'confirm-1', confidence_record_id: 'conf-2', tier: 'require_confirmation',
        }) })
      }
      if (url.includes('/api/decision-precedent/conf-2/confirm')) {
        return Promise.resolve({ ok: true, json: async () => ({
          confirmation_id: 'confirm-1', confidence_record_id: 'conf-2', tier: 'require_confirmation',
        }) })
      }
      if (url.includes('/api/chat')) {
        return Promise.resolve({ ok: true, json: async () => ({
          session_id: 'session-1', response: 'Confirmed chat response', action: 'continue',
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
    fireEvent.change(input, { target: { value: 'needs confirmation' } })
    fireEvent.click(screen.getByRole('button', { name: '' }))

    // Should show confirmation panel and NOT call chat yet
    await waitFor(() => {
      expect(screen.getByText(/requires explicit confirmation/i)).toBeInTheDocument()
    })
    // Assert no chat call yet
    const chatCallsBefore = fetchMock.mock.calls.filter((call: unknown[]) => String(call[0]).includes('/api/chat'))
    expect(chatCallsBefore.length).toBe(0)

    // Click Continue button
    const continueButton = screen.getByRole('button', { name: 'Continue' })
    fireEvent.click(continueButton)

    // Now confirmation and chat should proceed — exactly one chat call
    await waitFor(() => {
      expect(screen.getByText('Confirmed chat response')).toBeInTheDocument()
    })
    const confirmCalls = fetchMock.mock.calls.filter((call: unknown[]) => String(call[0]).includes('/api/decision-precedent/conf-2/confirm'))
    const chatCallsAfter = fetchMock.mock.calls.filter((call: unknown[]) => String(call[0]).includes('/api/chat'))
    expect(confirmCalls.length).toBe(1)
    expect(chatCallsAfter.length).toBe(1)
  })

  it('mandatory_escalation blocks chat and shows no approval buttons', async () => {
    const scopedAuth = makeScopedAuth()
    window.localStorage.setItem('lumina.auth', JSON.stringify(scopedAuth))
    let chatCalled = false
    const fetchMock = vi.fn().mockImplementation((url: string) => {
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
      if (url.includes('/api/decision-precedent/preflight')) {
        return Promise.resolve({ ok: true, json: async () => ({
          confidence_record_id: 'conf-3', organization_id: 'org-a', site_id: 'site-a',
          actor_id: 'user1', policy_version: 1, risk_class: 'safety', final_score: 0.2,
          tier: 'mandatory_escalation', rationale_codes: ['low_confidence', 'high_risk'],
          confirmation_required: false, escalation_record_id: 'esc-1',
        }) })
      }
      if (url.includes('/api/chat')) {
        chatCalled = true
        return Promise.resolve({ ok: true, json: async () => ({
          session_id: 'session-1', response: 'Should not appear', action: 'continue',
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
    fireEvent.change(input, { target: { value: 'high risk action' } })
    fireEvent.click(screen.getByRole('button', { name: '' }))

    // Should show escalation notice and NOT call chat
    await waitFor(() => {
      expect(screen.getByText(/human approval is required/i)).toBeInTheDocument()
      // Should NOT have approve/reject buttons
      expect(screen.queryByRole('button', { name: /approve/i })).not.toBeInTheDocument()
      expect(screen.queryByRole('button', { name: /reject/i })).not.toBeInTheDocument()
    })
    const chatCalls = fetchMock.mock.calls.filter((call: unknown[]) => String(call[0]).includes('/api/chat'))
    expect(chatCalls.length).toBe(0)
  })

  it('preflight failure surfaces error and does not send chat', async () => {
    const scopedAuth = makeScopedAuth()
    window.localStorage.setItem('lumina.auth', JSON.stringify(scopedAuth))
    let chatCalled = false
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
      if (url.includes('/api/decision-precedent/preflight')) {
        return Promise.resolve({ ok: false, status: 422, json: async () => ({ detail: 'Preflight validation failed' }), text: async () => 'Preflight validation failed' })
      }
      if (url.includes('/api/chat')) {
        chatCalled = true
        return Promise.resolve({ ok: true, json: async () => ({
          session_id: 'session-1', response: 'Should not appear', action: 'continue',
          prompt_type: 'standard', escalated: false,
        }) })
      }
      return Promise.resolve({ ok: false, status: 404, text: async () => 'unmocked route', json: async () => ({ detail: 'unmocked route' }) })
    })
    vi.stubGlobal('fetch', fetchMock)

    render(<App />)
    await screen.findByRole('button', { name: 'I Agree' })
    fireEvent.click(screen.getByRole('button', { name: 'I Agree' }))
    const input = await screen.findByRole('textbox')
    fireEvent.change(input, { target: { value: 'test preflight failure' } })
    fireEvent.click(screen.getByRole('button', { name: '' }))

    // Wait for the error message to appear - use getAllByText since it may appear in multiple places
    await waitFor(() => {
      const errorElements = screen.getAllByText(/decision precedent check failed/i)
      expect(errorElements.length).toBeGreaterThan(0)
    })
    expect(chatCalled).toBe(false)
  })

  it('confirmation failure surfaces error and does not send chat', async () => {
    const scopedAuth = makeScopedAuth()
    window.localStorage.setItem('lumina.auth', JSON.stringify(scopedAuth))
    const fetchMock = vi.fn().mockImplementation((url: string) => {
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
      if (url.includes('/api/decision-precedent/preflight')) {
        return Promise.resolve({ ok: true, json: async () => ({
          confidence_record_id: 'conf-5', organization_id: 'org-a', site_id: 'site-a',
          actor_id: 'user1', policy_version: 1, risk_class: 'operational', final_score: 0.5,
          tier: 'require_confirmation', rationale_codes: ['medium_confidence'], confirmation_required: true,
          escalation_record_id: null,
        }) })
      }
      if (url.includes('/api/decision-precedent/conf-5/confirm')) {
        return Promise.resolve({ ok: false, status: 409, json: async () => ({ detail: 'Confirmation already consumed' }), text: async () => 'Confirmation already consumed' })
      }
      if (url.includes('/api/chat')) {
        return Promise.resolve({ ok: true, json: async () => ({
          session_id: 'session-1', response: 'Should not appear', action: 'continue',
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
    fireEvent.change(input, { target: { value: 'test confirmation failure' } })
    fireEvent.click(screen.getByRole('button', { name: '' }))

    // Wait for confirmation panel
    await waitFor(() => {
      expect(screen.getByText(/requires explicit confirmation/i)).toBeInTheDocument()
    })

    // Click Continue — confirmation will fail with 409
    const continueButton = screen.getByRole('button', { name: 'Continue' })
    fireEvent.click(continueButton)

    // Should show error and NOT call chat
    await waitFor(() => {
      expect(screen.getByText(/Confirmation already consumed/i)).toBeInTheDocument()
    })
    const chatCalls = fetchMock.mock.calls.filter((call: unknown[]) => String(call[0]).includes('/api/chat'))
    expect(chatCalls.length).toBe(0)
  })

  it('UI never renders submitted message in decision-status panel', async () => {
    const scopedAuth = makeScopedAuth()
    window.localStorage.setItem('lumina.auth', JSON.stringify(scopedAuth))
    const fetchMock = vi.fn().mockImplementation((url: string) => {
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
      if (url.includes('/api/decision-precedent/preflight')) {
        return Promise.resolve({ ok: true, json: async () => ({
          confidence_record_id: 'conf-4', organization_id: 'org-a', site_id: 'site-a',
          actor_id: 'user1', policy_version: 1, risk_class: 'operational', final_score: 0.5,
          tier: 'require_confirmation', rationale_codes: ['medium_confidence'], confirmation_required: true,
          escalation_record_id: null,
        }) })
      }
      return Promise.resolve({ ok: false, text: async () => 'unmocked route' })
    })
    vi.stubGlobal('fetch', fetchMock)

    render(<App />)
    await screen.findByRole('button', { name: 'I Agree' })
    fireEvent.click(screen.getByRole('button', { name: 'I Agree' }))
    const input = await screen.findByRole('textbox')
    const testMessage = 'sensitive message content'
    fireEvent.change(input, { target: { value: testMessage } })
    fireEvent.click(screen.getByRole('button', { name: '' }))

    await waitFor(() => {
      expect(screen.getByText(/requires explicit confirmation/i)).toBeInTheDocument()
      // The decision panel should NOT contain the submitted message text
      const decisionPanel = screen.getByText(/requires explicit confirmation/i).closest('div')
      expect(decisionPanel?.textContent).not.toContain(testMessage)
    })
  })
})
