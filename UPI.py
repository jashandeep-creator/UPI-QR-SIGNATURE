import io
import json
import os
import re
import shutil
import subprocess
import sys
import tkinter as tk
from decimal import Decimal, InvalidOperation
from tkinter import filedialog, messagebox, ttk
from urllib.parse import quote

import pymupdf as fitz
import qrcode
from PIL import Image, ImageChops, ImageDraw, ImageFont, ImageOps, ImageTk
from qrcode.constants import ERROR_CORRECT_H

# Config is stored next to the script, so it works no matter where you launch from
def app_dir():
    """Folder where settings live. Inside a PyInstaller .exe, __file__ points to a temp
    folder that is deleted on exit, so use the folder that holds the .exe instead."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def resolve_path(p):
    """Logo paths saved without a folder are looked up next to the app."""
    return p if os.path.isabs(p) else os.path.join(app_dir(), p)


CONFIG_FILE = os.path.join(app_dir(), "upi_config.json")

# ---- Theme ----
BG = "#F3F4F8"
CARD = "#FFFFFF"
ACCENT = "#4F46E5"
ACCENT_DARK = "#4338CA"
TEXT = "#1F2937"
MUTED = "#6B7280"
BORDER = "#E5E7EB"
FONT = "Segoe UI"

UPI_REGEX = re.compile(r"^[\w.\-]{2,256}@[A-Za-z]{2,64}$")


# =====================================================================
# QR generation
# =====================================================================
def parse_amount(text):
    """Return amount as a string with 2 decimals, or None if invalid."""
    try:
        value = Decimal(text.strip().replace(",", ""))
    except (InvalidOperation, AttributeError):
        return None
    if value <= 0 or value > Decimal("100000000"):
        return None
    return f"{value:.2f}"


def build_upi_string(upi_id, name, amount, note=""):
    parts = [
        f"pa={quote(upi_id.strip(), safe='@.-_')}",
        f"pn={quote(name.strip())}",
    ]
    if amount:  # optional: if missing, the payer types the amount in their UPI app
        parts.append(f"am={amount}")
    parts.append("cu=INR")
    if note.strip():
        parts.append(f"tn={quote(note.strip())}")
    return "upi://pay?" + "&".join(parts)


def build_qr_image(upi_string, logo_path=""):
    qr = qrcode.QRCode(error_correction=ERROR_CORRECT_H, box_size=12, border=2)
    qr.add_data(upi_string)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white").convert("RGBA")

    logo_path = resolve_path(logo_path) if logo_path else ""
    if logo_path and os.path.exists(logo_path):
        logo = Image.open(logo_path).convert("RGBA")  # always RGBA -> alpha handled safely
        max_side = int(img.width * 0.22)  # keep logo small enough for reliable scanning
        logo.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)

        pad = 6
        bg = Image.new("RGBA", (logo.width + pad * 2, logo.height + pad * 2), "white")
        x = (img.width - bg.width) // 2
        y = (img.height - bg.height) // 2
        img.paste(bg, (x, y))
        img.alpha_composite(logo, (x + pad, y + pad))  # this is the fixed part

    return img.convert("RGB")


FONTS_BOLD = ["segoeuib.ttf", "arialbd.ttf", "DejaVuSans-Bold.ttf", "Arial Bold.ttf",
              "/System/Library/Fonts/Supplemental/Arial Bold.ttf"]
FONTS_REG = ["segoeui.ttf", "arial.ttf", "DejaVuSans.ttf", "Arial.ttf",
             "/System/Library/Fonts/Supplemental/Arial.ttf"]


def load_font(candidates, size):
    """Return (font, is_truetype). Falls back to Pillow's default font."""
    for name in candidates:
        try:
            return ImageFont.truetype(name, size), True
        except OSError:
            continue
    try:
        return ImageFont.load_default(size=size), False
    except TypeError:
        return ImageFont.load_default(), False


