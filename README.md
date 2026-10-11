# trade-assistant

Console-based trading assistant for CNYRUBF futures on MOEX.
Analyzes market structure (trend, levels, candlestick patterns),
alerts on signals, logs trades with comments and tags, and tracks
performance stats. Does NOT execute trades — manual entry only.
Built with Python, pandas_ta, SQLite, APScheduler.

## Installation

```bash
python -m venv venv

# Linux / macOS
source venv/bin/activate

# Windows (PowerShell)
.\venv\Scripts\Activate.ps1

pip install -r requirements.txt