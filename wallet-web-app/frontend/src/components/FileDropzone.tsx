import React, { useCallback } from 'react';
import { useDropzone } from 'react-dropzone';

interface FileDropzoneProps {
  onFileSelect: (file: File) => void;
  disabled?: boolean;
  error?: string;
}

const FileDropzone: React.FC<FileDropzoneProps> = ({ onFileSelect, disabled = false, error }) => {
  const onDrop = useCallback((acceptedFiles: File[]) => {
    if (acceptedFiles.length > 0) {
      onFileSelect(acceptedFiles[0]);
    }
  }, [onFileSelect]);

  const { getRootProps, getInputProps, isDragActive, isDragReject } = useDropzone({
    onDrop,
    accept: {
      'application/pdf': ['.pdf']
    },
    maxFiles: 1,
    maxSize: 10 * 1024 * 1024, // 10MB
    disabled
  });

  return (
    <div
      {...getRootProps()}
      className={`
        relative border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-all
        ${isDragActive && !isDragReject ? 'border-primary-500 bg-primary-50' : ''}
        ${isDragReject ? 'border-red-500 bg-red-50' : ''}
        ${!isDragActive && !error ? 'border-gray-300 hover:border-gray-400' : ''}
        ${error ? 'border-red-500 bg-red-50' : ''}
        ${disabled ? 'opacity-50 cursor-not-allowed' : ''}
      `}
      aria-label="File upload area"
    >
      <input {...getInputProps()} aria-describedby="file-upload-description" />
      
      <div className="space-y-4">
        {/* Upload Icon */}
        <div className="mx-auto w-12 h-12 text-gray-400">
          <svg fill="none" stroke="currentColor" viewBox="0 0 24 24" className="w-full h-full">
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={1.5}
              d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"
            />
          </svg>
        </div>

        {/* Text Content */}
        <div>
          <p className="text-lg font-medium text-gray-900">
            {isDragActive ? 'Drop your PDF here' : 'Drop your PDF ticket here'}
          </p>
          <p id="file-upload-description" className="mt-1 text-sm text-gray-600">
            or <span className="text-primary-600 font-medium">click to browse</span>
          </p>
          <p className="mt-2 text-xs text-gray-500">
            PDF files only, up to 10MB
          </p>
        </div>

        {/* Error Message */}
        {error && (
          <div className="text-sm text-red-600 bg-red-100 border border-red-200 rounded-lg p-3" role="alert">
            {error}
          </div>
        )}

        {/* Drag Reject Message */}
        {isDragReject && (
          <div className="text-sm text-red-600" role="alert">
            Only PDF files are accepted
          </div>
        )}
      </div>
    </div>
  );
};

export default FileDropzone;
