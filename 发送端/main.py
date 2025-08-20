import tkinter as tk
from tkinter import messagebox
import psutil
import socket
import json
from datetime import datetime
import threading
import configparser
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from collections import deque
import matplotlib.pyplot as plt
import platform
import sys
from matplotlib import font_manager


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


# 设置matplotlib支持中文显示
chosen_font = find_chinese_font()
plt.rcParams['font.sans-serif'] = [chosen_font]
plt.rcParams['axes.unicode_minus'] = False

# 设置Tkinter字体
if platform.system() == 'Windows':
    tk_font = ('Microsoft YaHei', 10)
elif platform.system() == 'Darwin':  # macOS
    tk_font = ('PingFang SC', 10)
else:  # Linux
    tk_font = ('WenQuanYi Micro Hei', 10)

print(f"Using font: {chosen_font} for matplotlib")
print(f"Using Tkinter font: {tk_font}")

# GPU支持检测
try:
    import GPUtil

    GPU_ENABLED = True
except ImportError:
    GPU_ENABLED = False


class PerformanceMonitor:
    def __init__(self):
        # 初始化主窗口
        self.root = tk.Tk()
        self.root.title("服务器性能监视软件发送端")
        self.root.geometry("1024x768")
        self.root.attributes('-alpha', 0.85)
        self.root.configure(bg='#1a1a1a')


        if platform.system() == 'Windows':
            self.root.iconbitmap('send.ico')
        else:
        # macOS/Linux 推荐使用 .png
            try:
                from tkinter import PhotoImage
                icon = PhotoImage(file='send.png')
                self.root.iconphoto(True, icon)
            except Exception as e:
                print(f"设置图标失败: {e}")

        # 运行状态控制
        self.running = True
        self.after_id = None  # 用于跟踪定时任务

        # 配置和数据结构初始化
        self.config = configparser.ConfigParser()
        self.config.read('config.ini')
        self.history = {
            'cpu': deque(maxlen=60),
            'mem': deque(maxlen=60),
            'disk': deque(maxlen=60),
            'net_up': deque(maxlen=60),
            'net_down': deque(maxlen=60),
            'gpu': deque(maxlen=60)
        }

        # 初始化界面和绑定事件
        self.init_ui()
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.start_monitoring()

    def init_ui(self):
        """初始化用户界面组件"""
        # 创建图表
        self.figure = Figure(figsize=(10, 6), facecolor='#1a1a1a')
        self.ax = self.figure.add_subplot(111)
        self.ax.set_facecolor('#1a1a1a')
        self.ax.tick_params(colors='white')
        self.ax.spines['bottom'].set_color('white')
        self.ax.spines['top'].set_color('white')
        self.ax.spines['right'].set_color('white')
        self.ax.spines['left'].set_color('white')
        self.ax.xaxis.label.set_color('white')
        self.ax.yaxis.label.set_color('white')

        self.canvas = FigureCanvasTkAgg(self.figure, master=self.root)
        self.canvas.get_tk_widget().pack(expand=True, fill=tk.BOTH, padx=20, pady=20)

        # 实时数据状态栏
        self.status_frame = tk.Frame(self.root, bg='#1a1a1a')
        self.status_frame.pack(pady=10)

        status_labels = [
            ('CPU', 'cyan'), ('内存', 'yellow'),
            ('磁盘', 'magenta'), ('上行', 'green'),
            ('下行', 'blue')
        ]
        if GPU_ENABLED:
            status_labels.append(('GPU', 'red'))

        self.status_vars = {}
        for i, (text, color) in enumerate(status_labels):
            frame = tk.Frame(self.status_frame, bg='#1a1a1a')
            frame.grid(row=0, column=i, padx=10)
            tk.Label(frame, text=f"{text}:", fg=color, bg='#1a1a1a', font=tk_font).pack(side=tk.LEFT)
            var = tk.StringVar(value="0.0%")
            tk.Label(frame, textvariable=var, fg='white', bg='#1a1a1a', font=tk_font).pack(side=tk.LEFT)
            self.status_vars[text] = var

    def get_performance(self):
        """获取系统性能指标"""
        # CPU使用率
        cpu = psutil.cpu_percent()

        # 内存使用率
        mem = psutil.virtual_memory().percent

        # 磁盘使用率
        disk = psutil.disk_usage('/').percent

        # 网络流量
        net = psutil.net_io_counters()
        net_up = net.bytes_sent
        net_down = net.bytes_recv

        # GPU使用率（如果可用）
        gpu_load = None
        if GPU_ENABLED:
            try:
                gpus = GPUtil.getGPUs()
                if gpus:
                    gpu_load = gpus[0].load * 100
            except Exception as e:
                print(f"获取GPU数据失败: {str(e)}")

        return {
            'time': datetime.now().isoformat(),
            'cpu': cpu,
            'mem': mem,
            'disk': disk,
            'net_up': net_up,
            'net_down': net_down,
            'gpu': gpu_load
        }

    def update_ui(self, data):
        """更新界面显示"""
        # 清除旧图表
        self.ax.clear()

        # 设置坐标轴颜色
        self.ax.set_facecolor('#1a1a1a')
        self.ax.tick_params(colors='white')
        self.ax.spines['bottom'].set_color('white')
        self.ax.spines['top'].set_color('white')
        self.ax.spines['right'].set_color('white')
        self.ax.spines['left'].set_color('white')
        self.ax.xaxis.label.set_color('white')
        self.ax.yaxis.label.set_color('white')

        # 绘制新数据
        lines = [
            (self.history['cpu'], 'CPU', 'cyan'),
            (self.history['mem'], '内存', 'yellow'),
            (self.history['disk'], '磁盘', 'magenta')
        ]
        if GPU_ENABLED and self.history['gpu']:
            lines.append((self.history['gpu'], 'GPU', 'red'))

        for values, label, color in lines:
            if values:
                self.ax.plot(values, label=label, color=color, alpha=0.8)

        # 设置图表属性
        self.ax.set_ylim(0, 100)
        self.ax.set_xlabel('时间（秒）', color='white')
        self.ax.set_ylabel('使用率 (%)', color='white')
        self.ax.legend(facecolor='#1a1a1a', labelcolor='white', prop={'size': 9})
        self.ax.grid(True, color='#333333', linestyle='--', alpha=0.3)
        self.canvas.draw()

        # 更新数值显示
        self.status_vars['CPU'].set(f"{data['cpu']:.1f}%")
        self.status_vars['内存'].set(f"{data['mem']:.1f}%")
        self.status_vars['磁盘'].set(f"{data['disk']:.1f}%")

        # 计算网络速度 (KB/s)
        net_up = data['net_up'] // 1024
        net_down = data['net_down'] // 1024
        self.status_vars['上行'].set(f"{net_up}KB/s")
        self.status_vars['下行'].set(f"{net_down}KB/s")

        if GPU_ENABLED:
            gpu_text = f"{data['gpu']:.1f}%" if data['gpu'] else "N/A"
            self.status_vars['GPU'].set(gpu_text)

    def send_data(self):
        """执行监控和数据发送"""
        if not self.running:
            return

        try:
            # 获取并处理性能数据
            data = self.get_performance()

            # 更新历史记录
            self.history['cpu'].append(data['cpu'])
            self.history['mem'].append(data['mem'])
            self.history['disk'].append(data['disk'])
            if data['gpu'] is not None:
                self.history['gpu'].append(data['gpu'])

            # 准备发送数据
            payload = {
                'name': self.config['sender']['computer_name'],
                'data': data
            }

            # 启动发送线程
            threading.Thread(
                target=self.send_to_server,
                args=(
                    self.config['sender']['receiver_ip'],
                    self.config.getint('sender', 'receiver_port'),
                    json.dumps(payload).encode()
                ),
                daemon=True
            ).start()

            # 发送日志信息
            log_msg = f"[{data['time']}] {payload['name']} - CPU:{data['cpu']}% MEM:{data['mem']}%"
            threading.Thread(
                target=self.send_to_server,
                args=(
                    self.config['sender']['log_server_ip'],
                    self.config.getint('sender', 'log_server_port'),
                    log_msg.encode()
                ),
                daemon=True
            ).start()

            # 更新界面
            self.update_ui(data)

        except Exception as e:
            print(f"数据采集/发送异常: {str(e)}")

        # 调度下一次执行
        self.after_id = self.root.after(1000, self.send_data)

    def send_to_server(self, ip, port, data):
        """网络发送方法"""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(2)
                s.connect((ip, port))
                s.sendall(data)
        except Exception as e:
            print(f"连接错误 ({ip}:{port}): {str(e)}")

    def on_close(self):
        """处理关闭事件（新增确认对话框）"""
        if messagebox.askyesno(
                "退出确认",
                "确定要退出程序吗？",
                parent=self.root
        ):
            print("正在执行退出操作...")
            self.running = False

            # 取消定时任务
            if self.after_id:
                self.root.after_cancel(self.after_id)

            # 销毁窗口
            self.root.destroy()
            print("资源已释放，程序退出")

    def start_monitoring(self):
        """启动监控循环"""
        self.root.after(1000, self.send_data)
        self.root.mainloop()


if __name__ == "__main__":
    monitor = PerformanceMonitor()