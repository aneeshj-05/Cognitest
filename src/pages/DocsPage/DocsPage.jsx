import { Book } from 'lucide-react';

/**
 * Documentation Page Component
 */
const DocsPage = () => (
  <div className="max-w-4xl mx-auto py-16 px-6 animate-in fade-in duration-500">
    <h1 className="text-4xl font-bold mb-8 flex items-center gap-3">
      <Book className="text-purple-500 w-10 h-10" /> Documentation
    </h1>
    <div className="prose prose-slate max-w-none space-y-10">
      <section>
        <h2 className="text-2xl font-bold border-b pb-2 mb-4">How to upload swagger</h2>
        <p className="text-gray-600">
          Drag and drop your JSON or YAML Swagger file into the upload box on the Testing page. Our system
          supports OpenAPI 3.0 and Swagger 2.0 formats.
        </p>
      </section>
      <section>
        <h2 className="text-2xl font-bold border-b pb-2 mb-4">How to fetch test cases</h2>
        <p className="text-gray-600">
          Once your file is uploaded, enter your API's Base URI (e.g., https://api.example.com/v1) and
          click "Fetch Test Cases". The AI will populate the list below.
        </p>
      </section>
      <section>
        <h2 className="text-2xl font-bold border-b pb-2 mb-4">How to run tests</h2>
        <p className="text-gray-600">
          Select the tests you wish to perform using the checkboxes and hit the green "Run Tests" button.
          Results will appear in real-time as execution completes.
        </p>
      </section>
    </div>
  </div>
);

export default DocsPage;
