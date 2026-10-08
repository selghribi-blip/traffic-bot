@echo off
REM Traffic Bot - Windows Quick Start
REM Run this batch file to easily start the traffic bot

echo ========================================
echo   Traffic Bot - Windows Launcher
echo ========================================
echo.

REM Check if .env exists
if not exist .env (
    echo ERROR: .env file not found!
    echo Please copy .env.example to .env and fill in your credentials:
    echo   copy .env.example .env
    echo   notepad .env
    pause
    exit /b 1
)

REM Load environment variables
for /f "tokens=1,* delims==" %%a in (.env) do (
    set "%%a=%%b"
)

REM Get target URL
set TARGET_URL=%TARGET_URL%
if "%TARGET_URL%"=="" set TARGET_URL=https://www.forjo.tech/

echo Target URL: %TARGET_URL%
echo.

REM Parse arguments
set MODE=both
set LOG_LEVEL=INFO
set OUTPUT=
set PAGES=

:parse_args
if "%~1"=="" goto run
if "%~1"=="-u" set TARGET_URL=%~2 & shift & shift & goto parse_args
if "%~1"=="-o" set OUTPUT=%~2 & shift & shift & goto parse_args
if "%~1"=="-l" set LOG_LEVEL=%~2 & shift & shift & goto parse_args
if "%~1"=="-p" set PAGES=%~2 & shift & shift & goto parse_args
if "%~1"=="scrapy" set MODE=scrapy & shift & goto parse_args
if "%~1"=="browserstack" set MODE=browserstack & shift & goto parse_args
if "%~1"=="local" set MODE=local & shift & goto parse_args
if "%~1"=="both" set MODE=both & shift & goto parse_args
shift
goto parse_args

:run
echo Mode: %MODE%
echo Log Level: %LOG_LEVEL%
if not "%OUTPUT%"=="" echo Output: %OUTPUT%
if not "%PAGES%"=="" echo Max Pages: %PAGES%
echo ----------------------------------------

if "%MODE%"=="scrapy" (
    echo Starting Scrapy spider...
    scrapy crawl traffic_bot -a target_url="%TARGET_URL%" -L %LOG_LEVEL% %OUTPUT_OPTION% %PAGES_OPTION%
    exit /b %ERRORLEVEL%
)

if "%MODE%"=="browserstack" (
    echo Starting BrowserStack spider...
    scrapy crawl browserstack_bot -a target_url="%TARGET_URL%" -a use_browserstack=true -L %LOG_LEVEL% %OUTPUT_OPTION%
    exit /b %ERRORLEVEL%
)

if "%MODE%"=="local" (
    echo Starting Local Browser spider...
    scrapy crawl browserstack_bot -a target_url="%TARGET_URL%" -a use_browserstack=false -L %LOG_LEVEL% %OUTPUT_OPTION%
    exit /b %ERRORLEVEL%
)

if "%MODE%"=="both" (
    echo Starting BOTH spiders...
    echo.
    echo ========================================
    echo Running Scrapy Spider
    echo ========================================
    scrapy crawl traffic_bot -a target_url="%TARGET_URL%" -L %LOG_LEVEL% %OUTPUT_OPTION% %PAGES_OPTION%
    set SCRAPY_RESULT=%ERRORLEVEL%
    echo.
    echo ========================================
    echo Running BrowserStack Spider
    echo ========================================
    if defined BROWSERSTACK_USERNAME (
        scrapy crawl browserstack_bot -a target_url="%TARGET_URL%" -a use_browserstack=true -L %LOG_LEVEL% %OUTPUT_OPTION%
    ) else (
        echo BrowserStack credentials not found, running local browser instead...
        scrapy crawl browserstack_bot -a target_url="%TARGET_URL%" -a use_browserstack=false -L %LOG_LEVEL% %OUTPUT_OPTION%
    )
    set BS_RESULT=%ERRORLEVEL%
    
    if %SCRAPY_RESULT% NEQ 0 exit /b %SCRAPY_RESULT%
    if %BS_RESULT% NEQ 0 exit /b %BS_RESULT%
    exit /b 0
)

echo Invalid mode: %MODE%
echo Usage: run.bat [scrapy|browserstack|local|both] [-u URL] [-o output.json] [-l LEVEL] [-p PAGES]
pause