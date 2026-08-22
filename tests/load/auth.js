// k6 Load Test: Authentication Endpoints
// Run with: k6 run tests/load/auth.js

import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate } from 'k6/metrics';

export const options = {
  stages: [
    { duration: '30s', target: 20 },  // Ramp up
    { duration: '1m', target: 50 },   // Stay at 50 VUs
    { duration: '30s', target: 100 }, // Spike to 100 VUs
    { duration: '1m', target: 100 },  // Stay at 100 VUs
    { duration: '30s', target: 0 },   // Ramp down
  ],
  thresholds: {
    http_req_duration: ['p(95)<500'],      // 95% of requests < 500ms
    http_req_failed: ['rate<0.01'],        // Error rate < 1%
    'checks{type:register}': ['rate>0.99'], // 99% success rate for register
    'checks{type:login}': ['rate>0.99'],    // 99% success rate for login
  },
};

const BASE_URL = __ENV.BASE_URL || 'https://api.ominivoice.local';
const registerFailRate = new Rate('register_fail_rate');
const loginFailRate = new Rate('login_fail_rate');

export function setup() {
  // Create a test user for login tests
  const email = `loadtest-${Date.now()}@example.com`;
  const password = 'LoadTest123!';

  const registerRes = http.post(`${BASE_URL}/auth/register`, JSON.stringify({
    email,
    password,
  }), {
    headers: { 'Content-Type': 'application/json' },
  });

  if (registerRes.status !== 201) {
    console.log(`Setup: Failed to create test user: ${registerRes.body}`);
    return { email, password, token: null };
  }

  const loginRes = http.post(`${BASE_URL}/auth/login`, JSON.stringify({
    username: email,
    password,
  }), {
    headers: { 'Content-Type': 'application/json' },
  });

  let token = null;
  if (loginRes.status === 200) {
    token = loginRes.json('access_token');
  }

  return { email, password, token };
}

export default function (data) {
  const { email, password, token } = data;

  // Test 1: Register new user (each VU creates unique user)
  const uniqueEmail = `loadtest-${__VU}-${__ITER}-${Date.now()}@example.com`;
  const registerPayload = JSON.stringify({
    email: uniqueEmail,
    password: 'LoadTest123!',
  });

  const registerRes = http.post(`${BASE_URL}/auth/register`, registerPayload, {
    headers: { 'Content-Type': 'application/json' },
    tags: { type: 'register' },
  });

  const registerSuccess = check(registerRes, {
    'register status is 201': (r) => r.status === 201,
    'register returns user data': (r) => r.json('email') === uniqueEmail,
  });

  registerFailRate.add(!registerSuccess);

  sleep(1);

  // Test 2: Login with created user
  const loginPayload = JSON.stringify({
    username: uniqueEmail,
    password: 'LoadTest123!',
  });

  const loginRes = http.post(`${BASE_URL}/auth/login`, loginPayload, {
    headers: { 'Content-Type': 'application/json' },
    tags: { type: 'login' },
  });

  const loginSuccess = check(loginRes, {
    'login status is 200': (r) => r.status === 200,
    'login returns access_token': (r) => r.json('access_token') !== undefined,
    'login returns refresh_token': (r) => r.json('refresh_token') !== undefined,
  });

  loginFailRate.add(!loginSuccess);

  if (loginSuccess) {
    const accessToken = loginRes.json('access_token');

    // Test 3: Get current user (/auth/me)
    const meRes = http.get(`${BASE_URL}/auth/me`, {
      headers: { Authorization: `Bearer ${accessToken}` },
      tags: { type: 'me' },
    });

    check(meRes, {
      'me status is 200': (r) => r.status === 200,
      'me returns email': (r) => r.json('email') === uniqueEmail,
    });
  }

  sleep(2);
}

export function teardown(data) {
  console.log('Load test completed');
  console.log(`Register fail rate: ${registerFailRate.values.rate * 100}%`);
  console.log(`Login fail rate: ${loginFailRate.values.rate * 100}%`);
}