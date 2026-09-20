// End-to-end customer journey under load: login → create case → poll until
// done → fetch evidence pack. Verifies the full async pipeline.

import http from 'k6/http';
import { check, sleep, group } from 'k6';
import { uuidv4 } from 'https://jslib.k6.io/k6-utils/1.4.0/index.js';
import { Trend } from 'k6/metrics';
import { login, authHeaders } from '../lib/auth.js';

export const e2eLatency = new Trend('e2e_seconds', true);

export const options = {
  vus: 10,
  duration: '5m',
  thresholds: {
    'e2e_seconds': ['p(95)<90'],
    'http_req_failed': ['rate<0.01'],
  },
};

const BASE  = __ENV.API_BASE || 'http://localhost:8000';
const EMAIL = __ENV.USER     || 'admin@aerofyta.health';
const PASS  = __ENV.PASS     || 'clincase2026';

export function setup() { return { token: login(BASE, EMAIL, PASS) }; }

export default function (data) {
  const start = Date.now();
  let caseId;

  group('create case', () => {
    const res = http.post(`${BASE}/api/v1/cases`, JSON.stringify({
      patient_initials: 'T.S.',
      icd10:            'C50.911',
      cpt:              ['96413'],
      requested_drug:   'trastuzumab',
      payer_id:         'aetna',
    }), {
      headers: authHeaders(data.token, { 'Idempotency-Key': uuidv4() }),
    });
    check(res, { 'created': (r) => r.status >= 200 && r.status < 300 });
    caseId = res.json('id') || res.json('case_id');
  });

  if (!caseId) return;

  group('run async', () => {
    const res = http.post(`${BASE}/api/v1/cases/${caseId}/run-async`, '{}', {
      headers: authHeaders(data.token),
    });
    check(res, { 'started': (r) => r.status >= 200 && r.status < 300 });
  });

  group('poll until done', () => {
    let status = 'pending';
    for (let i = 0; i < 90; i++) {
      sleep(1);
      const res = http.get(`${BASE}/api/v1/cases/${caseId}`, {
        headers: authHeaders(data.token),
      });
      status = res.json('status') || 'unknown';
      if (status === 'done' || status === 'approved' || status === 'denied' || status === 'pended') break;
    }
    check(status, { 'reached terminal': (s) => s !== 'pending' && s !== 'running' });
  });

  group('evidence pack', () => {
    const res = http.get(`${BASE}/api/v1/cases/${caseId}/evidence-pack`, {
      headers: authHeaders(data.token),
    });
    check(res, { 'evidence 200': (r) => r.status === 200 });
  });

  e2eLatency.add((Date.now() - start) / 1000);
}
