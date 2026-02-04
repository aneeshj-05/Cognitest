import { CheckCircle2, XCircle } from 'lucide-react';

/**
 * Test Results Summary Component
 */
const TestResults = ({ results }) => {
  if (!results) return null;

  return (
    <div className="bg-white p-6 rounded-xl border border-gray-200 shadow-sm animate-in zoom-in-95 duration-300">
      <h3 className="text-xl font-bold mb-4 flex items-center gap-2">
        <CheckCircle2 className="text-green-500" /> Test Summary
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
      {results.failedEndpoints.length > 0 && (
        <div>
          <p className="text-sm font-bold text-red-600 mb-2">Failed Endpoints:</p>
          <ul className="space-y-1">
            {results.failedEndpoints.map((ep, i) => (
              <li
                key={i}
                className="text-sm text-gray-600 font-mono bg-red-50 px-2 py-1 rounded flex items-center gap-2"
              >
                <XCircle className="w-3 h-3 text-red-400" /> {ep}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
};

export default TestResults;
