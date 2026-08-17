# Infinity Trader Windows Worker
This directory contains the robust 24/7 Windows Compilation daemon. It securely polls the Render API, claims MT5 compilation jobs, dynamically injects MT5 IDs into the EA template, compiles via MetaEditor64, and uploads the `.ex5` directly back to the API.

## 1. Windows Requirements
- **OS:** Windows Server 2019+ or Windows 10+
- **MetaTrader 5:** Installed and accessible
- **Python:** Python 3.9+

## 2. Installation & Dependencies
1. Install Python from `python.org` (ensure "Add Python to PATH" is checked during installation).
2. Install dependencies:
   ```powershell
   pip install -r requirements.txt
   ```

## 3. Configuration (.env)
1. Copy `.env.example` to `.env`:
   ```powershell
   copy .env.example .env
   ```
2. Edit `.env` to include your specific paths and API keys:
   - `WORKER_API_KEY`: Must match the secret key set on your Render API `INFINITY_WORKER_API_KEY`.
   - `METAEDITOR_PATH`: Point to your actual MetaEditor. e.g., `C:\Program Files\MetaTrader 5\metaeditor64.exe`

## 4. Master Template Setup
**CRITICAL:** Do NOT leave the placeholder `bot.mq5` in production!
1. Place your real EA `.mq5` source code into the `windows-worker/templates/` folder (or anywhere accessible).
2. Ensure your template contains the EXACT string `__MT5_LICENSE_ID__` where the MT5 ID should be injected.
3. Update `TEMPLATE_PATH` in `.env` to point to it.

## 5. Running & Testing Manually
To test connectivity and compilation visually:
1. Open PowerShell.
2. Run:
   ```powershell
   .\start-worker.ps1
   ```
3. Watch the console output. Check `logs/worker.log` for any connection errors or API rejections.

## 6. Installing 24/7 Automatic Startup
The worker must run entirely unattended, even if you reboot the server or close your RDP session.
1. Right-click PowerShell and run as **Administrator**.
2. Run the install script:
   ```powershell
   .\install.ps1
   ```
3. This creates a Windows Scheduled Task named `InfinityTraderWorker` that starts on boot under the `SYSTEM` account.

> **Note on MetaEditor CLI:** If MetaEditor fails to compile when running under the `SYSTEM` account (some EA dependencies require an active user profile to resolve file paths), you may need to open Task Scheduler (`taskschd.msc`), edit `InfinityTraderWorker`, and change the "Run as user" from `SYSTEM` to your actual Administrator username, checking the box "Run whether user is logged on or not."

## 7. Troubleshooting
- **API Connection Fails:** Verify `API_BASE_URL` and `WORKER_API_KEY`.
- **MetaEditor Fails to Compile:** Check `logs/worker.log` for the exact MetaEditor error output. Ensure `METAEDITOR_PATH` is correct.
- **Worker Crashes:** The daemon is designed to catch all exceptions and keep polling, but if the Python process dies, check the Windows Event Viewer or start it manually to debug.

## 8. Security
- Never expose `WORKER_API_KEY`.
- Do not commit your real `.env` or your real `.mq5` master template if it is proprietary.
