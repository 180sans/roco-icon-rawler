"""Checkbox interface for all four icon collections."""
from pathlib import Path
import queue
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from urllib.parse import unquote
import webbrowser

from crawler import (CATALOG_URL, PET_CATALOG_URL, DEFAULT_OUTPUT, DATASET_LABELS, FILTER_LABELS, OPTION_LABELS,
                     download_icons, fetch_dataset, item_values, new_session, select_items)


class App:
    def __init__(self, root, output):
        self.root = root
        self.catalog = None
        self.cache = {}
        self.busy = False
        self.loading = False
        self.events = queue.Queue()
        self.stop = threading.Event()
        self.checks = {}
        self.dataset = "skill"
        self.dataset_label = tk.StringVar(value=DATASET_LABELS[self.dataset])
        self.source_url = tk.StringVar()
        self.output = tk.StringVar(value=str(output))
        self.keyword = tk.StringVar()
        self.all_items = tk.BooleanVar()
        self.overwrite = tk.BooleanVar()
        self.status = tk.StringVar()
        root.title("洛克王国世界 · 图像爬取")
        root.geometry("1050x820")
        root.minsize(920, 740)
        root.protocol("WM_DELETE_WINDOW", self.close)
        page = ttk.Frame(root)
        page.pack(fill="both", expand=True)
        self.page_canvas = tk.Canvas(page, highlightthickness=0, yscrollincrement=24)
        self.page_scrollbar = ttk.Scrollbar(page, orient="vertical", command=self.page_canvas.yview)
        self.page_canvas.configure(yscrollcommand=self.page_scrollbar.set)
        self.page_scrollbar.pack(side="right", fill="y")
        self.page_canvas.pack(side="left", fill="both", expand=True)
        wrapper = self.page_content = ttk.Frame(self.page_canvas, padding=14)
        self.page_window = self.page_canvas.create_window((0, 0), window=wrapper, anchor="nw")
        self.page_canvas.bind("<Configure>", self.update_page_layout)
        wrapper.bind("<Configure>", self.update_page_layout)
        root.bind("<MouseWheel>", self.scroll_page, add="+")
        ttk.Label(wrapper, text="技能 / 技能分类 / 系别 / 精灵头像",
                  font=("Microsoft YaHei", 14)).pack(anchor="w")
        ttk.Label(wrapper, text="图片分目录保存；同组多选取并集，不同组取交集。"
                  ).pack(anchor="w", pady=(4, 10))
        self.controls = ttk.Frame(wrapper)
        self.controls.pack(fill="x")
        row = ttk.Frame(self.controls)
        row.pack(fill="x", pady=4)
        ttk.Label(row, text="图片种类：").pack(side="left")
        self.dataset_box = ttk.Combobox(row, textvariable=self.dataset_label,
                                       values=list(DATASET_LABELS.values()), width=26, state="readonly")
        self.dataset_box.pack(side="left")
        self.dataset_box.bind("<<ComboboxSelected>>", self.switch_dataset)
        self.reload_button = ttk.Button(row, text="刷新网站数据", command=self.reload)
        self.reload_button.pack(side="left", padx=8)
        source_row = ttk.Frame(self.controls)
        source_row.pack(fill="x", pady=4)
        ttk.Label(source_row, text="下载来源（BWIKI）：").pack(side="left")
        self.source_link = ttk.Label(source_row, textvariable=self.source_url,
                                     foreground="#0969da", cursor="hand2")
        self.source_link.pack(side="left")
        self.source_link.bind("<Button-1>", lambda _event: webbrowser.open(self.source_url.get()))
        ttk.Label(self.controls, text="图片文件来源：patchwiki.biligame.com（BWIKI 图片服务）"
                  ).pack(anchor="w")
        self.hint = ttk.Label(self.controls)
        self.hint.pack(anchor="w", pady=(4, 6))
        self.filters = ttk.Frame(self.controls)
        self.filters.pack(fill="x")
        row = ttk.Frame(self.controls)
        row.pack(fill="x", pady=8)
        ttk.Label(row, text="名称或编号包含：").pack(side="left")
        ttk.Entry(row, textvariable=self.keyword, width=24).pack(side="left")
        ttk.Checkbutton(row, text="全量爬取", variable=self.all_items,
                        command=self.toggle_all).pack(side="left", padx=18)
        ttk.Checkbutton(row, text="重新下载已有图片", variable=self.overwrite).pack(side="left")
        self.keyword.trace_add("write", lambda *_: self.preview())
        row = ttk.Frame(self.controls)
        row.pack(fill="x", pady=4)
        ttk.Label(row, text="输出根目录：").pack(side="left")
        ttk.Entry(row, textvariable=self.output).pack(side="left", fill="x", expand=True)
        ttk.Button(row, text="选择文件夹", command=self.choose_output).pack(side="left", padx=6)
        self.destination = ttk.Label(self.controls)
        self.destination.pack(anchor="w", pady=4)
        self.output.trace_add("write", lambda *_: self.update_destination())
        row = ttk.Frame(wrapper)
        row.pack(fill="x", pady=8)
        self.start_button = ttk.Button(row, text="开始下载", command=self.start, state="disabled")
        self.start_button.pack(side="left")
        self.stop_button = ttk.Button(row, text="停止", command=self.stop.set, state="disabled")
        self.stop_button.pack(side="left", padx=8)
        ttk.Label(row, textvariable=self.status).pack(side="left", padx=8)
        self.progress = ttk.Progressbar(wrapper, mode="indeterminate")
        self.progress.pack(fill="x")
        ttk.Label(wrapper, text="匹配预览 / 下载日志：").pack(anchor="w", pady=(8, 4))
        box = ttk.Frame(wrapper, height=300)
        box.pack(fill="both", expand=True)
        box.pack_propagate(False)
        self.log = tk.Text(box, wrap="word", height=12, state="disabled")
        scroll = ttk.Scrollbar(box, command=self.log.yview)
        self.log.configure(yscrollcommand=scroll.set)
        self.log.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        self.root.after(100, self.poll)
        self.load()

    def update_page_layout(self, _event=None):
        width = self.page_canvas.winfo_width()
        height = max(self.page_content.winfo_reqheight(), self.page_canvas.winfo_height())
        self.page_canvas.itemconfigure(self.page_window, width=width, height=height)
        self.page_canvas.configure(scrollregion=(0, 0, width, height))

    def scroll_page(self, event):
        # The preview keeps its own Text scrollbar and native mouse-wheel behavior.
        if isinstance(event.widget, tk.Text) or not event.delta:
            return
        if self.page_canvas.yview() == (0.0, 1.0):
            return
        steps = -int(event.delta / 120) or (-1 if event.delta > 0 else 1)
        self.page_canvas.yview_scroll(steps, "units")
        return "break"

    def lock_controls(self, locked):
        def visit(widget):
            for child in widget.winfo_children():
                if isinstance(child, (ttk.Button, ttk.Checkbutton, ttk.Entry)):
                    child.configure(state="disabled" if locked else "normal")
                visit(child)
        visit(self.controls)
        self.dataset_box.configure(state="disabled" if locked else "readonly")

    def switch_dataset(self, _event=None):
        if self.busy or self.loading:
            return
        self.dataset = next(key for key, value in DATASET_LABELS.items()
                            if value == self.dataset_label.get())
        self.load()

    def reload(self):
        self.cache.pop(self.dataset, None)
        self.load()

    def load(self):
        self.catalog = None
        self.source_url.set(unquote(PET_CATALOG_URL if self.dataset == "pet" else CATALOG_URL))
        self.keyword.set("")
        self.all_items.set(False)
        for child in self.filters.winfo_children():
            child.destroy()
        self.checks = {}
        self.update_destination()
        self.page_canvas.yview_moveto(0)
        self.root.after_idle(self.update_page_layout)
        if self.dataset in self.cache:
            self.accept_catalog(self.cache[self.dataset])
            return
        self.loading = True
        self.lock_controls(True)
        self.start_button.configure(state="disabled")
        self.status.set("正在读取网站筛选条件…")
        dataset = self.dataset
        def worker():
            try:
                with new_session() as session:
                    self.events.put(("catalog", fetch_dataset(session, dataset)))
            except Exception as error:
                self.events.put(("load_error", str(error)))
        threading.Thread(target=worker, daemon=True).start()

    def accept_catalog(self, catalog):
        self.catalog = catalog
        self.cache[self.dataset] = catalog
        self.loading = False
        self.lock_controls(False)
        hints = {"skill": "保存为 技能名.png；默认只勾选 S4。",
                 "skill_type": "物攻、魔攻、防御、状态；保存为 选项名.png。",
                 "element": "普通、草、火、水等系别；保存为 选项名.png。",
                 "pet": "下载紧凑模式头像；保存为 编号名称（形态）.png，省略空形态和首领形态后缀。"}
        self.hint.configure(text=hints[self.dataset])
        self.show_filters()
        self.preview()
        self.root.after_idle(self.update_page_layout)

    def show_filters(self):
        for key, values in self.catalog.options.items():
            frame = ttk.LabelFrame(self.filters, text=FILTER_LABELS[key], padding=5)
            frame.pack(fill="x", pady=2)
            self.checks[key] = {}
            for index, value in enumerate(values):
                default = (self.dataset == "skill" and key == "season" and value == "S4"
                           or self.dataset in ("skill_type", "element"))
                variable = tk.BooleanVar(value=default)
                self.checks[key][value] = variable
                count = sum(value in item_values(item, key) for item in self.catalog.skills)
                label = value if key == "name" else OPTION_LABELS.get(value, value)
                ttk.Checkbutton(frame, text=f"{label} ({count})", variable=variable,
                                command=self.changed).grid(row=index // 8, column=index % 8,
                                                           sticky="w", padx=4)
            for column in range(min(8, len(values))):
                frame.columnconfigure(column, weight=1)

    def selected(self):
        filters = {key: [value for value, var in values.items() if var.get()]
                   for key, values in self.checks.items()}
        return select_items(self.catalog, filters, keyword=self.keyword.get(), all_items=self.all_items.get())

    def changed(self):
        self.all_items.set(False)
        self.preview()

    def toggle_all(self):
        if self.all_items.get():
            for values in self.checks.values():
                for var in values.values():
                    var.set(False)
            self.keyword.set("")
        self.preview()

    def preview(self):
        if not self.catalog or self.busy:
            return
        try:
            selected = self.selected()
        except ValueError as error:
            self.status.set(str(error))
            self.start_button.configure(state="disabled")
            self.set_log(str(error))
            return
        self.status.set(f"匹配 {len(selected)} / {len(self.catalog.skills)} 张图片")
        self.start_button.configure(state="normal" if selected else "disabled")
        self.set_log("\n".join(f"{item.name}.png" for item in selected)
                     or "没有匹配的图片，请调整筛选条件。")

    def update_destination(self):
        self.destination.configure(text=f"实际保存目录：{Path(self.output.get()) / self.dataset}")

    def choose_output(self):
        chosen = filedialog.askdirectory(parent=self.root, title="选择输出根目录")
        if chosen:
            self.output.set(chosen)

    def set_log(self, text, append=False):
        self.log.configure(state="normal")
        if not append:
            self.log.delete("1.0", "end")
        self.log.insert("end", text + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def start(self):
        try:
            selected = self.selected()
            if not selected:
                raise ValueError("没有匹配的图片。")
            if not self.output.get().strip():
                raise ValueError("请选择输出根目录。")
            output = Path(self.output.get()).expanduser().resolve() / self.dataset
        except (ValueError, OSError) as error:
            messagebox.showerror("无法开始", str(error), parent=self.root)
            return
        self.busy = True
        self.stop.clear()
        self.lock_controls(True)
        self.start_button.configure(state="disabled")
        self.stop_button.configure(state="normal")
        self.status.set(f"正在下载 {len(selected)} 张图片…")
        self.progress.start(10)
        self.set_log(f"本次下载 {len(selected)} 张图片，输出目录：{output}")
        overwrite = self.overwrite.get()
        def worker():
            try:
                with new_session() as session:
                    result = download_icons(selected, output, session, overwrite=overwrite,
                                            stop=self.stop,
                                            log=lambda text: self.events.put(("log", text)))
                self.events.put(("done", result))
            except Exception as error:
                self.events.put(("error", str(error)))
        threading.Thread(target=worker, daemon=True).start()

    def poll(self):
        try:
            while True:
                kind, value = self.events.get_nowait()
                if kind == "catalog":
                    self.accept_catalog(value)
                elif kind == "log":
                    self.set_log(value, append=True)
                elif kind == "load_error":
                    self.loading = False
                    self.lock_controls(False)
                    self.status.set("加载失败，可点击刷新重试。")
                    self.set_log(value)
                elif kind in ("done", "error"):
                    self.busy = False
                    self.progress.stop()
                    self.lock_controls(False)
                    self.stop_button.configure(state="disabled")
                    self.start_button.configure(state="normal")
                    if kind == "done":
                        prefix = "已停止" if self.stop.is_set() else "下载结束"
                        self.status.set(f"{prefix}：新增 {value['saved']}，跳过 {value['skipped']}，失败 {value['failed']}")
                    else:
                        self.status.set("下载失败")
                        self.set_log(value, append=True)
        except queue.Empty:
            pass
        self.root.after(100, self.poll)

    def close(self):
        if self.busy:
            self.stop.set()
            self.status.set("正在结束当前请求，请稍候…")
            self.root.after(100, self.close_after_download)
        else:
            self.root.destroy()

    def close_after_download(self):
        if self.busy:
            self.root.after(100, self.close_after_download)
        else:
            self.root.destroy()


def run_gui(output=DEFAULT_OUTPUT):
    root = tk.Tk()
    App(root, output)
    root.mainloop()


if __name__ == "__main__":
    run_gui()
