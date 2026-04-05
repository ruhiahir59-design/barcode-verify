# Fake Product Identification (College Demo)

## What to keep when submitting

| Folder / file | Purpose |
|---------------|---------|
| `app.py` | Run the app from project root |
| `demo-simple/` | Templates, CSS, data (`blockchain.json`), QR output folder |
| `presentation/` | PPT content + HTML slides |
| `requirements.txt` | Python dependencies |

## Do **not** zip these (optional — saves space)

- **`venv/`** — recreate on any PC: `python -m venv venv` then `pip install -r requirements.txt`
- **`__pycache__/`** — Python cache; safe to delete (recreated automatically)
- **`demo-simple/static/qrcodes/*.png`** — generated QR images (optional; empty folder is OK)

## Quick run (Windows)

```powershell
cd D:\College
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
python app.py
```

Use **`Activate.ps1`** in PowerShell (no trailing `\` after `activate`). If scripts are blocked:  
`Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`  
Alternative: **CMD** → `venv\Scripts\activate.bat`

Browser: **http://127.0.0.1:5001**

## More help

- **Simple explanation (easy English):** `SIMPLE_GUIDE.md`
- Step-by-step: `demo-simple\README.md`
- Slides: `presentation\README.md`
