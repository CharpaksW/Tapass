import React, { useState } from 'react';
import FileDropzone from './components/FileDropzone';
import LoadingSpinner from './components/LoadingSpinner';

interface ProcessResponse {
  ok: boolean;
  error?: string;
}

type AppState = 'idle' | 'processing' | 'success' | 'error';

const App: React.FC = () => {
  const [state, setState] = useState<AppState>('idle');
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [email, setEmail] = useState('');
  const [errorMessage, setErrorMessage] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  const validateEmail = (email: string): boolean => {
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return emailRegex.test(email);
  };

  const handleFileSelect = (file: File) => {
    setSelectedFile(file);
    setErrorMessage('');
    if (state === 'error') {
      setState('idle');
    }
  };

  const handleEmailChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setEmail(e.target.value);
    setErrorMessage('');
    if (state === 'error') {
      setState('idle');
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (isSubmitting) return; // Prevent double submission

    // Validation
    if (!selectedFile) {
      setErrorMessage('Please select a PDF file');
      return;
    }

    if (!email.trim()) {
      setErrorMessage('Please enter your email address');
      return;
    }

    if (!validateEmail(email.trim())) {
      setErrorMessage('Please enter a valid email address');
      return;
    }

    setIsSubmitting(true);
    setState('processing');
    setErrorMessage('');

    try {
      const formData = new FormData();
      formData.append('file', selectedFile);
      formData.append('email', email.trim());

      const response = await fetch('/api/process', {
        method: 'POST',
        body: formData,
      });

      const result: ProcessResponse = await response.json();

      if (result.ok) {
        setState('success');
      } else {
        setState('error');
        setErrorMessage(result.error || 'An error occurred while processing your file');
      }
    } catch (error) {
      setState('error');
      setErrorMessage('Network error. Please check your connection and try again.');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleReset = () => {
    setState('idle');
    setSelectedFile(null);
    setEmail('');
    setErrorMessage('');
    setIsSubmitting(false);
  };

  const getFileDisplayName = (file: File): string => {
    if (file.name.length > 30) {
      return file.name.substring(0, 27) + '...';
    }
    return file.name;
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-primary-50 to-blue-100 py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-md mx-auto">
        {/* Header */}
        <div className="text-center mb-8">
          <div className="mx-auto w-16 h-16 bg-primary-600 rounded-full flex items-center justify-center mb-4">
            <svg className="w-8 h-8 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z" />
            </svg>
          </div>
          <h1 className="text-3xl font-bold text-gray-900 mb-2">PDF to Wallet</h1>
          <p className="text-gray-600">Convert your PDF tickets to Apple Wallet passes</p>
        </div>

        {/* Main Card */}
        <div className="card p-6">
          {state === 'success' ? (
            /* Success State */
            <div className="text-center space-y-4">
              <div className="mx-auto w-16 h-16 bg-green-100 rounded-full flex items-center justify-center">
                <svg className="w-8 h-8 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                </svg>
              </div>
              <h2 className="text-xl font-semibold text-gray-900">Success!</h2>
              <p className="text-gray-600">
                We've emailed your wallet JSON to <span className="font-medium text-gray-900">{email}</span>. 
                Check your inbox.
              </p>
              <button
                onClick={handleReset}
                className="btn-primary w-full"
                type="button"
              >
                Process Another File
              </button>
            </div>
          ) : (
            /* Form State */
            <form onSubmit={handleSubmit} className="space-y-6">
              {/* File Upload */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Upload PDF Ticket
                </label>
                <FileDropzone
                  onFileSelect={handleFileSelect}
                  disabled={state === 'processing'}
                  error={!selectedFile && errorMessage && errorMessage.includes('PDF') ? errorMessage : undefined}
                />
                {selectedFile && (
                  <div className="mt-3 flex items-center text-sm text-gray-600">
                    <svg className="w-4 h-4 mr-2 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                    {getFileDisplayName(selectedFile)} ({Math.round(selectedFile.size / 1024)} KB)
                  </div>
                )}
              </div>

              {/* Email Input */}
              <div>
                <label htmlFor="email" className="block text-sm font-medium text-gray-700 mb-2">
                  Your Email Address
                </label>
                <input
                  type="email"
                  id="email"
                  value={email}
                  onChange={handleEmailChange}
                  placeholder="Enter your email"
                  className={`input-field ${errorMessage && errorMessage.includes('email') ? 'border-red-500 focus:border-red-500 focus:ring-red-500' : ''}`}
                  disabled={state === 'processing'}
                  required
                  aria-describedby={errorMessage && errorMessage.includes('email') ? 'email-error' : undefined}
                />
                {errorMessage && errorMessage.includes('email') && (
                  <p id="email-error" className="mt-1 text-sm text-red-600" role="alert">
                    {errorMessage}
                  </p>
                )}
              </div>

              {/* General Error Message */}
              {errorMessage && !errorMessage.includes('email') && !errorMessage.includes('PDF') && (
                <div className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg p-3" role="alert">
                  {errorMessage}
                </div>
              )}

              {/* Submit Button */}
              <button
                type="submit"
                disabled={state === 'processing' || isSubmitting}
                className="btn-primary w-full flex items-center justify-center space-x-2"
              >
                {state === 'processing' ? (
                  <>
                    <LoadingSpinner size="sm" className="text-white" />
                    <span>Processing...</span>
                  </>
                ) : (
                  <span>Convert to Wallet Pass</span>
                )}
              </button>
            </form>
          )}
        </div>

        {/* Footer */}
        <div className="text-center mt-8 text-sm text-gray-500">
          <p>Secure processing • Your files are not stored</p>
        </div>
      </div>
    </div>
  );
};

export default App;
