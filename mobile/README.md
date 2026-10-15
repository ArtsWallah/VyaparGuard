@'
# VyaparGuard

A mobile-first utility for inspecting payment screenshots and
comparing extracted details with trusted transaction records.

## Stack
- Mobile: React Native, Expo, TypeScript
- Backend: FastAPI, Python
- Image processing: OpenCV
- Database: SQLite

## Development
- Backend API: http://127.0.0.1:8000
- API documentation: http://127.0.0.1:8000/docs
- Health check: http://127.0.0.1:8000/health

## Important
A screenshot alone does not prove that money was received.
The MVP uses simulated trusted records unless a real authorized
transaction source is explicitly configured.
'@ | Set-Content README.md

### TesseractOCR
 winget install --id UB-Mannheim.TesseractOCR -e