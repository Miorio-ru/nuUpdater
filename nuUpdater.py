import tkinter as tk
from tkinter import messagebox, scrolledtext, ttk, filedialog
import threading
import requests
import time
import os
import json

# ==========================
# КОНСТАНТЫ ПРИЛОЖЕНИЯ
# ==========================
APP_NAME = "nuUpdater"
APP_VERSION = "1.1"

# Папка для настроек: C:\Users\ИМЯ\Documents\nuUpdater
USER_DOCS_DIR = os.path.join(os.path.expanduser("~"), "Documents", "nuUpdater")
os.makedirs(USER_DOCS_DIR, exist_ok=True)

SETTINGS_FILE = os.path.join(USER_DOCS_DIR, "nuUpdaterSettings.json")

# ==========================
# СПУТНИКИ ПО УМОЛЧАНИЮ
# ==========================
DEFAULT_SATELLITES = [
    {
        "name": "NOAA 20",
        "url": "https://celestrak.org/NORAD/elements/gp.php?CATNR=43013&FORMAT=TLE",
    },
    {
        "name": "SUOMI NPP",
        "url": "https://celestrak.org/NORAD/elements/gp.php?CATNR=37849&FORMAT=TLE",
    },
    {
        "name": "AQUA",
        "url": "https://celestrak.org/NORAD/elements/gp.php?CATNR=27424&FORMAT=TLE",
    },
]


