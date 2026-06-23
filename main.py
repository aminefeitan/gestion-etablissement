import math
import os
import sqlite3
import tkinter as tk
import unicodedata
from datetime import datetime
from pathlib import Path
from tkinter import messagebox, ttk

import customtkinter as ctk

try:
    import matplotlib.pyplot as plt
    import numpy as np
except ModuleNotFoundError:
    plt = None
    np = None

try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import cm
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfgen import canvas
except ModuleNotFoundError:
    colors = None
    A4 = None
    cm = None
    ImageReader = None
    canvas = None

try:
    from tkcalendar import DateEntry
except ModuleNotFoundError:
    DateEntry = None

# ──────────────────────────────────────────────────────────────
# Paths & Constants
# ──────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "main.db"
SIGNATURE_PATH = BASE_DIR / "signature.jpg"

APP_TITLE = "Gestion des Étudiants"
PASSING_GRADE = 10
MIN_GRADE = 0
MAX_GRADE = 20

# ──────────────────────────────────────────────────────────────
# Dark-Mode Color Palette
# ──────────────────────────────────────────────────────────────
COLORS = {
    # Backgrounds
    "bg_primary": "#0f1117",
    "bg_secondary": "#1a1b2e",
    "bg_card": "#252742",
    "bg_input": "#1e2040",
    "bg_hover": "#2d2f54",
    "bg_sidebar": "#12131f",
    "bg_sidebar_active": "#1e2040",
    # Text
    "text_primary": "#e8eaf0",
    "text_secondary": "#8b8fa3",
    "text_muted": "#5c5f78",
    # Accents
    "accent": "#6c63ff",
    "accent_hover": "#5a52e0",
    "accent_glow": "#6c63ff30",
    "cyan": "#00d4aa",
    "cyan_dark": "#00b894",
    # Status
    "success": "#00d4aa",
    "success_bg": "#00d4aa18",
    "danger": "#ff6b6b",
    "danger_bg": "#ff6b6b18",
    "warning": "#ffd43b",
    "warning_bg": "#ffd43b18",
    "info": "#74b9ff",
    "info_bg": "#74b9ff18",
    # Borders
    "border": "#2d2f54",
    "border_light": "#3d3f64",
    # Table
    "table_header": "#1a1b2e",
    "table_row_alt": "#1e2040",
    "table_row": "#252742",
    "table_selected": "#6c63ff30",
}

# Icons (Unicode)
ICONS = {
    "dashboard": "📊",
    "students": "🎓",
    "branches": "🏛️",
    "subjects": "📚",
    "grades": "📝",
    "ranking": "🏆",
    "statistics": "📈",
    "reports": "📄",
    "search": "🔍",
    "add": "➕",
    "refresh": "🔄",
    "success": "✅",
    "error": "❌",
    "info": "ℹ️",
    "warning": "⚠️",
    "student_metric": "👥",
    "branch_metric": "🏛️",
    "subject_metric": "📖",
    "average_metric": "📊",
}


# ──────────────────────────────────────────────────────────────
# Toast Notification System
# ──────────────────────────────────────────────────────────────
class ToastNotification:
    """Animated in-app toast notification — replaces messagebox."""

    def __init__(self, parent):
        self.parent = parent
        self._current_toast = None
        self._after_id = None

    def show(self, message, kind="info", duration=3000):
        self._dismiss_current()

        color_map = {
            "success": (COLORS["success"], COLORS["success_bg"], ICONS["success"]),
            "error": (COLORS["danger"], COLORS["danger_bg"], ICONS["error"]),
            "info": (COLORS["info"], COLORS["info_bg"], ICONS["info"]),
            "warning": (COLORS["warning"], COLORS["warning_bg"], ICONS["warning"]),
        }
        fg, bg, icon = color_map.get(kind, color_map["info"])

        toast = tk.Frame(
            self.parent,
            bg=bg,
            highlightbackground=fg,
            highlightthickness=1,
            padx=18,
            pady=12,
        )

        tk.Label(
            toast,
            text=f"{icon}  {message}",
            bg=bg,
            fg=fg,
            font=("Segoe UI Semibold", 11),
            anchor="w",
        ).pack(side=tk.LEFT, fill=tk.X, expand=True)

        close_btn = tk.Label(
            toast,
            text="✕",
            bg=bg,
            fg=COLORS["text_muted"],
            font=("Segoe UI", 12),
            cursor="hand2",
        )
        close_btn.pack(side=tk.RIGHT, padx=(12, 0))
        close_btn.bind("<Button-1>", lambda _: self._dismiss_current())

        toast.place(relx=0.5, rely=0.0, anchor="n", y=-60)
        self._current_toast = toast

        # Animate in
        self._slide_in(toast, target_y=16, current_y=-60, step=8)
        self._after_id = self.parent.after(duration, self._dismiss_current)

    def _slide_in(self, widget, target_y, current_y, step):
        if current_y < target_y:
            current_y = min(current_y + step, target_y)
            try:
                widget.place_configure(y=current_y)
                self.parent.after(12, self._slide_in, widget, target_y, current_y, step)
            except tk.TclError:
                pass

    def _slide_out(self, widget, current_y, step):
        if current_y > -70:
            current_y -= step
            try:
                widget.place_configure(y=current_y)
                self.parent.after(10, self._slide_out, widget, current_y, step)
            except tk.TclError:
                pass
        else:
            try:
                widget.destroy()
            except tk.TclError:
                pass

    def _dismiss_current(self):
        if self._after_id:
            try:
                self.parent.after_cancel(self._after_id)
            except (tk.TclError, ValueError):
                pass
            self._after_id = None
        if self._current_toast:
            self._slide_out(self._current_toast, 16, 10)
            self._current_toast = None


