import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from PIL import Image, ImageTk, ImageOps, ImageDraw, ImageEnhance
import numpy as np
import threading
import math
import json
import re
import csv
import time

# =================================================================================
# БЛОК ИМПОРТА REMBG (БЕЗОПАСНЫЙ РЕЖИМ)
# Мы оборачиваем импорт в try-except. Если библиотека сломана или не установлена,
# программа просто отключит функцию удаления фона, но продолжит работать.
# =================================================================================
REMBG_AVAILABLE = False
try:
    from rembg import remove as remove_bg
    REMBG_AVAILABLE = True
    print("[INFO] Библиотека rembg найдена. Удаление фона доступно.")
except Exception as e:
    print(f"[INFO] rembg недоступен ({e}). Программа запущена в базовом режиме.")
    REMBG_AVAILABLE = False

# =================================================================================
# UI: СКРОЛЛ-ПАНЕЛЬ
# Позволяет прокручивать боковую панель настроек, если экран маленький.
# =================================================================================
class ScrollableFrame(tk.Frame):
    def __init__(self, container, *args, **kwargs):
        super().__init__(container, *args, **kwargs)
        self.canvas = tk.Canvas(self, borderwidth=0, background="#f5f5f5")
        self.view = tk.Frame(self.canvas, background="#f5f5f5")
        self.vsb = tk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        
        self.canvas.configure(yscrollcommand=self.vsb.set)
        self.vsb.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)
        
        self.canvas_window = self.canvas.create_window((4,4), window=self.view, anchor="nw", tags="self.view")
        
        self.view.bind("<Configure>", self.on_frame_configure)
        self.canvas.bind("<Configure>", self.on_canvas_configure)
        self.view.bind_all("<MouseWheel>", self._on_mousewheel)

    def on_frame_configure(self, event):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))
    def on_canvas_configure(self, event):
        self.canvas.itemconfig(self.canvas_window, width=event.width)
    def _on_mousewheel(self, event):
        self.canvas.yview_scroll(int(-1*(event.delta/120)), "units")