class NuUpdaterApp(tk.Tk):
    def __init__(self):
        super().__init__()

        # ---- ОКНО ----
        # Пытаемся установить иконку nuUpdater.ico из той же папки, где лежит скрипт/exe
        try:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            icon_path = os.path.join(base_dir, "nuUpdater.ico")
            if os.path.exists(icon_path):
                self.iconbitmap(icon_path)
        except Exception:
            pass

        self.title(f"{APP_NAME} v{APP_VERSION} by MioRio")
        self.geometry("450x700")
        self.resizable(False, False)

        # Состояния
        self.is_downloading = False
        self.auto_running = False
        self.interval_seconds = 0
        self.next_run_in = 0
        self.timer_job = None

        # Файл вывода
        self.output_filename = "nu.txt"

        # Список спутников
        self.satellites = []

        # Настройки для инициализации GUI
        self.interval_value_setting = None
        self.interval_unit_setting = None
        self.selected_sats_setting = None
        self.skip_file_dialog = False

        # Загружаем настройки (включая спутники)
        self.load_settings()

        # Если файл вывода не выбран/не найден — спросить
        if not self.skip_file_dialog:
            self.choose_output_file_on_start()

        # Собираем GUI
        self.create_widgets()

        # Применяем настройки в интерфейс
        self.apply_settings_to_gui()

        # Меню "Справка → О программе"
        self.create_menubar()

        # Сохраняем настройки (на случай нового пути к файлу)
        self.save_settings()

    # ==========================
    # МЕНЮ
    # ==========================
    def create_menubar(self):
        menubar = tk.Menu(self)

        # Меню "Справка"
        helpmenu = tk.Menu(menubar, tearoff=0)
        helpmenu.add_command(label="О программе", command=self.show_about)

        menubar.add_cascade(label="Справка", menu=helpmenu)

        self.config(menu=menubar)

    def show_about(self):
        text = (
            f"{APP_NAME} v{APP_VERSION}\n\n by MioRio. 2025\n"
            "Программа обновляет TLE-данные спутников с сайта Celestrak\n"
            "и сохраняет их в выбранный файл (обычно nu.txt).\n\n"
            f"Файл настроек:\n{SETTINGS_FILE}"
        )
        messagebox.showinfo("О программе", text)

    # ==========================
    # ЗАГРУЗКА/СОХРАНЕНИЕ НАСТРОЕК
    # ==========================
    def load_settings(self):
        """Загрузить настройки из SETTINGS_FILE, если есть."""
        if not os.path.exists(SETTINGS_FILE):
            self.satellites = DEFAULT_SATELLITES.copy()
            return

        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            self.satellites = DEFAULT_SATELLITES.copy()
            return

        # Файл вывода
        out = data.get("output_filename")
        if out and isinstance(out, str) and os.path.exists(out):
            self.output_filename = out
            self.skip_file_dialog = True

        # Интервал
        interval_value = data.get("interval_value")
        interval_unit = data.get("interval_unit")
        if isinstance(interval_value, (int, float, str)):
            self.interval_value_setting = str(interval_value)
        if interval_unit in ("секунд", "минут", "часов"):
            self.interval_unit_setting = interval_unit

        # Спутники
        satellites_data = data.get("satellites")
        if isinstance(satellites_data, list):
            sats = []
            for item in satellites_data:
                name = item.get("name")
                url = item.get("url")
                if isinstance(name, str) and isinstance(url, str):
                    sats.append({"name": name, "url": url})
            if sats:
                self.satellites = sats

        if not self.satellites:
            self.satellites = DEFAULT_SATELLITES.copy()

        # Выбранные спутники
        selected_sats = data.get("selected_sats")
        if isinstance(selected_sats, list):
            self.selected_sats_setting = set(selected_sats)

    def save_settings(self):
        """Сохранить настройки в SETTINGS_FILE (Documents\\nuUpdater)."""
        try:
            selected_sats = []
            if hasattr(self, "sat_vars"):
                selected_sats = [name for name, var in self.sat_vars.items() if var.get()]

            data = {
                "output_filename": self.output_filename,
                "interval_value": self.entry_interval.get() if hasattr(self, "entry_interval") else "",
                "interval_unit": self.interval_unit.get() if hasattr(self, "interval_unit") else "минут",
                "selected_sats": selected_sats,
                "satellites": self.satellites,
            }
            with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    # ==========================
    # ВЫБОР ФАЙЛА ПРИ ЗАПУСКЕ
    # ==========================
    def choose_output_file_on_start(self):
        """При запуске спрашиваем файл nu.txt (с возможностью создать)."""
        while True:
            path = filedialog.asksaveasfilename(
                parent=self,
                title="Выберите файл nu.txt",
                initialfile="nu.txt",
                defaultextension=".txt",
                filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
            )

            if not path:
                use_default = messagebox.askyesno(
                    "Файл по умолчанию",
                    "Файл не выбран.\nИспользовать nu.txt в папке программы?"
                )
                if use_default:
                    path = "nu.txt"
                else:
                    continue

            if os.path.exists(path):
                self.output_filename = path
                break
            else:
                create = messagebox.askyesno(
                    "Файл не найден",
                    f"Файл:\n{path}\nне существует.\n\nСоздать его?"
                )
                if create:
                    try:
                        with open(path, "w", encoding="utf-8") as f:
                            f.write("")
                        self.output_filename = path
                        break
                    except OSError as e:
                        messagebox.showerror(
                            "Ошибка",
                            f"Не удалось создать файл:\n{e}\n\nПопробуйте выбрать другой путь."
                        )
                        continue
                else:
                    continue

    # ==========================
    # GUI
    # ==========================
    def create_widgets(self):
        # Описание
        top_frame = tk.Frame(self, padx=10, pady=10)
        top_frame.pack(fill=tk.X)

        desc = (

            "Выберите спутники, задайте интервал и нажмите Старт."
        )
        tk.Label(top_frame, text=desc, justify="left").pack(anchor="w")

        # ---- Спутники ----
        sats_frame = tk.LabelFrame(self, text="Спутники", padx=10, pady=10)
        sats_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

        self.sats_checks_frame = tk.Frame(sats_frame)
        self.sats_checks_frame.pack(fill=tk.X)

        self.sat_vars = {}
        self.build_sat_checkbuttons()

        # Кнопки выбора
        btn_sel_frame = tk.Frame(sats_frame)
        btn_sel_frame.pack(fill=tk.X, pady=(5, 0))

        tk.Button(
            btn_sel_frame,
            text="Выбрать все",
            command=self.select_all_sats
        ).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 5))

        tk.Button(
            btn_sel_frame,
            text="Снять все",
            command=self.deselect_all_sats
        ).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(5, 0))

        # Управление списком спутников
        tk.Button(
            sats_frame,
            text="Управление списком спутников...",
            command=self.open_satellite_manager
        ).pack(anchor="w", pady=(8, 0))

        # ---- Файл вывода ----
        file_frame = tk.Frame(self, padx=10, pady=5)
        file_frame.pack(fill=tk.X)

        tk.Label(file_frame, text="Файл для записи данных:").pack(anchor="w")
        self.lbl_output = tk.Label(file_frame, text=self.output_filename, fg="blue")
        self.lbl_output.pack(anchor="w")

        tk.Button(
            file_frame,
            text="Файл...",
            command=self.change_output_file
        ).pack(anchor="w", pady=(5, 0))

        # ---- Интервал ----
        interval_frame = tk.LabelFrame(self, text="Интервал автообновления", padx=10, pady=10)
        interval_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

        tk.Label(interval_frame, text="Каждые:").grid(row=0, column=0, sticky="w")

        self.entry_interval = tk.Entry(interval_frame, width=6)
        self.entry_interval.insert(0, "10")
        self.entry_interval.grid(row=0, column=1, sticky="w", padx=(5, 5))

        self.interval_unit = tk.StringVar(value="минут")
        combo = ttk.Combobox(
            interval_frame,
            textvariable=self.interval_unit,
            values=["секунд", "минут", "часов"],
            state="readonly",
            width=8
        )
        combo.grid(row=0, column=2, sticky="w")

        # ---- Старт/Стоп + Обновить сейчас ----
        control_frame = tk.Frame(self, padx=10, pady=10)
        control_frame.pack(fill=tk.X)

        self.btn_start_stop = tk.Button(
            control_frame,
            text="Старт автообновления",
            command=self.toggle_auto
        )
        self.btn_start_stop.pack(fill=tk.X)

        tk.Button(
            control_frame,
            text="Обновить сейчас (разово)",
            command=self.start_manual_download
        ).pack(fill=tk.X, pady=(5, 0))

        # ---- Статус ----
        status_frame = tk.LabelFrame(self, text="Статус", padx=10, pady=10)
        status_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

        self.indicator_canvas = tk.Canvas(status_frame, width=20, height=20, highlightthickness=0)
        self.indicator_canvas.grid(row=0, column=0, rowspan=2, padx=(0, 10))
        self.indicator_id = self.indicator_canvas.create_oval(2, 2, 18, 18, fill="gray", outline="black")

        self.lbl_status = tk.Label(status_frame, text="Остановлено", fg="gray")
        self.lbl_status.grid(row=0, column=1, sticky="w")

        self.lbl_timer = tk.Label(status_frame, text="До следующего обновления: —")
        self.lbl_timer.grid(row=1, column=1, sticky="w")

        # ---- Лог ----
        log_frame = tk.LabelFrame(self, text="Лог", padx=10, pady=10)
        log_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        self.log_text = scrolledtext.ScrolledText(log_frame, wrap=tk.WORD, state="disabled")
        self.log_text.pack(fill=tk.BOTH, expand=True)

        self.set_indicator("gray", "Остановлено")

    def apply_settings_to_gui(self):
        if hasattr(self, "lbl_output"):
            self.lbl_output.config(text=self.output_filename)

        if self.interval_value_setting is not None:
            self.entry_interval.delete(0, tk.END)
            self.entry_interval.insert(0, self.interval_value_setting)
        if self.interval_unit_setting is not None:
            self.interval_unit.set(self.interval_unit_setting)

        if self.selected_sats_setting is not None and hasattr(self, "sat_vars"):
            for name, var in self.sat_vars.items():
                var.set(name in self.selected_sats_setting)

    # ==========================
    # УПРАВЛЕНИЕ СПУТНИКАМИ
    # ==========================
    def build_sat_checkbuttons(self, selected_names=None):
        if selected_names is None and hasattr(self, "sat_vars"):
            selected_names = {name for name, var in self.sat_vars.items() if var.get()}
        elif selected_names is None:
            selected_names = set()

        for child in self.sats_checks_frame.winfo_children():
            child.destroy()

        self.sat_vars = {}
        for sat in self.satellites:
            name = sat["name"]
            var = tk.BooleanVar(value=(name in selected_names or not selected_names))
            chk = tk.Checkbutton(self.sats_checks_frame, text=name, variable=var)
            chk.pack(anchor="w")
            self.sat_vars[name] = var

    def open_satellite_manager(self):
        win = tk.Toplevel(self)
        win.title("Управление спутниками")
        win.resizable(False, False)
        win.grab_set()
        win.transient(self)

        main_frame = tk.Frame(win, padx=10, pady=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Список
        left_frame = tk.Frame(main_frame)
        left_frame.grid(row=0, column=0, sticky="nsw")

        tk.Label(left_frame, text="Список спутников:").pack(anchor="w")

        lb = tk.Listbox(left_frame, height=10, width=30)
        lb.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        for sat in self.satellites:
            lb.insert(tk.END, sat["name"])

        scroll = tk.Scrollbar(left_frame, command=lb.yview)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        lb.config(yscrollcommand=scroll.set)

        # Редактирование
        right_frame = tk.Frame(main_frame, padx=10)
        right_frame.grid(row=0, column=1, sticky="nsew")

        tk.Label(right_frame, text="Название:").grid(row=0, column=0, sticky="w")
        entry_name = tk.Entry(right_frame, width=40)
        entry_name.grid(row=0, column=1, sticky="w")

        tk.Label(right_frame, text="URL:").grid(row=1, column=0, sticky="w", pady=(5, 0))
        entry_url = tk.Entry(right_frame, width=40)
        entry_url.grid(row=1, column=1, sticky="w", pady=(5, 0))

        btn_frame = tk.Frame(right_frame, pady=10)
        btn_frame.grid(row=2, column=0, columnspan=2, sticky="w")

        def on_select(event=None):
            idxs = lb.curselection()
            if not idxs:
                return
            idx = idxs[0]
            sat = self.satellites[idx]
            entry_name.delete(0, tk.END)
            entry_name.insert(0, sat["name"])
            entry_url.delete(0, tk.END)
            entry_url.insert(0, sat["url"])

        lb.bind("<<ListboxSelect>>", on_select)

        def add_satellite():
            name = entry_name.get().strip()
            url = entry_url.get().strip()
            if not name or not url:
                messagebox.showerror("Ошибка", "Введите название и URL спутника.")
                return
            self.satellites.append({"name": name, "url": url})
            lb.insert(tk.END, name)
            entry_name.delete(0, tk.END)
            entry_url.delete(0, tk.END)
            self.log(f"Добавлен спутник: {name}")
            self.save_settings()

        def save_satellite():
            idxs = lb.curselection()
            if not idxs:
                messagebox.showinfo("Информация", "Выберите спутник в списке слева.")
                return
            idx = idxs[0]
            name = entry_name.get().strip()
            url = entry_url.get().strip()
            if not name or not url:
                messagebox.showerror("Ошибка", "Название и URL не могут быть пустыми.")
                return
            self.satellites[idx] = {"name": name, "url": url}
            lb.delete(idx)
            lb.insert(idx, name)
            self.log(f"Изменён спутник: {name}")
            self.save_settings()

        def delete_satellite():
            idxs = lb.curselection()
            if not idxs:
                messagebox.showinfo("Информация", "Выберите спутник для удаления.")
                return
            idx = idxs[0]
            sat = self.satellites[idx]
            ok = messagebox.askyesno(
                "Подтверждение",
                f"Удалить спутник:\n{sat['name']}?"
            )
            if not ok:
                return
            self.log(f"Удалён спутник: {sat['name']}")
            del self.satellites[idx]
            lb.delete(idx)
            entry_name.delete(0, tk.END)
            entry_url.delete(0, tk.END)
            self.save_settings()

        tk.Button(btn_frame, text="Добавить как новый", command=add_satellite).grid(row=0, column=0, sticky="w")
        tk.Button(btn_frame, text="Сохранить изменения", command=save_satellite).grid(row=0, column=1, sticky="w", padx=(5, 0))
        tk.Button(btn_frame, text="Удалить", command=delete_satellite).grid(row=0, column=2, sticky="w", padx=(5, 0))

        def on_close():
            self.build_sat_checkbuttons()
            self.save_settings()
            win.destroy()

        tk.Button(right_frame, text="Закрыть", command=on_close).grid(row=3, column=0, columnspan=2, pady=(5, 0))

        win.protocol("WM_DELETE_WINDOW", on_close)

    def change_output_file(self):
        path = filedialog.asksaveasfilename(
            parent=self,
            title="Выберите файл nu.txt",
            initialfile=os.path.basename(self.output_filename),
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
        )

        if not path:
            return

        if not os.path.exists(path):
            create = messagebox.askyesno(
                "Создать файл?",
                f"Файл:\n{path}\nне существует.\nСоздать его?"
            )
            if create:
                try:
                    with open(path, "w", encoding="utf-8") as f:
                        f.write("")
                except Exception as e:
                    messagebox.showerror("Ошибка", f"Не удалось создать файл:\n{e}")
                    return
            else:
                return

        self.output_filename = path
        self.lbl_output.config(text=self.output_filename)
        self.log(f"Выбран новый файл: {self.output_filename}")
        self.save_settings()

    # ==========================
    # ВСПОМОГАТЕЛЬНЫЕ МЕТОДЫ GUI
    # ==========================
    def select_all_sats(self):
        for var in self.sat_vars.values():
            var.set(True)
        self.save_settings()

    def deselect_all_sats(self):
        for var in self.sat_vars.values():
            var.set(False)
        self.save_settings()

    def log(self, msg: str):
        self.log_text.config(state="normal")
        timestamp = time.strftime("%H:%M:%S")
        self.log_text.insert(tk.END, f"[{timestamp}] {msg}\n")
        self.log_text.see(tk.END)
        self.log_text.config(state="disabled")

    def set_indicator(self, color: str, text: str, text_color: str = None):
        if text_color is None:
            text_color = "black"
        self.indicator_canvas.itemconfig(self.indicator_id, fill=color)
        self.lbl_status.config(text=text, fg=text_color)

    def set_timer_label(self):
        if not self.auto_running or self.interval_seconds == 0:
            self.lbl_timer.config(text="До следующего обновления: —")
            return

        if self.next_run_in <= 0:
            self.lbl_timer.config(text="До следующего обновления: сейчас")
        else:
            s = self.next_run_in
            h = s // 3600
            s %= 3600
            m = s // 60
            s %= 60
            if h > 0:
                txt = f"{h:02d}:{m:02d}:{s:02d}"
            else:
                txt = f"{m:02d}:{s:02d}"
            self.lbl_timer.config(text=f"До следующего обновления: {txt}")

    # ==========================
    # АВТООБНОВЛЕНИЕ
    # ==========================
    def toggle_auto(self):
        if self.auto_running:
            self.auto_running = False
            self.btn_start_stop.config(text="Старт автообновления")
            self.set_indicator("gray", "Остановлено", "gray")
            self.next_run_in = 0
            self.set_timer_label()
            if self.timer_job is not None:
                self.after_cancel(self.timer_job)
                self.timer_job = None
            self.log("Автообновление остановлено.")
            self.save_settings()
        else:
            try:
                val = float(self.entry_interval.get().replace(",", "."))
            except ValueError:
                messagebox.showerror("Ошибка", "Некорректный интервал.")
                return

            if val <= 0:
                messagebox.showerror("Ошибка", "Интервал должен быть больше нуля.")
                return

            unit = self.interval_unit.get()
            seconds = val
            if unit == "минут":
                seconds = val * 60
            elif unit == "часов":
                seconds = val * 3600

            self.interval_seconds = int(seconds)
            if self.interval_seconds <= 0:
                messagebox.showerror("Ошибка", "Слишком маленький интервал.")
                return

            selected_sats = [name for name, var in self.sat_vars.items() if var.get()]
            if not selected_sats:
                messagebox.showerror("Ошибка", "Не выбрано ни одного спутника.")
                return

            self.auto_running = True
            self.btn_start_stop.config(text="Стоп автообновления")
            self.set_indicator("green", "Автообновление включено", "green")
            self.log(f"Автообновление запущено. Интервал: {val} {unit}.")
            self.next_run_in = 0
            self.set_timer_label()
            self.save_settings()
            self.schedule_timer_tick()

    def schedule_timer_tick(self):
        if not self.auto_running:
            return

        if not self.is_downloading and self.next_run_in <= 0:
            self.start_auto_download()
        else:
            if self.next_run_in > 0:
                self.next_run_in -= 1
                if self.next_run_in < 0:
                    self.next_run_in = 0
            self.set_timer_label()

        self.timer_job = self.after(1000, self.schedule_timer_tick)

    # ==========================
    # ЗАПУСК ЗАГРУЗОК
    # ==========================
    def start_manual_download(self):
        if self.is_downloading:
            messagebox.showinfo("Информация", "Загрузка уже выполняется.")
            return

        selected_sats = [name for name, var in self.sat_vars.items() if var.get()]
        if not selected_sats:
            messagebox.showerror("Ошибка", "Не выбрано ни одного спутника.")
            return

        self.log("Ручное обновление TLE-данных.")
        self.run_download(selected_sats, is_manual=True)

    def start_auto_download(self):
        if self.is_downloading:
            return
        selected_sats = [name for name, var in self.sat_vars.items() if var.get()]
        if not selected_sats:
            self.log("Автообновление: нет выбранных спутников, пропуск.")
            self.next_run_in = self.interval_seconds
            self.set_timer_label()
            return

        self.log("Автообновление TLE-данных.")
        self.run_download(selected_sats, is_manual=False)

    def run_download(self, selected_sats, is_manual: bool):
        if self.is_downloading:
            return

        self.is_downloading = True
        self.set_indicator("yellow", "Загрузка данных...", "orange")

        def worker():
            cooldown = self.download_tles(selected_sats, is_manual)
            self.is_downloading = False

            if self.auto_running and not is_manual:
                if cooldown and cooldown > 0:
                    self.next_run_in = cooldown
                    self.after(0, self.set_timer_label)
                    self.after(
                        0,
                        lambda: self.set_indicator(
                            "yellow",
                            "Пауза 2 часа (ошибка сайта)",
                            "orange"
                        )
                    )
                else:
                    self.next_run_in = self.interval_seconds
                    self.after(0, self.set_timer_label)
                    self.after(
                        0,
                        lambda: self.set_indicator(
                            "green",
                            "Автообновление включено",
                            "green"
                        )
                    )
            else:
                if not self.auto_running:
                    self.after(
                        0,
                        lambda: self.set_indicator("gray", "Остановлено", "gray")
                    )
                else:
                    self.after(
                        0,
                        lambda: self.set_indicator("green", "Автообновление включено", "green")
                    )

        t = threading.Thread(target=worker, daemon=True)
        t.start()

    # ==========================
    # ЗАГРУЗКА TLE
    # ==========================
    def download_tles(self, selected_sats, is_manual: bool):
        """
        Возвращает:
            cooldown_seconds: 0 или 2*60*60 (при 403/таймауте).
        """
        blocks = []
        success_count = 0
        cooldown_seconds = 0
        had_403_or_timeout = False

        def get_url_by_name(name):
            for sat in self.satellites:
                if sat["name"] == name:
                    return sat["url"]
            return None

        for sat_name in selected_sats:
            url = get_url_by_name(sat_name)
            if not url:
                self.after(0, lambda name=sat_name: self.log(f"URL для {name} не найден."))
                continue

            self.after(0, lambda name=sat_name: self.log(f"Получение данных для: {name}"))

            try:
                resp = requests.get(url, timeout=20)
                try:
                    resp.raise_for_status()
                except requests.exceptions.HTTPError as http_err:
                    if resp.status_code == 403:
                        had_403_or_timeout = True
                    raise http_err

                raw_text = resp.text

                lines = []
                for ln in raw_text.splitlines():
                    clean_ln = ln.strip()
                    if not clean_ln:
                        continue
                    lines.append(clean_ln)

                if not lines:
                    self.after(0, lambda name=sat_name: self.log(f"  ⚠ Пустой ответ от сервера для {name}."))
                    continue

                clean_text = "\n".join(lines)
                blocks.append(clean_text)
                success_count += 1

                self.after(0, lambda name=sat_name, ln=len(clean_text):
                           self.log(f"  ✔ {name}: получено {ln} символов (после очистки)."))

            except (requests.exceptions.ConnectTimeout,
                    requests.exceptions.ReadTimeout,
                    requests.exceptions.Timeout) as e:
                had_403_or_timeout = True
                self.after(0, lambda name=sat_name, err=e:
                           self.log(f"  ✖ Таймаут при получении {name}: {err}"))

            except requests.exceptions.RequestException as e:
                self.after(0, lambda name=sat_name, err=e:
                           self.log(f"  ✖ Ошибка при получении {name}: {err}"))

        if self.auto_running and not is_manual and had_403_or_timeout:
            cooldown_seconds = 2 * 60 * 60
            self.after(
                0,
                lambda: self.log("Обнаружен 403 или таймаут. Автообновление приостановлено на 2 часа.")
            )

        if success_count > 0 and blocks:
            try:
                final_text = "\n".join(blocks) + "\n"
                with open(self.output_filename, "w", encoding="utf-8") as f:
                    f.write(final_text)
                self.after(0, lambda: self.log(f"Данные записаны в файл {self.output_filename}"))
                if is_manual:
                    self.after(0, lambda: messagebox.showinfo("Готово", f"Данные записаны в\n{self.output_filename}"))
            except OSError as e:
                self.after(0, lambda: self.log(f"✖ Ошибка записи файла {self.output_filename}: {e}"))
                self.after(0, lambda: messagebox.showerror("Ошибка", f"Не удалось записать файл:\n{e}"))
        else:
            self.after(0, lambda: self.log("Не удалось получить данные ни для одного спутника."))
            if is_manual:
                self.after(0, lambda: messagebox.showwarning(
                    "Предупреждение",
                    "Нет данных для записи.\nПроверь подключение к интернету или URL."
                ))

        self.after(0, self.save_settings)
        return cooldown_seconds


# ==========================
# СПЛЭШ-СКРИН И ЗАПУСК ПРИЛОЖЕНИЯ
# ==========================
def show_splash():
    """Простенький сплэш-скрин перед запуском главного окна."""
    splash = tk.Tk()
    splash.overrideredirect(True)  # без рамки и кнопок

    w, h = 300, 150
    sw = splash.winfo_screenwidth()
    sh = splash.winfo_screenheight()
    x = (sw - w) // 2
    y = (sh - h) // 2
    splash.geometry(f"{w}x{h}+{x}+{y}")

    frame = tk.Frame(splash, bg="#202840")
    frame.pack(fill="both", expand=True)

    lbl_title = tk.Label(
        frame,
        text=f"{APP_NAME} v{APP_VERSION}",
        fg="white",
        bg="#202840",
        font=("Segoe UI", 14, "bold")
    )
    lbl_title.pack(pady=(25, 5))

    lbl_text = tk.Label(
        frame,
        text="Загрузка...\nПодготовка интерфейса...",
        fg="white",
        bg="#202840",
        font=("Segoe UI", 10)
    )
    lbl_text.pack(pady=(0, 10))

    # Можно добавить маленький "индикатор"
    dot_label = tk.Label(frame, text="● ● ●", fg="lightgray", bg="#202840", font=("Segoe UI", 12))
    dot_label.pack()

    splash.after(3000, splash.destroy)  # сплэш живёт 1.5 секунды
    splash.mainloop()


if __name__ == "__main__":
    # Сплэш-скрин перед запуском основного окна
    show_splash()

    app = NuUpdaterApp()
    app.mainloop()
