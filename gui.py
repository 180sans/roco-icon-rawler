"""Checkbox interface for all four icon collections."""
from pathlib import Path
import queue
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from urllib.parse import unquote
import webbrowser

from crawler import (CATALOG_URL, PET_CATALOG_URL, DEFAULT_OUTPUT, DATASET_LABELS, FILTER_LABELS, OPTION_LABELS,
                     crawl_images, fetch_dataset, item_values, new_session, select_items)

SCOPE_LABELS = {"all": "总爬取（全部四类图像）", **DATASET_LABELS}


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
        self.dataset = "all"
        self.dataset_label = tk.StringVar(value=SCOPE_LABELS[self.dataset])
        self.source_url = tk.StringVar()
        self.output = tk.StringVar(value=str(output))
        self.keyword = tk.StringVar()
        self.all_items = tk.BooleanVar(value=True)
        self.missing_only = tk.BooleanVar(value=True)
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
        ttk.Label(wrapper, text="日常使用：直接点击“总爬取”；默认只补缺失。需要刷新已有图片时取消“缺失爬取”。"
                  ).pack(anchor="w", pady=(4, 10))
        self.controls = ttk.Frame(wrapper)
        self.controls.pack(fill="x")
        row = ttk.Frame(self.controls)
        row.pack(fill="x", pady=4)
        ttk.Label(row, text="图片种类：").pack(side="left")
        self.dataset_box = ttk.Combobox(row, textvariable=self.dataset_label,
                                       values=list(SCOPE_LABELS.values()), width=26, state="readonly")
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
        self.source_link.bind("<Button-1>", lambda _event: webbrowser.open(
            PET_CATALOG_URL if self.dataset == "pet" else CATALOG_URL))
        self.pet_source_link = ttk.Label(self.controls, text=f"精灵图鉴：{unquote(PET_CATALOG_URL)}",
                                         foreground="#0969da", cursor="hand2")
        self.pet_source_link.pack(anchor="w")
        self.pet_source_link.bind("<Button-1>", lambda _event: webbrowser.open(PET_CATALOG_URL))
        ttk.Label(self.controls, text="图片文件来源：patchwiki.biligame.com（BWIKI 图片服务）"
                  ).pack(anchor="w")
        self.hint = ttk.Label(self.controls)
        self.hint.pack(anchor="w", pady=(4, 6))
        self.filters = ttk.Frame(self.controls)
        self.filters.pack(fill="x")
        row = ttk.Frame(self.controls)
        row.pack(fill="x", pady=8)
        ttk.Label(row, text="名称或编号包含：").pack(side="left")
        self.keyword_entry = ttk.Entry(row, textvariable=self.keyword, width=24)
        self.keyword_entry.pack(side="left")
        self.scope_all_check = ttk.Checkbutton(row, text="当前类别全部（不筛选子类）", variable=self.all_items,
                                               command=self.toggle_all)
        self.scope_all_check.pack(side="left", padx=18)
        self.keyword.trace_add("write", self.keyword_changed)
        row = ttk.Frame(self.controls)
        row.pack(fill="x", pady=4)
        ttk.Label(row, text="输出根目录：").pack(side="left")
        ttk.Entry(row, textvariable=self.output).pack(side="left", fill="x", expand=True)
        ttk.Button(row, text="选择文件夹", command=self.choose_output).pack(side="left", padx=6)
        self.destination = ttk.Label(self.controls)
        self.destination.pack(anchor="w", pady=4)
        self.output.trace_add("write", lambda *_: self.update_destination())
        self.actions = ttk.Frame(self.controls)
        self.actions.pack(fill="x", pady=8)
        self.total_button = ttk.Button(self.actions, text="总爬取（全部四类）",
                                       command=lambda: self.start("all"), state="disabled")
        self.total_button.pack(side="left")
        self.missing_button = ttk.Button(self.actions, text="开始爬取当前范围",
                                         command=lambda: self.start("current"), state="disabled")
        self.missing_button.pack(side="left", padx=(8, 14))
        self.start_button = self.missing_button  # Keep the app smoke-test entry point stable.
        ttk.Checkbutton(self.actions, text="缺失爬取（默认开启，仅补缺少/损坏）",
                        variable=self.missing_only, command=self.update_mode_hint).pack(side="left")
        self.mode_hint = ttk.Label(self.controls)
        self.mode_hint.pack(anchor="w", pady=(0, 4))
        self.update_mode_hint()
        row = ttk.Frame(wrapper)
        row.pack(fill="x", pady=4)
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
        self.total_button.configure(state="disabled" if locked or self.loading else "normal")
        if not locked and self.dataset == "all":
            self.scope_all_check.configure(state="disabled")
            self.keyword_entry.configure(state="disabled")

    def switch_dataset(self, _event=None):
        if self.busy or self.loading:
            return
        self.dataset = next(key for key, value in SCOPE_LABELS.items()
                            if value == self.dataset_label.get())
        self.load()

    def reload(self):
        self.cache.pop(self.dataset, None)
        self.load()

    def load(self):
        self.catalog = None
        self.source_url.set(unquote(PET_CATALOG_URL if self.dataset == "pet" else CATALOG_URL))
        self.keyword.set("")
        self.all_items.set(True)
        for child in self.filters.winfo_children():
            child.destroy()
        self.checks = {}
        self.update_destination()
        self.total_button.configure(state="disabled" if self.loading else "normal")
        self.missing_button.configure(state="disabled")
        self.page_canvas.yview_moveto(0)
        self.root.after_idle(self.update_page_layout)
        if self.dataset == "all":
            self.loading = False
            self.lock_controls(False)
            self.hint.configure(text="一次处理 skill、skill_type、element、pet；每次开始均重新读取网页清单。")
            self.scope_all_check.configure(state="disabled")
            self.preview()
            return
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
        self.total_button.configure(state="normal")
        hints = {"skill": "保存为 技能名.png；默认全部技能，也可勾选 S4 等子类。",
                 "skill_type": "物攻、魔攻、防御、状态；保存为 选项名.png。",
                 "element": "普通、草、火、水等系别；保存为 选项名.png。",
                 "pet": "下载紧凑模式头像；保存为 编号名称（形态）.png，省略空形态和首领形态后缀。"}
        self.hint.configure(text=hints[self.dataset])
        self.show_filters()
        self.preview()
        self.root.after_idle(self.update_page_layout)

    def show_filters(self):
        previous = {key: {value: var.get() for value, var in values.items()}
                    for key, values in self.checks.items()}
        for child in self.filters.winfo_children():
            child.destroy()
        self.checks = {}
        for key, values in self.catalog.options.items():
            frame = ttk.LabelFrame(self.filters, text=FILTER_LABELS[key], padding=5)
            frame.pack(fill="x", pady=2)
            self.checks[key] = {}
            for index, value in enumerate(values):
                variable = tk.BooleanVar(value=previous.get(key, {}).get(value, False))
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

    def keyword_changed(self, *_args):
        if self.keyword.get().strip():
            self.all_items.set(False)
        self.preview()

    def toggle_all(self):
        if self.all_items.get():
            for values in self.checks.values():
                for var in values.values():
                    var.set(False)
            self.keyword.set("")
        self.preview()

    def update_mode_hint(self):
        text = ("缺失模式：已有有效 PNG 自动跳过；只下载新增或损坏的文件，适用于总爬取及所有子类。"
                if self.missing_only.get() else
                "全量模式：当前范围内所有图片都会重新下载并覆盖，可用于更新已有图标。")
        self.mode_hint.configure(text=text)

    def preview(self):
        if self.dataset == "all" and not self.busy:
            self.status.set("就绪：全部四类图像")
            self.missing_button.configure(state="normal")
            self.set_log("当前范围：总爬取（全部四类）\n\n"
                         "skill / 技能图标\nskill_type / 技能分类图标\n"
                         "element / 系别图标\npet / 精灵紧凑头像\n\n"
                         "点击“总爬取”即可开始。程序会重新读取网页，并对比输出目录。\n"
                         "默认仅补缺失；若想更新所有已有图标，取消勾选“缺失爬取”。")
            return
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
        self.missing_button.configure(state="normal" if selected else "disabled")
        self.set_log("\n".join(f"{item.name}.png" for item in selected)
                     or "没有匹配的图片，请调整筛选条件。")

    def update_destination(self):
        folder = Path(self.output.get())
        text = (f"实际保存目录：{folder} 下的 skill / skill_type / element / pet"
                if self.dataset == "all" else f"实际保存目录：{folder / self.dataset}")
        self.destination.configure(text=text)

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

    def start(self, scope="current"):
        if self.busy or self.loading:
            return
        scope = "all" if scope == "all" or self.dataset == "all" else "current"
        try:
            if not self.output.get().strip():
                raise ValueError("请选择输出根目录。")
            if scope == "current":
                selected = self.selected()
                if not selected:
                    raise ValueError("没有匹配的图片。")
                filters = {key: [value for value, var in values.items() if var.get()]
                           for key, values in self.checks.items()}
                dataset = self.dataset
                keyword = self.keyword.get()
            else:
                filters = {}
                dataset = "all"
                keyword = ""
            output = Path(self.output.get()).expanduser().resolve()
        except (ValueError, OSError) as error:
            messagebox.showerror("无法开始", str(error), parent=self.root)
            return
        self.busy = True
        self.stop.clear()
        self.lock_controls(True)
        self.total_button.configure(state="disabled")
        self.missing_button.configure(state="disabled")
        self.stop_button.configure(state="normal")
        missing_only = self.missing_only.get()
        include_all = scope == "all" or self.all_items.get()
        scope_label = "全部四类" if scope == "all" else f"{DATASET_LABELS[dataset]}当前筛选"
        mode_label = "缺失爬取" if missing_only else "全量更新"
        self.status.set(f"{mode_label}：正在处理{scope_label}…")
        self.progress.start(10)
        self.set_log(f"{mode_label}：{scope_label}；图片会写入 {output}")
        def worker():
            try:
                with new_session() as session:
                    result = crawl_images(
                        session, output, dataset=dataset, filters=filters, keyword=keyword,
                        all_items=include_all, missing_only=missing_only,
                        stop=self.stop, log=lambda text: self.events.put(("log", text)),
                        on_catalog=lambda key, catalog: self.events.put(("fresh_catalog", (key, catalog))))
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
                elif kind == "fresh_catalog":
                    key, catalog = value
                    self.cache[key] = catalog
                    if key == self.dataset:
                        self.catalog = catalog
                elif kind == "log":
                    self.set_log(value, append=True)
                elif kind == "load_error":
                    self.loading = False
                    self.lock_controls(False)
                    self.missing_button.configure(state="disabled")
                    self.status.set("加载失败，可点击刷新重试。")
                    self.set_log(value)
                elif kind in ("done", "error"):
                    self.busy = False
                    self.progress.stop()
                    self.lock_controls(False)
                    self.stop_button.configure(state="disabled")
                    self.total_button.configure(state="normal")
                    if self.dataset != "all" and self.catalog:
                        self.show_filters()
                    try:
                        can_start = self.dataset == "all" or bool(self.catalog and self.selected())
                    except ValueError:
                        can_start = False
                    self.missing_button.configure(state="normal" if can_start else "disabled")
                    self.root.after_idle(self.update_page_layout)
                    if kind == "done":
                        prefix = "已停止" if self.stop.is_set() else "下载结束"
                        self.status.set(f"{prefix}：下载 {value['saved']}，已有跳过 {value['skipped']}，"
                                        f"失败 {value['failed'] + value['category_errors']}")
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