def build_qr_card(qr_img, merchant="", amount=None):
    """Wrap the QR in a clean card: QR, 'SCAN & PAY' pill, amount, merchant, hint line."""
    pad = int(qr_img.width * 0.06)
    W = qr_img.width + pad * 2
    canvas = Image.new("RGB", (W, qr_img.height + W), "white")
    d = ImageDraw.Draw(canvas)
    canvas.paste(qr_img, (pad, pad))
    max_w = W - pad * 2
    y = pad + qr_img.height + int(pad * 0.6)

    def fitted(text, bold, size):
        cands = FONTS_BOLD if bold else FONTS_REG
        while True:
            font, ok = load_font(cands, size)
            if d.textlength(text, font=font) <= max_w or size <= 12:
                return font, ok, size
            size -= 2

    # pill: SCAN & PAY
    label = "SCAN & PAY"
    font, ok, size = fitted(label, True, int(W * 0.075))
    tw = d.textlength(label, font=font)
    ph = int(size * 1.9)
    pw = tw + size * 1.8
    x0 = (W - pw) / 2
    d.rounded_rectangle([x0, y, x0 + pw, y + ph], radius=ph / 2, fill=ACCENT)
    d.text((W / 2, y + ph / 2), label, font=font, fill="white", anchor="mm")
    y += ph + int(pad * 0.5)

    # amount (only when one was entered)
    if amount:
        txt = f"{'₹' if ok else 'Rs.'}{amount}"
        font, _ok, size = fitted(txt, True, int(W * 0.10))
        d.text((W / 2, y + size * 0.65), txt, font=font, fill=TEXT, anchor="mm")
        y += int(size * 1.3)

    # merchant name
    if merchant:
        font, _ok, size = fitted(merchant, False, int(W * 0.052))
        d.text((W / 2, y + size * 0.65), merchant, font=font, fill=MUTED, anchor="mm")
        y += int(size * 1.4)

    # hint line
    hint = "Pay using any UPI app"
    font, _ok, size = fitted(hint, False, int(W * 0.04))
    d.text((W / 2, y + size * 0.65), hint, font=font, fill="#9CA3AF", anchor="mm")
    y += int(size * 1.3) + pad

    card = canvas.crop((0, 0, W, y))
    ImageDraw.Draw(card).rounded_rectangle([1, 1, W - 2, y - 2], radius=int(W * 0.05),
                                           outline="#D1D5DB", width=3)
    return card


def build_sign_image(path, remove_bg=True):
    """Load a signature photo as RGBA. With remove_bg, the paper becomes transparent
    (only the ink stays) and the image is cropped tight around the signature."""
    img = Image.open(path)
    img = ImageOps.exif_transpose(img).convert("RGBA")  # fixes sideways phone photos
    img.thumbnail((1400, 1400), Image.Resampling.LANCZOS)

    if remove_bg:
        gray = img.convert("L")
        # Paper brightness = 90th percentile, so shadows / dim lighting still count as paper
        hist = gray.histogram()
        total, acc, paper = sum(hist), 0, 255
        for value, count in enumerate(hist):
            acc += count
            if acc >= total * 0.9:
                paper = max(value, 120)
                break
        norm = gray.point(lambda v: min(255, int(v * 255 / paper)))
        alpha = norm.point(lambda v: 255 if v <= 140 else (0 if v >= 215 else int((215 - v) * 255 / 75)))
        img.putalpha(ImageChops.multiply(alpha, img.getchannel("A")))

    box = img.getchannel("A").point(lambda v: 255 if v > 20 else 0).getbbox()
    if box:
        m = 6
        img = img.crop((max(0, box[0] - m), max(0, box[1] - m),
                        min(img.width, box[2] + m), min(img.height, box[3] + m)))
    return img


