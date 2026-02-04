/**
 * Navigation Bar Component
 */
const Navbar = ({ setPage }) => (
  <nav className="flex items-center justify-between px-8 py-10 border-b border-gray-300 bg-blue-100 sticky top-0 z-50 h-16 shrink-0">
    <div className="flex items-center cursor-pointer" onClick={() => setPage('home')}>
      <div className="w-10 h-10 bg-gray-100 rounded-full flex items-center justify-center border border-gray-300 mr-2">
        <span className="text-xs font-bold text-gray-400 flex items-center">
          <img src="/logo.png" alt="LOGO" />
          <h2 className="text-black text-base">Cognitest</h2>
        </span>
      </div>
    </div>
    <div className="flex gap-4">
      <button
        onClick={() => setPage('features')}
        className="px-6 py-2 bg-gray-700 text-white rounded-md hover:bg-gray-800 transition-colors text-sm font-medium"
      >
        Features
      </button>
      <button
        onClick={() => setPage('docs')}
        className="px-6 py-2 bg-gray-700 text-white rounded-md hover:bg-gray-800 transition-colors text-sm font-medium"
      >
        Docs
      </button>
    </div>
  </nav>
);

export default Navbar;
