import Navbar from './components/Navbar/Navbar';
import HomePage from './pages/HomePage/HomePage';
import TestingPage from './pages/TestingPage/TestingPage';
import FeaturesPage from './pages/FeaturesPage/FeaturesPage';
import DocsPage from './pages/DocsPage/DocsPage';
import { useNavigation } from './hooks/useNavigation';

/**
 * Main App Component
 */
export default function App() {
  const { currentPage, navigateTo, goBack } = useNavigation('home');

  const renderPage = () => {
    switch (currentPage) {
      case 'testing':
        return <TestingPage onBack={goBack} />;
      case 'features':
        return <FeaturesPage />;
      case 'docs':
        return <DocsPage />;
      default:
        return <HomePage setPage={navigateTo} />;
    }
  };

  return (
    <div className="flex flex-col min-h-screen bg-blue-50 font-sans text-gray-900 overflow-x-hidden">
      <Navbar setPage={navigateTo} />
      <main className="flex-1 flex flex-col relative">
        {renderPage()}
      </main>
    </div>
  );
}
