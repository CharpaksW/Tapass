# PDF to Wallet Pass Test Suite

This directory contains a comprehensive test suite for the `pdf_to_wallet_pass_modular.py` module.

## Test Files

The test suite uses PDF files located in the `Test_files/` directory:
- `1.pdf` through `6.pdf` - Various PDF ticket/receipt samples
- `7.png` - Image file (for testing image handling)

## Running Tests

### Option 1: Interactive Test Runner (Recommended)
```bash
# Windows
run_tests.bat

# Linux/Mac
python run_tests.py
```

This provides an interactive menu to:
1. Run all tests
2. Test a specific file
3. Run with verbose output
4. Test self-tests only

### Option 2: Direct Test Execution
```bash
# Run all tests
python test_pdf_to_wallet_pass.py

# Run with verbose output
python test_pdf_to_wallet_pass.py --verbose

# Test specific file
python test_pdf_to_wallet_pass.py --test-file 1.pdf
```

### Option 3: Using unittest directly
```bash
python -m unittest test_pdf_to_wallet_pass.py -v
```

## Test Categories

### 1. Unit Tests
- **Self-tests**: Tests the built-in self-test functionality
- **Initialization**: Tests processor component initialization
- **Text Extraction**: Tests PDF text extraction for all test files
- **Field Parsing**: Tests field parsing with sample data
- **File Utils**: Tests utility functions for saving passes

### 2. Integration Tests
- **Pass Generation**: Tests complete PDF-to-pass conversion for all test files
- **Specific File Testing**: Detailed testing of individual files
- **LLM Integration**: Tests LLM-assisted processing (if API key available)

### 3. Validation Tests
- **Pass Structure**: Validates generated passes conform to Apple Wallet standards
- **Required Fields**: Ensures all mandatory fields are present
- **Content Fields**: Verifies passes contain appropriate content

## Test Output

Tests generate output in temporary directories:
- Individual test outputs are saved to separate folders
- Generated passes are saved as JSON files for inspection
- Detailed logs show processing steps and results

## Environment Setup

### Required Dependencies
```bash
pip install pymupdf opencv-python pillow jsonschema python-dateutil numpy
```

### Optional LLM Testing
For LLM-assisted processing tests, set:
```bash
export ANTHROPIC_API_KEY=your_api_key_here
```

## Test Results Interpretation

### Success Indicators
- ✅ Test passes successfully
- 🎉 All tests completed
- Generated pass JSON files are valid

### Warning Indicators
- ⚠️ No text extracted from PDF (may be image-only)
- ⚠️ No passes generated (PDF format not recognized)

### Error Indicators
- ❌ Test failed with exception
- Missing required fields in generated passes
- Import errors or dependency issues

## Troubleshooting

### Common Issues

1. **Import Errors**
   - Ensure you're running from the correct directory
   - Check that all dependencies are installed
   - Verify Python path includes the module directory

2. **No Text Extracted**
   - PDF may be image-only (requires OCR)
   - PDF may be corrupted or encrypted
   - Check PDF file permissions

3. **No Passes Generated**
   - PDF content may not match expected ticket/receipt patterns
   - Try with different test files
   - Check logs for specific error messages

4. **LLM Tests Skipped**
   - API key not set in environment
   - Network connectivity issues
   - API quota exceeded

### Debug Mode
Run with `--verbose` flag or set logging level to DEBUG for detailed output:
```bash
python test_pdf_to_wallet_pass.py --verbose
```

## Adding New Test Files

1. Place PDF files in the `Test_files/` directory
2. Name them descriptively (e.g., `concert_ticket.pdf`)
3. Run tests to verify they process correctly
4. Update this README if needed

## Test Coverage

The test suite covers:
- ✅ PDF text extraction
- ✅ QR code detection
- ✅ Field parsing and extraction
- ✅ Pass structure generation
- ✅ Apple Wallet format compliance
- ✅ File I/O operations
- ✅ Error handling
- ✅ LLM integration (optional)

## Contributing

When adding new tests:
1. Follow the existing test structure
2. Add appropriate assertions
3. Include logging for debugging
4. Test both success and failure cases
5. Update documentation as needed
