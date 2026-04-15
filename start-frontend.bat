@echo off
echo ========================================
echo Starting Genesis AI Frontend Server
echo ========================================
echo.

cd genesis-ai-frontend

echo Starting Vite dev server...
echo Frontend will be available at: http://127.0.0.1:5173/genesis-ai/
echo.

pnpm run dev
