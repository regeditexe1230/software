import socket
import socketserver
import threading
import logging
import tkinter as tk
from tkinter import ttk, filedialog, messagebox  # 添加messagebox
from datetime import datetime
import platform


class ThreadedTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = True
    address_family = socket.AF_INET6
    service_core = None


class HighPerfUDPServer(socketserver.ThreadingMixIn, socketserver.UDPServer):
    allow_reuse_address = True
    address_family = socket.AF_INET6
    service_core = None


# 创建自定义日志处理器
class TextWidgetLogHandler(logging.Handler):
    def __init__(self, ui_reference):
        super().__init__()
        self.ui = ui_reference
        self.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))

    def emit(self, record):
        log_entry = self.format(record)
        self.ui.append_log(log_entry)


class LogServiceCore:
    def __init__(self, port=54321):
        self.port = port
        self._running = threading.Event()
        self._running.set()
        self.gui_handler = None  # 稍后会被设置

        # 日志初始化
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(f'server_{datetime.now().strftime("%Y%m%d")}.log'),
            ]
        )

        # 网络服务初始化
        self.tcp_server = ThreadedTCPServer(('::', port), self.TCPHandler)
        self.udp_server = HighPerfUDPServer(('::', port), self.UDPHandler)
        self.tcp_server.service_core = self
        self.udp_server.service_core = self

    class TCPHandler(socketserver.BaseRequestHandler):
        def handle(self):
            try:
                data = self.request.recv(1024).decode()
                logging.info(f"[TCP]来自{self.client_address}的消息: {data.strip()}")
            except Exception as e:
                logging.error(f"TCP处理错误: {str(e)}")

    class UDPHandler(socketserver.BaseRequestHandler):
        def handle(self):
            try:
                data = self.request[0].decode()
                logging.info(f"[UDP]来自{self.client_address}的消息: {data.strip()}")
            except Exception as e:
                logging.error(f"UDP处理错误: {str(e)}")

    def start_service(self):
        tcp_thread = threading.Thread(target=self.tcp_server.serve_forever)
        udp_thread = threading.Thread(target=self.udp_server.serve_forever)

        tcp_thread.daemon = True
        udp_thread.daemon = True

        tcp_thread.start()
        udp_thread.start()
        logging.info(f"服务已启动，监听[::]:{self.port}")

    def shutdown(self):
        self._running.clear()
        self.tcp_server.shutdown()
        self.udp_server.shutdown()
        logging.info("服务已安全终止")

    def set_gui_handler(self, ui_handler):
        """设置GUI日志处理器"""
        self.gui_handler = ui_handler
        logging.getLogger().addHandler(ui_handler)