# =================================================================================
# ОКНО ПРОСМОТРА ИНСТРУКЦИИ (ПЛЕЕР)
# =================================================================================
class InstructionPlayer(tk.Toplevel):
    def __init__(self, master, nails_count, sequence, title="Проверка инструкции"):
        super().__init__(master)
        self.title(title)
        self.geometry("850x950")
        
        self.nails_count = nails_count
        self.sequence = sequence
        self.is_playing = False
        
        # Панель управления плеером
        control_frame = tk.Frame(self, padx=10, pady=10, bg="#eee")
        control_frame.pack(side=tk.BOTTOM, fill=tk.X)
        
        self.slider_var = tk.IntVar(value=0)
        self.lbl_step = tk.Label(control_frame, text="Шаг: 0", bg="#eee", width=20, font=("Arial", 10, "bold"))
        self.lbl_step.pack(side=tk.RIGHT)
        
        self.slider = ttk.Scale(control_frame, from_=0, to=len(sequence), orient=tk.HORIZONTAL, variable=self.slider_var, command=self.on_slider_move)
        self.slider.pack(fill=tk.X, padx=5, pady=5)
        
        btn_frame = tk.Frame(control_frame, bg="#eee")
        btn_frame.pack(side=tk.LEFT)
        tk.Button(btn_frame, text="▶ START", command=self.play_animation, bg="#ccffcc", width=8).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="⏸ PAUSE", command=self.pause_animation, bg="#ffcccc", width=8).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="📂 Открыть файл...", command=self.load_external_file).pack(side=tk.LEFT, padx=20)

        # Холст плеера
        self.canvas_size = 800
        self.canvas = tk.Canvas(self, width=self.canvas_size, height=self.canvas_size, bg="white")
        self.canvas.pack(expand=True, pady=10)
        
        self.nails_coords = self._calculate_nails(self.canvas_size, self.nails_count)
        self.update_view(0)

    def _calculate_nails(self, size, count):
        cx, cy = size / 2, size / 2
        radius = size / 2 - 20
        coords = []
        for i in range(count):
            angle = 2 * math.pi * i / count
            x = cx + radius * math.cos(angle)
            y = cy + radius * math.sin(angle)
            coords.append((x, y))
        return coords

    def on_slider_move(self, val):
        step = int(float(val))
        self.lbl_step.config(text=f"Шаг: {step}/{len(self.sequence)}")
        self.update_view(step)

    def update_view(self, step):
        img = Image.new("RGB", (self.canvas_size, self.canvas_size), "white")
        draw = ImageDraw.Draw(img, "RGBA")
        if step > 1:
            current_seq = self.sequence[:step]
            line_points = [self.nails_coords[idx] for idx in current_seq if idx < len(self.nails_coords)]
            # Рисуем прозрачным черным (наложение)
            draw.line(line_points, fill=(0, 0, 0, 30), width=1)
            # Последняя линия красная
            if len(line_points) >= 2:
                draw.line([line_points[-2], line_points[-1]], fill="red", width=2)

        self.tk_img = ImageTk.PhotoImage(img)
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, image=self.tk_img, anchor="nw")
        
        if step > 0 and step <= len(self.sequence):
             curr_idx = self.sequence[step-1]
             if curr_idx < len(self.nails_coords):
                 cx, cy = self.nails_coords[curr_idx]
                 self.canvas.create_text(cx, cy, text=str(curr_idx), fill="red", font=("Arial", 12, "bold"))

    def play_animation(self):
        if self.is_playing: return
        self.is_playing = True
        def run():
            current = self.slider_var.get()
            total = len(self.sequence)
            while self.is_playing and current < total:
                current += 1
                self.slider_var.set(current)
                self.master.after(0, self.on_slider_move, current)
                time.sleep(0.01)
            self.is_playing = False
        threading.Thread(target=run, daemon=True).start()

    def pause_animation(self):
        self.is_playing = False

    def load_external_file(self):
        path = filedialog.askopenfilename(filetypes=[("Files", "*.txt;*.json;*.csv")])
        if not path: return
        seq, nails = [], 240
        try:
            if path.endswith(".json"):
                with open(path, "r") as f:
                    data = json.load(f)
                    nails = data.get("nails_count", 240)
                    seq = data.get("sequence", [])
            elif path.endswith(".csv"):
                with open(path, "r") as f:
                    reader = csv.reader(f)
                    rows = list(reader)
                    flat = []
                    for row in rows:
                        for c in row:
                            if c.isdigit(): flat.append(int(c))
                    seq = flat
            else: # TXT
                with open(path, "r", encoding='utf-8') as f:
                    c = f.read()
                    m = re.search(r"Гвозди:\s*(\d+)", c)
                    if m: nails = int(m.group(1))
                    seq = [int(s) for s in re.findall(r'\b\d+\b', c)]
                    if seq and seq[0] == nails: seq.pop(0)
            
            if not seq: raise ValueError("Данные не найдены")
            self.pause_animation()
            self.nails_count = nails
            self.sequence = seq
            self.nails_coords = self._calculate_nails(self.canvas_size, self.nails_count)
            self.slider.config(to=len(seq))
            self.slider_var.set(0)
            self.update_view(0)
            messagebox.showinfo("OK", f"Загружено {len(seq)} шагов.")
        except Exception as e:
            messagebox.showerror("Error", str(e))

