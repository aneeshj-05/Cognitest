import { Info, ChevronRight } from 'lucide-react';

/**
 * Features Page Component
 */
const FeaturesPage = () => {
  const features = [
    { title: 'Swagger/OpenAPI Parsing', desc: 'Seamlessly import your API definitions for instant test generation.' },
    { title: 'AI Test Generation', desc: 'Our agents analyze your schema to create meaningful edge cases and security checks.' },
    { title: 'Automated Execution (Newman)', desc: 'Tests are bundled and run in high-performance CI/CD friendly environments.' },
    { title: 'Report Generation', desc: 'Detailed PDF and HTML reports with visual execution timelines.' }
  ];

  return (
    <div className="max-w-4xl mx-auto py-16 px-6 animate-in fade-in duration-500">
      <h1 className="text-4xl font-bold mb-8 flex items-center gap-3">
        <Info className="text-blue-500 w-10 h-10" /> Features
      </h1>
      <ul className="space-y-6">
        {features.map((f, i) => (
          <li
            key={i}
            className="flex gap-4 p-6 bg-white border border-gray-100 rounded-xl shadow-sm hover:shadow-md transition-shadow"
          >
            <div className="w-8 h-8 bg-blue-50 text-blue-600 rounded-full flex items-center justify-center shrink-0">
              <ChevronRight className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-xl font-bold text-gray-800">{f.title}</h3>
              <p className="text-gray-600 mt-1">{f.desc}</p>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
};

export default FeaturesPage;