# ================== 修复后的暗色主题GUI ==================
class DarkThemeLogUI(tk.Tk):
    def __init__(self, service_core):
        super().__init__()
        self.service = service_core
        self._configure_ui()
        self._build_components()
        self._auto_start_service()

        # 设置窗口大小和透明度
        self.geometry("1024x768")  # 设置窗口大小为1024x768
        self.attributes("-alpha", 0.85)  # 设置窗口透明度为85%

        # 初始化日志队列
        self.log_queue = []

        # 设置关闭确认处理
        self.protocol("WM_DELETE_WINDOW", self.confirm_shutdown)

    def _configure_ui(self):
        """统一的暗色主题配置"""
        self.title("日志服务控制台")
        self.configure(bg='#2d2d2d')
        self.style = ttk.Style()
        self.style.theme_use('alt')

        if platform.system() == 'Windows':
            self.iconbitmap('1.ico')
        else:
        # macOS/Linux 推荐使用 .png
            try:
                from tkinter import PhotoImage
                icon = PhotoImage(file='1.png')
                self.iconphoto(True, icon)
            except Exception as e:
                print(f"设置图标失败: {e}")

        # 配置主框架背景
        self.style.configure('TFrame', background='#2d2d2d')

        # 按钮样式
        self.style.configure('TButton',
                             background='#404040',
                             foreground='white',
                             bordercolor='#404040',
                             relief='flat',
                             padding=5,
                             font=('Arial', 10)
                             )
        self.style.map('TButton',
                       background=[('active', '#505050'), ('pressed', '#303030')],
                       foreground=[('active', 'white'), ('pressed', '#cccccc')]
                       )

        # 滚动条样式
        self.style.configure('Vertical.TScrollbar',
                             background='#404040',
                             troughcolor='#2d2d2d',
                             borderwidth=0,
                             arrowsize=12
                             )
        self.style.map('Vertical.TScrollbar',
                       background=[('active', '#505050')]
                       )

        # 文本框样式
        self.style.configure('Dark.TEntry',
                             fieldbackground='#1a1a1a',
                             foreground='#c0c0c0',
                             insertcolor='white'
                             )

    def _build_components(self):
        """修正的界面布局 - 按钮分布合理"""
        # 使用frame作为容器，确保颜色统一
        main_frame = ttk.Frame(self)
        main_frame.grid(row=0, column=0, sticky="nsew")
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # 日志显示区域
        self.txt_log = tk.Text(main_frame,
                               bg='#1a1a1a',
                               fg='#c0c0c0',
                               insertbackground='white',
                               wrap=tk.WORD,
                               padx=10,
                               pady=10,
                               font=('Consolas', 10)
                               )
        self.txt_log.grid(row=0, column=0, padx=5, pady=5, sticky="nsew")

        # 使用样式化滚动条
        scrollbar = ttk.Scrollbar(main_frame,
                                  command=self.txt_log.yview,
                                  style='Vertical.TScrollbar')
        scrollbar.grid(row=0, column=1, sticky='ns')
        self.txt_log.config(yscrollcommand=scrollbar.set)

        # 控制面板 - 使用网格布局分开按钮
        ctrl_frame = ttk.Frame(main_frame)
        ctrl_frame.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(0, 5))

        # 左侧按钮容器
        left_btn_frame = ttk.Frame(ctrl_frame)
        left_btn_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # 右侧按钮容器
        right_btn_frame = ttk.Frame(ctrl_frame)
        right_btn_frame.pack(side=tk.RIGHT, fill=tk.X, expand=True)

        # 停止服务按钮放在左侧
        ttk.Button(left_btn_frame,
                   text="停止服务",
                   command=self._stop_service
                   ).pack(side=tk.LEFT, padx=10, ipadx=10)

        # 导出日志按钮放在右侧
        ttk.Button(right_btn_frame,
                   text="导出日志",
                   command=self._export_log
                   ).pack(side=tk.RIGHT, padx=10, ipadx=10)

        # 添加状态栏
        status_frame = ttk.Frame(main_frame)
        status_frame.grid(row=2, column=0, columnspan=2, sticky="ew", padx=5, pady=(0, 5))

        self.status_label = ttk.Label(status_frame,
                                      text="服务运行中",
                                      foreground="#40c040",
                                      background='#2d2d2d',
                                      anchor=tk.W
                                      )
        self.status_label.pack(side=tk.LEFT, fill=tk.X, expand=True)

        port_label = ttk.Label(status_frame,
                               text=f"监听端口: {self.service.port}",
                               foreground="#a0a0a0",
                               background='#2d2d2d',
                               anchor=tk.E
                               )
        port_label.pack(side=tk.RIGHT, fill=tk.X)

        # 主框架权重配置
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(0, weight=1)

        # 主窗口权重配置
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

    def _auto_start_service(self):
        """自动启动服务"""
        threading.Thread(target=self.service.start_service).start()
        self.txt_log.insert(tk.END, "服务已自动启动\n")
        self.status_label.config(text="服务运行中", foreground="#40c040")

    def _stop_service(self):
        self.service.shutdown()
        self.txt_log.insert(tk.END, "服务停止命令已发送\n")
        self.status_label.config(text="服务已停止", foreground="#ff6060")

    def _export_log(self):
        """日志导出实现"""
        file_path = filedialog.asksaveasfilename(
            defaultextension=".log",
            filetypes=[("日志文件", "*.log"), ("文本文件", "*.txt"), ("所有文件", "*.*")]
        )
        if file_path:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(self.txt_log.get(1.0, tk.END))
                self.txt_log.insert(tk.END, f"日志已导出至: {file_path}\n")
            except Exception as e:
                logging.error(f"导出失败: {str(e)}")
                self.status_label.config(text=f"导出失败: {str(e)}", foreground="#ff6060")

    def _safe_shutdown(self):
        """执行实际的关闭操作"""
        self.service.shutdown()
        self.destroy()

    def confirm_shutdown(self):
        """在关闭前显示确认对话框"""
        # 弹出确认对话框
        result = messagebox.askquestion("退出程序", "确定要退出程序吗？",
                                        icon="warning",
                                        type="yesno")

        if result == "yes":
            self._safe_shutdown()

    def update_log_display(self):
        """更新文本框显示来自日志系统的消息"""
        if self.log_queue:
            for msg in self.log_queue:
                self.txt_log.insert(tk.END, msg + "\n")
                self.txt_log.see(tk.END)  # 自动滚动到最新内容
            self.log_queue = []
        self.after(100, self.update_log_display)  # 继续计划下一次更新

    def append_log(self, message):
        """线程安全添加日志消息"""
        self.log_queue.append(message)


# ================== 主程序入口 ==================
if __name__ == "__main__":
    service = LogServiceCore(port=54321)
    app = DarkThemeLogUI(service)

    # 创建GUI日志处理器并将其添加到服务中
    gui_handler = TextWidgetLogHandler(app)
    service.set_gui_handler(gui_handler)

    app.log_queue = []  # 确保日志队列已初始化
    # 启动日志更新循环
    app.update_log_display()
    app.mainloop()