# =================================================================================
# ГЛАВНЫЙ КЛАСС ПРИЛОЖЕНИЯ
# =================================================================================
class RingStringApp:
    def __init__(self, root):
        self.root = root
        self.root.title("RingString Master v7.0 (Improved Algorithm)")
        self.root.geometry("1400x950")

        # --- Данные ---
        self.original_image = None
        self.processed_image = None
        self.final_strings_pil = None
        
        # --- Настройки Фото ---
        self.brightness_var = tk.DoubleVar(value=1.0)
        self.contrast_var = tk.DoubleVar(value=1.0)
        self.scale_var = tk.DoubleVar(value=1.0)
        
        # --- Видимость ---
        self.show_original_var = tk.BooleanVar(value=True)
        self.bg_opacity_var = tk.DoubleVar(value=0.5)
        self.strings_opacity_var = tk.DoubleVar(value=1.0)
        
        # --- Параметры Алгоритма ---
        self.nails_count_var = tk.IntVar(value=240)
        self.lines_count_var = tk.IntVar(value=3000)
        self.calc_opacity_var = tk.IntVar(value=30) # "Вес" одной нити
        
        # --- Холст ---
        self.canvas_size = 750
        self.hoop_radius_var = tk.IntVar(value=340) # Радиус круга
        self.img_x = 0
        self.img_y = 0
        self.drag_data = {"x": 0, "y": 0}
        
        # --- Процесс ---
        self.is_generating = False
        self.stop_flag = False
        self.sequence = []

        self._init_ui()
        self.reset_canvas_position()

    def _init_ui(self):
        # Левая панель (Скролл)
        left_container = tk.Frame(self.root, width=420, bg="#f5f5f5")
        left_container.pack(side=tk.LEFT, fill=tk.Y)
        left_container.pack_propagate(False)

        self.scroll_frame = ScrollableFrame(left_container)
        self.scroll_frame.pack(fill="both", expand=True)
        content = self.scroll_frame.view
        
        # Кнопка СБРОС
        btn_reset = tk.Button(content, text="🔄 НОВЫЙ ПРОЕКТ (СБРОС)", command=self.reset_app, bg="#ff8a80", fg="white", font=("Arial", 10, "bold"))
        btn_reset.pack(fill=tk.X, padx=10, pady=(15, 15))

        # 1. Загрузка
        self._add_header(content, "1. Исходное изображение")
        tk.Button(content, text="📂 Загрузить фото", command=self.load_image, bg="#e1e1e1", height=2).pack(fill=tk.X, padx=10, pady=2)
        
        # Кнопка удаления фона (активна только если библиотека работает)
        if REMBG_AVAILABLE:
            tk.Button(content, text="✂️ Удалить фон (rembg)", command=self.remove_background, bg="#ffdddd").pack(fill=tk.X, padx=10, pady=2)
        else:
            tk.Button(content, text="⚠️ Удаление фона недоступно", state="disabled", bg="#eee").pack(fill=tk.X, padx=10, pady=2)
            
        tk.Button(content, text="🪄 Авто-контраст", command=self.auto_enhance, bg="#ddffdd").pack(fill=tk.X, padx=10, pady=2)

        # 2. Настройки фото
        self._add_header(content, "2. Настройка фото")
        self._create_slider(content, "Яркость", self.brightness_var, 0.1, 3.0, self.update_preview)
        self._create_slider(content, "Контраст", self.contrast_var, 0.5, 4.0, self.update_preview)
        self._create_slider(content, "Масштаб (Zoom)", self.scale_var, 0.2, 4.0, self.update_preview)
        
        tk.Label(content, text="Размер круга:", bg="#f5f5f5", font=("Arial", 9, "bold")).pack(anchor="w", padx=10, pady=(5,0))
        tk.Scale(content, from_=100, to=370, orient=tk.HORIZONTAL, variable=self.hoop_radius_var, command=lambda x: self.update_preview()).pack(fill=tk.X, padx=10)

        # 3. Настройки алгоритма
        self._add_header(content, "3. Настройки схемы")
        tk.Button(content, text="✨ Подобрать параметры", command=self.auto_calculate_params, bg="gold").pack(fill=tk.X, padx=10, pady=(0, 10))

        # Гвозди
        f_nails = tk.Frame(content, bg="#f5f5f5")
        f_nails.pack(fill=tk.X, padx=10)
        tk.Label(f_nails, text="Гвозди (шт):", bg="#f5f5f5").pack(side=tk.LEFT)
        tk.Entry(f_nails, textvariable=self.nails_count_var, width=6).pack(side=tk.RIGHT)
        tk.Scale(content, from_=100, to=360, orient=tk.HORIZONTAL, variable=self.nails_count_var).pack(fill=tk.X, padx=10)

        # Линии
        f_lines = tk.Frame(content, bg="#f5f5f5")
        f_lines.pack(fill=tk.X, padx=10, pady=(5,0))
        tk.Label(f_lines, text="Линии (шт):", bg="#f5f5f5").pack(side=tk.LEFT)
        tk.Entry(f_lines, textvariable=self.lines_count_var, width=6).pack(side=tk.RIGHT)
        tk.Scale(content, from_=1000, to=6000, orient=tk.HORIZONTAL, variable=self.lines_count_var).pack(fill=tk.X, padx=10)
        
        tk.Label(content, text="Плотность нити (при расчете):", bg="#f5f5f5").pack(anchor="w", padx=10)
        tk.Scale(content, from_=10, to=150, orient=tk.HORIZONTAL, variable=self.calc_opacity_var).pack(fill=tk.X, padx=10)

        # 4. Генерация
        self._add_header(content, "4. Генерация")
        f_gen = tk.Frame(content, bg="#f5f5f5")
        f_gen.pack(fill=tk.X, padx=10)
        tk.Button(f_gen, text="🚀 Быстро", command=lambda: self.start_generation(animate=False), bg="#b3e5fc", width=15).pack(side=tk.LEFT, padx=2)
        tk.Button(f_gen, text="🎬 Анимация", command=lambda: self.start_generation(animate=True), bg="#e1bee7", width=15).pack(side=tk.RIGHT, padx=2)
        
        tk.Button(content, text="⛔ СТОП", command=self.stop_generation, bg="#ffccbc").pack(fill=tk.X, padx=10, pady=5)
        tk.Button(content, text="🗑 Очистить нити", command=self.clear_strings_only, bg="#eee", fg="red").pack(fill=tk.X, padx=10, pady=2)
        
        tk.Label(content, text="Прогресс:", bg="#f5f5f5").pack(padx=10, pady=(5,0), anchor="w")
        self.progress = ttk.Progressbar(content, orient="horizontal", length=100, mode="determinate")
        self.progress.pack(fill=tk.X, padx=10, pady=2)

        # 5. Слои
        self._add_header(content, "5. Слои (Финал)")
        tk.Checkbutton(content, text="Показывать исходное фото", variable=self.show_original_var, command=self.update_layers_visibility, bg="#f5f5f5", anchor="w").pack(fill=tk.X, padx=10)
        
        tk.Label(content, text="Прозрачность ФОНА:", bg="#f5f5f5").pack(anchor="w", padx=10)
        tk.Scale(content, from_=0.0, to=1.0, resolution=0.05, orient=tk.HORIZONTAL, variable=self.bg_opacity_var, command=lambda x: self.update_layers_visibility()).pack(fill=tk.X, padx=10)

        tk.Label(content, text="Прозрачность НИТЕЙ:", bg="#f5f5f5").pack(anchor="w", padx=10)
        tk.Scale(content, from_=0.0, to=1.0, resolution=0.05, orient=tk.HORIZONTAL, variable=self.strings_opacity_var, command=lambda x: self.update_layers_visibility()).pack(fill=tk.X, padx=10)

        # 6. Экспорт
        self._add_header(content, "6. Сохранение")
        f_exp = tk.Frame(content, bg="#f5f5f5")
        f_exp.pack(fill=tk.X, padx=10, pady=5)
        tk.Button(f_exp, text="💾 Схема", command=self.save_instructions).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=1)
        tk.Button(f_exp, text="👁 Плеер", command=self.open_player_window).pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=1)

        tk.Label(content, text="Миниатюра (400x400):", bg="#f5f5f5", font=("Arial", 9, "bold")).pack(pady=(15,0))
        self.miniature_lbl = tk.Label(content, bg="white", width=400, height=400, relief="sunken")
        self.miniature_lbl.pack(pady=5, padx=10)
        self.empty_img = ImageTk.PhotoImage(Image.new("RGB", (400, 400), "#ddd"))
        self.miniature_lbl.config(image=self.empty_img)

        self.status_var = tk.StringVar(value="Готов к работе")
        tk.Label(content, textvariable=self.status_var, fg="blue", wraplength=350, bg="#f5f5f5").pack(pady=20)

        # Правая панель (Холст)
        right_panel = tk.Frame(self.root, bg="#333")
        right_panel.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        self.canvas = tk.Canvas(right_panel, width=self.canvas_size, height=self.canvas_size, bg="white", highlightthickness=0)
        self.canvas.pack(expand=True)
        
        self.canvas.bind("<ButtonPress-1>", self.on_drag_start)
        self.canvas.bind("<B1-Motion>", self.on_drag_motion)
        
        self._draw_base_structure()

    # --- UI Helpers ---
    def _add_header(self, parent, text):
        tk.Label(parent, text=text, font=("Arial", 11, "bold"), bg="#ddd", anchor="w", padx=5).pack(fill=tk.X, pady=(15, 5))

    def _create_slider(self, parent, label, var, mn, mx, cmd):
        f = tk.Frame(parent, bg="#f5f5f5")
        f.pack(fill=tk.X, padx=10)
        tk.Label(f, text=label, bg="#f5f5f5").pack(side=tk.LEFT)
        tk.Scale(parent, from_=mn, to=mx, resolution=0.1, orient=tk.HORIZONTAL, variable=var, command=lambda x: cmd()).pack(fill=tk.X, padx=10)

    def reset_canvas_position(self):
        self.img_x = self.canvas_size // 2
        self.img_y = self.canvas_size // 2

    def _draw_base_structure(self):
        # Рисуем круг и маску
        cx, cy = self.canvas_size // 2, self.canvas_size // 2
        r = self.hoop_radius_var.get()
        w = self.canvas_size
        
        self.canvas.delete("hoop_mask")
        self.canvas.delete("hoop_ring")
        self.canvas.delete("hoop_text")
        
        mask_width = (w/2 - r) + 150 
        self.canvas.create_oval(cx-r-mask_width/2, cy-r-mask_width/2, 
                                cx+r+mask_width/2, cy+r+mask_width/2, 
                                outline="white", width=mask_width, tags="hoop_mask")
        
        self.canvas.create_oval(cx-r, cy-r, cx+r, cy+r, outline="#ccc", width=3, tags="hoop_ring")
        self.canvas.create_text(cx, cy - r - 20, text="ОБЛАСТЬ ПОСТРОЕНИЯ", fill="#999", font=("Arial", 10), tags="hoop_text")
        
        self.canvas.tag_raise("hoop_mask")
        self.canvas.tag_raise("hoop_ring")
        self.canvas.tag_raise("hoop_text")

    # --- Функционал ---

    def reset_app(self):
        self.stop_flag = True
        self.is_generating = False
        self.original_image = None
        self.processed_image = None
        self.final_strings_pil = None
        self.sequence = []
        
        self.brightness_var.set(1.0)
        self.contrast_var.set(1.0)
        self.scale_var.set(1.0)
        self.hoop_radius_var.set(340)
        self.show_original_var.set(True)
        self.bg_opacity_var.set(0.5)
        self.strings_opacity_var.set(1.0)
        self.progress['value'] = 0
        
        self.canvas.delete("image_bg")
        self.canvas.delete("string_art")
        self.canvas.delete("final_res")
        self.reset_canvas_position()
        self._draw_base_structure()
        self.miniature_lbl.config(image=self.empty_img)
        self.status_var.set("Сброс выполнен.")

    def clear_strings_only(self):
        self.stop_flag = True
        self.is_generating = False
        self.sequence = []
        self.final_strings_pil = None
        self.canvas.delete("string_art")
        self.canvas.delete("final_res")
        self.progress['value'] = 0
        self.miniature_lbl.config(image=self.empty_img)
        self.status_var.set("Нити очищены.")

    def load_image(self):
        path = filedialog.askopenfilename(filetypes=[("Images", "*.jpg;*.png;*.jpeg")])
        if not path: return
        try:
            img = Image.open(path).convert("RGBA")
            img.thumbnail((1200, 1200))
            self.original_image = img
            self.reset_canvas_position()
            self.scale_var.set(1.0)
            self.update_preview()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def remove_background(self):
        if not REMBG_AVAILABLE:
            messagebox.showwarning("Ошибка", "Библиотека rembg недоступна.")
            return

        if not self.original_image: return
        self.status_var.set("Удаление фона...")
        self.root.update()
        def t():
            try:
                out = remove_bg(self.original_image)
                bg = Image.new("RGBA", out.size, (255,255,255,255))
                bg.paste(out, (0,0), out)
                self.original_image = bg
                self.root.after(0, self.update_preview)
                self.root.after(0, lambda: self.status_var.set("Фон удален."))
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("Ошибка", str(e)))
        threading.Thread(target=t, daemon=True).start()

    def auto_enhance(self):
        self.contrast_var.set(1.5)
        self.brightness_var.set(1.1)
        self.update_preview()

    def auto_calculate_params(self):
        if self.processed_image is None:
            messagebox.showwarning("!", "Загрузите изображение")
            return
        img = self.get_cropped_image()
        stat = ImageOps.invert(img)
        arr = np.array(stat)
        avg_darkness = np.mean(arr)
        
        # Логика подбора параметров
        if avg_darkness < 30:
            lines = 2500
            opacity = 20
        elif avg_darkness < 60:
            lines = 3000
            opacity = 30
        elif avg_darkness < 100:
            lines = 3500
            opacity = 35
        else:
            lines = 4000
            opacity = 45
        
        nails = 240
        self.lines_count_var.set(lines)
        self.calc_opacity_var.set(opacity)
        self.nails_count_var.set(nails)
        msg = f"Анализ завершен:\nНасыщенность: {avg_darkness:.1f}\n\nРекомендовано:\nЛиний: {lines}\nПлотность: {opacity}"
        messagebox.showinfo("Автоподбор", msg)

    def update_preview(self, *args):
        if self.original_image is None: return
        img = self.original_image.copy().convert("RGB")
        img = ImageOps.grayscale(img)
        img = ImageEnhance.Brightness(img).enhance(self.brightness_var.get())
        img = ImageEnhance.Contrast(img).enhance(self.contrast_var.get())
        self.processed_image = img
        self.update_layers_visibility()

    def update_layers_visibility(self, *args):
        self._draw_base_structure()
        
        if self.processed_image:
            scale = self.scale_var.get()
            nw, nh = int(self.processed_image.width * scale), int(self.processed_image.height * scale)
            img_bg = self.processed_image.resize((nw, nh), Image.Resampling.NEAREST).convert("RGBA")
            
            alpha_val = self.bg_opacity_var.get()
            if not self.show_original_var.get(): alpha_val = 0.0
            img_bg.putalpha(int(255 * alpha_val))
            
            self.tk_img_bg = ImageTk.PhotoImage(img_bg)
            self.canvas.delete("image_bg")
            self.canvas.create_image(self.img_x, self.img_y, image=self.tk_img_bg, tags="image_bg")
            self.canvas.tag_lower("image_bg")
        
        if self.final_strings_pil:
            r = self.hoop_radius_var.get()
            disp_size = r * 2
            str_img = self.final_strings_pil.resize((disp_size, disp_size), Image.Resampling.LANCZOS)
            
            user_alpha = self.strings_opacity_var.get()
            if user_alpha < 1.0:
                r_ch, g_ch, b_ch, a_ch = str_img.split()
                a_ch = a_ch.point(lambda p: int(p * user_alpha))
                str_img = Image.merge("RGBA", (r_ch, g_ch, b_ch, a_ch))
            
            self.tk_img_res = ImageTk.PhotoImage(str_img)
            cx, cy = self.canvas_size // 2, self.canvas_size // 2
            self.canvas.delete("final_res")
            self.canvas.create_image(cx, cy, image=self.tk_img_res, tags="final_res")
            
        self.canvas.tag_raise("hoop_mask")
        self.canvas.tag_raise("hoop_ring")
        self.canvas.tag_raise("hoop_text")

    def on_drag_start(self, event):
        self.drag_data["x"] = event.x
        self.drag_data["y"] = event.y

    def on_drag_motion(self, event):
        dx = event.x - self.drag_data["x"]
        dy = event.y - self.drag_data["y"]
        self.img_x += dx
        self.img_y += dy
        self.drag_data["x"] = event.x
        self.drag_data["y"] = event.y
        self.canvas.move("image_bg", dx, dy)

    def get_cropped_image(self):
        if self.processed_image is None: return None
        r = self.hoop_radius_var.get()
        size = r * 2
        calc_size = 500
        
        cx, cy = self.canvas_size // 2, self.canvas_size // 2
        rel_x = self.img_x - cx
        rel_y = self.img_y - cy
        
        scale = self.scale_var.get()
        cur_w = int(self.processed_image.width * scale)
        cur_h = int(self.processed_image.height * scale)
        
        base = Image.new("L", (size, size), 255)
        img_res = self.processed_image.resize((cur_w, cur_h), Image.Resampling.LANCZOS)
        
        paste_x = int(rel_x + r - cur_w/2)
        paste_y = int(rel_y + r - cur_h/2)
        base.paste(img_res, (paste_x, paste_y))
        
        mask = Image.new("L", (size, size), 0)
        ImageDraw.Draw(mask).ellipse((0,0,size,size), fill=255)
        final = Image.composite(base, Image.new("L", base.size, 255), mask)
        return final.resize((calc_size, calc_size), Image.Resampling.LANCZOS)

    def start_generation(self, animate=True):
        if self.is_generating: return
        if not self.processed_image:
            messagebox.showwarning("!", "Загрузите изображение")
            return
        
        self.canvas.delete("string_art")
        self.canvas.delete("final_res")
        self.final_strings_pil = None
        
        self.calc_img_pil = self.get_cropped_image()
        self.is_generating = True
        self.stop_flag = False
        self.status_var.set("Расчет...")
        self.progress['value'] = 0
        
        self.thread = threading.Thread(target=self.run_algorithm_improved, args=(animate,))
        self.thread.start()

    def stop_generation(self):
        self.stop_flag = True

    # =========================================================================
    # ГЛАВНЫЙ АЛГОРИТМ (ERROR MINIMIZATION)
    # =========================================================================
    def run_algorithm_improved(self, animate):
        # Целевое изображение: 255 - черный, 0 - белый
        target_img = ImageOps.invert(self.calc_img_pil)
        w, h = target_img.size
        
        # Маска круга
        msk = Image.new("L", (w,h), 0)
        ImageDraw.Draw(msk).ellipse((0,0,w,h), fill=255)
        target_img = Image.composite(target_img, Image.new("L", target_img.size, 0), msk)
        
        # Error Matrix: содержит "сколько еще нужно добавить черноты"
        # Может уходить в минус (перечернено)
        error_matrix = np.array(target_img, dtype=np.float32)
        
        n_nails = self.nails_count_var.get()
        max_lines = self.lines_count_var.get()
        
        nails = []
        cx, cy = w/2, h/2
        rad = w/2 - 1
        for i in range(n_nails):
            a = 2*math.pi*i/n_nails
            nails.append((int(cx+rad*math.cos(a)), int(cy+rad*math.sin(a))))

        curr = 0
        self.sequence = [curr]
        
        line_weight = float(self.calc_opacity_var.get())
        skip_nails = 15 # Пропуск соседей
        
        for i in range(max_lines):
            if self.stop_flag: break
            
            best_nail = -1
            best_score = -999999999.0
            sx, sy = nails[curr]
            
            for t in range(n_nails):
                dist_idx = abs(t - curr)
                if dist_idx < skip_nails or dist_idx > (n_nails - skip_nails): continue
                
                ex, ey = nails[t]
                ln = int(math.hypot(ex-sx, ey-sy))
                if ln == 0: continue
                
                xs = np.linspace(sx, ex, ln).astype(int)
                ys = np.linspace(sy, ey, ln).astype(int)
                xs = np.clip(xs, 0, w-1)
                ys = np.clip(ys, 0, h-1)
                
                # СУТЬ АЛГОРИТМА: Считаем сумму значений под линией.
                # Если значения положительные - там нужно рисовать.
                # Если отрицательные (уже перечернено) - сумма уменьшается, линия не выбирается.
                vals = error_matrix[ys, xs]
                score = np.sum(vals)
                
                if score > best_score:
                    best_score = score
                    best_nail = t
            
            if best_nail == -1: break
            
            # Рисуем
            ex, ey = nails[best_nail]
            ln = int(math.hypot(ex-sx, ey-sy))
            xs = np.linspace(sx, ex, ln).astype(int)
            ys = np.linspace(sy, ey, ln).astype(int)
            xs = np.clip(xs, 0, w-1)
            ys = np.clip(ys, 0, h-1)
            
            # Вычитаем вес нити из матрицы. 
            # Разрешаем уходить в минус (не используем clip(0)).
            error_matrix[ys, xs] -= line_weight
            
            self.sequence.append(best_nail)
            curr = best_nail
            
            # UI Updates
            if i % 25 == 0:
                pct = (i / max_lines) * 100
                self.root.after(0, lambda p=pct: self.progress.configure(value=p))
            if animate and i % 5 == 0:
                self.root.after(0, self.draw_line_live, nails[self.sequence[-2]], nails[curr])

        self.is_generating = False
        self.root.after(0, lambda: self.finalize_result(nails))

    def draw_line_live(self, p1, p2):
        r = self.hoop_radius_var.get()
        scale = (r * 2) / 500
        off_x = (self.canvas_size//2) - r
        off_y = (self.canvas_size//2) - r
        self.canvas.create_line(p1[0]*scale+off_x, p1[1]*scale+off_y, 
                                p2[0]*scale+off_x, p2[1]*scale+off_y, 
                                width=1, fill="black", tags="string_art")

    def finalize_result(self, nails):
        self.status_var.set("Рендер высокой четкости...")
        self.progress['value'] = 100
        self.canvas.delete("string_art")
        
        size = 2000 
        img = Image.new("RGBA", (size, size), (255, 255, 255, 0))
        draw = ImageDraw.Draw(img)
        sf = size / 500
        sc_nails = [(x*sf, y*sf) for x,y in nails]
        
        # Полупрозрачная нить для реализма
        color = (0, 0, 0, 40)
        pts = [sc_nails[i] for i in self.sequence]
        
        for i in range(len(pts)-1):
            draw.line([pts[i], pts[i+1]], fill=color, width=2)
            
        mask = Image.new("L", (size, size), 0)
        ImageDraw.Draw(mask).ellipse((0,0,size,size), fill=255)
        
        self.final_strings_pil = img
        white_thumb = Image.new("RGB", (size, size), "white")
        white_thumb.paste(img, (0,0), img)
        thumb = white_thumb.resize((400, 400), Image.Resampling.LANCZOS)
        tk_thumb = ImageTk.PhotoImage(thumb)
        self.miniature_lbl.config(image=tk_thumb)
        self.miniature_lbl.image = tk_thumb
        self.update_layers_visibility()
        self.status_var.set(f"Готово! Линий: {len(self.sequence)}")

    def save_instructions(self):
        if not self.sequence: return
        types = [("TXT", "*.txt"), ("JSON", "*.json"), ("CSV", "*.csv")]
        path = filedialog.asksaveasfilename(defaultextension=".txt", filetypes=types)
        if not path: return
        try:
            if path.endswith(".json"):
                json.dump({"nails_count": self.nails_count_var.get(), "sequence": self.sequence}, open(path, "w"))
            elif path.endswith(".csv"):
                with open(path, "w", newline='') as f:
                    w = csv.writer(f)
                    for i in range(0, len(self.sequence), 20): w.writerow(self.sequence[i:i+20])
            else:
                with open(path, "w") as f:
                    f.write(f"Гвозди: {self.nails_count_var.get()}\n")
                    for i in range(0, len(self.sequence), 10):
                        f.write(" - ".join(map(str, self.sequence[i:i+10])) + "\n")
            messagebox.showinfo("OK", "Сохранено")
        except Exception as e:
            messagebox.showerror("Err", str(e))

    def open_player_window(self):
        InstructionPlayer(self.root, self.nails_count_var.get(), self.sequence)

if __name__ == "__main__":
    root = tk.Tk()
    app = RingStringApp(root)
    root.mainloop()