# ──────────────────────────────────────────────────────────────
# Main Application
# ──────────────────────────────────────────────────────────────
class StudentManagerApp:
    # Navigation items: (key, icon, label)
    NAV_ITEMS = [
        ("dashboard", ICONS["dashboard"], "Tableau de bord"),
        ("students", ICONS["students"], "Étudiants"),
        ("branches", ICONS["branches"], "Branches"),
        ("subjects", ICONS["subjects"], "Matières"),
        ("grades", ICONS["grades"], "Notes"),
        ("ranking", ICONS["ranking"], "Classements"),
        ("statistics", ICONS["statistics"], "Statistiques"),
        ("reports", ICONS["reports"], "Relevés"),
    ]

    def __init__(self, root):
        self.root = root
        self.root.title(APP_TITLE)
        self.root.geometry("1140x760")
        self.root.minsize(1020, 660)
        self.root.configure(bg=COLORS["bg_primary"])

        # Database
        self.conn = sqlite3.connect(DB_PATH)
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.execute("PRAGMA journal_mode = WAL")
        self.conn.row_factory = sqlite3.Row

        # State
        self.inputs = {}
        self.metric_vars = {}
        self.pages = {}
        self.nav_buttons = {}
        self.current_page = None

        # Init
        self.create_tables()
        self.build_ui()
        self.toast = ToastNotification(self.content_area)
        self.update_combobox_values()
        self.navigate("dashboard")

        self.root.protocol("WM_DELETE_WINDOW", self.close)

    # ──────────────────────────────────────────────────────────
    # Database Setup
    # ──────────────────────────────────────────────────────────
    def create_tables(self):
        with self.conn:
            self.conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS branche (
                    code TEXT PRIMARY KEY,
                    nom  TEXT UNIQUE
                );
                CREATE TABLE IF NOT EXISTS etudiant (
                    code_massar    TEXT PRIMARY KEY,
                    nom_arabe      TEXT,
                    nom_francais   TEXT,
                    genre          TEXT,
                    lieu_naissance TEXT,
                    date_naissance DATE,
                    code_branche   TEXT,
                    FOREIGN KEY (code_branche) REFERENCES branche(code)
                );
                CREATE TABLE IF NOT EXISTS matiere (
                    code        TEXT PRIMARY KEY,
                    nom         TEXT UNIQUE,
                    coefficient REAL
                );
                CREATE TABLE IF NOT EXISTS note (
                    code_massar  TEXT,
                    code_matiere TEXT,
                    note         REAL,
                    FOREIGN KEY (code_massar)  REFERENCES etudiant(code_massar),
                    FOREIGN KEY (code_matiere) REFERENCES matiere(code)
                );
                CREATE INDEX IF NOT EXISTS idx_etudiant_branche ON etudiant(code_branche);
                CREATE INDEX IF NOT EXISTS idx_note_student     ON note(code_massar);
                CREATE INDEX IF NOT EXISTS idx_note_subject     ON note(code_matiere);
                """
            )

    # ──────────────────────────────────────────────────────────
    # UI Layout
    # ──────────────────────────────────────────────────────────
    def build_ui(self):
        # Main container
        main = tk.Frame(self.root, bg=COLORS["bg_primary"])
        main.pack(fill=tk.BOTH, expand=True)
        main.columnconfigure(1, weight=1)
        main.rowconfigure(0, weight=1)

        # Sidebar
        self.build_sidebar(main)

        # Content area
        self.content_area = tk.Frame(main, bg=COLORS["bg_primary"], padx=28, pady=22)
        self.content_area.grid(row=0, column=1, sticky="nsew")
        self.content_area.columnconfigure(0, weight=1)
        self.content_area.rowconfigure(0, weight=1)

        # Build all pages
        self.build_dashboard_page()
        self.build_student_page()
        self.build_branch_page()
        self.build_subject_page()
        self.build_grade_page()
        self.build_ranking_page()
        self.build_statistics_page()
        self.build_report_page()

    # ──────────────────────────────────────────────────────────
    # Sidebar
    # ──────────────────────────────────────────────────────────
    def build_sidebar(self, parent):
        sidebar = tk.Frame(parent, bg=COLORS["bg_sidebar"], width=230)
        sidebar.grid(row=0, column=0, sticky="ns")
        sidebar.grid_propagate(False)

        # App branding
        brand_frame = tk.Frame(sidebar, bg=COLORS["bg_sidebar"], pady=24, padx=20)
        brand_frame.pack(fill=tk.X)

        tk.Label(
            brand_frame,
            text="🎓",
            bg=COLORS["bg_sidebar"],
            fg=COLORS["accent"],
            font=("Segoe UI", 28),
        ).pack(anchor="w")
        tk.Label(
            brand_frame,
            text="Gestion des",
            bg=COLORS["bg_sidebar"],
            fg=COLORS["text_primary"],
            font=("Segoe UI Semibold", 14),
            anchor="w",
        ).pack(fill=tk.X, pady=(8, 0))
        tk.Label(
            brand_frame,
            text="Étudiants",
            bg=COLORS["bg_sidebar"],
            fg=COLORS["accent"],
            font=("Segoe UI Bold", 16),
            anchor="w",
        ).pack(fill=tk.X)

        # Separator
        tk.Frame(sidebar, bg=COLORS["border"], height=1).pack(fill=tk.X, padx=16, pady=(4, 12))

        # Navigation
        nav_frame = tk.Frame(sidebar, bg=COLORS["bg_sidebar"])
        nav_frame.pack(fill=tk.BOTH, expand=True, padx=10)

        for key, icon, label in self.NAV_ITEMS:
            btn = self._create_nav_button(nav_frame, key, icon, label)
            btn.pack(fill=tk.X, pady=2)

        # Bottom info
        tk.Frame(sidebar, bg=COLORS["border"], height=1).pack(fill=tk.X, padx=16, pady=(8, 12))
        tk.Label(
            sidebar,
            text=f"📁 {DB_PATH.name}",
            bg=COLORS["bg_sidebar"],
            fg=COLORS["text_muted"],
            font=("Segoe UI", 9),
            anchor="w",
            padx=20,
        ).pack(fill=tk.X, pady=(0, 6))

        # Refresh button at bottom
        refresh_frame = tk.Frame(sidebar, bg=COLORS["bg_sidebar"], padx=16, pady=12)
        refresh_frame.pack(fill=tk.X, side=tk.BOTTOM)
        refresh_btn = tk.Label(
            refresh_frame,
            text=f"{ICONS['refresh']}  Actualiser",
            bg=COLORS["bg_sidebar"],
            fg=COLORS["text_secondary"],
            font=("Segoe UI", 10),
            cursor="hand2",
            padx=14,
            pady=8,
        )
        refresh_btn.pack(fill=tk.X)
        refresh_btn.bind("<Button-1>", lambda _: self.refresh_all())
        refresh_btn.bind("<Enter>", lambda e: e.widget.configure(fg=COLORS["accent"]))
        refresh_btn.bind("<Leave>", lambda e: e.widget.configure(fg=COLORS["text_secondary"]))

    def _create_nav_button(self, parent, key, icon, label):
        btn = tk.Frame(parent, bg=COLORS["bg_sidebar"], cursor="hand2", padx=14, pady=10)

        text_label = tk.Label(
            btn,
            text=f"{icon}   {label}",
            bg=COLORS["bg_sidebar"],
            fg=COLORS["text_secondary"],
            font=("Segoe UI", 11),
            anchor="w",
        )
        text_label.pack(fill=tk.X)

        # Active indicator
        indicator = tk.Frame(btn, bg=COLORS["bg_sidebar"], width=3, height=0)
        indicator.place(x=0, rely=0.15, relheight=0.7)

        self.nav_buttons[key] = {"frame": btn, "label": text_label, "indicator": indicator}

        for widget in (btn, text_label):
            widget.bind("<Button-1>", lambda _, k=key: self.navigate(k))
            widget.bind(
                "<Enter>",
                lambda e, k=key: self._on_nav_hover(k, True),
            )
            widget.bind(
                "<Leave>",
                lambda e, k=key: self._on_nav_hover(k, False),
            )

        return btn

    def _on_nav_hover(self, key, entering):
        if key == self.current_page:
            return
        nav = self.nav_buttons[key]
        if entering:
            nav["frame"].configure(bg=COLORS["bg_hover"])
            nav["label"].configure(bg=COLORS["bg_hover"], fg=COLORS["text_primary"])
        else:
            nav["frame"].configure(bg=COLORS["bg_sidebar"])
            nav["label"].configure(bg=COLORS["bg_sidebar"], fg=COLORS["text_secondary"])

    def navigate(self, page_key):
        # Deactivate current
        if self.current_page and self.current_page in self.nav_buttons:
            prev = self.nav_buttons[self.current_page]
            prev["frame"].configure(bg=COLORS["bg_sidebar"])
            prev["label"].configure(bg=COLORS["bg_sidebar"], fg=COLORS["text_secondary"])
            prev["indicator"].configure(bg=COLORS["bg_sidebar"])

        # Activate new
        self.current_page = page_key
        nav = self.nav_buttons[page_key]
        nav["frame"].configure(bg=COLORS["bg_sidebar_active"])
        nav["label"].configure(bg=COLORS["bg_sidebar_active"], fg=COLORS["accent"])
        nav["indicator"].configure(bg=COLORS["accent"])

        # Show page
        for key, frame in self.pages.items():
            if key == page_key:
                frame.grid(row=0, column=0, sticky="nsew")
            else:
                frame.grid_forget()

        # Refresh data for specific pages
        if page_key == "dashboard":
            self.refresh_dashboard()

    # ──────────────────────────────────────────────────────────
    # Page Helpers
    # ──────────────────────────────────────────────────────────
    def _create_page(self, key):
        page = tk.Frame(self.content_area, bg=COLORS["bg_primary"])
        page.columnconfigure(0, weight=1)
        self.pages[key] = page
        return page

    def _page_title(self, parent, title, subtitle="", row=0):
        frame = tk.Frame(parent, bg=COLORS["bg_primary"])
        frame.grid(row=row, column=0, sticky="ew", pady=(0, 20))
        tk.Label(
            frame,
            text=title,
            bg=COLORS["bg_primary"],
            fg=COLORS["text_primary"],
            font=("Segoe UI Bold", 22),
            anchor="w",
        ).pack(fill=tk.X)
        if subtitle:
            tk.Label(
                frame,
                text=subtitle,
                bg=COLORS["bg_primary"],
                fg=COLORS["text_secondary"],
                font=("Segoe UI", 11),
                anchor="w",
            ).pack(fill=tk.X, pady=(4, 0))

    def _card(self, parent, row=0, column=0, colspan=1, padx=(0, 0), pady=(0, 0), sticky="nsew"):
        card = tk.Frame(
            parent,
            bg=COLORS["bg_card"],
            highlightbackground=COLORS["border"],
            highlightthickness=1,
            padx=20,
            pady=18,
        )
        card.grid(row=row, column=column, columnspan=colspan, padx=padx, pady=pady, sticky=sticky)
        return card

    def _section_label(self, parent, text, row=0, pady=(0, 12)):
        tk.Label(
            parent,
            text=text,
            bg=COLORS["bg_card"],
            fg=COLORS["accent"],
            font=("Segoe UI Semibold", 13),
            anchor="w",
        ).grid(row=row, column=0, columnspan=2, sticky="w", pady=pady)

    def _form_label(self, parent, text, row):
        tk.Label(
            parent,
            text=text,
            bg=COLORS["bg_card"],
            fg=COLORS["text_secondary"],
            font=("Segoe UI", 10),
            anchor="w",
        ).grid(row=row, column=0, sticky="w", padx=(0, 16), pady=7)

    def _form_entry(self, parent, key, label, row, placeholder=""):
        self._form_label(parent, label, row)
        entry = ctk.CTkEntry(
            parent,
            fg_color=COLORS["bg_input"],
            border_color=COLORS["border"],
            text_color=COLORS["text_primary"],
            placeholder_text=placeholder,
            placeholder_text_color=COLORS["text_muted"],
            corner_radius=8,
            height=38,
            font=("Segoe UI", 11),
        )
        entry.grid(row=row, column=1, sticky="ew", pady=7)
        self.inputs[key] = entry
        return entry

    def _form_combobox(self, parent, key, label, row, values=()):
        self._form_label(parent, label, row)
        combo = ctk.CTkComboBox(
            parent,
            values=list(values),
            fg_color=COLORS["bg_input"],
            border_color=COLORS["border"],
            button_color=COLORS["accent"],
            button_hover_color=COLORS["accent_hover"],
            dropdown_fg_color=COLORS["bg_card"],
            dropdown_hover_color=COLORS["bg_hover"],
            dropdown_text_color=COLORS["text_primary"],
            text_color=COLORS["text_primary"],
            corner_radius=8,
            height=38,
            font=("Segoe UI", 11),
            state="readonly",
        )
        combo.grid(row=row, column=1, sticky="ew", pady=7)
        combo.set("")
        self.inputs[key] = combo
        return combo

    def _accent_button(self, parent, text, command, row=None, column=None, sticky="e", pady=(18, 0), padx=(0, 0), colspan=1):
        btn = ctk.CTkButton(
            parent,
            text=text,
            command=command,
            fg_color=COLORS["accent"],
            hover_color=COLORS["accent_hover"],
            text_color="#ffffff",
            corner_radius=8,
            height=40,
            font=("Segoe UI Semibold", 11),
        )
        if row is not None:
            btn.grid(row=row, column=column or 0, columnspan=colspan, sticky=sticky, pady=pady, padx=padx)
        return btn

    def _secondary_button(self, parent, text, command, row=None, column=None, sticky="e", pady=(0, 0), padx=(0, 0)):
        btn = ctk.CTkButton(
            parent,
            text=text,
            command=command,
            fg_color=COLORS["bg_hover"],
            hover_color=COLORS["border_light"],
            text_color=COLORS["text_primary"],
            corner_radius=8,
            height=38,
            font=("Segoe UI", 11),
        )
        if row is not None:
            btn.grid(row=row, column=column or 0, sticky=sticky, pady=pady, padx=padx)
        return btn

    def _build_treeview(self, parent, columns, headings, widths, row=0, height=10):
        """Build a styled Treeview with scrollbar."""
        container = tk.Frame(parent, bg=COLORS["bg_card"])
        container.grid(row=row, column=0, columnspan=len(columns), sticky="nsew", pady=(10, 0))
        container.rowconfigure(0, weight=1)
        container.columnconfigure(0, weight=1)

        style = ttk.Style()
        style.theme_use("clam")
        style.configure(
            "Dark.Treeview",
            background=COLORS["bg_card"],
            foreground=COLORS["text_primary"],
            fieldbackground=COLORS["bg_card"],
            bordercolor=COLORS["border"],
            rowheight=34,
            font=("Segoe UI", 10),
        )
        style.configure(
            "Dark.Treeview.Heading",
            background=COLORS["table_header"],
            foreground=COLORS["text_secondary"],
            bordercolor=COLORS["border"],
            font=("Segoe UI Semibold", 10),
            relief="flat",
        )
        style.map(
            "Dark.Treeview",
            background=[("selected", COLORS["table_selected"])],
            foreground=[("selected", COLORS["accent"])],
        )
        style.map(
            "Dark.Treeview.Heading",
            background=[("active", COLORS["bg_hover"])],
        )

        tree = ttk.Treeview(container, columns=columns, show="headings", height=height, style="Dark.Treeview")
        for col, heading, width in zip(columns, headings, widths):
            tree.heading(col, text=heading)
            tree.column(col, width=width, anchor="center" if width < 130 else "w")

        tree.tag_configure("oddrow", background=COLORS["table_row_alt"])
        tree.tag_configure("evenrow", background=COLORS["table_row"])
        tree.tag_configure("success", foreground=COLORS["success"])
        tree.tag_configure("danger", foreground=COLORS["danger"])

        tree.grid(row=0, column=0, sticky="nsew")

        scrollbar = ttk.Scrollbar(container, orient=tk.VERTICAL, command=tree.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        tree.configure(yscrollcommand=scrollbar.set)

        return tree

    # ──────────────────────────────────────────────────────────
    # Dashboard
    # ──────────────────────────────────────────────────────────
    def build_dashboard_page(self):
        page = self._create_page("dashboard")
        page.rowconfigure(2, weight=1)

        self._page_title(page, "Tableau de bord", "Vue d'ensemble de votre établissement")

        # Metric cards
        metrics_frame = tk.Frame(page, bg=COLORS["bg_primary"])
        metrics_frame.grid(row=1, column=0, sticky="ew", pady=(0, 18))
        for i in range(4):
            metrics_frame.columnconfigure(i, weight=1, uniform="metrics")

        metrics = [
            ("students_count", ICONS["student_metric"], "Étudiants", COLORS["accent"]),
            ("branches_count", ICONS["branch_metric"], "Branches", COLORS["cyan"]),
            ("subjects_count", ICONS["subject_metric"], "Matières", COLORS["warning"]),
            ("global_average", ICONS["average_metric"], "Moyenne Générale", COLORS["success"]),
        ]

        for col, (key, icon, label, color) in enumerate(metrics):
            card = tk.Frame(
                metrics_frame,
                bg=COLORS["bg_card"],
                highlightbackground=COLORS["border"],
                highlightthickness=1,
                padx=20,
                pady=16,
            )
            card.grid(row=0, column=col, sticky="ew", padx=(0 if col == 0 else 8, 8 if col < 3 else 0))

            # Colored top border accent
            accent_bar = tk.Frame(card, bg=color, height=3)
            accent_bar.pack(fill=tk.X, pady=(0, 12))

            top = tk.Frame(card, bg=COLORS["bg_card"])
            top.pack(fill=tk.X)

            tk.Label(
                top,
                text=icon,
                bg=COLORS["bg_card"],
                font=("Segoe UI", 22),
                anchor="w",
            ).pack(side=tk.LEFT)

            self.metric_vars[key] = tk.StringVar(value="0")
            tk.Label(
                top,
                textvariable=self.metric_vars[key],
                bg=COLORS["bg_card"],
                fg=color,
                font=("Segoe UI Bold", 24),
                anchor="e",
            ).pack(side=tk.RIGHT)

            tk.Label(
                card,
                text=label,
                bg=COLORS["bg_card"],
                fg=COLORS["text_secondary"],
                font=("Segoe UI", 10),
                anchor="w",
            ).pack(fill=tk.X, pady=(8, 0))

        # Recent students table
        table_card = self._card(page, row=2, column=0, pady=(0, 0))
        table_card.columnconfigure(0, weight=1)
        table_card.rowconfigure(1, weight=1)

        self._section_label(table_card, "📋  Derniers étudiants inscrits")

        columns = ("code", "nom", "branche", "genre")
        headings = ("Code Massar", "Nom français", "Branche", "Genre")
        widths = (150, 250, 220, 100)
        self.recent_tree = self._build_treeview(table_card, columns, headings, widths, row=1, height=9)

    # ──────────────────────────────────────────────────────────
    # Students Page
    # ──────────────────────────────────────────────────────────
    def build_student_page(self):
        page = self._create_page("students")
        self._page_title(page, "Étudiants", "Ajouter et gérer les étudiants")

        card = self._card(page, row=1)
        card.columnconfigure(1, weight=1)

        self._section_label(card, f"{ICONS['add']}  Ajouter un étudiant", row=0)
        self._form_entry(card, "student_code", "Code Massar", 1, placeholder="Ex: M130099095")
        self._form_entry(card, "student_ar_name", "Nom arabe", 2, placeholder="الاسم بالعربية")
        self._form_entry(card, "student_fr_name", "Nom français", 3, placeholder="Nom et prénom")
        self._form_combobox(card, "student_gender", "Genre", 4, values=("Homme", "Femme"))
        self._form_entry(card, "student_birthplace", "Lieu de naissance", 5, placeholder="Ville")

        # Date de naissance
        self._form_label(card, "Date de naissance", 6)
        if DateEntry:
            birth_date = DateEntry(card, date_pattern="yyyy-mm-dd", width=18)
        else:
            birth_date = ctk.CTkEntry(
                card,
                fg_color=COLORS["bg_input"],
                border_color=COLORS["border"],
                text_color=COLORS["text_primary"],
                placeholder_text="AAAA-MM-JJ",
                placeholder_text_color=COLORS["text_muted"],
                corner_radius=8,
                height=38,
                font=("Segoe UI", 11),
            )
            birth_date.insert(0, datetime.now().strftime("%Y-%m-%d"))
        birth_date.grid(row=6, column=1, sticky="ew", pady=7)
        self.inputs["student_birth_date"] = birth_date

        self._form_combobox(card, "student_branch", "Branche", 7)
        self._accent_button(card, f"{ICONS['add']}  Ajouter l'étudiant", self.submit_student, row=8, column=0, colspan=2, pady=(20, 4))

    # ──────────────────────────────────────────────────────────
    # Branches Page
    # ──────────────────────────────────────────────────────────
    def build_branch_page(self):
        page = self._create_page("branches")
        self._page_title(page, "Branches", "Gérer les filières d'études")

        card = self._card(page, row=1)
        card.columnconfigure(1, weight=1)

        self._section_label(card, f"{ICONS['add']}  Ajouter une branche", row=0)
        self._form_entry(card, "branch_name", "Nom de la branche", 1, placeholder="Ex: Sciences Mathématiques")
        self._accent_button(card, f"{ICONS['add']}  Ajouter la branche", self.submit_branch, row=2, column=0, colspan=2, pady=(20, 4))

    # ──────────────────────────────────────────────────────────
    # Subjects Page
    # ──────────────────────────────────────────────────────────
    def build_subject_page(self):
        page = self._create_page("subjects")
        self._page_title(page, "Matières", "Gérer les matières et coefficients")

        card = self._card(page, row=1)
        card.columnconfigure(1, weight=1)

        self._section_label(card, f"{ICONS['add']}  Ajouter une matière", row=0)
        self._form_entry(card, "subject_name", "Nom de la matière", 1, placeholder="Ex: Mathématiques")
        self._form_entry(card, "subject_coefficient", "Coefficient", 2, placeholder="Ex: 4")
        self._accent_button(card, f"{ICONS['add']}  Ajouter la matière", self.submit_subject, row=3, column=0, colspan=2, pady=(20, 4))

    # ──────────────────────────────────────────────────────────
    # Grades Page
    # ──────────────────────────────────────────────────────────
    def build_grade_page(self):
        page = self._create_page("grades")
        self._page_title(page, "Notes", "Saisir et modifier les notes")

        card = self._card(page, row=1)
        card.columnconfigure(1, weight=1)

        self._section_label(card, f"{ICONS['add']}  Ajouter ou remplacer une note", row=0)
        self._form_combobox(card, "grade_student", "Code Massar", 1)
        self._form_combobox(card, "grade_subject", "Matière", 2)
        self._form_entry(card, "grade_value", "Note / 20", 3, placeholder="Entre 0 et 20")
        self._accent_button(card, "💾  Enregistrer la note", self.submit_grade, row=4, column=0, colspan=2, pady=(20, 4))

    # ──────────────────────────────────────────────────────────
    # Ranking Page
    # ──────────────────────────────────────────────────────────
    def build_ranking_page(self):
        page = self._create_page("ranking")
        page.rowconfigure(2, weight=1)
        self._page_title(page, "Classements", "Classement des étudiants par branche")

        # Controls
        controls = self._card(page, row=1, pady=(0, 14))
        controls.columnconfigure(1, weight=1)

        tk.Label(
            controls,
            text="Branche",
            bg=COLORS["bg_card"],
            fg=COLORS["text_secondary"],
            font=("Segoe UI", 10),
            anchor="w",
        ).grid(row=0, column=0, sticky="w", padx=(0, 16))

        self._form_combobox(controls, "ranking_branch", "", 0)
        # Fix: remove the label that _form_combobox added
        for widget in controls.grid_slaves(row=0, column=0):
            if isinstance(widget, tk.Label) and widget.cget("text") == "":
                widget.destroy()
                break

        tk.Label(
            controls,
            text="Branche",
            bg=COLORS["bg_card"],
            fg=COLORS["text_secondary"],
            font=("Segoe UI", 10),
        ).grid(row=0, column=0, sticky="w", padx=(0, 16))

        self._accent_button(controls, f"{ICONS['search']}  Afficher", self.show_student_by_branch, row=0, column=2, pady=(0, 0), padx=(12, 0))

        # Table
        table_card = self._card(page, row=2, pady=(0, 0))
        table_card.columnconfigure(0, weight=1)
        table_card.rowconfigure(0, weight=1)

        columns = ("rank", "code", "arabic", "french", "average", "status")
        headings = ("Rang", "Code Massar", "Nom arabe", "Nom français", "Moyenne", "Validation")
        widths = (70, 150, 170, 220, 100, 120)
        self.ranking_tree = self._build_treeview(table_card, columns, headings, widths, height=12)

    # ──────────────────────────────────────────────────────────
    # Statistics Page
    # ──────────────────────────────────────────────────────────
    def build_statistics_page(self):
        page = self._create_page("statistics")
        page.rowconfigure(2, weight=1)
        self._page_title(page, "Statistiques", "Analyse des performances par branche")

        # Controls
        controls = self._card(page, row=1, pady=(0, 14))
        controls.columnconfigure(1, weight=1)

        self._form_combobox(controls, "stats_branch", "Branche", 0)

        btn_frame = tk.Frame(controls, bg=COLORS["bg_card"])
        btn_frame.grid(row=0, column=2, padx=(12, 0))

        self._accent_button(btn_frame, "📊  Statistiques", self.calculate_branch_statistics).pack(side=tk.LEFT, padx=(0, 8))
        self._secondary_button(btn_frame, "📈  Courbe de Gauss", self.plot_gaussian_curve).pack(side=tk.LEFT, padx=(0, 8))
        self._secondary_button(btn_frame, "📉  Graphiques", self.show_validation_graphs).pack(side=tk.LEFT)

        # Result
        result_card = self._card(page, row=2, pady=(0, 0))
        result_card.columnconfigure(0, weight=1)
        result_card.rowconfigure(0, weight=1)

        self.stats_text = tk.Text(
            result_card,
            wrap="word",
            bg=COLORS["bg_input"],
            fg=COLORS["text_primary"],
            relief="flat",
            padx=16,
            pady=16,
            font=("Consolas", 11),
            insertbackground=COLORS["text_primary"],
            selectbackground=COLORS["accent"],
            selectforeground="#ffffff",
            borderwidth=0,
            highlightthickness=1,
            highlightbackground=COLORS["border"],
        )
        self.stats_text.grid(row=0, column=0, sticky="nsew")
        self.stats_text.configure(state="disabled")

    # ──────────────────────────────────────────────────────────
    # Reports Page
    # ──────────────────────────────────────────────────────────
    def build_report_page(self):
        page = self._create_page("reports")
        self._page_title(page, "Relevés de Notes", "Générer un relevé PDF pour un étudiant")

        card = self._card(page, row=1)
        card.columnconfigure(1, weight=1)

        self._section_label(card, "📄  Générer un relevé de notes", row=0)
        self._form_combobox(card, "report_student", "Code Massar", 1)
        self._accent_button(card, "📄  Créer le PDF", self.print_grade_report, row=2, column=0, colspan=2, pady=(20, 4))

    # ──────────────────────────────────────────────────────────
    # Form Submissions
    # ──────────────────────────────────────────────────────────
    def value(self, key):
        widget = self.inputs[key]
        if isinstance(widget, ctk.CTkComboBox):
            return widget.get().strip()
        elif isinstance(widget, ctk.CTkEntry):
            return widget.get().strip()
        elif hasattr(widget, "get"):
            return widget.get().strip()
        return ""

    def clear_inputs(self, *keys):
        for key in keys:
            widget = self.inputs[key]
            if isinstance(widget, ctk.CTkComboBox):
                widget.set("")
            elif isinstance(widget, ctk.CTkEntry):
                widget.delete(0, tk.END)
            elif isinstance(widget, ttk.Combobox):
                widget.set("")
            elif hasattr(widget, "delete"):
                widget.delete(0, tk.END)

    def submit_student(self):
        code_massar = self.value("student_code").upper()
        nom_arabe = self.value("student_ar_name")
        nom_francais = self.value("student_fr_name")
        genre = self.value("student_gender")
        lieu_naissance = self.value("student_birthplace")
        date_naissance = self.value("student_birth_date")
        nom_branche = self.value("student_branch")

        if not all((code_massar, nom_arabe, nom_francais, genre, lieu_naissance, date_naissance, nom_branche)):
            self.show_error("Veuillez remplir tous les champs.")
            return

        try:
            datetime.strptime(date_naissance, "%Y-%m-%d")
        except ValueError:
            self.show_error("La date de naissance doit respecter le format AAAA-MM-JJ.")
            return

        code_branche = self.get_branch_code(nom_branche)
        if not code_branche:
            self.show_error("La branche sélectionnée n'existe pas.")
            return

        try:
            with self.conn:
                self.conn.execute(
                    """
                    INSERT INTO etudiant (
                        code_massar, nom_arabe, nom_francais, genre,
                        lieu_naissance, date_naissance, code_branche
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (code_massar, nom_arabe, nom_francais, genre, lieu_naissance, date_naissance, code_branche),
                )
        except sqlite3.IntegrityError:
            self.show_error("Ce code Massar existe déjà.")
            return

        self.show_success("Étudiant ajouté avec succès.")
        self.clear_inputs("student_code", "student_ar_name", "student_fr_name", "student_gender", "student_birthplace", "student_branch")
        self.refresh_all()

    def submit_branch(self):
        nom_branche = self.value("branch_name")
        if not nom_branche:
            self.show_error("Veuillez entrer le nom de la branche.")
            return

        code_branche = self.generate_unique_code(nom_branche, "branche")
        try:
            with self.conn:
                self.conn.execute("INSERT INTO branche (code, nom) VALUES (?, ?)", (code_branche, nom_branche))
        except sqlite3.IntegrityError:
            self.show_error("Cette branche existe déjà.")
            return

        self.show_success(f"Branche ajoutée avec le code {code_branche}.")
        self.clear_inputs("branch_name")
        self.refresh_all()

    def submit_subject(self):
        nom_matiere = self.value("subject_name")
        coefficient_text = self.value("subject_coefficient")

        if not nom_matiere or not coefficient_text:
            self.show_error("Veuillez remplir tous les champs.")
            return

        coefficient = self.parse_float(coefficient_text, "Le coefficient doit être un nombre.")
        if coefficient is None:
            return
        if coefficient <= 0:
            self.show_error("Le coefficient doit être supérieur à 0.")
            return

        code_matiere = self.generate_unique_code(nom_matiere, "matiere")
        try:
            with self.conn:
                self.conn.execute(
                    "INSERT INTO matiere (code, nom, coefficient) VALUES (?, ?, ?)",
                    (code_matiere, nom_matiere, coefficient),
                )
        except sqlite3.IntegrityError:
            self.show_error("Cette matière existe déjà.")
            return

        self.show_success(f"Matière ajoutée avec le code {code_matiere}.")
        self.clear_inputs("subject_name", "subject_coefficient")
        self.refresh_all()

    def submit_grade(self):
        code_massar = self.value("grade_student")
        nom_matiere = self.value("grade_subject")
        note_text = self.value("grade_value")

        if not code_massar or not nom_matiere or not note_text:
            self.show_error("Veuillez remplir tous les champs.")
            return

        note = self.parse_float(note_text, "La note doit être un nombre.")
        if note is None:
            return
        if not MIN_GRADE <= note <= MAX_GRADE:
            self.show_error(f"La note doit être comprise entre {MIN_GRADE} et {MAX_GRADE}.")
            return

        code_matiere = self.get_subject_code(nom_matiere)
        if not code_matiere:
            self.show_error("La matière sélectionnée n'existe pas.")
            return

        existing = self.conn.execute(
            "SELECT COUNT(*) FROM note WHERE code_massar = ? AND code_matiere = ?",
            (code_massar, code_matiere),
        ).fetchone()[0]
        if existing and not messagebox.askyesno("Note existante", "Une note existe déjà pour cette matière. Voulez-vous la remplacer ?"):
            return

        with self.conn:
            self.conn.execute("DELETE FROM note WHERE code_massar = ? AND code_matiere = ?", (code_massar, code_matiere))
            self.conn.execute(
                "INSERT INTO note (code_massar, code_matiere, note) VALUES (?, ?, ?)",
                (code_massar, code_matiere, note),
            )

        self.show_success("Note enregistrée avec succès.")
        self.clear_inputs("grade_value")
        self.refresh_all()

    # ──────────────────────────────────────────────────────────
    # Rankings & Statistics
    # ──────────────────────────────────────────────────────────
    def show_student_by_branch(self):
        selected_branch = self.value("ranking_branch")
        if not selected_branch:
            self.show_error("Veuillez sélectionner une branche.")
            return

        code_branche = self.get_branch_code(selected_branch)
        students = self.fetch_branch_ranking(code_branche)

        self.ranking_tree.delete(*self.ranking_tree.get_children())
        if not students:
            self.show_info("Aucun étudiant avec notes trouvé pour cette branche.")
            return

        for i, row in enumerate(students):
            status = "Validé" if row["average"] >= PASSING_GRADE else "Rattrapage"
            tag = "success" if row["average"] >= PASSING_GRADE else "danger"
            row_tag = "oddrow" if i % 2 else "evenrow"
            self.ranking_tree.insert(
                "",
                tk.END,
                values=(row["rank"], row["code"], row["arabic_name"], row["french_name"], f"{row['average']:.2f}", status),
                tags=(tag, row_tag),
            )

    def calculate_branch_statistics(self):
        selected_branch = self.value("stats_branch")
        if not selected_branch:
            self.show_error("Veuillez sélectionner une branche.")
            return

        code_branche = self.get_branch_code(selected_branch)
        averages = [row["average"] for row in self.fetch_branch_averages(code_branche)]
        if not averages:
            self.set_stats_text("Aucun étudiant avec notes trouvé pour cette branche.")
            return

        average = sum(averages) / len(averages)
        variance = sum((value - average) ** 2 for value in averages) / len(averages)
        std_dev = math.sqrt(variance)
        validation_count = sum(1 for value in averages if value >= PASSING_GRADE)
        validation_rate = validation_count * 100 / len(averages)

        self.set_stats_text(
            "\n".join(
                [
                    f"  📌  Branche : {selected_branch}",
                    f"  👥  Nombre d'étudiants notés : {len(averages)}",
                    f"  📊  Moyenne : {average:.2f} / 20",
                    f"  📐  Variance : {variance:.2f}",
                    f"  📏  Écart-type : {std_dev:.2f}",
                    f"  ✅  Taux de validation : {validation_rate:.1f} %",
                ]
            )
        )

    def show_validation_graphs(self):
        if not self.ensure_plot_dependencies():
            return

        selected_branch = self.value("stats_branch")
        if not selected_branch:
            self.show_error("Veuillez sélectionner une branche.")
            return

        code_branche = self.get_branch_code(selected_branch)
        rows = self.fetch_branch_averages(code_branche)
        if not rows:
            self.show_info("Aucune donnée disponible pour cette branche.")
            return

        averages = [row["average"] for row in rows]
        valid_count = sum(1 for value in averages if value >= PASSING_GRADE)
        catchup_count = len(averages) - valid_count

        gender_stats = {}
        for row in rows:
            gender = row["gender"] or "Non renseigné"
            gender_stats.setdefault(gender, {"Validé": 0, "Rattrapage": 0})
            key = "Validé" if row["average"] >= PASSING_GRADE else "Rattrapage"
            gender_stats[gender][key] += 1

        self.apply_plot_style()
        fig, axes = plt.subplots(1, 3, figsize=(16, 5))
        fig.suptitle(f"Analyse de validation — {selected_branch}", fontsize=14, fontweight="bold")

        axes[0].bar(["Validé", "Rattrapage"], [valid_count, catchup_count], color=[COLORS["success"], COLORS["danger"]])
        axes[0].set_title("Validation globale")
        axes[0].set_ylabel("Étudiants")

        labels = list(gender_stats)
        valid_values = [gender_stats[label]["Validé"] for label in labels]
        catchup_values = [gender_stats[label]["Rattrapage"] for label in labels]
        x = np.arange(len(labels))
        axes[1].bar(x, valid_values, label="Validé", color=COLORS["success"])
        axes[1].bar(x, catchup_values, bottom=valid_values, label="Rattrapage", color=COLORS["danger"])
        axes[1].set_xticks(x, labels)
        axes[1].set_title("Validation par genre")
        axes[1].legend()

        axes[2].hist(averages, bins=np.arange(0, 21, 2), color=COLORS["accent"], edgecolor="#ffffff")
        axes[2].axvline(PASSING_GRADE, color=COLORS["danger"], linestyle="--", linewidth=2)
        axes[2].set_title("Distribution des moyennes")
        axes[2].set_xlabel("Moyenne")
        axes[2].set_ylabel("Étudiants")

        fig.tight_layout()
        plt.show()

    def plot_gaussian_curve(self):
        if not self.ensure_plot_dependencies():
            return

        selected_branch = self.value("stats_branch")
        if not selected_branch:
            self.show_error("Veuillez sélectionner une branche.")
            return

        code_branche = self.get_branch_code(selected_branch)
        averages = [row["average"] for row in self.fetch_branch_averages(code_branche)]
        if not averages:
            self.show_info("Aucune donnée disponible pour cette branche.")
            return

        mean = float(np.mean(averages))
        std = float(np.std(averages))

        self.apply_plot_style()
        plt.figure(figsize=(9, 5.5))
        if std == 0:
            plt.axvline(mean, color=COLORS["accent"], linewidth=3, label=f"Moyenne unique : {mean:.2f}")
        else:
            x = np.linspace(0, 20, 300)
            y = (1 / (std * np.sqrt(2 * np.pi))) * np.exp(-0.5 * ((x - mean) / std) ** 2)
            plt.plot(x, y, label="Courbe de Gauss", linewidth=2.5, color=COLORS["accent"])
            plt.fill_between(x, y, color=COLORS["accent"], alpha=0.12)

        plt.axvline(PASSING_GRADE, color=COLORS["danger"], linestyle="--", linewidth=2, label="Seuil de validation")
        plt.title(f"Distribution normale des moyennes — {selected_branch}")
        plt.xlabel("Moyenne")
        plt.ylabel("Densité")
        plt.xticks(np.arange(0, 21, 1))
        plt.legend()
        plt.tight_layout()
        plt.show()

    # ──────────────────────────────────────────────────────────
    # PDF Report
    # ──────────────────────────────────────────────────────────
    def print_grade_report(self):
        if canvas is None:
            self.show_error("Le module reportlab n'est pas installé. Installez les dépendances pour générer les PDF.")
            return

        code_massar = self.value("report_student")
        if not code_massar:
            self.show_error("Veuillez sélectionner un code Massar.")
            return

        student = self.fetch_student(code_massar)
        if not student:
            self.show_error("Aucun étudiant trouvé avec ce code Massar.")
            return

        notes = self.fetch_student_notes(code_massar)
        if not notes:
            self.show_info("Aucune note trouvée pour cet étudiant.")
            return

        pdf_filename = BASE_DIR / f"releve_de_notes_{code_massar}.pdf"
        try:
            self.generate_grade_pdf(pdf_filename, student, notes)
        except OSError as exc:
            self.show_error(f"Erreur d'écriture du fichier PDF : {exc}")
            return
        except Exception as exc:
            self.show_error(f"Impossible de générer le PDF : {exc}")
            return

        self.show_success(f"Le relevé de notes a été enregistré : {pdf_filename.name}")
        try:
            os.startfile(str(pdf_filename))
        except OSError:
            pass

    def generate_grade_pdf(self, pdf_filename, student, notes):
        pdf = canvas.Canvas(str(pdf_filename), pagesize=A4)
        width, height = A4
        margin_x = 1.6 * cm
        y = height - 1.6 * cm

        # Header
        pdf.setFillColor(colors.HexColor("#6c63ff"))
        pdf.rect(0, height - 3.1 * cm, width, 3.1 * cm, fill=1, stroke=0)
        pdf.setFillColor(colors.white)
        pdf.setFont("Helvetica-Bold", 18)
        pdf.drawString(margin_x, height - 1.5 * cm, "Relevé de notes")
        pdf.setFont("Helvetica", 10)
        pdf.drawString(margin_x, height - 2.15 * cm, f"Code Massar : {student['code']}")
        pdf.drawRightString(width - margin_x, height - 2.15 * cm, datetime.now().strftime("%d/%m/%Y"))

        y -= 3.0 * cm
        pdf.setFillColor(colors.HexColor("#1f2937"))
        pdf.setFont("Helvetica-Bold", 11)
        pdf.drawString(margin_x, y, student["french_name"])
        pdf.setFont("Helvetica", 10)
        pdf.drawString(margin_x, y - 0.55 * cm, f"Branche : {student['branch']}")
        pdf.drawString(margin_x, y - 1.1 * cm, f"Genre : {student['gender']}    Date de naissance : {student['birth_date']}")

        y -= 2.0 * cm
        columns = [
            ("Matière", margin_x, 7.3 * cm),
            ("Coef.", 8.8 * cm, 1.4 * cm),
            ("Note", 10.4 * cm, 1.8 * cm),
            ("N x C", 12.4 * cm, 2.2 * cm),
            ("Remarque", 14.9 * cm, 3.8 * cm),
        ]
        row_height = 0.72 * cm
        self.draw_pdf_table_header(pdf, columns, y, row_height)
        y -= row_height

        total_coefficients = 0
        total_weighted = 0
        for note in notes:
            if y < 3.4 * cm:
                pdf.showPage()
                y = height - 2 * cm
                self.draw_pdf_table_header(pdf, columns, y, row_height)
                y -= row_height

            weighted = note["note"] * note["coefficient"]
            total_coefficients += note["coefficient"]
            total_weighted += weighted
            status = "Validé" if note["note"] >= PASSING_GRADE else "Rattrapage"
            values = [
                note["subject"],
                f"{note['coefficient']:g}",
                f"{note['note']:.2f}",
                f"{weighted:.2f}",
                status,
            ]
            self.draw_pdf_table_row(pdf, columns, values, y, row_height)
            y -= row_height

        average = total_weighted / total_coefficients if total_coefficients else 0
        branch_averages = [row["average"] for row in self.fetch_branch_averages(student["branch_code"])]
        class_average = sum(branch_averages) / len(branch_averages) if branch_averages else 0
        variance = sum((value - class_average) ** 2 for value in branch_averages) / len(branch_averages) if branch_averages else 0
        std_dev = math.sqrt(variance)
        general_status = "VALIDÉ" if average >= PASSING_GRADE else "RATTRAPAGE"

        y -= 0.55 * cm
        pdf.setFillColor(colors.HexColor("#eef7fa"))
        pdf.roundRect(margin_x, y - 2.15 * cm, width - 2 * margin_x, 2.15 * cm, 6, fill=1, stroke=0)
        pdf.setFillColor(colors.HexColor("#1f2937"))
        pdf.setFont("Helvetica-Bold", 11)
        pdf.drawString(margin_x + 0.35 * cm, y - 0.55 * cm, f"Moyenne générale : {average:.2f} / 20")
        pdf.drawString(margin_x + 0.35 * cm, y - 1.15 * cm, f"Remarque générale : {general_status}")
        pdf.setFont("Helvetica", 10)
        pdf.drawRightString(width - margin_x - 0.35 * cm, y - 0.55 * cm, f"Moyenne de branche : {class_average:.2f}")
        pdf.drawRightString(width - margin_x - 0.35 * cm, y - 1.15 * cm, f"Écart-type : {std_dev:.2f}")

        if SIGNATURE_PATH.exists():
            signature = ImageReader(str(SIGNATURE_PATH))
            pdf.drawImage(signature, width - 6.0 * cm, 1.0 * cm, width=4.5 * cm, height=2.4 * cm, mask="auto")

        pdf.setFont("Helvetica", 8)
        pdf.setFillColor(colors.HexColor("#6b7280"))
        pdf.drawString(margin_x, 1.1 * cm, "Document généré automatiquement.")
        pdf.save()

    def draw_pdf_table_header(self, pdf, columns, y, row_height):
        table_x = columns[0][1]
        table_width = max(x + col_width for _, x, col_width in columns) - table_x
        pdf.setFillColor(colors.HexColor("#6c63ff"))
        pdf.rect(table_x, y - row_height + 0.1 * cm, table_width, row_height, fill=1, stroke=0)
        pdf.setFillColor(colors.white)
        pdf.setFont("Helvetica-Bold", 9)
        for title, x, _ in columns:
            pdf.drawString(x + 0.15 * cm, y - 0.42 * cm, title)

    def draw_pdf_table_row(self, pdf, columns, values, y, row_height):
        pdf.setStrokeColor(colors.HexColor("#d9e2ec"))
        pdf.setFillColor(colors.HexColor("#1f2937"))
        pdf.setFont("Helvetica", 9)
        for (_, x, col_width), value in zip(columns, values):
            pdf.rect(x, y - row_height + 0.1 * cm, col_width, row_height, fill=0, stroke=1)
            clipped = self.clip_text(str(value), 34 if col_width > 5 * cm else 14)
            pdf.drawString(x + 0.15 * cm, y - 0.42 * cm, clipped)

    # ──────────────────────────────────────────────────────────
    # Refresh & Helpers
    # ──────────────────────────────────────────────────────────
    def refresh_all(self):
        self.update_combobox_values()
        self.refresh_dashboard()

    def ensure_plot_dependencies(self):
        if plt is None or np is None:
            self.show_error("Les modules matplotlib et numpy ne sont pas installés.")
            return False
        return True

    def apply_plot_style(self):
        try:
            plt.style.use("seaborn-v0_8-whitegrid")
        except OSError:
            plt.style.use("default")

    def update_combobox_values(self):
        branches = [row[0] for row in self.conn.execute("SELECT nom FROM branche ORDER BY nom").fetchall()]
        subjects = [row[0] for row in self.conn.execute("SELECT nom FROM matiere ORDER BY nom").fetchall()]
        students = [row[0] for row in self.conn.execute("SELECT code_massar FROM etudiant ORDER BY code_massar").fetchall()]

        branch_keys = ("student_branch", "ranking_branch", "stats_branch")
        subject_keys = ("grade_subject",)
        student_keys = ("grade_student", "report_student")

        for key in branch_keys:
            if key in self.inputs:
                self.inputs[key].configure(values=branches)
        for key in subject_keys:
            if key in self.inputs:
                self.inputs[key].configure(values=subjects)
        for key in student_keys:
            if key in self.inputs:
                self.inputs[key].configure(values=students)

    def refresh_dashboard(self):
        self.metric_vars["students_count"].set(str(self.count("etudiant")))
        self.metric_vars["branches_count"].set(str(self.count("branche")))
        self.metric_vars["subjects_count"].set(str(self.count("matiere")))

        averages = [row["average"] for row in self.fetch_all_averages()]
        self.metric_vars["global_average"].set(f"{sum(averages) / len(averages):.2f}" if averages else "0.00")

        self.recent_tree.delete(*self.recent_tree.get_children())
        # Temporarily switch row_factory for simple tuple access
        old_factory = self.conn.row_factory
        self.conn.row_factory = None
        rows = self.conn.execute(
            """
            SELECT e.code_massar, e.nom_francais, COALESCE(b.nom, '-'), e.genre
            FROM etudiant e
            LEFT JOIN branche b ON b.code = e.code_branche
            ORDER BY e.rowid DESC
            LIMIT 12
            """,
        ).fetchall()
        self.conn.row_factory = old_factory

        for i, row in enumerate(rows):
            tag = "oddrow" if i % 2 else "evenrow"
            self.recent_tree.insert("", tk.END, values=row, tags=(tag,))

    # ──────────────────────────────────────────────────────────
    # Database Queries
    # ──────────────────────────────────────────────────────────
    def fetch_student(self, code_massar):
        row = self.conn.execute(
            """
            SELECT e.code_massar, e.nom_arabe, e.nom_francais, e.genre,
                   e.lieu_naissance, e.date_naissance, e.code_branche, b.nom
            FROM etudiant e
            LEFT JOIN branche b ON b.code = e.code_branche
            WHERE e.code_massar = ?
            """,
            (code_massar,),
        ).fetchone()
        if not row:
            return None
        return {
            "code": row[0],
            "arabic_name": row[1],
            "french_name": row[2],
            "gender": row[3],
            "birthplace": row[4],
            "birth_date": row[5],
            "branch_code": row[6],
            "branch": row[7] or "-",
        }

    def fetch_student_notes(self, code_massar):
        rows = self.conn.execute(
            """
            SELECT m.nom, m.coefficient, n.note
            FROM note n
            JOIN matiere m ON m.code = n.code_matiere
            WHERE n.code_massar = ?
            ORDER BY m.nom
            """,
            (code_massar,),
        ).fetchall()
        return [{"subject": row[0], "coefficient": row[1], "note": row[2]} for row in rows]

    def fetch_branch_ranking(self, code_branche):
        rows = self.conn.execute(
            """
            SELECT e.code_massar, e.nom_arabe, e.nom_francais, e.genre,
                   SUM(n.note * m.coefficient) / SUM(m.coefficient) AS moyenne
            FROM etudiant e
            JOIN note n ON n.code_massar = e.code_massar
            JOIN matiere m ON m.code = n.code_matiere
            WHERE e.code_branche = ?
            GROUP BY e.code_massar, e.nom_arabe, e.nom_francais, e.genre
            ORDER BY moyenne DESC
            """,
            (code_branche,),
        ).fetchall()
        ranking = []
        previous_average = None
        current_rank = 0
        for index, row in enumerate(rows, start=1):
            average = float(row[4])
            if previous_average is None or average < previous_average:
                current_rank = index
            previous_average = average
            ranking.append(
                {
                    "rank": current_rank,
                    "code": row[0],
                    "arabic_name": row[1],
                    "french_name": row[2],
                    "gender": row[3],
                    "average": average,
                }
            )
        return ranking

    def fetch_branch_averages(self, code_branche):
        rows = self.conn.execute(
            """
            SELECT e.code_massar, e.genre,
                   SUM(n.note * m.coefficient) / SUM(m.coefficient) AS moyenne
            FROM etudiant e
            JOIN note n ON n.code_massar = e.code_massar
            JOIN matiere m ON m.code = n.code_matiere
            WHERE e.code_branche = ?
            GROUP BY e.code_massar, e.genre
            """,
            (code_branche,),
        ).fetchall()
        return [{"code": row[0], "gender": row[1], "average": float(row[2])} for row in rows]

    def fetch_all_averages(self):
        rows = self.conn.execute(
            """
            SELECT e.code_massar,
                   SUM(n.note * m.coefficient) / SUM(m.coefficient) AS moyenne
            FROM etudiant e
            JOIN note n ON n.code_massar = e.code_massar
            JOIN matiere m ON m.code = n.code_matiere
            GROUP BY e.code_massar
            """,
        ).fetchall()
        return [{"code": row[0], "average": float(row[1])} for row in rows]

    def get_branch_code(self, branch_name):
        row = self.conn.execute("SELECT code FROM branche WHERE nom = ?", (branch_name,)).fetchone()
        return row[0] if row else None

    def get_subject_code(self, subject_name):
        row = self.conn.execute("SELECT code FROM matiere WHERE nom = ?", (subject_name,)).fetchone()
        return row[0] if row else None

    def generate_unique_code(self, name, table):
        if table not in {"branche", "matiere"}:
            raise ValueError("Table non autorisée pour la génération de code.")

        base = self.slug_initials(name)
        code = base
        suffix = 1
        while self.conn.execute(f"SELECT 1 FROM {table} WHERE code = ?", (code,)).fetchone():
            suffix += 1
            code = f"{base[:2]}{suffix}"
        return code

    def slug_initials(self, text):
        normalized = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
        words = ["".join(char for char in word if char.isalnum()) for word in normalized.split()]
        words = [word for word in words if word]
        if len(words) >= 2:
            code = "".join(word[0] for word in words)
        elif words:
            code = words[0][:3]
        else:
            code = "COD"
        return code.upper().ljust(3, "0")[:3]

    def count(self, table):
        if table not in {"etudiant", "branche", "matiere", "note"}:
            return 0
        return self.conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]

    def parse_float(self, text, error_message):
        try:
            return float(text.replace(",", "."))
        except ValueError:
            self.show_error(error_message)
            return None

    def set_stats_text(self, text):
        self.stats_text.configure(state="normal")
        self.stats_text.delete("1.0", tk.END)
        self.stats_text.insert("1.0", text)
        self.stats_text.configure(state="disabled")

    def clip_text(self, text, max_chars):
        return text if len(text) <= max_chars else f"{text[:max_chars - 1]}…"

    # ──────────────────────────────────────────────────────────
    # Toast Notification Wrappers
    # ──────────────────────────────────────────────────────────
    def show_success(self, message):
        self.toast.show(message, "success")

    def show_error(self, message):
        self.toast.show(message, "error", duration=4500)

    def show_info(self, message):
        self.toast.show(message, "info")

    def close(self):
        self.conn.close()
        self.root.destroy()


# ──────────────────────────────────────────────────────────────
# Entry Point
# ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")

    root = ctk.CTk()
    app = StudentManagerApp(root)
    root.mainloop()
