import { useState } from 'react';
import { Trash2, Eye } from 'lucide-react';
import PayloadModal from '../PayloadModal/PayloadModal';

/**
 * Test Cases Table Component
 */
const TestTable = ({ testCases, onToggleSelection, onDeleteTestCase }) => {
  const [modalOpen, setModalOpen] = useState(false);
  const [selectedPayload, setSelectedPayload] = useState({});
  const [selectedTestCase, setSelectedTestCase] = useState('');

  const handleViewPayload = (testCase) => {
    setSelectedPayload(testCase.payloadData || {});
    setSelectedTestCase(testCase.description || testCase.method);
    setModalOpen(true);
  };

  if (testCases.length === 0) return null;

  return (
    <div className="bg-white rounded-lg border border-gray-200 shadow-sm overflow-hidden">
      <div 
        className="overflow-y-auto"
        style={{ 
          maxHeight: '400px',
          scrollbarGutter: 'stable'
        }}
      >
        <table className="w-full text-left border-collapse">
          <thead className="bg-[#1a1a1a] text-white sticky top-0 z-10">
            <tr>
              <th className="px-4 py-3 text-sm font-medium w-12 text-center">✔</th>
              <th className="px-4 py-3 text-sm font-medium">Method</th>
              <th className="px-4 py-3 text-sm font-medium">Endpoint</th>
              <th className="px-4 py-3 text-sm font-medium">Expected</th>
              <th className="px-4 py-3 text-sm font-medium">Payload</th>
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
                <td className="px-4 py-4 text-sm text-gray-600">
                  {tc.payloadData && Object.keys(tc.payloadData).length > 0 ? (
                    <button
                      onClick={() => handleViewPayload(tc)}
                      className="flex items-center gap-2 bg-blue-50 hover:bg-blue-100 text-blue-600 px-3 py-2 rounded-lg transition-colors font-medium text-sm border border-blue-200"
                    >
                      <Eye className="w-4 h-4" />
                      See
                    </button>
                  ) : (
                    <span className="text-gray-400 italic">No payload</span>
                  )}
                </td>
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
      <PayloadModal 
        isOpen={modalOpen}
        onClose={() => setModalOpen(false)}
        payload={selectedPayload}
        testCaseName={selectedTestCase}
      />
    </div>
  );
};

export default TestTable;
