// k6 Load Test: Agent CRUD Operations
// Run with: k6 run tests/load/agents.js

import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate } from 'k6/metrics';

export const options = {
  stages: [
    { duration: '30s', target: 10 },  // Ramp up
    { duration: '1m', target: 30 },   // Stay at 30 VUs
    { duration: '30s', target: 50 },  // Spike to 50 VUs
    { duration: '1m', target: 50 },   // Stay at 50 VUs
    { duration: '30s', target: 0 },   // Ramp down
  ],
  thresholds: {
    http_req_duration: ['p(95)<500'],
    http_req_failed: ['rate<0.01'],
    'checks{type:create}': ['rate>0.99'],
    'checks{type:list}': ['rate>0.99'],
    'checks{type:get}': ['rate>0.99'],
    'checks{type:update}': ['rate>0.99'],
    'checks{type:delete}': ['rate>0.99'],
  },
};

const BASE_URL = __ENV.BASE_URL || 'https://api.ominivoice.local';
const createFailRate = new Rate('create_fail_rate');
const listFailRate = new Rate('list_fail_rate');
const getFailRate = new Rate('get_fail_rate');
const updateFailRate = new Rate('update_fail_rate');
const deleteFailRate = new Rate('delete_fail_rate');

function getHeaders(token) {
  return {
    Authorization: `Bearer ${token}`,
    'Content-Type': 'application/json',
  };
}

export function setup() {
  // Create a test user and get token
  const email = `loadtest-agent-${Date.now()}@example.com`;
  const password = 'LoadTest123!';

  let registerRes = http.post(`${BASE_URL}/auth/register`, JSON.stringify({
    email,
    password,
  }), {
    headers: { 'Content-Type': 'application/json' },
  });

  if (registerRes.status !== 201) {
    console.log(`Setup: Failed to create test user: ${registerRes.body}`);
    return { token: null };
  }

  let loginRes = http.post(`${BASE_URL}/auth/login`, JSON.stringify({
    username: email,
    password,
  }), {
    headers: { 'Content-Type': 'application/json' },
  });

  let token = null;
  if (loginRes.status === 200) {
    token = loginRes.json('access_token');
  }

  return { token };
}

export default function (data) {
  const { token } = data;

  if (!token) {
    console.log('No token available, skipping test');
    return;
  }

  const headers = getHeaders(token);
  let agentId = null;

  // Test 1: Create Agent
  const createPayload = JSON.stringify({
    name: `Load Test Agent ${__VU}-${__ITER}`,
    direction: 'outbound',
    system_prompt: 'You are a test agent.',
    opening_line: 'Hello, this is a test call.',
    objective_prompt: 'Verify the system works.',
    llm_provider: 'nvidia_integrate',
    llm_model: 'stepfun-ai/step-3.7-flash',
  });

  const createRes = http.post(`${BASE_URL}/agents`, createPayload, {
    headers,
    tags: { type: 'create' },
  });

  const createSuccess = check(createRes, {
    'create status is 201': (r) => r.status === 201,
    'create returns agent id': (r) => r.json('id') !== undefined,
  });

  createFailRate.add(!createSuccess);

  if (createSuccess) {
    agentId = createRes.json('id');
  }

  sleep(1);

  // Test 2: List Agents
  const listRes = http.get(`${BASE_URL}/agents`, {
    headers,
    tags: { type: 'list' },
  });

  const listSuccess = check(listRes, {
    'list status is 200': (r) => r.status === 200,
    'list returns array': (r) => Array.isArray(r.json()),
  });

  listFailRate.add(!listSuccess);

  sleep(1);

  // Test 3: Get Agent (if created)
  if (agentId) {
    const getRes = http.get(`${BASE_URL}/agents/${agentId}`, {
      headers,
      tags: { type: 'get' },
    });

    const getSuccess = check(getRes, {
      'get status is 200': (r) => r.status === 200,
      'get returns correct agent': (r) => r.json('id') === agentId,
    });

    getFailRate.add(!getSuccess);

    sleep(1);

    // Test 4: Update Agent
    const updatePayload = JSON.stringify({
      name: `Updated Load Test Agent ${__VU}-${__ITER}`,
      system_prompt: 'You are an updated test agent.',
    });

    const updateRes = http.patch(`${BASE_URL}/agents/${agentId}`, updatePayload, {
      headers,
      tags: { type: 'update' },
    });

    const updateSuccess = check(updateRes, {
      'update status is 200': (r) => r.status === 200,
      'update returns updated name': (r) => r.json('name').includes('Updated'),
    });

    updateFailRate.add(!updateSuccess);

    sleep(1);

    // Test 5: Delete Agent
    const deleteRes = http.del(`${BASE_URL}/agents/${agentId}`, null, {
      headers,
      tags: { type: 'delete' },
    });

    const deleteSuccess = check(deleteRes, {
      'delete status is 204': (r) => r.status === 204,
    });

    deleteFailRate.add(!deleteSuccess);
  }

  sleep(2);
}

export function teardown(data) {
  console.log('Agent CRUD load test completed');
  console.log(`Create fail rate: ${createFailRate.values.rate * 100}%`);
  console.log(`List fail rate: ${listFailRate.values.rate * 100}%`);
  console.log(`Get fail rate: ${getFailRate.values.rate * 100}%`);
  console.log(`Update fail rate: ${updateFailRate.values.rate * 100}%`);
  console.log(`Delete fail rate: ${deleteFailRate.values.rate * 100}%`);
}