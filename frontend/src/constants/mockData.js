/**
 * Mock data for test cases
 */
export const INITIAL_TEST_CASES = [
  { id: 1, method: 'GET', endpoint: '/users/1', expected: 200, description: 'Fetch user', selected: true },
  { id: 2, method: 'POST', endpoint: '/users', expected: 400, description: 'Missing field', selected: true },
  { id: 3, method: 'GET', endpoint: '/users/1', expected: 200, description: 'Fetch user', selected: true },
  { id: 4, method: 'POST', endpoint: '/users', expected: 400, description: 'Missing field', selected: true },
];
