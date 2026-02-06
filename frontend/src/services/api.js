/**
 * API Service for communicating with the backend
 */

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:5000';

/**
 * Generate test cases from a Swagger URL
 * Flow: Swagger URL → FastAPI parses → FastAPI generates Postman collection → Node stores it
 */
export async function generateTestCases(swaggerUrl) {
  const response = await fetch(`${API_BASE_URL}/api/runs/generate`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ swaggerUrl }),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ message: 'Failed to generate test cases' }));
    throw new Error(error.error || error.message || 'Failed to generate test cases');
  }

  return response.json();
}

/**
 * Generate test cases from a Swagger JSON spec (for file uploads)
 */
export async function generateTestCasesFromSpec(spec) {
  const response = await fetch(`${API_BASE_URL}/api/runs/generate-from-spec`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ spec }),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ message: 'Failed to generate test cases' }));
    throw new Error(error.error || error.message || 'Failed to generate test cases');
  }

  return response.json();
}

/**
 * Update test cases for a specific run
 */
export async function updateTestCases(runId, collection) {
  const response = await fetch(`${API_BASE_URL}/api/runs/update`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ runId, collection }),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ message: 'Failed to update test cases' }));
    throw new Error(error.message || 'Failed to update test cases');
  }

  return response.json();
}

/**
 * Execute tests for a specific run
 * Flow: Node loads collection → Newman runs → report produced → FastAPI analyzes → Node stores summary
 */
export async function executeTests(runId) {
  // Use AbortController for timeout - tests can take a while
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 300000); // 5 minute timeout

  try {
    const response = await fetch(`${API_BASE_URL}/api/runs/${runId}/execute`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      signal: controller.signal,
    });

    clearTimeout(timeoutId);

    if (!response.ok) {
      const error = await response.json().catch(() => ({ message: 'Failed to execute tests' }));
      throw new Error(error.error || error.message || 'Failed to execute tests');
    }

    return response.json();
  } catch (err) {
    clearTimeout(timeoutId);
    if (err.name === 'AbortError') {
      throw new Error('Test execution timed out. The tests are taking too long to complete.');
    }
    throw err;
  }
}

/**
 * Get the collection for a specific run
 */
export async function getCollection(runId) {
  const response = await fetch(`${API_BASE_URL}/api/runs/${runId}`, {
    method: 'GET',
    headers: {
      'Content-Type': 'application/json',
    },
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ message: 'Failed to get collection' }));
    throw new Error(error.error || error.message || 'Failed to get collection');
  }

  return response.json();
}

/**
 * Get the total number of tests in a collection
 */
export async function getTestCount(runId) {
  const response = await fetch(`${API_BASE_URL}/api/runs/${runId}/count`, {
    method: 'GET',
    headers: {
      'Content-Type': 'application/json',
    },
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ message: 'Failed to get test count' }));
    throw new Error(error.error || error.message || 'Failed to get test count');
  }

  return response.json();
}

/**
 * Execute a batch of tests
 * @param {string} runId - The run ID
 * @param {number} batchIndex - The batch number (0-indexed)
 * @param {number} batchSize - Number of tests per batch (default: 10)
 */
export async function executeBatch(runId, batchIndex, batchSize = 10) {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 120000); // 2 minute timeout per batch

  try {
    const response = await fetch(`${API_BASE_URL}/api/runs/${runId}/execute-batch`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ batchIndex, batchSize }),
      signal: controller.signal,
    });

    clearTimeout(timeoutId);

    if (!response.ok) {
      const error = await response.json().catch(() => ({ message: 'Failed to execute batch' }));
      throw new Error(error.error || error.message || 'Failed to execute batch');
    }

    return response.json();
  } catch (err) {
    clearTimeout(timeoutId);
    if (err.name === 'AbortError') {
      throw new Error(`Batch ${batchIndex + 1} timed out. Please try again.`);
    }
    throw err;
  }
}

export default {
  generateTestCases,
  generateTestCasesFromSpec,
  getCollection,
  updateTestCases,
  executeTests,
  getTestCount,
  executeBatch,
};
