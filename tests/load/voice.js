// k6 Load Test: Voice WebSocket Streaming
// Run with: k6 run tests/load/voice.js
// Requires k6 with WebSocket support (built-in)

import ws from 'k6/ws';
import { check, sleep } from 'k6';
import { Rate } from 'k6/metrics';

export const options = {
  stages: [
    { duration: '30s', target: 5 },   // Ramp up to 5 VUs
    { duration: '1m', target: 10 },   // Stay at 10 VUs
    { duration: '30s', target: 20 },  // Spike to 20 VUs
    { duration: '2m', target: 20 },   // Stay at 20 VUs (5 min calls)
    { duration: '30s', target: 0 },   // Ramp down
  ],
  thresholds: {
    ws_connecting: ['avg<1000'],        // WebSocket connection < 1s
    ws_messages_received: ['rate>10'],  // Messages per second
    checks: ['rate>0.95'],              // 95% success rate
  },
};

const BASE_URL = __ENV.BASE_URL || 'https://api.ominivoice.local';
const WS_URL = BASE_URL.replace('https://', 'wss://').replace('http://', 'ws://');
const connectFailRate = new Rate('connect_fail_rate');
const messageFailRate = new Rate('message_fail_rate');

export function setup() {
  // Create a test user and agent, get API key
  const email = `loadtest-voice-${Date.now()}@example.com`;
  const password = 'LoadTest123!';

  let registerRes = http.post(`${BASE_URL}/auth/register`, JSON.stringify({
    email,
    password,
  }), {
    headers: { 'Content-Type': 'application/json' },
  });

  if (registerRes.status !== 201) {
    console.log(`Setup: Failed to create test user: ${registerRes.body}`);
    return { apiKey: null, agentId: null };
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

  if (!token) {
    return { apiKey: null, agentId: null };
  }

  // Create agent
  let agentRes = http.post(`${BASE_URL}/agents`, JSON.stringify({
    name: `Load Test Voice Agent`,
    direction: 'outbound',
    system_prompt: 'You are a test agent for load testing. Keep responses very brief - one sentence max.',
    opening_line: 'Hello! This is a load test call.',
    objective_prompt: 'Verify the WebSocket connection works.',
    llm_provider: 'nvidia_integrate',
    llm_model: 'stepfun-ai/step-3.7-flash',
  }), {
    headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
  });

  let agentId = null;
  if (agentRes.status === 201) {
    agentId = agentRes.json('id');
  }

  // Generate API key
  let apiKeyRes = http.post(`${BASE_URL}/agents/${agentId}/api-key`, null, {
    headers: { Authorization: `Bearer ${token}` },
  });

  let apiKey = null;
  if (apiKeyRes.status === 201) {
    apiKey = apiKeyRes.json('key');
  }

  return { apiKey, agentId };
}

export default function (data) {
  const { apiKey, agentId } = data;

  if (!apiKey || !agentId) {
    console.log('No API key or agent ID available, skipping test');
    return;
  }

  const wsUrl = `${WS_URL}/ws?api_key=${apiKey}`;

  ws.connect(wsUrl, {}, function (socket) {
    socket.on('open', function () {
      console.log(`VU ${__VU}: WebSocket connected`);

      // Send config message (required first message)
      const config = {
        type: 'config',
        data: {
          agent_id: agentId,
          direction: 'outbound',
          system_prompt: 'You are a test agent for load testing. Keep responses very brief - one sentence max.',
          voice_stack: 'stack_a',
          opening_line: 'Hello! This is a load test call.',
          objective_prompt: 'Verify the WebSocket connection works.',
          interruption_sensitivity: 'medium',
          max_call_duration_s: 300,
          silence_timeout_s: 5,
          language: 'en-US',
          stt_engine: 'faster-whisper',
          tts_engine: 'kokoro',
          tts_voice: 'af_heart',
          llm_provider: 'nvidia_integrate',
          llm_model: 'stepfun-ai/step-3.7-flash'
        }
      };

      socket.send(JSON.stringify(config));
    });

    socket.on('message', function (message) {
      // Handle binary audio frames and JSON control messages
      if (message.data instanceof ArrayBuffer) {
        // Binary audio frame received from TTS
        // In a real test, we'd play this or measure latency
      } else {
        // JSON control message
        try {
          const msg = JSON.parse(message);
          if (msg.type === 'error') {
            console.log(`VU ${__VU}: Error: ${msg.data.message}`);
            messageFailRate.add(1);
          } else if (msg.type === 'ended') {
            console.log(`VU ${__VU}: Call ended, duration: ${msg.data.duration_seconds}s`);
          }
        } catch (e) {
          // Ignore parse errors
        }
      }
    });

    socket.on('close', function () {
      console.log(`VU ${__VU}: WebSocket closed`);
    });

    socket.on('error', function (e) {
      console.log(`VU ${__VU}: WebSocket error: ${e.error()}`);
      connectFailRate.add(1);
    });

    // Send audio frames every 20ms (simulate 16kHz, 20ms frames)
    const interval = setInterval(function () {
      if (socket.readyState === ws.OPEN) {
        // Generate dummy audio data (int16, 16kHz, mono, 20ms = 320 samples = 640 bytes)
        const audioData = new Int16Array(320);
        for (let i = 0; i < 320; i++) {
          // Generate some dummy audio (sine wave)
          audioData[i] = Math.sin(i * 0.1) * 10000;
        }
        socket.sendBinary(audioData.buffer);
      } else {
        clearInterval(interval);
      }
    }, 20);

    // End call after 30 seconds
    socket.setTimeout(function () {
      socket.send(JSON.stringify({ type: 'end' }));
      clearInterval(interval);
      socket.close();
    }, 30000);
  });

  sleep(35); // Wait for call to complete
}

export function teardown(data) {
  console.log('Voice WebSocket load test completed');
  console.log(`Connect fail rate: ${connectFailRate.values.rate * 100}%`);
  console.log(`Message fail rate: ${messageFailRate.values.rate * 100}%`);
}

// Import http for setup
import http from 'k6/http';