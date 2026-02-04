/**
 * Loading Spinner Component
 */
const LoadingSpinner = () => (
  <div className="flex flex-col items-center py-6 animate-pulse">
    <div className="w-12 h-12 border-4 border-green-500 border-t-transparent rounded-full animate-spin mb-4"></div>
    <p className="text-gray-600 font-medium">Running Tests...</p>
  </div>
);

export default LoadingSpinner;
