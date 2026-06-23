import math
import os
import sqlite3
import tkinter as tk
import unicodedata
from datetime import datetime
from pathlib import Path
from tkinter import messagebox, ttk

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


BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "main.db"
SIGNATURE_PATH = BASE_DIR / "signature.jpg"

APP_TITLE = "Gestion des étudiants"
PASSING_GRADE = 10
MIN_GRADE = 0
MAX_GRADE = 20

COLORS = {
    "bg": "#f5f7fb",
    "panel": "#ffffff",
    "text": "#1f2937",
    "muted": "#6b7280",
    "accent": "#1f6f8b",
    "accent_hover": "#155e75",
    "success": "#15803d",
    "danger": "#b91c1c",
    "border": "#d9e2ec",
    "header": "#eef7fa",
}


class StudentManagerApp:
    def __init__(self, root):
        self.root = root
        self.root.title(APP_TITLE)
        self.root.geometry("1040x720")
        self.root.minsize(940, 620)
        self.root.configure(bg=COLORS["bg"])

        self.conn = sqlite3.connect(DB_PATH)
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.cursor = self.conn.cursor()

        self.inputs = {}
        self.metric_vars = {}

        self.configure_styles()
        self.create_tables()
        self.build_ui()
        self.update_combobox_values()
        self.refresh_dashboard()

        self.root.protocol("WM_DELETE_WINDOW", self.close)

    def configure_styles(self):
        style = ttk.Style(self.root)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        style.configure(".", font=("Segoe UI", 10), foreground=COLORS["text"])
        style.configure("App.TFrame", background=COLORS["bg"])
        style.configure("Panel.TFrame", background=COLORS["panel"], relief="flat")
        style.configure("Header.TFrame", background=COLORS["bg"])
        style.configure("Card.TFrame", background=COLORS["panel"], relief="flat")
        style.configure("TLabel", background=COLORS["panel"], foreground=COLORS["text"])
        style.configure("Muted.TLabel", background=COLORS["panel"], foreground=COLORS["muted"])
        style.configure("Title.TLabel", background=COLORS["bg"], foreground=COLORS["text"], font=("Segoe UI Semibold", 20))
        style.configure("MetricValue.TLabel", background=COLORS["panel"], foreground=COLORS["accent"], font=("Segoe UI Semibold", 18))
        style.configure("MetricLabel.TLabel", background=COLORS["panel"], foreground=COLORS["muted"], font=("Segoe UI", 9))
        style.configure("TLabelframe", background=COLORS["panel"], bordercolor=COLORS["border"], relief="solid")
        style.configure("TLabelframe.Label", background=COLORS["panel"], foreground=COLORS["accent"], font=("Segoe UI Semibold", 10))
        style.configure("TNotebook", background=COLORS["bg"], borderwidth=0)
        style.configure("TNotebook.Tab", padding=(18, 10), background="#e9eef5", foreground=COLORS["muted"])
        style.map(
            "TNotebook.Tab",
            background=[("selected", COLORS["panel"])],
            foreground=[("selected", COLORS["accent"])],
        )
        style.configure("TEntry", padding=8, fieldbackground="#ffffff", bordercolor=COLORS["border"])
        style.configure("TCombobox", padding=8, fieldbackground="#ffffff", bordercolor=COLORS["border"])
        style.configure("Accent.TButton", padding=(16, 9), background=COLORS["accent"], foreground="#ffffff", borderwidth=0)
        style.map(
            "Accent.TButton",
            background=[("active", COLORS["accent_hover"]), ("pressed", COLORS["accent_hover"])],
            foreground=[("disabled", "#e5e7eb")],
        )
        style.configure("Secondary.TButton", padding=(14, 8), background="#edf2f7", foreground=COLORS["text"], borderwidth=0)
        style.map("Secondary.TButton", background=[("active", "#dbeafe")])
        style.configure("Treeview", rowheight=30, bordercolor=COLORS["border"], fieldbackground="#ffffff", background="#ffffff")
        style.configure("Treeview.Heading", background=COLORS["header"], foreground=COLORS["text"], font=("Segoe UI Semibold", 10))

    def create_tables(self):
        self.cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS branche (
                code TEXT PRIMARY KEY,
                nom TEXT UNIQUE
            )
            """
        )
        self.cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS etudiant (
                code_massar TEXT PRIMARY KEY UNIQUE,
                nom_arabe TEXT,
                nom_francais TEXT,
                genre TEXT,
                lieu_naissance TEXT,
                date_naissance DATE,
                code_branche TEXT,
                FOREIGN KEY (code_branche) REFERENCES branche(code)
            )
            """
        )
        self.cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS matiere (
                code TEXT PRIMARY KEY,
                nom TEXT UNIQUE,
                coefficient REAL
            )
            """
        )
        self.cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS note (
                code_massar TEXT,
                code_matiere TEXT,
                note REAL,
                FOREIGN KEY (code_massar) REFERENCES etudiant(code_massar),
                FOREIGN KEY (code_matiere) REFERENCES matiere(code)
            )
            """
        )
        self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_etudiant_branche ON etudiant(code_branche)")
        self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_note_student ON note(code_massar)")
        self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_note_subject ON note(code_matiere)")
        self.conn.commit()

    def build_ui(self):
        container = ttk.Frame(self.root, style="App.TFrame", padding=(22, 18, 22, 16))
        container.pack(fill=tk.BOTH, expand=True)
        container.columnconfigure(0, weight=1)
        container.rowconfigure(1, weight=1)

        header = ttk.Frame(container, style="Header.TFrame")
        header.grid(row=0, column=0, sticky="ew", pady=(0, 16))
        header.columnconfigure(0, weight=1)

        ttk.Label(header, text=APP_TITLE, style="Title.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Button(header, text="Actualiser", style="Secondary.TButton", command=self.refresh_all).grid(row=0, column=1, sticky="e")

        self.notebook = ttk.Notebook(container)
        self.notebook.grid(row=1, column=0, sticky="nsew")

        self.create_dashboard_tab()
        self.create_student_tab()
        self.create_branch_tab()
        self.create_subject_tab()
        self.create_grade_tab()
        self.create_ranking_tab()
        self.create_statistics_tab()
        self.create_report_tab()

        status = ttk.Frame(container, style="App.TFrame")
        status.grid(row=2, column=0, sticky="ew", pady=(12, 0))
        status.columnconfigure(0, weight=1)
        ttk.Label(
            status,
            text=f"Base de données : {DB_PATH.name}",
            background=COLORS["bg"],
            foreground=COLORS["muted"],
        ).grid(row=0, column=0, sticky="w")

    def create_dashboard_tab(self):
        frame = self.create_tab("Tableau de bord")
        frame.columnconfigure((0, 1, 2, 3), weight=1, uniform="metrics")
        frame.rowconfigure(1, weight=1)

        metrics = [
            ("students_count", "Étudiants"),
            ("branches_count", "Branches"),
            ("subjects_count", "Matières"),
            ("global_average", "Moyenne générale"),
        ]
        for col, (key, label) in enumerate(metrics):
            card = ttk.Frame(frame, style="Card.TFrame", padding=(18, 16))
            card.grid(row=0, column=col, sticky="ew", padx=(0 if col == 0 else 10, 0), pady=(0, 18))
            self.metric_vars[key] = tk.StringVar(value="0")
            ttk.Label(card, textvariable=self.metric_vars[key], style="MetricValue.TLabel").pack(anchor="w")
            ttk.Label(card, text=label, style="MetricLabel.TLabel").pack(anchor="w", pady=(6, 0))

        recent_box = ttk.LabelFrame(frame, text="Derniers étudiants", padding=12)
        recent_box.grid(row=1, column=0, columnspan=4, sticky="nsew")
        recent_box.rowconfigure(0, weight=1)
        recent_box.columnconfigure(0, weight=1)

        columns = ("code", "nom", "branche", "genre")
        self.recent_tree = ttk.Treeview(recent_box, columns=columns, show="headings", height=9)
        self.recent_tree.heading("code", text="Code Massar")
        self.recent_tree.heading("nom", text="Nom français")
        self.recent_tree.heading("branche", text="Branche")
        self.recent_tree.heading("genre", text="Genre")
        self.recent_tree.column("code", width=150, anchor="w")
        self.recent_tree.column("nom", width=240, anchor="w")
        self.recent_tree.column("branche", width=220, anchor="w")
        self.recent_tree.column("genre", width=120, anchor="center")
        self.recent_tree.grid(row=0, column=0, sticky="nsew")

        scrollbar = ttk.Scrollbar(recent_box, orient=tk.VERTICAL, command=self.recent_tree.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.recent_tree.configure(yscrollcommand=scrollbar.set)

    def create_student_tab(self):
        frame = self.create_tab("Étudiants")
        form = ttk.LabelFrame(frame, text="Ajouter un étudiant", padding=18)
        form.grid(row=0, column=0, sticky="nsew")
        form.columnconfigure(1, weight=1)

        self.add_entry(form, "student_code", "Code Massar", 0)
        self.add_entry(form, "student_ar_name", "Nom arabe", 1)
        self.add_entry(form, "student_fr_name", "Nom français", 2)
        self.add_combobox(form, "student_gender", "Genre", 3, values=("Homme", "Femme"))
        self.add_entry(form, "student_birthplace", "Lieu de naissance", 4)

        ttk.Label(form, text="Date de naissance").grid(row=5, column=0, sticky="w", padx=(0, 16), pady=8)
        if DateEntry:
            birth_date = DateEntry(form, date_pattern="yyyy-mm-dd", width=18)
        else:
            birth_date = ttk.Entry(form)
            birth_date.insert(0, datetime.now().strftime("%Y-%m-%d"))
        birth_date.grid(row=5, column=1, sticky="ew", pady=8)
        self.inputs["student_birth_date"] = birth_date

        self.add_combobox(form, "student_branch", "Branche", 6)
        ttk.Button(form, text="Ajouter l'étudiant", style="Accent.TButton", command=self.submit_student).grid(
            row=7, column=0, columnspan=2, sticky="e", pady=(18, 0)
        )

    def create_branch_tab(self):
        frame = self.create_tab("Branches")
        form = ttk.LabelFrame(frame, text="Ajouter une branche", padding=18)
        form.grid(row=0, column=0, sticky="nsew")
        form.columnconfigure(1, weight=1)

        self.add_entry(form, "branch_name", "Nom de la branche", 0)
        ttk.Button(form, text="Ajouter la branche", style="Accent.TButton", command=self.submit_branch).grid(
            row=1, column=0, columnspan=2, sticky="e", pady=(18, 0)
        )

    def create_subject_tab(self):
        frame = self.create_tab("Matières")
        form = ttk.LabelFrame(frame, text="Ajouter une matière", padding=18)
        form.grid(row=0, column=0, sticky="nsew")
        form.columnconfigure(1, weight=1)

        self.add_entry(form, "subject_name", "Nom de la matière", 0)
        self.add_entry(form, "subject_coefficient", "Coefficient", 1)
        ttk.Button(form, text="Ajouter la matière", style="Accent.TButton", command=self.submit_subject).grid(
            row=2, column=0, columnspan=2, sticky="e", pady=(18, 0)
        )

    def create_grade_tab(self):
        frame = self.create_tab("Notes")
        form = ttk.LabelFrame(frame, text="Ajouter ou remplacer une note", padding=18)
        form.grid(row=0, column=0, sticky="nsew")
        form.columnconfigure(1, weight=1)

        self.add_combobox(form, "grade_student", "Code Massar", 0)
        self.add_combobox(form, "grade_subject", "Matière", 1)
        self.add_entry(form, "grade_value", "Note / 20", 2)
        ttk.Button(form, text="Enregistrer la note", style="Accent.TButton", command=self.submit_grade).grid(
            row=3, column=0, columnspan=2, sticky="e", pady=(18, 0)
        )

    def create_ranking_tab(self):
        frame = self.create_tab("Classements")
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(1, weight=1)

        controls = ttk.LabelFrame(frame, text="Classement par branche", padding=14)
        controls.grid(row=0, column=0, sticky="ew", pady=(0, 14))
        controls.columnconfigure(1, weight=1)
        self.add_combobox(controls, "ranking_branch", "Branche", 0)
        ttk.Button(controls, text="Afficher", style="Accent.TButton", command=self.show_student_by_branch).grid(
            row=0, column=2, sticky="e", padx=(12, 0)
        )

        table_box = ttk.Frame(frame, style="Panel.TFrame")
        table_box.grid(row=1, column=0, sticky="nsew")
        table_box.rowconfigure(0, weight=1)
        table_box.columnconfigure(0, weight=1)

        columns = ("rank", "code", "arabic", "french", "average", "status")
        self.ranking_tree = ttk.Treeview(table_box, columns=columns, show="headings")
        headings = {
            "rank": "Rang",
            "code": "Code Massar",
            "arabic": "Nom arabe",
            "french": "Nom français",
            "average": "Moyenne",
            "status": "Validation",
        }
        widths = {
            "rank": 70,
            "code": 150,
            "arabic": 170,
            "french": 220,
            "average": 100,
            "status": 120,
        }
        for col in columns:
            self.ranking_tree.heading(col, text=headings[col])
            self.ranking_tree.column(col, width=widths[col], anchor="center" if col in {"rank", "average", "status"} else "w")
        self.ranking_tree.tag_configure("success", foreground=COLORS["success"])
        self.ranking_tree.tag_configure("danger", foreground=COLORS["danger"])
        self.ranking_tree.grid(row=0, column=0, sticky="nsew")

        y_scroll = ttk.Scrollbar(table_box, orient=tk.VERTICAL, command=self.ranking_tree.yview)
        y_scroll.grid(row=0, column=1, sticky="ns")
        self.ranking_tree.configure(yscrollcommand=y_scroll.set)

    def create_statistics_tab(self):
        frame = self.create_tab("Statistiques")
        frame.rowconfigure(1, weight=1)
        form = ttk.LabelFrame(frame, text="Analyse par branche", padding=18)
        form.grid(row=0, column=0, sticky="ew", pady=(0, 16))
        form.columnconfigure(1, weight=1)

        self.add_combobox(form, "stats_branch", "Branche", 0)
        ttk.Button(form, text="Afficher les statistiques", style="Accent.TButton", command=self.calculate_branch_statistics).grid(
            row=0, column=2, sticky="e", padx=(12, 0)
        )
        ttk.Button(form, text="Courbe de Gauss", style="Secondary.TButton", command=self.plot_gaussian_curve).grid(
            row=0, column=3, sticky="e", padx=(10, 0)
        )
        ttk.Button(form, text="Graphiques", style="Secondary.TButton", command=self.show_validation_graphs).grid(
            row=0, column=4, sticky="e", padx=(10, 0)
        )

        result = ttk.LabelFrame(frame, text="Résultat", padding=18)
        result.grid(row=1, column=0, sticky="nsew")
        result.columnconfigure(0, weight=1)
        result.rowconfigure(0, weight=1)
        self.stats_text = tk.Text(
            result,
            height=9,
            wrap="word",
            bg="#ffffff",
            fg=COLORS["text"],
            relief="flat",
            padx=12,
            pady=12,
            font=("Segoe UI", 10),
        )
        self.stats_text.grid(row=0, column=0, sticky="nsew")
        self.stats_text.configure(state="disabled")

    def create_report_tab(self):
        frame = self.create_tab("Relevés")
        form = ttk.LabelFrame(frame, text="Générer un relevé de notes", padding=18)
        form.grid(row=0, column=0, sticky="nsew")
        form.columnconfigure(1, weight=1)

        self.add_combobox(form, "report_student", "Code Massar", 0)
        ttk.Button(form, text="Créer le PDF", style="Accent.TButton", command=self.print_grade_report).grid(
            row=1, column=0, columnspan=2, sticky="e", pady=(18, 0)
        )

    def create_tab(self, title):
        frame = ttk.Frame(self.notebook, style="App.TFrame", padding=18)
        frame.columnconfigure(0, weight=1)
        self.notebook.add(frame, text=title)
        return frame

    def add_entry(self, parent, key, label, row):
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", padx=(0, 16), pady=8)
        entry = ttk.Entry(parent)
        entry.grid(row=row, column=1, sticky="ew", pady=8)
        self.inputs[key] = entry
        return entry

    def add_combobox(self, parent, key, label, row, values=()):
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", padx=(0, 16), pady=8)
        combo = ttk.Combobox(parent, values=values, state="readonly")
        combo.grid(row=row, column=1, sticky="ew", pady=8)
        self.inputs[key] = combo
        return combo

    def value(self, key):
        return self.inputs[key].get().strip()

    def clear_inputs(self, *keys):
        for key in keys:
            widget = self.inputs[key]
            if isinstance(widget, ttk.Combobox):
                widget.set("")
            else:
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
            self.error("Veuillez remplir tous les champs.")
            return

        try:
            datetime.strptime(date_naissance, "%Y-%m-%d")
        except ValueError:
            self.error("La date de naissance doit respecter le format AAAA-MM-JJ.")
            return

        code_branche = self.get_branch_code(nom_branche)
        if not code_branche:
            self.error("La branche sélectionnée n'existe pas.")
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
            self.error("Ce code Massar existe déjà.")
            return

        self.success("Étudiant ajouté avec succès.")
        self.clear_inputs("student_code", "student_ar_name", "student_fr_name", "student_gender", "student_birthplace", "student_branch")
        self.refresh_all()

    def submit_branch(self):
        nom_branche = self.value("branch_name")
        if not nom_branche:
            self.error("Veuillez entrer le nom de la branche.")
            return

        code_branche = self.generate_unique_code(nom_branche, "branche")
        try:
            with self.conn:
                self.conn.execute("INSERT INTO branche (code, nom) VALUES (?, ?)", (code_branche, nom_branche))
        except sqlite3.IntegrityError:
            self.error("Cette branche existe déjà.")
            return

        self.success(f"Branche ajoutée avec le code {code_branche}.")
        self.clear_inputs("branch_name")
        self.refresh_all()

    def submit_subject(self):
        nom_matiere = self.value("subject_name")
        coefficient_text = self.value("subject_coefficient")

        if not nom_matiere or not coefficient_text:
            self.error("Veuillez remplir tous les champs.")
            return

        coefficient = self.parse_float(coefficient_text, "Le coefficient doit être un nombre.")
        if coefficient is None:
            return
        if coefficient <= 0:
            self.error("Le coefficient doit être supérieur à 0.")
            return

        code_matiere = self.generate_unique_code(nom_matiere, "matiere")
        try:
            with self.conn:
                self.conn.execute(
                    "INSERT INTO matiere (code, nom, coefficient) VALUES (?, ?, ?)",
                    (code_matiere, nom_matiere, coefficient),
                )
        except sqlite3.IntegrityError:
            self.error("Cette matière existe déjà.")
            return

        self.success(f"Matière ajoutée avec le code {code_matiere}.")
        self.clear_inputs("subject_name", "subject_coefficient")
        self.refresh_all()

    def submit_grade(self):
        code_massar = self.value("grade_student")
        nom_matiere = self.value("grade_subject")
        note_text = self.value("grade_value")

        if not code_massar or not nom_matiere or not note_text:
            self.error("Veuillez remplir tous les champs.")
            return

        note = self.parse_float(note_text, "La note doit être un nombre.")
        if note is None:
            return
        if not MIN_GRADE <= note <= MAX_GRADE:
            self.error(f"La note doit être comprise entre {MIN_GRADE} et {MAX_GRADE}.")
            return

        code_matiere = self.get_subject_code(nom_matiere)
        if not code_matiere:
            self.error("La matière sélectionnée n'existe pas.")
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

        self.success("Note enregistrée avec succès.")
        self.clear_inputs("grade_value")
        self.refresh_all()

    def show_student_by_branch(self):
        selected_branch = self.value("ranking_branch")
        if not selected_branch:
            self.error("Veuillez sélectionner une branche.")
            return

        code_branche = self.get_branch_code(selected_branch)
        students = self.fetch_branch_ranking(code_branche)

        self.ranking_tree.delete(*self.ranking_tree.get_children())
        if not students:
            self.info("Aucun étudiant avec notes trouvé pour cette branche.")
            return

        for row in students:
            status = "Validé" if row["average"] >= PASSING_GRADE else "Rattrapage"
            tag = "success" if row["average"] >= PASSING_GRADE else "danger"
            self.ranking_tree.insert(
                "",
                tk.END,
                values=(row["rank"], row["code"], row["arabic_name"], row["french_name"], f"{row['average']:.2f}", status),
                tags=(tag,),
            )

    def calculate_branch_statistics(self):
        selected_branch = self.value("stats_branch")
        if not selected_branch:
            self.error("Veuillez sélectionner une branche.")
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
                    f"Branche : {selected_branch}",
                    f"Nombre d'étudiants notés : {len(averages)}",
                    f"Moyenne : {average:.2f} / 20",
                    f"Variance : {variance:.2f}",
                    f"Écart-type : {std_dev:.2f}",
                    f"Taux de validation : {validation_rate:.1f} %",
                ]
            )
        )

    def show_validation_graphs(self):
        if not self.ensure_plot_dependencies():
            return

        selected_branch = self.value("stats_branch")
        if not selected_branch:
            self.error("Veuillez sélectionner une branche.")
            return

        code_branche = self.get_branch_code(selected_branch)
        rows = self.fetch_branch_averages(code_branche)
        if not rows:
            self.info("Aucune donnée disponible pour cette branche.")
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
        fig.suptitle(f"Analyse de validation - {selected_branch}", fontsize=14, fontweight="bold")

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
            self.error("Veuillez sélectionner une branche.")
            return

        code_branche = self.get_branch_code(selected_branch)
        averages = [row["average"] for row in self.fetch_branch_averages(code_branche)]
        if not averages:
            self.info("Aucune donnée disponible pour cette branche.")
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
        plt.title(f"Distribution normale des moyennes - {selected_branch}")
        plt.xlabel("Moyenne")
        plt.ylabel("Densité")
        plt.xticks(np.arange(0, 21, 1))
        plt.legend()
        plt.tight_layout()
        plt.show()

    def print_grade_report(self):
        if canvas is None:
            self.error("Le module reportlab n'est pas installé. Installez les dépendances pour générer les PDF.")
            return

        code_massar = self.value("report_student")
        if not code_massar:
            self.error("Veuillez sélectionner un code Massar.")
            return

        student = self.fetch_student(code_massar)
        if not student:
            self.error("Aucun étudiant trouvé avec ce code Massar.")
            return

        notes = self.fetch_student_notes(code_massar)
        if not notes:
            self.info("Aucune note trouvée pour cet étudiant.")
            return

        pdf_filename = BASE_DIR / f"releve_de_notes_{code_massar}.pdf"
        try:
            self.generate_grade_pdf(pdf_filename, student, notes)
        except OSError as exc:
            self.error(f"Erreur d'écriture du fichier PDF : {exc}")
            return
        except Exception as exc:
            self.error(f"Impossible de générer le PDF : {exc}")
            return

        self.success(f"Le relevé de notes a été enregistré : {pdf_filename.name}")
        try:
            os.startfile(str(pdf_filename))
        except OSError:
            pass

    def generate_grade_pdf(self, pdf_filename, student, notes):
        pdf = canvas.Canvas(str(pdf_filename), pagesize=A4)
        width, height = A4
        margin_x = 1.6 * cm
        y = height - 1.6 * cm

        pdf.setFillColor(colors.HexColor(COLORS["accent"]))
        pdf.rect(0, height - 3.1 * cm, width, 3.1 * cm, fill=1, stroke=0)
        pdf.setFillColor(colors.white)
        pdf.setFont("Helvetica-Bold", 18)
        pdf.drawString(margin_x, height - 1.5 * cm, "Relevé de notes")
        pdf.setFont("Helvetica", 10)
        pdf.drawString(margin_x, height - 2.15 * cm, f"Code Massar : {student['code']}")
        pdf.drawRightString(width - margin_x, height - 2.15 * cm, datetime.now().strftime("%d/%m/%Y"))

        y -= 3.0 * cm
        pdf.setFillColor(colors.HexColor(COLORS["text"]))
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
        pdf.setFillColor(colors.HexColor(COLORS["header"]))
        pdf.roundRect(margin_x, y - 2.15 * cm, width - 2 * margin_x, 2.15 * cm, 6, fill=1, stroke=0)
        pdf.setFillColor(colors.HexColor(COLORS["text"]))
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
        pdf.setFillColor(colors.HexColor(COLORS["muted"]))
        pdf.drawString(margin_x, 1.1 * cm, "Document généré automatiquement.")
        pdf.save()

    def draw_pdf_table_header(self, pdf, columns, y, row_height):
        table_x = columns[0][1]
        table_width = max(x + col_width for _, x, col_width in columns) - table_x
        pdf.setFillColor(colors.HexColor(COLORS["accent"]))
        pdf.rect(table_x, y - row_height + 0.1 * cm, table_width, row_height, fill=1, stroke=0)
        pdf.setFillColor(colors.white)
        pdf.setFont("Helvetica-Bold", 9)
        for title, x, _ in columns:
            pdf.drawString(x + 0.15 * cm, y - 0.42 * cm, title)

    def draw_pdf_table_row(self, pdf, columns, values, y, row_height):
        pdf.setStrokeColor(colors.HexColor(COLORS["border"]))
        pdf.setFillColor(colors.HexColor(COLORS["text"]))
        pdf.setFont("Helvetica", 9)
        for (_, x, col_width), value in zip(columns, values):
            pdf.rect(x, y - row_height + 0.1 * cm, col_width, row_height, fill=0, stroke=1)
            clipped = self.clip_text(str(value), 34 if col_width > 5 * cm else 14)
            pdf.drawString(x + 0.15 * cm, y - 0.42 * cm, clipped)

    def refresh_all(self):
        self.update_combobox_values()
        self.refresh_dashboard()

    def ensure_plot_dependencies(self):
        if plt is None or np is None:
            self.error("Les modules matplotlib et numpy ne sont pas installés. Installez les dépendances pour afficher les graphiques.")
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
            self.inputs[key]["values"] = branches
        for key in subject_keys:
            self.inputs[key]["values"] = subjects
        for key in student_keys:
            self.inputs[key]["values"] = students

    def refresh_dashboard(self):
        self.metric_vars["students_count"].set(str(self.count("etudiant")))
        self.metric_vars["branches_count"].set(str(self.count("branche")))
        self.metric_vars["subjects_count"].set(str(self.count("matiere")))

        averages = [row["average"] for row in self.fetch_all_averages()]
        self.metric_vars["global_average"].set(f"{sum(averages) / len(averages):.2f}" if averages else "0.00")

        self.recent_tree.delete(*self.recent_tree.get_children())
        rows = self.conn.execute(
            """
            SELECT e.code_massar, e.nom_francais, COALESCE(b.nom, '-'), e.genre
            FROM etudiant e
            LEFT JOIN branche b ON b.code = e.code_branche
            ORDER BY e.rowid DESC
            LIMIT 12
            """
        ).fetchall()
        for row in rows:
            self.recent_tree.insert("", tk.END, values=row)

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
            """
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
            self.error(error_message)
            return None

    def set_stats_text(self, text):
        self.stats_text.configure(state="normal")
        self.stats_text.delete("1.0", tk.END)
        self.stats_text.insert("1.0", text)
        self.stats_text.configure(state="disabled")

    def clip_text(self, text, max_chars):
        return text if len(text) <= max_chars else f"{text[:max_chars - 1]}…"

    def success(self, message):
        messagebox.showinfo("Succès", message)

    def info(self, message):
        messagebox.showinfo("Information", message)

    def error(self, message):
        messagebox.showerror("Erreur", message)

    def close(self):
        self.conn.close()
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    app = StudentManagerApp(root)
    root.mainloop()
