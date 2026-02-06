import { Trash2 } from 'lucide-react';

/**
 * Test Cases Table Component
 */
const TestTable = ({ testCases, onToggleSelection, onDeleteTestCase }) => {
  if (testCases.length === 0) return null;

  return (
    <div className="bg-white rounded-lg border border-gray-200 shadow-sm overflow-hidden">
      <div 
        className="overflow-y-auto"
        style={{ 
          maxHeight: '400px',
        }}
      >
        <table className="w-full text-left border-collapse">
          <thead className="bg-[#1a1a1a] text-white sticky top-0 z-10">
            <tr>
              <th className="px-4 py-3 text-sm font-medium w-12 text-center">✔</th>
              <th className="px-4 py-3 text-sm font-medium">Method</th>
              <th className="px-4 py-3 text-sm font-medium">Endpoint</th>
              <th className="px-4 py-3 text-sm font-medium">Expected</th>
              <th className="px-4 py-3 text-sm font-medium">Description</th>
              <th className="px-4 py-3 text-sm font-medium w-20 text-center">×</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-200">
            {testCases.map((tc) => (
              <tr key={tc.id} className="hover:bg-gray-50 transition-colors">
                <td className="px-4 py-4 text-center">
                  <input
                    type="checkbox"
                    checked={tc.selected}
                    onChange={() => onToggleSelection(tc.id)}
                    className="w-4 h-4 accent-gray-700"
                  />
                </td>
                <td className="px-4 py-4 font-mono text-sm text-gray-400 uppercase">{tc.method}</td>
                <td className="px-4 py-4 text-sm text-[#4d97e8] font-medium">{tc.endpoint}</td>
                <td className="px-4 py-4 text-sm text-gray-400">{tc.expected}</td>
                <td className="px-4 py-4 text-sm text-[#4d97e8] italic">{tc.description}</td>
                <td className="px-4 py-4 text-center">
                  <button
                    onClick={() => onDeleteTestCase(tc.id)}
                    className="text-gray-400 hover:text-red-500 transition-colors p-1"
                  >
                    <Trash2 className="w-5 h-5" />
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};

export default TestTable;
