import tkinter as tk
from tkinter import ttk
from tkinter import messagebox  # 兼容性导入
import socket
import json
import threading
import time
from collections import deque
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.pyplot as plt
import configparser
import platform
from matplotlib import font_manager  # 修复导入问题


# ===== 从样本中添加的字体选择函数 =====
def get_system_fonts():
    """获取系统可用字体列表"""
    fonts = set()
    for f in font_manager.findSystemFonts():
        try:
            fonts.add(font_manager.FontProperties(fname=f).get_name())
        except:
            pass
    return sorted(fonts)


def find_chinese_font():
    """寻找可用的中文字体"""
    # 根据系统设置候选字体列表
    candidates = []
    if platform.system() == 'Windows':
        candidates = [
            'Microsoft YaHei', 'SimHei', 'KaiTi', 'FangSong', 'STKaiti',
            'STSong', 'STFangsong', 'YouYuan', 'MS Gothic', 'Arial Unicode MS'
        ]
    elif platform.system() == 'Darwin':  # macOS
        candidates = [
            'PingFang SC', 'Hiragino Sans GB', 'Apple SD Gothic Neo',
            'STHeiti', 'STXihei', 'Heiti SC', 'Heiti TC', 'Arial Unicode MS'
        ]
    else:  # Linux
        candidates = [
            'WenQuanYi Micro Hei', 'WenQuanYi Zen Hei', 'AR PL UMing CN',
            'Noto Sans CJK SC', 'Noto Serif CJK SC', 'Droid Sans Fallback',
            'DejaVu Sans', 'Arial Unicode MS'
        ]

    # 添加通用字体
    candidates += ['sans-serif', 'Arial', 'Helvetica']

    # 查找系统中实际存在的字体
    system_fonts = get_system_fonts()
    for font in candidates:
        if font in system_fonts:
            return font

    # 如果都没有，返回第一个备选字体
    return candidates[0] if candidates else 'sans-serif'


# ===== 结束字体选择函数 =====

class EnhancedDeviceManager:
    def __init__(self, max_devices=5):
        self.active_devices = deque(maxlen=max_devices)
        self.device_lock = threading.Lock()
        self.current_index = 0
        self.last_switch = time.time()
        self.heartbeat_timeout = 10

    def update_device(self, device_data):
        with self.device_lock:
            ip = device_data['ip']
            existing = next((d for d in self.active_devices if d['ip'] == ip), None)
            if existing:
                existing['name'] = device_data.get('name', existing['name'])
                existing['last_seen'] = time.time()
                existing['data']['cpu_history'].append(device_data['cpu'])
                existing['data']['mem_history'].append(device_data['mem'])
                existing['data']['disk_history'].append(device_data['disk'])

                time_diff = time.time() - existing['last_net_time']
                net_up_diff = device_data['net_up'] - existing['last_net_up']
                net_down_diff = device_data['net_down'] - existing['last_net_down']

                if time_diff > 0:
                    existing['data']['net_up_history'].append(net_up_diff / time_diff / 1024)
                    existing['data']['net_down_history'].append(net_down_diff / time_diff / 1024)
                else:
                    existing['data']['net_up_history'].append(0)
                    existing['data']['net_down_history'].append(0)

                existing['last_net_up'] = device_data['net_up']
                existing['last_net_down'] = device_data['net_down']
                existing['last_net_time'] = time.time()
            else:
                device_data['last_seen'] = time.time()
                device_data['data'] = {
                    'cpu_history': deque([device_data['cpu']], maxlen=60),
                    'mem_history': deque([device_data['mem']], maxlen=60),
                    'disk_history': deque([device_data['disk']], maxlen=60),
                    'net_up_history': deque([0], maxlen=60),
                    'net_down_history': deque([0], maxlen=60)
                }
                device_data['last_net_up'] = device_data['net_up']
                device_data['last_net_down'] = device_data['net_down']
                device_data['last_net_time'] = time.time()
                self.active_devices.append(device_data)


