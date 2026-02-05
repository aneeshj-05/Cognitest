import { CheckCircle2, XCircle, Clock, Loader2 } from 'lucide-react';
import { useState } from 'react';

/**
 * Test Results Summary Component
 * @param {Object} results - The test results
 * @param {boolean} isPartial - Whether results are still being collected
 */
const TestResults = ({ results, isPartial = false }) => {
  const [activeTab, setActiveTab] = useState('failed');

  if (!results) return null;

  return (
    <div className="bg-white p-6 rounded-xl border border-gray-200 shadow-sm animate-in zoom-in-95 duration-300">
      <h3 className="text-xl font-bold mb-4 flex items-center gap-2">
        {isPartial ? (
          <>
            <Loader2 className="text-blue-500 animate-spin" /> Test Results (In Progress...)
          </>
        ) : (
          <>
            <CheckCircle2 className="text-green-500" /> Test Summary
          </>
        )}
      </h3>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
        <div className="p-4 bg-gray-50 rounded-lg text-center">
          <p className="text-xs text-gray-500 uppercase font-bold">Total</p>
          <p className="text-2xl font-bold">{results.total}</p>
        </div>
        <div className="p-4 bg-green-50 rounded-lg text-center">
          <p className="text-xs text-green-600 uppercase font-bold">Passed</p>
          <p className="text-2xl font-bold text-green-700">{results.passed}</p>
        </div>
        <div className="p-4 bg-red-50 rounded-lg text-center">
          <p className="text-xs text-red-600 uppercase font-bold">Failed</p>
          <p className="text-2xl font-bold text-red-700">{results.failed}</p>
        </div>
      </div>

      {/* Tabs for switching between passed and failed */}
      <div className="flex gap-2 mb-4 border-b">
        <button
          onClick={() => setActiveTab('failed')}
          className={`px-4 py-2 font-medium text-sm transition-colors ${
            activeTab === 'failed'
              ? 'text-red-600 border-b-2 border-red-600'
              : 'text-gray-500 hover:text-gray-700'
          }`}
        >
          Failed ({results.failedEndpoints?.length || 0})
        </button>
        <button
          onClick={() => setActiveTab('passed')}
          className={`px-4 py-2 font-medium text-sm transition-colors ${
            activeTab === 'passed'
              ? 'text-green-600 border-b-2 border-green-600'
              : 'text-gray-500 hover:text-gray-700'
          }`}
        >
          Passed ({results.successEndpoints?.length || 0})
        </button>
      </div>

      {/* Failed Endpoints */}
      {activeTab === 'failed' && results.failedEndpoints?.length > 0 && (
        <div className="max-h-64 overflow-y-auto">
          <ul className="space-y-2">
            {results.failedEndpoints.map((ep, i) => (
              <li
                key={i}
                className="text-sm text-gray-700 bg-red-50 px-3 py-2 rounded-lg flex items-start gap-2"
              >
                <XCircle className="w-4 h-4 text-red-500 mt-0.5 flex-shrink-0" />
                <div>
                  <span className="font-medium">{typeof ep === 'string' ? ep : ep.endpoint}</span>
                  {ep.message && (
                    <p className="text-xs text-red-600 mt-1">{ep.message}</p>
                  )}
                </div>
              </li>
            ))}
          </ul>
        </div>
      )}

      {activeTab === 'failed' && (!results.failedEndpoints || results.failedEndpoints.length === 0) && (
        <p className="text-sm text-green-600 text-center py-4">🎉 All tests passed!</p>
      )}

      {/* Passed Endpoints */}
      {activeTab === 'passed' && results.successEndpoints?.length > 0 && (
        <div className="max-h-64 overflow-y-auto">
          <ul className="space-y-2">
            {results.successEndpoints.map((ep, i) => (
              <li
                key={i}
                className="text-sm text-gray-700 bg-green-50 px-3 py-2 rounded-lg flex items-center justify-between"
              >
                <div className="flex items-center gap-2">
                  <CheckCircle2 className="w-4 h-4 text-green-500 flex-shrink-0" />
                  <span className="font-medium">{typeof ep === 'string' ? ep : ep.endpoint}</span>
                </div>
                {ep.status && (
                  <div className="flex items-center gap-3 text-xs text-gray-500">
                    <span className="bg-green-100 text-green-700 px-2 py-0.5 rounded">{ep.status}</span>
                    {ep.responseTime && (
                      <span className="flex items-center gap-1">
                        <Clock className="w-3 h-3" /> {ep.responseTime}
                      </span>
                    )}
                  </div>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}

      {activeTab === 'passed' && (!results.successEndpoints || results.successEndpoints.length === 0) && (
        <p className="text-sm text-gray-500 text-center py-4">No passed tests</p>
      )}
    </div>
  );
};

export default TestResults;
