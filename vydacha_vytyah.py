import sqlite3
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog
from datetime import datetime, date
from pathlib import Path
import csv, hashlib, secrets, sys, html, webbrowser

APP_TITLE = "Видача витягів з Реєстру територіальної громади"
DB_NAME = "vydacha_vytyah.db"

def app_data_dir():
    root = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
    folder = root / "data"
    folder.mkdir(exist_ok=True)
    return folder

DB_PATH = app_data_dir() / DB_NAME

class VytyahApp:
    def __init__(self, root):
        self.root = root
        self.root.title(APP_TITLE)
        self.root.geometry("1180x740")
        self.root.minsize(940, 600)
        self.selected_id = None
        self.conn = sqlite3.connect(DB_PATH)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pib TEXT NOT NULL,
                issue_date TEXT NOT NULL,
                extract_number TEXT NOT NULL UNIQUE,
                created_at TEXT NOT NULL
            )
        """)
        self.conn.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        self.conn.commit()
        self._style()
        if not self.authenticate():
            self.conn.close()
            self.root.destroy()
            return
        self._build_ui()
        self.refresh()

    def _style(self):
        s = ttk.Style()
        try: s.theme_use("vista")
        except tk.TclError: pass
        s.configure("Title.TLabel", font=("Segoe UI", 17, "bold"))
        s.configure("Sub.TLabel", font=("Segoe UI", 9), foreground="#555")
        s.configure("Treeview", rowheight=29, font=("Segoe UI", 10))
        s.configure("Treeview.Heading", font=("Segoe UI", 10, "bold"))
        s.configure("TButton", font=("Segoe UI", 10), padding=7)
        s.configure("TLabel", font=("Segoe UI", 10))

    def get_setting(self, key):
        row = self.conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return row[0] if row else None

    def set_setting(self, key, value):
        self.conn.execute("INSERT OR REPLACE INTO settings(key,value) VALUES(?,?)", (key, value))
        self.conn.commit()

    def authenticate(self):
        saved = self.get_setting("password_hash")
        if not saved:
            messagebox.showinfo("Перший запуск", "Створіть пароль для захисту журналу. Не забудьте його.")
            while True:
                p1 = simpledialog.askstring("Створення пароля", "Введіть новий пароль:", show="*")
                if p1 is None: return False
                if len(p1) < 6:
                    messagebox.showwarning("Короткий пароль", "Пароль має містити щонайменше 6 символів.")
                    continue
                p2 = simpledialog.askstring("Підтвердження", "Повторіть пароль:", show="*")
                if p1 != p2:
                    messagebox.showerror("Помилка", "Паролі не збігаються.")
                    continue
                salt = secrets.token_hex(16)
                digest = hashlib.pbkdf2_hmac("sha256", p1.encode(), salt.encode(), 200000).hex()
                self.set_setting("password_hash", salt + ":" + digest)
                return True
        salt, digest = saved.split(":", 1)
        for _ in range(3):
            p = simpledialog.askstring("Вхід до програми", "Введіть пароль:", show="*")
            if p is None: return False
            test = hashlib.pbkdf2_hmac("sha256", p.encode(), salt.encode(), 200000).hex()
            if secrets.compare_digest(test, digest): return True
            messagebox.showerror("Доступ заборонено", "Неправильний пароль.")
        return False

    def _build_ui(self):
        outer = ttk.Frame(self.root, padding=16)
        outer.pack(fill="both", expand=True)
        ttk.Label(outer, text="ВИДАЧА ВИТЯГІВ", style="Title.TLabel").pack(anchor="w")
        ttk.Label(outer, text="З РЕЄСТРУ ТЕРИТОРІАЛЬНОЇ ГРОМАДИ", style="Sub.TLabel").pack(anchor="w", pady=(0, 13))

        stats = ttk.Frame(outer); stats.pack(fill="x", pady=(0, 10))
        self.total_var = tk.StringVar(); self.month_var = tk.StringVar()
        ttk.Label(stats, textvariable=self.total_var, font=("Segoe UI", 11, "bold")).pack(side="left", padx=(0, 28))
        ttk.Label(stats, textvariable=self.month_var, font=("Segoe UI", 11, "bold")).pack(side="left")

        form = ttk.LabelFrame(outer, text="Дані про виданий витяг", padding=11)
        form.pack(fill="x", pady=(0, 11))
        for col, label in enumerate(("ПІБ", "Дата видачі (ДД.ММ.РРРР)", "Номер витягу")):
            ttk.Label(form, text=label).grid(row=0, column=col, sticky="w", padx=(0, 9), pady=3)
        self.pib_var, self.date_var, self.number_var = tk.StringVar(), tk.StringVar(value=date.today().strftime("%d.%m.%Y")), tk.StringVar()
        ttk.Entry(form, textvariable=self.pib_var).grid(row=1, column=0, sticky="ew", padx=(0, 10))
        ttk.Entry(form, textvariable=self.date_var, width=20).grid(row=1, column=1, sticky="ew", padx=(0, 10))
        ttk.Entry(form, textvariable=self.number_var).grid(row=1, column=2, sticky="ew", padx=(0, 10))
        form.columnconfigure(0, weight=3); form.columnconfigure(1, weight=1); form.columnconfigure(2, weight=1)
        btns = ttk.Frame(form); btns.grid(row=1, column=3, sticky="e")
        ttk.Button(btns, text="Зберегти", command=self.save_record).pack(side="left", padx=3)
        ttk.Button(btns, text="Очистити", command=self.clear_form).pack(side="left", padx=3)

        filters = ttk.Frame(outer); filters.pack(fill="x", pady=(0, 8))
        ttk.Label(filters, text="Пошук:").pack(side="left")
        self.search_var = tk.StringVar()
        ent = ttk.Entry(filters, textvariable=self.search_var, width=25); ent.pack(side="left", padx=6)
        ent.bind("<KeyRelease>", lambda _e: self.refresh())
        ttk.Label(filters, text="Рік:").pack(side="left", padx=(10, 3))
        self.year_var = tk.StringVar(value="Усі")
        self.year_combo = ttk.Combobox(filters, textvariable=self.year_var, width=8, state="readonly")
        self.year_combo.pack(side="left")
        self.year_combo.bind("<<ComboboxSelected>>", lambda _e: self.refresh())
        ttk.Label(filters, text="Місяць:").pack(side="left", padx=(8, 3))
        self.month_var_filter = tk.StringVar(value="Усі")
        self.month_combo = ttk.Combobox(filters, textvariable=self.month_var_filter, width=12, state="readonly",
            values=["Усі","Січень","Лютий","Березень","Квітень","Травень","Червень","Липень","Серпень","Вересень","Жовтень","Листопад","Грудень"])
        self.month_combo.pack(side="left")
        self.month_combo.bind("<<ComboboxSelected>>", lambda _e: self.refresh())
        ttk.Button(filters, text="Скинути", command=self.reset_filters).pack(side="left", padx=7)

        tf = ttk.Frame(outer); tf.pack(fill="both", expand=True)
        cols = ("pib", "date", "number")
        self.tree = ttk.Treeview(tf, columns=cols, show="headings", selectmode="browse")
        self.tree.heading("pib", text="ПІБ"); self.tree.heading("date", text="Дата видачі"); self.tree.heading("number", text="Номер витягу")
        self.tree.column("pib", width=510); self.tree.column("date", width=170, anchor="center"); self.tree.column("number", width=230, anchor="center")
        sb = ttk.Scrollbar(tf, orient="vertical", command=self.tree.yview); self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side="left", fill="both", expand=True); sb.pack(side="right", fill="y")

        bottom = ttk.Frame(outer); bottom.pack(fill="x", pady=(11, 0))
        ttk.Button(bottom, text="Редагувати", command=self.load_selected).pack(side="left")
        ttk.Button(bottom, text="Видалити", command=self.delete_selected).pack(side="left", padx=6)
        ttk.Button(bottom, text="Звіт за період", command=self.show_report).pack(side="left", padx=6)
        ttk.Button(bottom, text="Друк журналу", command=self.print_journal).pack(side="left", padx=6)
        ttk.Button(bottom, text="Змінити пароль", command=self.change_password).pack(side="left", padx=6)
        ttk.Button(bottom, text="Резервна копія", command=self.backup_db).pack(side="right")
        ttk.Button(bottom, text="Експорт Excel / CSV", command=self.export_records).pack(side="right", padx=7)
        ttk.Label(outer, text=f"Локальна база даних: {DB_PATH}", style="Sub.TLabel").pack(anchor="w", pady=(8, 0))

    def parse_date(self, value):
        try: return datetime.strptime(value.strip(), "%d.%m.%Y").date().isoformat()
        except ValueError: raise ValueError("Введіть дату у форматі ДД.ММ.РРРР, наприклад 16.11.2026.")

    def save_record(self):
        pib, number = self.pib_var.get().strip(), self.number_var.get().strip()
        if not pib or not number:
            messagebox.showwarning("Не заповнено", "Заповніть ПІБ та номер витягу."); return
        try: d = self.parse_date(self.date_var.get())
        except ValueError as e: messagebox.showerror("Невірна дата", str(e)); return
        try:
            if self.selected_id is None:
                self.conn.execute("INSERT INTO records(pib,issue_date,extract_number,created_at) VALUES(?,?,?,?)",
                                  (pib,d,number,datetime.now().isoformat(timespec="seconds")))
            else:
                self.conn.execute("UPDATE records SET pib=?,issue_date=?,extract_number=? WHERE id=?",
                                  (pib,d,number,self.selected_id))
            self.conn.commit()
        except sqlite3.IntegrityError:
            messagebox.showerror("Дублікат", "Такий номер витягу вже зареєстрований."); return
        self.clear_form(); self.refresh()

    def clear_form(self):
        self.selected_id = None
        self.pib_var.set(""); self.date_var.set(date.today().strftime("%d.%m.%Y")); self.number_var.set("")

    def selected_record(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Запис не вибрано", "Виберіть запис у таблиці."); return None
        return self.conn.execute("SELECT id,pib,issue_date,extract_number FROM records WHERE id=?", (int(sel[0]),)).fetchone()

    def load_selected(self):
        r = self.selected_record()
        if not r: return
        self.selected_id = r[0]; self.pib_var.set(r[1])
        self.date_var.set(datetime.strptime(r[2], "%Y-%m-%d").strftime("%d.%m.%Y")); self.number_var.set(r[3])

    def delete_selected(self):
        r = self.selected_record()
        if not r: return
        if messagebox.askyesno("Підтвердження", f"Видалити запис для «{r[1]}»?"):
            self.conn.execute("DELETE FROM records WHERE id=?", (r[0],)); self.conn.commit()
            self.clear_form(); self.refresh()

    def current_rows(self):
        sql = "SELECT id,pib,issue_date,extract_number FROM records WHERE 1=1"; args=[]
        term = self.search_var.get().strip()
        if term: sql += " AND (pib LIKE ? OR extract_number LIKE ?)"; args += [f"%{term}%",f"%{term}%"]
        year = self.year_var.get()
        if year and year != "Усі": sql += " AND substr(issue_date,1,4)=?"; args.append(year)
        month = self.month_combo.current()
        if month > 0: sql += " AND substr(issue_date,6,2)=?"; args.append(f"{month:02d}")
        sql += " ORDER BY issue_date DESC,id DESC"
        return self.conn.execute(sql,args).fetchall()

    def refresh(self):
        years = [r[0] for r in self.conn.execute("SELECT DISTINCT substr(issue_date,1,4) FROM records ORDER BY 1 DESC")]
        vals = ["Усі"] + years
        self.year_combo["values"] = vals
        if self.year_var.get() not in vals: self.year_var.set("Усі")
        for i in self.tree.get_children(): self.tree.delete(i)
        rows = self.current_rows()
        for r in rows:
            d = datetime.strptime(r[2], "%Y-%m-%d").strftime("%d.%m.%Y")
            self.tree.insert("", "end", iid=str(r[0]), values=(r[1],d,r[3]))
        total = self.conn.execute("SELECT COUNT(*) FROM records").fetchone()[0]
        ym = date.today().strftime("%Y-%m")
        count = self.conn.execute("SELECT COUNT(*) FROM records WHERE substr(issue_date,1,7)=?",(ym,)).fetchone()[0]
        self.total_var.set(f"Усього видано: {total}")
        self.month_var.set(f"За поточний місяць: {count}")

    def reset_filters(self):
        self.search_var.set(""); self.year_var.set("Усі"); self.month_var_filter.set("Усі"); self.refresh()

    def export_records(self):
        rows = self.current_rows()
        if not rows: messagebox.showinfo("Експорт","Немає записів для експорту."); return
        path = filedialog.asksaveasfilename(defaultextension=".xlsx",filetypes=[("Excel","*.xlsx"),("CSV UTF-8","*.csv")])
        if not path: return
        data = [(r[1],datetime.strptime(r[2],"%Y-%m-%d").strftime("%d.%m.%Y"),r[3]) for r in rows]
        if path.lower().endswith(".csv"):
            with open(path,"w",newline="",encoding="utf-8-sig") as f:
                w=csv.writer(f,delimiter=";"); w.writerow(["ПІБ","Дата видачі","Номер витягу"]); w.writerows(data)
        else:
            try:
                from openpyxl import Workbook
                from openpyxl.styles import Font, PatternFill, Alignment
                wb=Workbook(); ws=wb.active; ws.title="Журнал видачі"
                ws.append(["ПІБ","Дата видачі","Номер витягу"])
                for row in data: ws.append(row)
                for c in ws[1]:
                    c.font=Font(bold=True,color="FFFFFF"); c.fill=PatternFill("solid",fgColor="244062")
                    c.alignment=Alignment(horizontal="center")
                ws.column_dimensions["A"].width=42; ws.column_dimensions["B"].width=18; ws.column_dimensions["C"].width=22
                ws.freeze_panes="A2"; ws.auto_filter.ref=ws.dimensions; wb.save(path)
            except ImportError:
                messagebox.showerror("Експорт","Для XLSX встановіть openpyxl. Або виберіть CSV."); return
        messagebox.showinfo("Готово",f"Файл збережено:\n{path}")

    def show_report(self):
        rows = self.current_rows()
        by_month = {}
        by_year = {}
        for r in rows:
            y,m = r[2][:4],r[2][5:7]
            by_month[(y,m)] = by_month.get((y,m),0)+1
            by_year[y] = by_year.get(y,0)+1
        win=tk.Toplevel(self.root); win.title("Звіт про видачу витягів"); win.geometry("520x500")
        ttk.Label(win,text=f"Кількість записів у вибірці: {len(rows)}",font=("Segoe UI",12,"bold")).pack(anchor="w",padx=14,pady=12)
        tree=ttk.Treeview(win,columns=("period","count"),show="headings")
        tree.heading("period",text="Період"); tree.heading("count",text="Кількість")
        tree.column("period",width=300); tree.column("count",width=120,anchor="center")
        tree.pack(fill="both",expand=True,padx=14,pady=(0,14))
        months=["Січень","Лютий","Березень","Квітень","Травень","Червень","Липень","Серпень","Вересень","Жовтень","Листопад","Грудень"]
        for y,n in sorted(by_year.items(),reverse=True): tree.insert("","end",values=(f"Усього за {y} рік",n))
        for (y,m),n in sorted(by_month.items(),reverse=True): tree.insert("","end",values=(f"{months[int(m)-1]} {y}",n))

    def print_journal(self):
        rows = self.current_rows()
        if not rows: messagebox.showinfo("Друк","Немає записів для друку."); return
        body = "".join(
            f"<tr><td>{i}</td><td>{html.escape(r[1])}</td><td>{datetime.strptime(r[2],'%Y-%m-%d').strftime('%d.%m.%Y')}</td><td>{html.escape(r[3])}</td></tr>"
            for i,r in enumerate(rows,1))
        doc = f"""<!doctype html><html lang='uk'><meta charset='utf-8'><title>Журнал видачі витягів</title>
        <style>body{{font-family:Arial,sans-serif;margin:25px}}h2{{text-align:center}}table{{border-collapse:collapse;width:100%}}
        th,td{{border:1px solid #555;padding:7px;text-align:left}}th{{background:#eee}}@media print{{button{{display:none}}}}</style>
        <h2>ЖУРНАЛ ВИДАЧІ ВИТЯГІВ<br>З РЕЄСТРУ ТЕРИТОРІАЛЬНОЇ ГРОМАДИ</h2>
        <p>Сформовано: {date.today().strftime('%d.%m.%Y')} &nbsp; Кількість записів: {len(rows)}</p>
        <table><thead><tr><th>№</th><th>ПІБ</th><th>Дата видачі</th><th>Номер витягу</th></tr></thead><tbody>{body}</tbody></table>
        <p style='margin-top:35px'>Відповідальна особа: __________________________</p>
        <button onclick='window.print()'>Друкувати</button></html>"""
        path = app_data_dir() / "journal_print.html"
        path.write_text(doc,encoding="utf-8")
        webbrowser.open(path.as_uri())

    def change_password(self):
        old = simpledialog.askstring("Зміна пароля","Поточний пароль:",show="*")
        if old is None: return
        saved=self.get_setting("password_hash"); salt,digest=saved.split(":",1)
        check=hashlib.pbkdf2_hmac("sha256",old.encode(),salt.encode(),200000).hex()
        if not secrets.compare_digest(check,digest):
            messagebox.showerror("Помилка","Поточний пароль неправильний."); return
        p1=simpledialog.askstring("Новий пароль","Новий пароль (від 6 символів):",show="*")
        if p1 is None: return
        if len(p1)<6: messagebox.showwarning("Пароль","Пароль має містити щонайменше 6 символів."); return
        p2=simpledialog.askstring("Підтвердження","Повторіть новий пароль:",show="*")
        if p1!=p2: messagebox.showerror("Помилка","Паролі не збігаються."); return
        salt=secrets.token_hex(16); digest=hashlib.pbkdf2_hmac("sha256",p1.encode(),salt.encode(),200000).hex()
        self.set_setting("password_hash",salt+":"+digest)
        messagebox.showinfo("Готово","Пароль успішно змінено.")

    def backup_db(self):
        path=filedialog.asksaveasfilename(defaultextension=".db",filetypes=[("SQLite database","*.db")])
        if not path: return
        dest=sqlite3.connect(path)
        try: self.conn.backup(dest)
        finally: dest.close()
        messagebox.showinfo("Резервна копія","Резервну копію створено.")

    def close(self):
        self.conn.close(); self.root.destroy()

if __name__=="__main__":
    root=tk.Tk(); app=VytyahApp(root)
    if root.winfo_exists():
        root.protocol("WM_DELETE_WINDOW",app.close)
        root.mainloop()
