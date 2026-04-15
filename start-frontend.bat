@echo off
echo ========================================
echo Starting Genesis AI Frontend Server
echo ========================================
echo.

cd genesis-ai-frontend

echo Starting Vite dev server...
echo Frontend will be available at: http://localhost:5173
echo.

pnpm run dev
