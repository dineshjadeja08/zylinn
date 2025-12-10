import http from 'k6/http';
import { check, sleep, group } from 'k6';
import { Rate, Trend, Counter } from 'k6/metrics';

// Custom metrics
const errorRate = new Rate('errors');
const callDuration = new Trend('call_duration');
const apiResponseTime = new Trend('api_response_time');
const appointmentBookings = new Counter('appointment_bookings');

// Test configuration
export const options = {
  stages: [
    { duration: '2m', target: 10 },   // Ramp up to 10 users
    { duration: '5m', target: 50 },   // Ramp up to 50 users
    { duration: '10m', target: 100 }, // Peak at 100 users
    { duration: '5m', target: 50 },   // Ramp down to 50
    { duration: '2m', target: 0 },    // Ramp down to 0
  ],
  thresholds: {
    http_req_duration: ['p(95)<2000'], // 95% of requests under 2s
    http_req_failed: ['rate<0.05'],     // Error rate under 5%
    errors: ['rate<0.1'],               // Custom error rate under 10%
  },
};

// Test data
const BASE_URL = __ENV.BASE_URL || 'http://localhost:8000';
const API_KEY = __ENV.API_KEY || 'test-api-key';

// Test users pool
const testUsers = [
  { email: 'test1@example.com', password: 'TestPass123!' },
  { email: 'test2@example.com', password: 'TestPass123!' },
  { email: 'test3@example.com', password: 'TestPass123!' },
];

// Helper functions
function getRandomUser() {
  return testUsers[Math.floor(Math.random() * testUsers.length)];
}

function authenticate(user) {
  const loginRes = http.post(`${BASE_URL}/auth/login`, JSON.stringify({
    email: user.email,
    password: user.password,
  }), {
    headers: { 'Content-Type': 'application/json' },
  });

  check(loginRes, {
    'login successful': (r) => r.status === 200,
    'got access token': (r) => JSON.parse(r.body).access_token !== undefined,
  });

  if (loginRes.status === 200) {
    return JSON.parse(loginRes.body).access_token;
  }
  return null;
}

// Main test scenario
export default function() {
  const user = getRandomUser();
  
  group('Authentication', () => {
    const token = authenticate(user);
    if (!token) {
      errorRate.add(1);
      return;
    }

    const headers = {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${token}`,
    };

    group('Health Check', () => {
      const healthRes = http.get(`${BASE_URL}/health`);
      const success = check(healthRes, {
        'health check ok': (r) => r.status === 200,
        'response time < 500ms': (r) => r.timings.duration < 500,
      });
      errorRate.add(!success);
      apiResponseTime.add(healthRes.timings.duration);
    });

    group('List Calls', () => {
      const callsRes = http.get(`${BASE_URL}/calls`, { headers });
      const success = check(callsRes, {
        'calls retrieved': (r) => r.status === 200,
        'response is array': (r) => Array.isArray(JSON.parse(r.body)),
      });
      errorRate.add(!success);
      apiResponseTime.add(callsRes.timings.duration);
    });

    group('Get Call Details', () => {
      // First, get list of calls
      const callsRes = http.get(`${BASE_URL}/calls`, { headers });
      if (callsRes.status === 200) {
        const calls = JSON.parse(callsRes.body);
        if (calls.length > 0) {
          const callId = calls[0].id;
          
          // Get call details
          const callRes = http.get(`${BASE_URL}/call/${callId}`, { headers });
          const success = check(callRes, {
            'call details retrieved': (r) => r.status === 200,
            'call has id': (r) => JSON.parse(r.body).id !== undefined,
          });
          errorRate.add(!success);
          apiResponseTime.add(callRes.timings.duration);

          // Get transcripts
          const transcriptRes = http.get(`${BASE_URL}/call/${callId}/transcript`, { headers });
          check(transcriptRes, {
            'transcript retrieved': (r) => r.status === 200,
          });
          apiResponseTime.add(transcriptRes.timings.duration);
        }
      }
    });

    group('List Appointments', () => {
      const appointmentsRes = http.get(`${BASE_URL}/appointments`, { headers });
      const success = check(appointmentsRes, {
        'appointments retrieved': (r) => r.status === 200,
        'response is array': (r) => Array.isArray(JSON.parse(r.body)),
      });
      errorRate.add(!success);
      apiResponseTime.add(appointmentsRes.timings.duration);
    });

    group('WebSocket Connection Simulation', () => {
      // Simulate websocket overhead with HTTP polling
      for (let i = 0; i < 5; i++) {
        const wsSimRes = http.get(`${BASE_URL}/health`, { headers });
        check(wsSimRes, {
          'ws simulation ok': (r) => r.status === 200,
        });
        sleep(0.1); // 100ms between polls
      }
    });
  });

  sleep(Math.random() * 3 + 1); // Random sleep 1-4 seconds
}

// Setup function (runs once at start)
export function setup() {
  console.log('Starting load test...');
  console.log(`Base URL: ${BASE_URL}`);
  console.log(`Test users: ${testUsers.length}`);
  
  // Verify backend is reachable
  const healthRes = http.get(`${BASE_URL}/health`);
  if (healthRes.status !== 200) {
    throw new Error('Backend is not reachable!');
  }
  
  return { startTime: Date.now() };
}

// Teardown function (runs once at end)
export function teardown(data) {
  const duration = (Date.now() - data.startTime) / 1000;
  console.log(`Load test completed in ${duration}s`);
}