# =====================================================================
# PDF placement window
# =====================================================================
class PlacementWindow(tk.Toplevel):
    MAX_ZOOM = 4.0

    def __init__(self, master, pdf_path, qr_img, sign_img, on_saved):
        super().__init__(master)
        self.title("Place QR Code & Signature" if sign_img is not None else "Place QR Code")
        self.configure(bg=BG)
        self.pdf_path = pdf_path
        self.on_saved = on_saved
        self.doc = fitz.open(pdf_path)
        self.page_no = 0
        self.zoom = 1.0          # 1.0 = whole page fits the view
        self.fit = 1.0           # canvas px per PDF point when zoom == 1
        self.scale = 1.0         # canvas px per PDF point right now
        self.ox = self.oy = 0    # offset used to centre a small page inside the view
        self.cache = {}
        self._updating = False

        # Everything that can be placed: image, centre (PDF points), page, width (PDF points)
        self.items = {"qr": {"label": "QR code", "img": qr_img, "center": None,
                             "page": 0, "size": 90.0, "range": (50, 220)}}
        if sign_img is not None:
            self.items["sign"] = {"label": "Signature", "img": sign_img, "center": None,
                                  "page": 0, "size": 110.0, "range": (30, 320)}
        self.active = tk.StringVar(value="qr")
        self.size_pt = tk.DoubleVar(value=90)
        self.protocol("WM_DELETE_WINDOW", self.close)

        # --- left: scrollable page view ---
        left = tk.Frame(self, bg=BG)
        left.pack(side="left", padx=(16, 8), pady=16)
        self.canvas = tk.Canvas(left, bg="#D1D5DB", highlightthickness=1,
                                highlightbackground=BORDER, cursor="crosshair")
        self.vsb = ttk.Scrollbar(left, orient="vertical", command=self.canvas.yview)
        self.hsb = ttk.Scrollbar(left, orient="horizontal", command=self.canvas.xview)
        self.canvas.configure(xscrollcommand=self.hsb.set, yscrollcommand=self.vsb.set)
        self.canvas.grid(row=0, column=0)
        self.vsb.grid(row=0, column=1, sticky="ns")
        self.hsb.grid(row=1, column=0, sticky="we")

        self.canvas.bind("<Button-1>", self.on_click)
        self.canvas.bind("<B1-Motion>", self.on_click)
        self.canvas.bind("<MouseWheel>", self.on_wheel)                 # Windows / macOS
        self.canvas.bind("<Button-4>", lambda e: self.on_wheel(e, 1))   # Linux
        self.canvas.bind("<Button-5>", lambda e: self.on_wheel(e, -1))
        for b in (2, 3):  # middle / right mouse drag = pan
            self.canvas.bind(f"<ButtonPress-{b}>", lambda e: self.canvas.scan_mark(e.x, e.y))
            self.canvas.bind(f"<B{b}-Motion>", lambda e: self.canvas.scan_dragto(e.x, e.y, gain=1))
        for seq in ("<Control-equal>", "<Control-plus>"):
            self.bind(seq, lambda e: self.zoom_by(1.25))
        self.bind("<Control-minus>", lambda e: self.zoom_by(0.8))
        self.bind("<Control-0>", lambda e: self.zoom_fit())

        # --- right: controls ---
        side = tk.Frame(self, bg=CARD, padx=18, pady=16,
                        highlightthickness=1, highlightbackground=BORDER)
        side.pack(side="right", fill="y", padx=(8, 16), pady=16)

        tk.Label(side, text="Place on invoice", font=(FONT, 15, "bold"),
                 bg=CARD, fg=TEXT).pack(anchor="w")
        tk.Label(side, text="Click or drag to place.  Ctrl + wheel zooms,\nright-drag moves the view.",
                 font=(FONT, 9), bg=CARD, fg=MUTED, justify="left").pack(anchor="w", pady=(2, 12))

        tk.Label(side, text="PLACING", font=(FONT, 8, "bold"), bg=CARD, fg=MUTED).pack(anchor="w")
        for key, it in self.items.items():
            ttk.Radiobutton(side, text=it["label"], value=key, variable=self.active,
                            command=self.on_mode_change).pack(anchor="w", pady=1)
        self.status_lbl = tk.Label(side, bg=CARD, fg=MUTED, font=(FONT, 9), justify="left")
        self.status_lbl.pack(anchor="w", pady=(4, 12))

        tk.Label(side, text="ZOOM", font=(FONT, 8, "bold"), bg=CARD, fg=MUTED).pack(anchor="w")
        zrow = tk.Frame(side, bg=CARD)
        zrow.pack(fill="x", pady=(4, 12))
        ttk.Button(zrow, text="−", width=3, command=lambda: self.zoom_by(0.8)).pack(side="left")
        self.zoom_lbl = tk.Label(zrow, bg=CARD, fg=TEXT, font=(FONT, 10, "bold"), width=6)
        self.zoom_lbl.pack(side="left")
        ttk.Button(zrow, text="+", width=3, command=lambda: self.zoom_by(1.25)).pack(side="left")
        ttk.Button(zrow, text="Fit", width=5, command=self.zoom_fit).pack(side="right")

        tk.Label(side, text="PAGE", font=(FONT, 8, "bold"), bg=CARD, fg=MUTED).pack(anchor="w")
        nav = tk.Frame(side, bg=CARD)
        nav.pack(fill="x", pady=(4, 12))
        ttk.Button(nav, text="‹", width=3, command=lambda: self.change_page(-1)).pack(side="left")
        self.page_lbl = tk.Label(nav, bg=CARD, fg=TEXT, font=(FONT, 10, "bold"))
        self.page_lbl.pack(side="left", expand=True)
        ttk.Button(nav, text="›", width=3, command=lambda: self.change_page(1)).pack(side="right")

        tk.Label(side, text="SIZE (WIDTH)", font=(FONT, 8, "bold"), bg=CARD, fg=MUTED).pack(anchor="w")
        self.size_lbl = tk.Label(side, bg=CARD, fg=TEXT, font=(FONT, 10))
        self.size_lbl.pack(anchor="w")
        self.size_slider = ttk.Scale(side, from_=50, to=220, variable=self.size_pt,
                                     command=lambda _v: self.on_size(), length=200)
        self.size_slider.pack(pady=(2, 12))

        tk.Label(side, text="NUDGE (1 pt)", font=(FONT, 8, "bold"), bg=CARD, fg=MUTED).pack(anchor="w")
        nudge = tk.Frame(side, bg=CARD)
        nudge.pack(fill="x", pady=(4, 8))
        for text, dx, dy in (("◀", -1, 0), ("▲", 0, -1), ("▼", 0, 1), ("▶", 1, 0)):
            ttk.Button(nudge, text=text, width=3,
                       command=lambda dx=dx, dy=dy: self.nudge(dx, dy)).pack(side="left", expand=True)
        ttk.Button(side, text="Remove from page", command=self.unplace).pack(fill="x", pady=(0, 14))

        ttk.Button(side, text="Save PDF", style="Accent.TButton",
                   command=self.save).pack(fill="x", ipady=6)
        ttk.Button(side, text="Cancel", command=self.close).pack(fill="x", pady=(8, 0))

        self.setup_viewport()
        self.render_page()
        self.on_mode_change()

    # ----- view / zoom -----
    def setup_viewport(self):
        page = self.doc[0]
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        self.vh = max(380, min(820, sh - 190))
        max_w = max(480, sw - 380)
        self.vw = int(min(max_w, max(page.rect.width * self.vh / page.rect.height, 560)))
        self.canvas.config(width=self.vw, height=self.vh)

    def render_page(self, anchor=None):
        page = self.doc[self.page_no]
        self.fit = min(self.vh / page.rect.height, self.vw / page.rect.width)
        pix = page.get_pixmap(matrix=fitz.Matrix(self.fit * self.zoom, self.fit * self.zoom))
        w, h = pix.width, pix.height
        self.scale = w / page.rect.width  # canvas pixels per PDF point
        self.tk_page = ImageTk.PhotoImage(Image.open(io.BytesIO(pix.tobytes("ppm"))))
        self.ox = max(0, (self.vw - w) // 2)
        self.oy = max(0, (self.vh - h) // 2)
        self.canvas.delete("all")
        self.canvas.create_image(self.ox, self.oy, anchor="nw", image=self.tk_page)
        tw, th = w + 2 * self.ox, h + 2 * self.oy
        self.canvas.config(scrollregion=(0, 0, tw, th))
        if anchor:  # keep the same spot of the page under the pointer / view centre
            ax, ay, vx, vy = anchor
            self.canvas.xview_moveto(max(0.0, (ax * self.scale + self.ox - vx) / tw))
            self.canvas.yview_moveto(max(0.0, (ay * self.scale + self.oy - vy) / th))
        self.page_lbl.config(text=f"{self.page_no + 1} / {len(self.doc)}")
        self.zoom_lbl.config(text=f"{round(self.zoom * 100)}%")
        self.cache.clear()
        self.draw_ghosts()

    def set_zoom(self, new_zoom, view_x=None, view_y=None):
        new_zoom = min(max(new_zoom, 1.0), self.MAX_ZOOM)
        if abs(new_zoom - self.zoom) < 1e-6:
            return
        if view_x is None:
            view_x, view_y = self.vw / 2, self.vh / 2
        cx, cy = self.canvas.canvasx(view_x), self.canvas.canvasy(view_y)
        anchor = ((cx - self.ox) / self.scale, (cy - self.oy) / self.scale, view_x, view_y)
        self.zoom = new_zoom
        self.render_page(anchor=anchor)

    def zoom_by(self, factor):
        self.set_zoom(self.zoom * factor)

    def zoom_fit(self):
        self.zoom = 1.0
        self.render_page()
        self.canvas.xview_moveto(0)
        self.canvas.yview_moveto(0)

    def on_wheel(self, event, direction=None):
        d = direction if direction is not None else (1 if event.delta > 0 else -1)
        if event.state & 0x4:        # Ctrl + wheel = zoom at the pointer
            self.set_zoom(self.zoom * (1.25 if d > 0 else 0.8), event.x, event.y)
        elif event.state & 0x1:      # Shift + wheel = scroll sideways
            self.canvas.xview_scroll(-d * 2, "units")
        else:                        # wheel = scroll up / down
            self.canvas.yview_scroll(-d * 2, "units")

    # ----- ghosts -----
    def draw_ghosts(self):
        self.canvas.delete("ghost")
        if len(self.cache) > 60:
            self.cache.clear()
        for key, it in self.items.items():
            if not it["center"] or it["page"] != self.page_no:
                continue
            pw = max(10, int(it["size"] * self.scale))
            ph = max(10, int(pw * it["img"].height / it["img"].width))
            tk_img = self.cache.get((key, pw, ph))
            if tk_img is None:
                tk_img = ImageTk.PhotoImage(it["img"].resize((pw, ph), Image.Resampling.LANCZOS))
                self.cache[(key, pw, ph)] = tk_img
            cx = it["center"][0] * self.scale + self.ox
            cy = it["center"][1] * self.scale + self.oy
            self.canvas.create_image(cx, cy, image=tk_img, tags="ghost")
            is_active = key == self.active.get()
            self.canvas.create_rectangle(cx - pw / 2, cy - ph / 2, cx + pw / 2, cy + ph / 2,
                                         outline=ACCENT if is_active else "#9CA3AF",
                                         width=2, dash=(4, 3), tags="ghost")

    def update_labels(self):
        size = self.items[self.active.get()]["size"]
        self.size_lbl.config(text=f"{size:.0f} pt  (~{size / 72 * 2.54:.1f} cm wide)")
        lines = []
        for other in self.items.values():
            state = f"page {other['page'] + 1}" if other["center"] else "not placed"
            lines.append(f"{other['label']}: {state}")
        self.status_lbl.config(text="\n".join(lines))

    # ----- events -----
    def on_mode_change(self):
        self._updating = True
        try:
            it = self.items[self.active.get()]
            lo, hi = it["range"]
            self.size_slider.config(from_=lo, to=hi)
            self.size_pt.set(it["size"])
        finally:
            self._updating = False
        self.update_labels()
        self.draw_ghosts()

    def on_size(self):
        if self._updating:
            return
        self.items[self.active.get()]["size"] = float(self.size_pt.get())
        self.update_labels()
        self.draw_ghosts()

    def on_click(self, event):
        page = self.doc[self.page_no]
        x = (self.canvas.canvasx(event.x) - self.ox) / self.scale
        y = (self.canvas.canvasy(event.y) - self.oy) / self.scale
        it = self.items[self.active.get()]
        it["center"] = (min(max(x, 0), page.rect.width), min(max(y, 0), page.rect.height))
        it["page"] = self.page_no
        self.update_labels()
        self.draw_ghosts()

    def nudge(self, dx, dy):
        it = self.items[self.active.get()]
        if not it["center"]:
            return
        page = self.doc[it["page"]]
        it["center"] = (min(max(it["center"][0] + dx, 0), page.rect.width),
                        min(max(it["center"][1] + dy, 0), page.rect.height))
        self.draw_ghosts()

    def unplace(self):
        self.items[self.active.get()]["center"] = None
        self.update_labels()
        self.draw_ghosts()

    def change_page(self, delta):
        new = self.page_no + delta
        if 0 <= new < len(self.doc):
            self.page_no = new
            self.render_page()
            self.canvas.xview_moveto(0)
            self.canvas.yview_moveto(0)

    def close(self):
        try:
            self.doc.close()
        finally:
            self.destroy()

    # ----- save -----
    def save(self):
        if not self.items["qr"]["center"]:
            messagebox.showwarning("Place the QR", "Select \"QR code\" and click on the page to choose where it goes.",
                                   parent=self)
            return
        sign = self.items.get("sign")
        if sign and not sign["center"]:
            if not messagebox.askyesno("Signature not placed",
                                       "You added a signature but haven't placed it on the page.\n\n"
                                       "Save without the signature?", parent=self):
                return

        base = os.path.splitext(os.path.basename(self.pdf_path))[0]
        out = filedialog.asksaveasfilename(
            parent=self, title="Save invoice as", defaultextension=".pdf",
            initialfile=f"{base}_with_QR.pdf", filetypes=[("PDF Files", "*.pdf")])
        if not out:
            return
        if os.path.abspath(out) == os.path.abspath(self.pdf_path):
            messagebox.showerror("Choose another name",
                                 "Can't overwrite the original while it is open. Pick a different file name.",
                                 parent=self)
            return

        try:
            doc = fitz.open(self.pdf_path)
            for it in self.items.values():
                if not it["center"]:
                    continue
                page = doc[it["page"]]
                cx, cy = it["center"]
                half_w = it["size"] / 2
                half_h = half_w * it["img"].height / it["img"].width
                rect = fitz.Rect(cx - half_w, cy - half_h, cx + half_w, cy + half_h) * page.derotation_matrix
                buf = io.BytesIO()
                it["img"].save(buf, format="PNG")
                page.insert_image(rect, stream=buf.getvalue())
            doc.save(out, garbage=3, deflate=True)
            doc.close()
        except Exception as e:
            messagebox.showerror("Error", f"Could not save the PDF:\n{e}", parent=self)
            return

        self.close()
        self.on_saved(out)


# =====================================================================
# Main window
# =====================================================================
class UPIInvoiceApp:
    def __init__(self, root):
        self.root = root
        root.title("UPI Invoice QR Tool")
        root.geometry("500x760")
        root.minsize(500, 700)
        root.configure(bg=BG)

        self.upi_id = tk.StringVar()
        self.merchant_name = tk.StringVar()
        self.logo_path = tk.StringVar()
        self.amount = tk.StringVar()
        self.note = tk.StringVar()
        self.show_caption = tk.BooleanVar(value=True)
        self.sign_path = tk.StringVar()
        self.sign_remove_bg = tk.BooleanVar(value=True)
        self.sign_enabled = tk.BooleanVar(value=True)
        self.status = tk.StringVar(value="")

        self.setup_style()
        self.load_config()
        self.build_ui()
        self.refresh_logo_thumb()
        self.refresh_sign_thumb()

    # ----- style -----
    def setup_style(self):
        s = ttk.Style()
        s.theme_use("clam")
        s.configure("TFrame", background=CARD)
        s.configure("TEntry", padding=6, fieldbackground="#F9FAFB", bordercolor=BORDER,
                    lightcolor=BORDER, darkcolor=BORDER)
        s.map("TEntry", bordercolor=[("focus", ACCENT)], lightcolor=[("focus", ACCENT)],
              darkcolor=[("focus", ACCENT)])
        s.configure("TButton", font=(FONT, 10), padding=6, background="#EEF0F6",
                    foreground=TEXT, borderwidth=0)
        s.map("TButton", background=[("active", "#E0E3EE")])
        s.configure("Accent.TButton", font=(FONT, 11, "bold"), background=ACCENT,
                    foreground="white", borderwidth=0)
        s.map("Accent.TButton", background=[("active", ACCENT_DARK)])
        s.configure("Horizontal.TScale", background=CARD)
        s.configure("TCheckbutton", background=CARD, foreground=TEXT, font=(FONT, 9))
        s.map("TCheckbutton", background=[("active", CARD)])
        s.configure("TRadiobutton", background=CARD, foreground=TEXT, font=(FONT, 10))
        s.map("TRadiobutton", background=[("active", CARD)])

    # ----- config -----
    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self.upi_id.set(data.get("upi_id", ""))
                self.merchant_name.set(data.get("merchant_name", ""))
                self.logo_path.set(data.get("logo_path", ""))
                self.sign_path.set(data.get("sign_path", ""))
                self.sign_remove_bg.set(bool(data.get("sign_remove_bg", True)))
            except Exception:
                pass

    def save_config(self, silent=False):
        data = {
            "upi_id": self.upi_id.get().strip(),
            "merchant_name": self.merchant_name.get().strip(),
            "logo_path": self.logo_path.get().strip(),
            "sign_path": self.sign_path.get().strip(),
            "sign_remove_bg": bool(self.sign_remove_bg.get()),
        }
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        if not silent:
            self.set_status("Profile saved ✓")

    def set_status(self, msg):
        self.status.set(msg)
        self.root.after(3500, lambda: self.status.set(""))

    # ----- UI -----
    def card(self, parent, title):
        wrap = tk.Frame(parent, bg=CARD, highlightthickness=1, highlightbackground=BORDER)
        wrap.pack(fill="x", padx=20, pady=(0, 10))
        inner = tk.Frame(wrap, bg=CARD, padx=18, pady=10)
        inner.pack(fill="x")
        tk.Label(inner, text=title, font=(FONT, 11, "bold"), bg=CARD, fg=TEXT).grid(
            row=0, column=0, columnspan=3, sticky="w", pady=(0, 10))
        inner.columnconfigure(1, weight=1)
        return inner

    def field_label(self, parent, text, row):
        tk.Label(parent, text=text, font=(FONT, 9), bg=CARD, fg=MUTED).grid(
            row=row, column=0, sticky="w", padx=(0, 12), pady=5)

    def build_ui(self):
        header = tk.Frame(self.root, bg=ACCENT, height=72)
        header.pack(fill="x", pady=(0, 14))
        header.pack_propagate(False)
        tk.Label(header, text="UPI Invoice QR", font=(FONT, 18, "bold"),
                 bg=ACCENT, fg="white").pack(anchor="w", padx=22, pady=(12, 0))
        tk.Label(header, text="Stamp a payment QR on any invoice PDF",
                 font=(FONT, 9), bg=ACCENT, fg="#C7D2FE").pack(anchor="w", padx=22)

        # Footer credit (shown in the app only, not stamped on the PDF)
        tk.Label(self.root, text="Made & Designed by Jashandeep Singh", font=(FONT, 9, "bold"),
                 bg=BG, fg=MUTED).pack(side="bottom", pady=(4, 12))

        # --- Profile card ---
        p = self.card(self.root, "Merchant profile")
        self.field_label(p, "UPI ID", 1)
        ttk.Entry(p, textvariable=self.upi_id).grid(row=1, column=1, columnspan=2, sticky="we")
        self.field_label(p, "Merchant name", 2)
        ttk.Entry(p, textvariable=self.merchant_name).grid(row=2, column=1, columnspan=2, sticky="we")
        self.field_label(p, "Center logo", 3)
        self.logo_thumb = tk.Label(p, bg=CARD, text="none", fg=MUTED, font=(FONT, 9))
        self.logo_thumb.grid(row=3, column=1, sticky="w", pady=5)
        ttk.Button(p, text="Browse…", command=self.browse_logo).grid(row=3, column=2, sticky="e")
        ttk.Button(p, text="Save", width=7, command=self.save_config).grid(row=0, column=2, sticky="e")

        # --- Signature card ---
        g = self.card(self.root, "Signature (optional)")
        box = tk.Frame(g, width=260, height=66, bg="#F9FAFB",
                       highlightthickness=1, highlightbackground=BORDER)
        box.grid(row=1, column=0, columnspan=2, sticky="w")
        box.pack_propagate(False)
        self.sign_thumb = tk.Label(box, bg="#F9FAFB", fg=MUTED, font=(FONT, 9), text="No signature added")
        self.sign_thumb.pack(expand=True)
        btns = tk.Frame(g, bg=CARD)
        btns.grid(row=1, column=2, sticky="e")
        ttk.Button(btns, text="Browse…", command=self.browse_sign).pack(fill="x")
        ttk.Button(btns, text="Clear", command=self.clear_sign).pack(fill="x", pady=(6, 0))
        checks = tk.Frame(g, bg=CARD)
        checks.grid(row=2, column=0, columnspan=3, sticky="w", pady=(8, 0))
        ttk.Checkbutton(checks, text="Remove paper background", variable=self.sign_remove_bg,
                        command=self.refresh_sign_thumb).pack(side="left")
        ttk.Checkbutton(checks, text="Add to this invoice",
                        variable=self.sign_enabled).pack(side="left", padx=(16, 0))

        # --- Invoice card ---
        i = self.card(self.root, "New invoice")
        self.field_label(i, "Amount (₹)", 1)
        amount_entry = ttk.Entry(i, textvariable=self.amount, font=(FONT, 13))
        amount_entry.grid(row=1, column=1, columnspan=2, sticky="we")
        tk.Label(i, text="Optional. Leave empty and the customer enters the amount while paying.",
                 font=(FONT, 8), bg=CARD, fg=MUTED, wraplength=330, justify="left").grid(
            row=2, column=1, columnspan=2, sticky="w", pady=(0, 4))
        self.field_label(i, "Note (optional)", 3)
        ttk.Entry(i, textvariable=self.note).grid(row=3, column=1, columnspan=2, sticky="we")
        ttk.Checkbutton(i, text="Add \"Scan & Pay\" caption below the QR",
                        variable=self.show_caption).grid(row=4, column=0, columnspan=3,
                                                         sticky="w", pady=(10, 0))
        ttk.Button(i, text="Choose PDF & place QR  →", style="Accent.TButton",
                   command=self.start_placement).grid(row=5, column=0, columnspan=3,
                                                      sticky="we", pady=(12, 0), ipady=6)
        amount_entry.focus()
        self.root.bind("<Return>", lambda _e: self.start_placement())

        tk.Label(self.root, textvariable=self.status, bg=BG, fg="#059669",
                 font=(FONT, 9, "bold")).pack(pady=(0, 4))

    # ----- logo -----
    def browse_logo(self):
        name = filedialog.askopenfilename(filetypes=[("Image files", "*.png *.jpg *.jpeg *.webp")])
        if name:
            try:  # keep a copy beside the app so the profile still works if the folder is moved
                dest = os.path.join(app_dir(), "upi_logo" + os.path.splitext(name)[1].lower())
                if os.path.abspath(name) != os.path.abspath(dest):
                    shutil.copy2(name, dest)
                name = os.path.basename(dest)
            except Exception:
                pass
            self.logo_path.set(name)
            self.refresh_logo_thumb()

    def refresh_logo_thumb(self):
        path = resolve_path(self.logo_path.get()) if self.logo_path.get() else ""
        if path and os.path.exists(path):
            try:
                img = Image.open(path).convert("RGBA")
                img.thumbnail((40, 40))
                self.tk_logo = ImageTk.PhotoImage(img)
                self.logo_thumb.config(image=self.tk_logo, text="")
                return
            except Exception:
                pass
        self.logo_thumb.config(image="", text="none")

    # ----- signature -----
    def browse_sign(self):
        name = filedialog.askopenfilename(
            title="Select signature image",
            filetypes=[("Image files", "*.png *.jpg *.jpeg *.webp *.bmp")])
        if not name:
            return
        try:  # keep a copy beside the app so it travels with the .exe
            dest = os.path.join(app_dir(), "upi_signature" + os.path.splitext(name)[1].lower())
            if os.path.abspath(name) != os.path.abspath(dest):
                shutil.copy2(name, dest)
            name = os.path.basename(dest)
        except Exception:
            pass
        self.sign_path.set(name)
        self.sign_enabled.set(True)
        self.refresh_sign_thumb()
        self.save_config(silent=True)

    def clear_sign(self):
        self.sign_path.set("")
        self.refresh_sign_thumb()
        self.save_config(silent=True)

    def refresh_sign_thumb(self):
        path = resolve_path(self.sign_path.get()) if self.sign_path.get() else ""
        if path and os.path.exists(path):
            try:
                img = build_sign_image(path, self.sign_remove_bg.get())
                img.thumbnail((250, 58), Image.Resampling.LANCZOS)
                bg = Image.new("RGBA", img.size, (249, 250, 251, 255))
                bg.alpha_composite(img)
                self.tk_sign = ImageTk.PhotoImage(bg)
                self.sign_thumb.config(image=self.tk_sign, text="")
                return
            except Exception:
                pass
        self.sign_thumb.config(image="", text="No signature added")

    # ----- flow -----
    def start_placement(self):
        upi = self.upi_id.get().strip()
        name = self.merchant_name.get().strip()
        if not UPI_REGEX.match(upi):
            messagebox.showerror("UPI ID", "Enter a valid UPI ID, e.g. name@bank")
            return
        if not name:
            messagebox.showerror("Merchant name", "Please enter the merchant name.")
            return
        raw_amount = self.amount.get().strip()
        amount = None  # optional: empty means the payer enters the amount themselves
        if raw_amount:
            amount = parse_amount(raw_amount)
            if amount is None:
                messagebox.showerror("Amount", "That amount doesn't look right. Enter a number, or leave it empty.")
                return

        pdf = filedialog.askopenfilename(title="Select invoice PDF", filetypes=[("PDF files", "*.pdf")])
        if not pdf:
            return

        try:
            self.save_config(silent=True)
            qr_img = build_qr_image(build_upi_string(upi, name, amount, self.note.get()),
                                    self.logo_path.get())
            if self.show_caption.get():
                qr_img = build_qr_card(qr_img, name, amount)
            sign_img = None
            if self.sign_path.get() and self.sign_enabled.get():
                sign_file = resolve_path(self.sign_path.get())
                if os.path.exists(sign_file):
                    sign_img = build_sign_image(sign_file, self.sign_remove_bg.get())
            PlacementWindow(self.root, pdf, qr_img, sign_img, self.on_saved)
        except Exception as e:
            messagebox.showerror("Error", f"Could not open the PDF or build the QR:\n{e}")

    def on_saved(self, path):
        self.amount.set("")
        self.note.set("")
        self.set_status("Invoice saved ✓")
        if messagebox.askyesno("Saved", "Invoice saved.\n\nOpen it now?"):
            try:
                if sys.platform.startswith("win"):
                    os.startfile(path)
                elif sys.platform == "darwin":
                    subprocess.run(["open", path])
                else:
                    subprocess.run(["xdg-open", path])
            except Exception:
                pass


if __name__ == "__main__":
    root = tk.Tk()
    UPIInvoiceApp(root)
    root.mainloop()
