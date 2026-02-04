import { useState } from 'react';
import { ArrowLeft } from 'lucide-react';
import FileUpload from '../../components/FileUpload/FileUpload';
import TestTable from '../../components/TestTable/TestTable';
import TestResults from '../../components/TestResults/TestResults';
import LoadingSpinner from '../../components/LoadingSpinner/LoadingSpinner';
import { INITIAL_TEST_CASES } from '../../constants/mockData';

/**
 * Testing Page - Main testing interface
 */
const TestingPage = ({ onBack }) => {
  const [baseUrl, setBaseUrl] = useState('');
  const [testCases, setTestCases] = useState([]);
  const [isRunning, setIsRunning] = useState(false);
  const [results, setResults] = useState(null);
  const [uploadedFile, setUploadedFile] = useState(null);

  const handleFileChange = (e) => {
    const file = e.target.files[0];
    if (file) {
      setUploadedFile(file);
    }
  };

  const fetchTestCases = () => {
    setTestCases([...INITIAL_TEST_CASES]);
    setResults(null);
  };

  const toggleSelection = (id) => {
    setTestCases(prev =>
      prev.map(tc => (tc.id === id ? { ...tc, selected: !tc.selected } : tc))
    );
  };

  const deleteTestCase = (id) => {
    setTestCases(prev => prev.filter(tc => tc.id !== id));
  };

  const runTests = () => {
    if (testCases.length === 0) return;
    setIsRunning(true);
    setResults(null);

    setTimeout(() => {
      setIsRunning(false);
      setResults({
        total: testCases.filter(t => t.selected).length,
        passed: Math.floor(testCases.filter(t => t.selected).length * 0.75),
        failed: Math.ceil(testCases.filter(t => t.selected).length * 0.25),
        failedEndpoints: testCases
          .filter((t, i) => t.selected && i % 3 === 0)
          .map(t => t.endpoint)
      });
    }, 2000);
  };

  return (
    <div className="max-w-5xl mx-auto py-10 px-6 space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-500 w-full">
      {/* Upload Section */}
      <FileUpload uploadedFile={uploadedFile} onFileChange={handleFileChange} />

      {/* Input / Fetch Row */}
      <div className="flex gap-4">
        <input
          type="text"
          placeholder="Enter Base URI"
          className="flex-1 px-4 py-3 border border-gray-300 rounded-lg outline-none focus:ring-2 focus:ring-green-500 transition-all shadow-sm"
          value={baseUrl}
          onChange={(e) => setBaseUrl(e.target.value)}
        />
        <button
          onClick={fetchTestCases}
          className="px-8 py-3 bg-[#32a832] text-white font-semibold rounded-full hover:bg-green-700 transition-colors shadow-sm whitespace-nowrap"
        >
          Fetch Test Cases
        </button>
      </div>

      {/* Table Section */}
      <TestTable
        testCases={testCases}
        onToggleSelection={toggleSelection}
        onDeleteTestCase={deleteTestCase}
      />

      {/* Execution Results */}
      {isRunning && <LoadingSpinner />}

      {results && !isRunning && <TestResults results={results} />}

      {/* Action Buttons Footer */}
      <div className="flex items-center justify-between pt-10 pb-10">
        <button
          onClick={onBack}
          className="flex items-center gap-2 px-8 py-3 bg-[#c22d2d] text-white font-bold rounded-2xl hover:bg-red-800 transition-colors shadow-md"
        >
          <ArrowLeft className="w-4 h-4" /> Back
        </button>

        {testCases.length > 0 && (
          <button
            onClick={runTests}
            disabled={isRunning}
            className={`px-12 py-3 bg-[#32a832] text-white font-bold rounded-full transition-all shadow-md transform hover:scale-105 active:scale-95 ${
              isRunning ? 'opacity-50 cursor-not-allowed' : ''
            }`}
          >
            Run Tests
          </button>
        )}
      </div>
    </div>
  );
};

export default TestingPage;
