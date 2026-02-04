import { CloudUpload, FileCode } from 'lucide-react';
import { useRef } from 'react';

/**
 * File Upload Component
 */
const FileUpload = ({ uploadedFile, onFileChange }) => {
  const fileInputRef = useRef(null);

  const triggerUpload = () => {
    fileInputRef.current.click();
  };

  return (
    <div
      onClick={triggerUpload}
      className="border-2 border-dashed border-gray-300 bg-[#f9f7f9] rounded-xl p-12 text-center group hover:border-gray-400 transition-colors cursor-pointer relative"
    >
      <input
        type="file"
        className="hidden"
        ref={fileInputRef}
        onChange={onFileChange}
        accept=".json,.yaml,.yml"
      />
      <div className="flex flex-col items-center">
        {uploadedFile ? (
          <>
            <FileCode className="w-12 h-12 text-green-600 mb-4" />
            <h2 className="text-xl font-bold text-[#3a2d42] mb-1">{uploadedFile.name}</h2>
            <p className="text-gray-500 text-sm">File ready. Click to change.</p>
          </>
        ) : (
          <>
            <CloudUpload className="w-12 h-12 text-gray-700 mb-4" />
            <h2 className="text-xl font-bold text-[#3a2d42] mb-1">Upload File</h2>
            <p className="text-gray-500 text-sm">Click to upload or drag and drop files</p>
          </>
        )}
      </div>
    </div>
  );
};

export default FileUpload;
