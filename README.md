# UPI Invoice QR

Stamp a UPI payment QR code (and an optional signature) onto any invoice PDF.
Pick the spot on the page, set the size, save. Works offline.

Download the exe from Releases

*Made & Designed by Jashandeep Singh*

---

## Features

- **Dynamic UPI QR** from your UPI ID and merchant name, with an optional **logo in the centre**.
- **Amount is optional.** Leave it empty and the customer types the amount in their UPI app.
- **Note field** (optional) that appears as the payment note in the customer's app.
- **"Scan & Pay" caption card** under the QR (amount, merchant name and a small hint line). Can be switched off.
- **Optional signature:** add a photo of your signature, see a preview, and the paper background is removed automatically so only the ink shows.
- **Placement window** with a live preview:
  - Click or drag to position the QR and the signature.
  - **Zoom up to 400%** (buttons, or Ctrl + mouse wheel), scroll and pan the page.
  - Size slider for each item, and 1 pt nudge buttons for fine adjustment.
  - Multi-page PDFs: the QR and the signature can go on different pages.
- Settings are remembered between runs.

---

## Files in the project folder

```
UPI_Tool\
├── UPI.py            the app
├── build_exe.bat     builds the .exe (optional)
└── README.md         this file
```

Files the app creates by itself, next to the app or the `.exe`:

| File | What it is |
|------|-----------|
| `upi_config.json` | Your UPI ID, merchant name, logo and signature settings |
| `upi_logo.png` / `.jpg` | Copy of your centre logo |
| `upi_signature.png` / `.jpg` | Copy of your signature image |

---

## How to use

1. **Merchant profile:** enter your UPI ID (like `name@bank`) and merchant name. Optionally add a centre logo. Click **Save**.
2. **Signature (optional):** click **Browse…** and pick a clear photo of your signature on white paper. Keep "Remove paper background" ticked for a clean result. Untick "Add to this invoice" to skip it for one invoice.
3. **New invoice:** enter the amount (or leave it empty), an optional note, then click **Choose PDF & place QR**.
4. **Placement window:**
   - Choose **QR code** or **Signature** under PLACING, then click or drag on the page.
   - Use **ZOOM** to see detail, **PAGE** to change pages, **SIZE** to resize, and **NUDGE** to move by 1 pt.
   - Click **Save PDF** and pick a new file name. The original PDF is never changed.

Tip: scan the finished QR with your own phone once before sending an invoice.

**Mouse and keyboard in the placement window**

| Action | How |
|--------|-----|
| Place / move the selected item | Left click or drag |
| Zoom in / out | Ctrl + mouse wheel, `+` / `-` buttons, or Ctrl + `+` / Ctrl + `-` |
| Fit the whole page | **Fit** button or Ctrl + `0` |
| Scroll | Mouse wheel (Shift + wheel for sideways) or the scrollbars |
| Move the view while zoomed | Right or middle mouse button drag |

---

## Run from source (needs Python)

1. Install Python 3.10 or newer (64-bit) from python.org. Tick **"Add python.exe to PATH"** in the installer.
2. Open Command Prompt in the project folder and run:

```
python -m pip install pymupdf qrcode pillow
python UPI.py
```

---

## Build the .exe (so other PCs need no Python)

You only need Python on the PC where you build.

1. Put `UPI.py` and `build_exe.bat` in one folder.
2. Double-click **`build_exe.bat`**.
   - It creates a clean build environment in `.build_env` (first time only), installs only the packages the app needs, and builds the exe.
   - The first run takes about 2 to 4 minutes.
3. When it says **Done!**, your app is at `dist\UPI Invoice QR.exe`.

The command it runs, if you want to do it by hand:

```
python -m PyInstaller --noconfirm --clean --onefile --windowed --collect-all pymupdf --name "UPI Invoice QR" UPI.py
```

**Custom icon (optional):** put a `logo.ico` in the folder and add `--icon logo.ico` before `UPI.py` in that command (or in `build_exe.bat`).

**Rebuilding after you edit `UPI.py`:** delete the `build` and `dist` folders, then run `build_exe.bat` again.

---

## Using the .exe on other PCs

- Copy `UPI Invoice QR.exe` into its own folder (for example `Desktop\UPI App`). Don't put it in `Program Files`, because Windows blocks the app from saving settings there.
- **Just the exe:** works on any 64-bit Windows 10 or 11 PC. Enter your profile once on the new PC.
- **With your settings:** copy the exe together with `upi_config.json`, `upi_logo.*` and `upi_signature.*` into the same folder.

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `python is not recognized` | Reinstall Python and tick "Add python.exe to PATH". Or replace `python` with `py` in `build_exe.bat`. |
| Build is very slow or the exe is huge | Use the included `build_exe.bat`. It builds in a clean environment, so unrelated packages (torch, pandas and so on) aren't pulled in. |
| Exe opens and closes instantly | Remove `--windowed` from the build command, rebuild, and run the exe from Command Prompt to see the error. |
| Windows SmartScreen or antivirus warning | Normal for unsigned exes. Click "More info", then "Run anyway", or add the exe to your antivirus exclusions. |
| Exe is slow to start the first time | One-file exes unpack themselves on launch. A few seconds is normal. |
| "Can't overwrite the original" | Save the new PDF under a different file name. |
| Signature still has a grey or white box | Use a photo with even lighting on plain white paper, or a PNG with a transparent background. |
| Rupee symbol shows as "Rs." in the caption | Your system has no font with the ₹ glyph. Windows has one, so this should only happen on other systems. |

---

## Good to know

- The QR sends the payment straight to your UPI ID. The app does not check or track payments.
- PDF pages that are rotated (90° or 270°) are not tested. Check the result if you use them.
- Requirements for running from source: `pymupdf`, `qrcode`, `pillow` (Tkinter comes with Python on Windows).

---

## Upcoming features (v2)

This is the plan for the next version. These are ideas, not promises, and the order may change.

**Faster invoicing**
- **Remember placement:** save the QR and signature position and size per invoice template, so repeat invoices take one click.
- **Batch mode:** load a CSV of invoice numbers and amounts, or a whole folder of PDFs, and stamp them all in one go.
- **Auto-detect the amount:** read the total from the invoice PDF's text so you don't type it.
- **Drag and drop:** drop a PDF onto the app window to open it.

**Better payments**
- **Invoice reference:** add the invoice number to the UPI link, so payments are easier to match in your bank statement.
- **Test QR button:** decode the generated QR and confirm it scans correctly before saving.
- **Multiple merchant profiles:** switch between personal and business UPI IDs, each with its own logo.

**Design and customisation**
- **Custom caption:** change the caption text, colours, and merchant details shown under the QR.
- **More stamps:** add a company seal or stamp alongside the signature, and keep several signatures to choose from.
- **Dark mode** and a few colour themes.

**Packaging**
- **Custom app icon** and version info inside the exe.
- **Proper installer** (Start Menu shortcut, uninstall) instead of a single loose exe.
- **Code signing**, so Windows SmartScreen stops warning on first run.

Have an idea? Add it here.
