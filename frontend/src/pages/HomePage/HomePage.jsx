/**
 * Home Page - Landing Page Component
 */
const HomePage = ({ setPage }) => (
  <div className="flex-1 flex flex-col items-center justify-center px-4 text-center animate-in fade-in zoom-in-95 duration-500">
    <h1 className="text-6xl font-bold text-gray-900 mb-6 max-w-4xl leading-tight">
      Autonomous API Testing <br /> Powered by AI Agents
    </h1>
    <p className="text-xl text-gray-600 mb-10 max-w-2xl">
      Upload your Swagger or Postman docs. Our AI generates, executes, and maintains
      functional, security, and performance tests automatically.
    </p>
    <div className="flex gap-6">
      <button
        onClick={() => setPage('testing')}
        className="px-10 py-4 bg-[#111a29] text-white rounded-full text-lg font-semibold hover:bg-black transition-all shadow-lg"
      >
        Upload file
      </button>
      <button
        onClick={() => setPage('docs')}
        className="px-10 py-4 bg-[#111a29] text-white rounded-full text-lg font-semibold hover:bg-black transition-all shadow-lg"
      >
        View Docs
      </button>
    </div>
  </div>
);

export default HomePage;
