import { X } from 'lucide-react';

/**
 * Payload Modal Component - Shows request payload in JSON format
 */
const PayloadModal = ({ isOpen, onClose, payload, testCaseName }) => {
  if (!isOpen) return null;

  const jsonString = JSON.stringify(payload, null, 2);

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-lg shadow-xl max-w-2xl w-full max-h-[80vh] overflow-hidden flex flex-col">
        {/* Header */}
        <div className="bg-[#1a1a1a] text-white px-6 py-4 flex items-center justify-between border-b border-gray-200">
          <div>
            <h3 className="text-lg font-bold">Payload Details</h3>
            <p className="text-sm text-gray-400 mt-1">{testCaseName}</p>
          </div>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-white transition-colors"
          >
            <X className="w-6 h-6" />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6">
          {Object.keys(payload).length === 0 ? (
            <p className="text-gray-500 text-center py-8">No payload data for this request</p>
          ) : (
            <div className="bg-gray-50 rounded-lg p-4 border border-gray-200">
              <pre className="text-sm font-mono text-gray-800 whitespace-pre-wrap break-words">
                {jsonString}
              </pre>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="bg-gray-50 px-6 py-4 border-t border-gray-200 flex justify-end">
          <button
            onClick={onClose}
            className="bg-gray-700 hover:bg-gray-800 text-white px-4 py-2 rounded-lg transition-colors font-medium"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
};

export default PayloadModal;
