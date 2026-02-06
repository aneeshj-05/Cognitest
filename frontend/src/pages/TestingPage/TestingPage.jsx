import { useState } from 'react';
import { ArrowLeft } from 'lucide-react';
import FileUpload from '../../components/FileUpload/FileUpload';
import TestTable from '../../components/TestTable/TestTable';
import TestResults from '../../components/TestResults/TestResults';
import LoadingSpinner from '../../components/LoadingSpinner/LoadingSpinner';
import { generateTestCases, generateTestCasesFromSpec, getCollection, updateTestCases, executeBatch } from '../../services/api';

const BATCH_SIZE = 10;

/**
 * Testing Page - Main testing interface
 * Flow 1 (Generate): Swagger URL → FastAPI parses → FastAPI generates Postman collection → Node stores it
 * Flow 2 (Execute): Node loads collection → Newman runs batches → reports produced → FastAPI analyzes → Node stores summary
 */
const TestingPage = ({ onBack }) => {
  const [swaggerUrl, setSwaggerUrl] = useState('');
  const [testCases, setTestCases] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isRunning, setIsRunning] = useState(false);
  const [results, setResults] = useState(null);
  const [uploadedFile, setUploadedFile] = useState(null);
  const [uploadedSpec, setUploadedSpec] = useState(null);
  const [runId, setRunId] = useState(null);
  const [error, setError] = useState(null);
  const [baseUrl, setBaseUrl] = useState('');
  const [batchProgress, setBatchProgress] = useState(null);

  const handleFileChange = (e) => {
    const file = e.target.files[0];
    if (file) {
      setUploadedFile(file);
      setError(null);
      
      // Read file content for JSON files
      if (file.name.endsWith('.json')) {
        const reader = new FileReader();
        reader.onload = (event) => {
          try {
            const content = JSON.parse(event.target.result);
            setUploadedSpec(content);
            
            // Extract base URL if available
            let extractedBaseUrl = '';
            if (content.servers && content.servers[0]?.url) {
              extractedBaseUrl = content.servers[0].url;
            } else if (content.host) {
              // Swagger 2.0 format
              const scheme = content.schemes?.[0] || 'https';
              extractedBaseUrl = `${scheme}://${content.host}${content.basePath || ''}`;
            }
            setBaseUrl(extractedBaseUrl);
          } catch (err) {
            setError('Could not parse file as JSON. Please upload a valid Swagger/OpenAPI JSON file.');
            setUploadedSpec(null);
          }
        };
        reader.readAsText(file);
      }
    }
  };

  const fetchTestCases = async () => {
    // Check if we have a file uploaded or a URL
    if (!uploadedSpec && !swaggerUrl.trim()) {
      setError('Please upload a Swagger JSON file or enter a Swagger URL');
      return;
    }

    setIsLoading(true);
    setError(null);
    setResults(null);
    setTestCases([]);

    try {
      // If using uploaded spec, inject the baseUrl
      let specToSend = uploadedSpec;
      if (uploadedSpec && baseUrl) {
        specToSend = {
          ...uploadedSpec,
          servers: [{ url: baseUrl }]
        };
      }
      
      // Use file upload if we have a spec, otherwise use URL
      const response = uploadedSpec 
        ? await generateTestCasesFromSpec(specToSend)
        : await generateTestCases(swaggerUrl);
      
      setRunId(response.runId);
      
      // Transform testcases to include id and selected fields for UI
      const transformedTestCases = response.testcases.map((tc, index) => ({
        id: index + 1,
        method: tc.method,
        endpoint: tc.path,
        expected: tc.expected,
        description: tc.description || tc.name,
        category: tc.category,
        priority: tc.priority,
        payloadData: tc.payloadData || {},
        selected: true
      }));
      
      setTestCases(transformedTestCases);
    } catch (err) {
      setError(err.message || 'Failed to generate test cases');
    } finally {
      setIsLoading(false);
    }
  };

  const toggleSelection = (id) => {
    setTestCases(prev =>
      prev.map(tc => (tc.id === id ? { ...tc, selected: !tc.selected } : tc))
    );
  };

  const deleteTestCase = (id) => {
    setTestCases(prev => prev.filter(tc => tc.id !== id));
  };

  const runTests = async () => {
    if (!runId || testCases.length === 0) return;
    
    setIsRunning(true);
    setResults(null);
    setError(null);
    setBatchProgress(null);

    // Aggregate results across all batches
    let aggregatedResults = {
      total: 0,
      passed: 0,
      failed: 0,
      failedEndpoints: [],
      successEndpoints: []
    };

    try {
      // Step 1: Get the current collection from the backend
      const { collection } = await getCollection(runId);

      // Step 2: Map test case IDs (which are indices + 1) to collection indices
      // testCases have id = index + 1 from the transformation, so we filter collection.item
      // based on which indices correspond to non-deleted test cases
      const deletedIndices = new Set();
      const maxId = Math.max(...testCases.map(tc => tc.id), 0);
      
      // Find indices that were deleted (exist in range but not in current testCases)
      for (let i = 1; i <= maxId; i++) {
        if (!testCases.find(tc => tc.id === i)) {
          deletedIndices.add(i - 1); // Convert to 0-based index
        }
      }

      // Filter the collection items to exclude deleted indices
      const filteredItems = collection.item.filter((item, index) => {
        return !deletedIndices.has(index);
      });

      // Create filtered collection with only non-deleted items
      const filteredCollection = {
        ...collection,
        item: filteredItems
      };

      // Step 3: Update the collection on the backend with filtered items
      await updateTestCases(runId, filteredCollection);

      // Step 4: Run tests against the updated collection
      const totalTests = testCases.length;
      const totalBatches = Math.ceil(totalTests / BATCH_SIZE);
      
      for (let batchIndex = 0; batchIndex < totalBatches; batchIndex++) {
        // Update progress
        setBatchProgress({
          currentBatch: batchIndex + 1,
          totalBatches,
          testedSoFar: batchIndex * BATCH_SIZE,
          totalTests
        });

        // Execute this batch
        const batchResult = await executeBatch(runId, batchIndex, BATCH_SIZE);
        
        // Aggregate the results
        aggregatedResults.total += batchResult.summary.total || 0;
        aggregatedResults.passed += batchResult.summary.passed || 0;
        aggregatedResults.failed += batchResult.summary.failed || 0;
        aggregatedResults.failedEndpoints = [
          ...aggregatedResults.failedEndpoints,
          ...(batchResult.summary.failedEndpoints || [])
        ];
        aggregatedResults.successEndpoints = [
          ...aggregatedResults.successEndpoints,
          ...(batchResult.summary.successEndpoints || [])
        ];

        // Update results progressively so user can see partial results
        setResults({ ...aggregatedResults });

        // Update progress with completed batch
        setBatchProgress({
          currentBatch: batchIndex + 1,
          totalBatches,
          testedSoFar: Math.min((batchIndex + 1) * BATCH_SIZE, totalTests),
          totalTests
        });

        // If batch indicates completion, break
        if (batchResult.isComplete) {
          break;
        }
      }

      // Final update
      setResults(aggregatedResults);
      setBatchProgress(null);
    } catch (err) {
      setError(err.message || 'Failed to execute tests');
    } finally {
      setIsRunning(false);
    }
  };

  return (
    <div className="max-w-5xl mx-auto py-10 px-6 space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-500 w-full">
      {/* Error Message */}
      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg">
          {error}
        </div>
      )}

      {/* Upload Section */}
      <FileUpload uploadedFile={uploadedFile} onFileChange={handleFileChange} />

      {/* Divider */}
      <div className="flex items-center gap-4">
        <div className="flex-1 border-t border-gray-300"></div>
        <span className="text-gray-500 font-medium">OR</span>
        <div className="flex-1 border-t border-gray-300"></div>
      </div>

      {/* Input / Fetch Row */}
      <div className="flex gap-4">
        <input
          type="text"
          placeholder="Enter URL"
          className={`flex-1 px-4 py-3 border border-gray-300 rounded-lg outline-none focus:ring-2 focus:ring-green-500 transition-all shadow-sm ${uploadedSpec ? 'bg-gray-100' : ''}`}
          value={swaggerUrl}
          onChange={(e) => setSwaggerUrl(e.target.value)}
          disabled={!!uploadedSpec}
        />
        <button
          onClick={fetchTestCases}
          disabled={isLoading || (!uploadedSpec && !swaggerUrl.trim())}
          className={`px-8 py-3 bg-[#32a832] text-white font-semibold rounded-full hover:bg-green-700 transition-colors shadow-sm whitespace-nowrap ${
            isLoading || (!uploadedSpec && !swaggerUrl.trim()) ? 'opacity-50 cursor-not-allowed' : ''
          }`}
        >
          {isLoading ? 'Generating...' : 'Generate Test Cases'}
        </button>
      </div>

      {/* Show which source will be used */}
      {uploadedSpec && (
        <div className="bg-green-50 border border-green-200 p-4 rounded-lg space-y-3">
          <p className="text-sm text-green-700">
            ✓ Using uploaded file: <strong>{uploadedFile?.name}</strong>
            <button 
              onClick={() => { setUploadedFile(null); setUploadedSpec(null); setSwaggerUrl(''); setBaseUrl(''); }}
              className="ml-2 text-red-500 hover:underline"
            >
              (Clear)
            </button>
          </p>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              API Base URL (for running tests):
            </label>
            <input
              type="text"
              placeholder="e.g., https://petstore.swagger.io/v2"
              className="w-full px-4 py-2 border border-gray-300 rounded-lg outline-none focus:ring-2 focus:ring-green-500"
              value={baseUrl}
              onChange={(e) => setBaseUrl(e.target.value)}
            />
            {baseUrl && <p className="text-xs text-gray-500 mt-1">Tests will run against: {baseUrl}</p>}
          </div>
        </div>
      )}

      {/* Loading Spinner for Generation */}
      {isLoading && <LoadingSpinner />}

      {/* Table Section */}
      <TestTable
        testCases={testCases}
        onToggleSelection={toggleSelection}
        onDeleteTestCase={deleteTestCase}
      />

      {/* Execution Results */}
      {isRunning && (
        <div className="bg-white p-6 rounded-xl border border-gray-200 shadow-sm">
          <LoadingSpinner />
          {batchProgress && (
            <div className="mt-4 text-center">
              <div className="flex items-center justify-center gap-2 mb-2">
                <span className="text-lg font-semibold text-gray-700">
                  Running Batch {batchProgress.currentBatch} of {batchProgress.totalBatches}
                </span>
              </div>
              <div className="w-full bg-gray-200 rounded-full h-3 mb-2">
                <div 
                  className="bg-green-500 h-3 rounded-full transition-all duration-300"
                  style={{ width: `${(batchProgress.testedSoFar / batchProgress.totalTests) * 100}%` }}
                ></div>
              </div>
              <p className="text-sm text-gray-500">
                {batchProgress.testedSoFar} of {batchProgress.totalTests} tests completed
              </p>
            </div>
          )}
        </div>
      )}

      {results && <TestResults results={results} isPartial={isRunning} />}

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