class ReceiverPro(tk.Tk):
    def __init__(self):
        super().__init__()

        # ===== 使用新的字体选择方案 =====
        # 查找并选择中文字体
        chosen_font = find_chinese_font()

        # 设置matplotlib支持中文显示
        plt.rcParams['font.sans-serif'] = [chosen_font]
        plt.rcParams['axes.unicode_minus'] = False

        # 设置Tkinter字体
        if platform.system() == 'Windows':
            tk_font = ('Microsoft YaHei', 10)
        elif platform.system() == 'Darwin':  # macOS
            tk_font = ('PingFang SC', 10)
        else:  # Linux
            tk_font = ('WenQuanYi Micro Hei', 10)

        self.tk_font = tk_font  # 保存为实例变量
        self.plot_font_family = chosen_font  # 保存为实例变量用于图表

        print(f"Using font: {chosen_font} for matplotlib")
        print(f"Using Tkinter font: {tk_font}")
        # ===== 结束字体设置 =====

        self.title("服务器监视软件接收端")
        self.geometry("1366x768")
        self.attributes('-alpha', 0.85)
        self.configure(bg='#000000')

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

        # 添加窗口关闭协议绑定
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        # 初始化配置
        self.config = configparser.ConfigParser()
        self.auto_switch_interval = 30
        self.load_config()

        # 初始化主题样式
        self.style = ttk.Style()
        self.style.theme_use('clam')
        self._configure_styles()

        # 设备管理
        self.dev_mgr = EnhancedDeviceManager()
        self.current_device = None

        # UI初始化
        self.init_ui()
        self.start_listener()
        self.after(1000, self.refresh_ui)

    # 新增关闭确认方法
    def on_close(self):
        if messagebox.askyesno("退出", "确定要退出程序吗？", icon='question'):
            self.destroy()

    def _configure_styles(self):
        self.style.configure('.',
                             background='#000000',
                             foreground='white',
                             fieldbackground='#1a1a1a')
        self.style.map('TCombobox',
                       fieldbackground=[('readonly', '#1a1a1a')],
                       selectbackground=[('readonly', '#333333')],
                       selectforeground=[('readonly', 'white')])
        self.style.configure('TCombobox',
                             background='#1a1a1a',
                             arrowcolor='white',
                             bordercolor='#333333')
        self.style.configure('TCheckbutton',
                             background='#000000',
                             foreground='white',
                             indicatorcolor='#333333')
        self.style.map('TCheckbutton',
                       indicatorcolor=[('selected', '#00ff00')])
        self.style.configure("Vertical.TScale",
                             troughcolor='#333333',
                             sliderthickness=15,
                             sliderrelief='flat',
                             background='#4ECDC4')

    def load_config(self):
        self.config.read('config.ini')
        if not self.config.has_section('Settings'):
            self.config.add_section('Settings')
            self.config.set('Settings', 'auto_interval', '30')
            self.save_config()
        try:
            self.auto_switch_interval = int(self.config.get('Settings', 'auto_interval'))
        except (configparser.NoOptionError, ValueError):
            self.auto_switch_interval = 30
            self.config.set('Settings', 'auto_interval', '30')
            self.save_config()

    def save_config(self):
        with open('config.ini', 'w') as configfile:
            self.config.write(configfile)

    def init_ui(self):
        control_frame = tk.Frame(self, bg='#0a0a0a', padx=15, pady=15)
        control_frame.pack(side=tk.LEFT, fill=tk.Y)

        self.device_selector = ttk.Combobox(
            control_frame,
            font=self.tk_font,  # 使用动态字体
            width=25,
            state='readonly'
        )
        self.device_selector.pack(pady=10)
        self.device_selector.bind('<<ComboboxSelected>>', self.select_device)

        self.auto_toggle = tk.BooleanVar()
        self.auto_toggle_label = tk.StringVar()
        self.auto_toggle_label.set(f"自动轮巡（{self.auto_switch_interval}秒）")
        ttk.Checkbutton(
            control_frame,
            textvariable=self.auto_toggle_label,
            variable=self.auto_toggle,
            command=self.toggle_auto_switch,
            style='TCheckbutton'  # 确保应用自定义样式
        ).pack(pady=5)

        self.status_indicator = tk.Canvas(
            control_frame,
            width=28,
            height=28,
            bg='#0a0a0a',
            highlightthickness=0
        )
        self.status_indicator.pack(pady=15)
        self.led = self.status_indicator.create_oval(4, 4, 24, 24, fill='#333333')

        scale_frame = tk.Frame(control_frame, bg='#0a0a0a')
        scale_frame.pack(pady=15)

        self.scale_label = tk.Label(
            scale_frame,
            text=f"{self.auto_switch_interval}s",
            bg='#0a0a0a',
            fg='white',
            font=self.tk_font  # 使用动态字体
        )
        self.scale_label.pack(side=tk.RIGHT, padx=5)

        self.time_scale = ttk.Scale(
            scale_frame,
            from_=10,
            to=60,
            orient=tk.VERTICAL,
            length=150,
            style="Vertical.TScale",
            command=self.update_interval
        )
        self.time_scale.set(self.auto_switch_interval)
        self.time_scale.pack(side=tk.LEFT)

        self.figure = Figure(figsize=(11, 7), facecolor='#0a0a0a')
        self.ax_cpu = self.figure.add_subplot(311)
        self.ax_mem = self.figure.add_subplot(312)
        self.ax_network = self.figure.add_subplot(313)
        self.setup_axes()

        self.chart_canvas = FigureCanvasTkAgg(self.figure, master=self)
        self.chart_canvas.get_tk_widget().pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

    def setup_axes(self):
        # 创建字体属性对象
        title_font = font_manager.FontProperties(family=self.plot_font_family, size=10)
        label_font = font_manager.FontProperties(family=self.plot_font_family, size=9)
        legend_font = font_manager.FontProperties(family=self.plot_font_family, size=8)

        for ax in [self.ax_cpu, self.ax_mem, self.ax_network]:
            ax.set_facecolor('#000000')
            ax.tick_params(axis='both', colors='white')

            # 设置轴标签字体
            ax.xaxis.label.set_color('white')
            ax.xaxis.label.set_fontproperties(label_font)
            ax.yaxis.label.set_color('white')
            ax.yaxis.label.set_fontproperties(label_font)

            # 设置刻度标签字体
            for label in ax.get_xticklabels():
                label.set_fontproperties(label_font)
                label.set_color('white')
            for label in ax.get_yticklabels():
                label.set_fontproperties(label_font)
                label.set_color('white')

            for spine in ax.spines.values():
                spine.set_color('#4a4a4a')

        self.ax_cpu.set_title('CPU利用率 (%)', color='white', pad=10, fontproperties=title_font)
        self.ax_mem.set_title('内存使用率 (%)', color='white', pad=10, fontproperties=title_font)
        self.ax_network.set_title('网络流量 (KB/s)', color='white', pad=10, fontproperties=title_font)
        self.figure.tight_layout(pad=3.0)

    def update_interval(self, value):
        interval = int(float(value))
        self.auto_switch_interval = interval
        self.scale_label.config(text=f"{interval}s")
        self.auto_toggle_label.set(f"自动轮巡（{interval}秒）")
        self.config.set('Settings', 'auto_interval', str(interval))
        self.save_config()

    def refresh_ui(self):
        device_list = []
        current_time = time.time()
        with self.dev_mgr.device_lock:
            for dev in self.dev_mgr.active_devices:
                status = '在线' if (current_time - dev['last_seen']) < self.dev_mgr.heartbeat_timeout else '离线'
                device_list.append(f"{dev['name']} ({dev['ip']}) - {status}")

        if self.device_selector['values'] != device_list:
            self.device_selector['values'] = device_list

        # 更新状态指示灯
        led_color = '#00ff00' if any(
            (current_time - dev['last_seen']) < self.dev_mgr.heartbeat_timeout
            for dev in self.dev_mgr.active_devices
        ) else '#ff0000'
        self.status_indicator.itemconfig(self.led, fill=led_color)

        # 更新图表
        if self.current_device:
            self.update_charts(self.current_device)

        self.after(1000, self.refresh_ui)

    def select_device(self, event):
        selected = self.device_selector.get()
        if '(' in selected and ')' in selected:
            ip = selected.split('(')[1].split(')')[0]
            self.switch_to_device(ip)

    def toggle_auto_switch(self):
        if self.auto_toggle.get():
            threading.Thread(target=self.auto_switch_task, daemon=True).start()

    def auto_switch_task(self):
        while self.auto_toggle.get():
            if time.time() - self.dev_mgr.last_switch > self.auto_switch_interval:
                with self.dev_mgr.device_lock:
                    if self.dev_mgr.active_devices:
                        self.dev_mgr.current_index = (self.dev_mgr.current_index + 1) % len(self.dev_mgr.active_devices)
                        target = self.dev_mgr.active_devices[self.dev_mgr.current_index]
                        self.switch_to_device(target['ip'])
                        self.dev_mgr.last_switch = time.time()
            time.sleep(1)

    def switch_to_device(self, target_ip):
        with self.dev_mgr.device_lock:
            target = next((d for d in self.dev_mgr.active_devices if d['ip'] == target_ip), None)
            if target:
                self.current_device = target
                self.update_charts(target)

    def update_charts(self, device):
        colors = {
            'cpu': '#FF6B6B',
            'mem': '#4ECDC4',
            'net_up': '#2E86C1',
            'net_down': '#A569BD'
        }

        # 创建字体属性对象
        legend_font = font_manager.FontProperties(family=self.plot_font_family, size=9)
        label_font = font_manager.FontProperties(family=self.plot_font_family, size=8)

        self.ax_cpu.clear()
        self.ax_cpu.plot(
            device['data']['cpu_history'],
            color=colors['cpu'],
            linewidth=1.5,
            label='CPU利用率'
        )
        self.ax_cpu.set_ylim(0, 100)
        self.ax_cpu.legend(loc='upper right', facecolor='#1a1a1a',
                           labelcolor='white', prop=legend_font)

        self.ax_mem.clear()
        self.ax_mem.plot(
            device['data']['mem_history'],
            color=colors['mem'],
            linewidth=1.5,
            label='内存使用率'
        )
        self.ax_mem.set_ylim(0, 100)
        self.ax_mem.legend(loc='upper right', facecolor='#1a1a1a',
                           labelcolor='white', prop=legend_font)

        self.ax_network.clear()
        self.ax_network.plot(
            device['data']['net_up_history'],
            color=colors['net_up'],
            linestyle='-',
            linewidth=1.2,
            label='上传速度'
        )
        self.ax_network.plot(
            device['data']['net_down_history'],
            color=colors['net_down'],
            linestyle='--',
            linewidth=1.2,
            label='下载速度'
        )
        self.ax_network.legend(loc='upper right', facecolor='#1a1a1a',
                               labelcolor='white', prop=legend_font)

        # 设置网络流量轴的最大值，避免空数据时报错
        up_max = max(device['data']['net_up_history']) if device['data']['net_up_history'] else 1
        down_max = max(device['data']['net_down_history']) if device['data']['net_down_history'] else 1
        y_max = max(up_max, down_max, 1)
        self.ax_network.set_ylim(0, y_max * 1.1)

        # 重新应用标签字体
        for ax in [self.ax_cpu, self.ax_mem, self.ax_network]:
            for label in ax.get_xticklabels():
                label.set_fontproperties(label_font)
            for label in ax.get_yticklabels():
                label.set_fontproperties(label_font)

        self.figure.tight_layout(pad=3.0)
        self.chart_canvas.draw()

    def start_listener(self):
        def listener():
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                s.bind(('0.0.0.0', 12345))
                s.listen(5)
                print("监听服务已启动...")
                while True:
                    conn, addr = s.accept()
                    threading.Thread(target=self.handle_connection, args=(conn,), daemon=True).start()

        threading.Thread(target=listener, daemon=True).start()

    def handle_connection(self, conn):
        try:
            raw_data = conn.recv(4096)
            if not raw_data:
                return

            device_data = json.loads(raw_data.decode())
            ip = conn.getpeername()[0]

            processed = {
                'ip': ip,
                'name': device_data.get('name', '未命名设备'),
                'cpu': device_data.get('data', {}).get('cpu', 0),
                'mem': device_data.get('data', {}).get('mem', 0),
                'disk': device_data.get('data', {}).get('disk', 0),
                'net_up': device_data.get('data', {}).get('net_up', 0),
                'net_down': device_data.get('data', {}).get('net_down', 0)
            }

            self.dev_mgr.update_device(processed)

        except (json.JSONDecodeError, KeyError) as e:
            print(f"数据解析错误: {str(e)}")
        except Exception as e:
            print(f"连接处理异常: {str(e)}")
        finally:
            conn.close()


if __name__ == "__main__":
    # 解决 macOS 特定的 TKinter 问题
    if platform.system() == 'Darwin':
        import matplotlib as mpl

        mpl.use('TkAgg')  # 强制使用TkAgg后端

    app = ReceiverPro()
    app.mainloop()