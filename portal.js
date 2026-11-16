(() => {
  const config = window.EZI_PORTAL;
  const portal = document.querySelector('#client-portal');
  const support = document.querySelector('#supportForm');
  const status = document.querySelector('#portalStatus');
  const login = document.querySelector('#portalLogin');
  const account = document.querySelector('#portalAccount');
  const applications = document.querySelector('#portalApplications');
  const more = document.querySelector('#portalMore');
  const callback = location.origin + '/';
  const sessionKey = 'ezi-portal-session';
  const flowKey = 'ezi-portal-login';
  let cursor;

  function session() {
    const stored = JSON.parse(sessionStorage.getItem(sessionKey) || 'null');
    return stored && stored.expires > Date.now() ? stored : null;
  }

  function encode(bytes) {
    return btoa(String.fromCharCode(...bytes)).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
  }

  async function request(path, { token, body } = {}) {
    const response = await fetch(config.api + path, {
      method: body ? 'POST' : 'GET',
      headers: {
        ...(token && { Authorization: token }),
        ...(body && { 'Content-Type': 'application/json' }),
      },
      body: body && JSON.stringify(body),
    });
    const data = await response.json().catch(() => ({}));
    if (response.status === 401) {
      sessionStorage.removeItem(sessionKey);
      account.hidden = true;
      login.hidden = false;
      throw new Error('Your session expired. Please sign in again.');
    }
    if (!response.ok) throw new Error(data.message || 'Please try again.');
    return data;
  }

  async function showApplications(append = false) {
    const current = session();
    if (!current) {
      account.hidden = true;
      login.hidden = false;
      status.textContent = 'Sign in to view your applications.';
      return;
    }

    account.hidden = false;
    login.hidden = true;
    status.textContent = 'Loading applications…';
    more.disabled = true;
    try {
      const result = await request('/applications' + (append ? '?before=' + encodeURIComponent(cursor) : ''), {
        token: current.token,
      });
      if (!append) applications.replaceChildren();
      for (const item of result.applications) {
        const row = document.createElement('li');
        const service = document.createElement('strong');
        service.textContent = item.service;
        const details = document.createElement('small');
        details.textContent = [item.status, new Date(item.createdAt).toLocaleDateString(), item.applicationId].join(' · ');
        row.append(service, details);
        applications.append(row);
      }
      cursor = result.next;
      more.hidden = !cursor;
      status.textContent = applications.children.length ? '' : 'You have no applications yet.';
    } catch (error) {
      status.textContent = error.message;
    } finally {
      more.disabled = false;
    }
  }

  if (!config) {
    status.textContent = 'The client portal is temporarily unavailable.';
    portal.querySelector('#portalLogin').disabled = true;
    support.querySelector('button').disabled = true;
    support.querySelector('[role="status"]').textContent = 'The support form is temporarily unavailable.';
    return;
  }

  login.addEventListener('click', async () => {
    login.disabled = true;
    try {
      const verifier = encode(crypto.getRandomValues(new Uint8Array(32)));
      const state = encode(crypto.getRandomValues(new Uint8Array(32)));
      const challenge = encode(new Uint8Array(await crypto.subtle.digest('SHA-256', new TextEncoder().encode(verifier))));
      sessionStorage.setItem(flowKey, JSON.stringify({ verifier, state }));
      location.assign(config.cognito + '/oauth2/authorize?' + new URLSearchParams({
        response_type: 'code', client_id: config.client, redirect_uri: callback,
        scope: 'openid email', state, code_challenge: challenge, code_challenge_method: 'S256',
      }));
    } catch {
      status.textContent = 'Unable to open sign-in. Please try again.';
      login.disabled = false;
    }
  });

  document.querySelector('#portalLogout').addEventListener('click', () => {
    sessionStorage.removeItem(sessionKey);
    location.assign(config.cognito + '/logout?' + new URLSearchParams({ client_id: config.client, logout_uri: callback }));
  });
  document.querySelector('#portalRefresh').addEventListener('click', () => showApplications());
  more.addEventListener('click', () => showApplications(true));

  async function finishSignIn() {
    const params = new URLSearchParams(location.search);
    if (params.has('code') || params.has('error')) {
      const flow = JSON.parse(sessionStorage.getItem(flowKey) || 'null');
      sessionStorage.removeItem(flowKey);
      history.replaceState(null, '', '/#client-portal');
      portal.scrollIntoView();
      if (!flow || flow.state !== params.get('state') || !params.has('code')) {
        throw new Error('Sign-in could not be completed. Please try again.');
      }
      const response = await fetch(config.cognito + '/oauth2/token', {
        method: 'POST',
        body: new URLSearchParams({
          grant_type: 'authorization_code', client_id: config.client, redirect_uri: callback,
          code: params.get('code'), code_verifier: flow.verifier,
        }),
      });
      if (!response.ok) throw new Error('Sign-in could not be completed. Please try again.');
      const tokens = await response.json();
      sessionStorage.setItem(sessionKey, JSON.stringify({
        token: tokens.id_token,
        expires: Date.now() + tokens.expires_in * 1000 - 5000,
      }));
    }
    if (session()) await showApplications();
  }

  const applicationForm = document.querySelector('#applicationForm');
  let pendingApplication;
  applicationForm.addEventListener('input', () => { pendingApplication = undefined; });
  applicationForm.addEventListener('submit', async event => {
    event.preventDefault();
    const feedback = applicationForm.querySelector('[role="status"]');
    const button = applicationForm.querySelector('button');
    const current = session();
    if (!current) {
      feedback.textContent = 'Your session expired. Sign in again to submit.';
      login.hidden = false;
      return;
    }

    pendingApplication ||= new Date().toISOString().replace(/\D/g, '') + '000-' + crypto.randomUUID().replace(/-/g, '');
    button.disabled = true;
    try {
      const body = Object.fromEntries(new FormData(applicationForm));
      body.applicationId = pendingApplication;
      const result = await request('/applications', { token: current.token, body });
      applicationForm.reset();
      pendingApplication = undefined;
      feedback.textContent = 'Application received. Reference ' + result.applicationId;
      await showApplications();
    } catch (error) {
      feedback.textContent = error.message;
    } finally {
      button.disabled = false;
    }
  });

  support.addEventListener('submit', async event => {
    event.preventDefault();
    const button = support.querySelector('button');
    const feedback = support.querySelector('[role="status"]');
    button.disabled = true;
    feedback.textContent = 'Sending your message…';
    try {
      const result = await request('/support', { body: Object.fromEntries(new FormData(support)) });
      feedback.textContent = result.message;
      support.reset();
    } catch (error) {
      feedback.textContent = error.message;
    } finally {
      button.disabled = false;
    }
  });

  finishSignIn().catch(error => { status.textContent = error.message; });
})();
