# 导入GUI、系统监控、网络、配置、绘图库等相关模块
import tkinter as tk
from tkinter import messagebox
import psutil  # 系统性能监控
import socket  # 网络通信
import json    # 数据序列化
from datetime import datetime  # 时间戳
import threading  # 多线程
import configparser  # 配置文件解析
from matplotlib.figure import Figure  # 图表对象
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg  # 嵌入Tkinter
from collections import deque  # 高效队列
import matplotlib.pyplot as plt
from matplotlib import font_manager  # 字体管理
import os
import sys
import platform
import subprocess
import time

def get_system_fonts():
    # 获取当前操作系统中所有可用字体名称列表。
    # 用于后续自动选择合适的中文字体，保证界面和图表的中文显示正常。
    fonts = set()
    for f in font_manager.findSystemFonts():
        try:
            fonts.add(font_manager.FontProperties(fname=f).get_name())
        except Exception:
            # 某些字体文件可能无法识别，忽略异常
            pass
    return sorted(fonts)


def find_chinese_font():
    # 自动检测并返回当前系统可用的中文字体名称。
    # 优先选择常见的中文字体，保证matplotlib和Tkinter界面中文显示无乱码。
    # 针对不同操作系统，设定常用中文字体候选列表
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
    # 添加通用字体备选
    candidates += ['sans-serif', 'Arial', 'Helvetica']
    # 检查系统中实际存在的字体，返回第一个可用的
    system_fonts = get_system_fonts()
    for font in candidates:
        if font in system_fonts:
            return font

    # 如果都没有，返回第一个备选字体
    return candidates[0] if candidates else 'sans-serif'



# 设置matplotlib和Tkinter的中文字体，保证跨平台中文显示
chosen_font = find_chinese_font()
plt.rcParams['font.sans-serif'] = [chosen_font]  # matplotlib中文字体
plt.rcParams['axes.unicode_minus'] = False       # 负号正常显示

# Tkinter界面字体设置
if platform.system() == 'Windows':
    tk_font = ('Microsoft YaHei', 10)
elif platform.system() == 'Darwin':
    tk_font = ('PingFang SC', 10)
else:
    tk_font = ('WenQuanYi Micro Hei', 10)

print(f"Using font: {chosen_font} for matplotlib")
print(f"Using Tkinter font: {tk_font}")

# 检查是否支持GPU监控（可选依赖GPUtil）
try:
    import GPUtil
    GPU_ENABLED = True
except ImportError:
    GPU_ENABLED = False


class LinuxTray:
    # Linux桌面环境下的系统托盘功能实现（无阻塞线程方式）。
    # 支持AppIndicator3、pystray或Tkinter多种方案，自动适配。
    def __init__(self, app):
        self.app = app
        # 启动系统托盘功能，采用新线程防止阻塞主界面
        threading.Thread(target=self.init_tray, daemon=True).start()

    def init_tray(self):
        # 初始化系统托盘（优先AppIndicator3，失败则回退pystray或Tkinter）。
        # 采用延迟导入，兼容不同Linux发行版。
        try:
            # 优先尝试AppIndicator3方案
            from PIL import Image, ImageDraw
            import gi
            gi.require_version('Gtk', '3.0')
            gi.require_version('AppIndicator3', '0.1')
            from gi.repository import Gtk, AppIndicator3

            # 创建托盘图标及菜单
            indicator = AppIndicator3.Indicator.new(
                "performance-monitor",
                "utilities-system-monitor",
                AppIndicator3.IndicatorCategory.APPLICATION_STATUS
            )
            indicator.set_status(AppIndicator3.IndicatorStatus.ACTIVE)

            menu = Gtk.Menu()
            show_item = Gtk.MenuItem.new_with_label("显示")
            show_item.connect("activate", self.on_show)
            menu.append(show_item)
            settings_item = Gtk.MenuItem.new_with_label("设置")
            settings_item.connect("activate", self.on_settings)
            menu.append(settings_item)
            exit_item = Gtk.MenuItem.new_with_label("退出")
            exit_item.connect("activate", self.on_exit)
            menu.append(exit_item)
            menu.show_all()
            indicator.set_menu(menu)
            Gtk.main()
        except ImportError:
            # 如果AppIndicator3不可用，自动回退到pystray方案
            self.fallback_tray()


    def on_show(self, *args):
        # 托盘菜单：显示主窗口
        self.app.root.after(0, self.app.restore_from_tray)

    def on_settings(self, *args):
        # 托盘菜单：打开设置界面
        self.app.root.after(0, self.app.open_config)

    def on_exit(self, *args):
        # 托盘菜单：退出应用
        self.app.root.after(0, self.app.exit_app)

    def fallback_tray(self):
        # pystray实现的系统托盘（回退方案），如pystray不可用则最终回退Tkinter菜单。
        try:
            from pystray import Icon, Menu, MenuItem
            from PIL import Image, ImageDraw
            # 创建简易16x16绿色方块图标
            image = Image.new('RGB', (16, 16), 'black')
            dc = ImageDraw.Draw(image)
            dc.rectangle([(4, 4), (12, 12)], fill='green')
            # 构建托盘菜单
            menu = Menu(
                MenuItem('显示', self.on_show),
                MenuItem('设置', self.on_settings),
                MenuItem('退出', self.on_exit)
            )
            tray = Icon("Performance Monitor", image, menu=menu)
            tray.run()
        except Exception:
            # 所有方案都失败，使用Tkinter右键菜单作为最后回退
            self.create_tk_tray()

    def create_tk_tray(self):
        # Tkinter简易托盘方案
        self.app.show_tray_menu = True
        self.app.tray_menu = tk.Menu(self.app.root, tearoff=0)
        self.app.tray_menu.add_command(label="显示", command=self.app.restore_from_tray)
        self.app.tray_menu.add_command(label="设置", command=self.app.open_config)
        self.app.tray_menu.add_separator()
        self.app.tray_menu.add_command(label="退出", command=self.app.exit_app)



def open_config_file(file_path):
    # 打开配置文件，自动调用系统默认文本编辑器。
    # 针对不同操作系统自动适配，最大程度兼容用户环境。
    try:
        if platform.system() == 'Windows':
            # Windows平台：调用记事本
            subprocess.Popen(['notepad', file_path], shell=True)
        elif platform.system() == 'Darwin':
            # macOS平台：调用TextEdit
            subprocess.Popen(['open', '-a', 'TextEdit', file_path])
        else:
            # Linux平台：优先尝试常见编辑器
            editors = ['gedit', 'kate', 'xed', 'nano']
            for editor in editors:
                try:
                    if subprocess.call(['which', editor], stdout=subprocess.PIPE, stderr=subprocess.PIPE) == 0:
                        subprocess.Popen([editor, file_path])
                        return
                except Exception:
                    continue
            # 若无图形编辑器，尝试xdg-open
            subprocess.Popen(['xdg-open', file_path])
    except Exception as e:
        print(f"打开配置文件时出错: {str(e)}")
        # 所有方案失败时的最终回退
        try:
            if platform.system() == 'Windows':
                subprocess.Popen(['notepad', file_path], shell=True)
            elif platform.system() == 'Darwin':
                subprocess.Popen(['open', file_path])
            else:
                subprocess.Popen(['nano', file_path])
        except Exception:
            print("所有尝试打开配置文件的方案都失败了")


class PerformanceMonitor:
    def __init__(self):
        # 初始化主程序，包括主窗口、状态、配置、历史数据、界面、托盘和监控循环。
        # 创建主窗口，设置标题、大小、透明度和背景色
        self.root = tk.Tk()
        self.root.title("服务器性能监视软件发送端")
        self.root.geometry("1024x768")
        self.root.attributes('-alpha', 0.85)
        self.root.configure(bg='#1a1a1a')

        # 设置窗口图标，兼容多平台
        if platform.system() == 'Windows':
            self.root.iconbitmap('send.ico')
        else:
            try:
                from tkinter import PhotoImage
                icon = PhotoImage(file='send.png')
                self.root.iconphoto(True, icon)
            except Exception as e:
                print(f"设置图标失败: {e}")

        # 启动时先隐藏主窗口（托盘模式）
        self.root.withdraw()

        # 初始化运行状态、定时器、托盘菜单等
        self.running = True
        self.after_id = None
        self.tray_menu = None
        self.show_tray_menu = False
        self.tray_support = None

        # 加载配置文件，初始化历史数据队列
        self.config = configparser.ConfigParser()
        self.config.read('config.ini')
        self.history = {
            'cpu': deque(maxlen=60),    # CPU历史
            'mem': deque(maxlen=60),    # 内存历史
            'disk': deque(maxlen=60),   # 磁盘历史
            'net_up': deque(maxlen=60), # 上行速率历史
            'net_down': deque(maxlen=60), # 下行速率历史
            'gpu': deque(maxlen=60)     # GPU历史
        }

        # 初始化界面组件和事件绑定
        self.init_ui()
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        # 创建系统托盘图标（多平台适配）
        self.create_system_tray()

        # 启动性能监控主循环
        self.start_monitoring()

    def create_system_tray(self):
       # 创建系统托盘图标，自动适配Windows、Linux、macOS等平台。
       # 优先使用pystray/AppIndicator/rumps，失败则回退Tkinter菜单。
        try:
            if platform.system() == 'Windows':
                self.create_pystray_tray()
            elif platform.system() == 'Linux':
                self.tray_support = LinuxTray(self)
            elif platform.system() == 'Darwin':
                self.create_macos_tray()
            else:
                self.create_pystray_tray()
        except Exception as e:
            print(f"创建系统托盘失败: {str(e)}")
            self.create_tk_tray()

    def create_pystray_tray(self):
        # 为Windows和macOS创建托盘图标
        try:
            # 尝试导入pystray
            import pystray
            from PIL import Image, ImageDraw
            print("使用pystray创建托盘图标")

            # 创建托盘图标
            icon_path = 'send.ico' if platform.system() == 'Windows' else 'send.png'
            if not os.path.exists(icon_path):
                # 如果图片不存在，回退到原有绿色方块
                from PIL import ImageDraw
                image = Image.new('RGB', (16, 16), 'black')
                dc = ImageDraw.Draw(image)
                dc.rectangle([(4, 4), (12, 12)], fill='green')
            else:
                image = Image.open(icon_path)


            # 托盘菜单
            menu = pystray.Menu(
                pystray.MenuItem('显示', self.restore_from_tray),
                pystray.MenuItem('设置', self.open_config),
                pystray.MenuItem('退出', self.exit_app)
            )

            # 在独立线程中运行托盘
            self.tray_icon = pystray.Icon("Performance Monitor", image, "性能监控", menu)
            threading.Thread(target=self.tray_icon.run, daemon=True).start()
            print("pystray托盘图标创建成功")
        except ImportError:
            print("pystray未安装，使用tkinter回退方案")
            # 使用tkinter回退方案
            self.create_tk_tray()
        except Exception as e:
            print(f"pystray创建托盘失败: {str(e)}")
            # 使用tkinter回退方案
            self.create_tk_tray()

    def create_macos_tray(self):
        # macOS托盘实现
        try:
            # 尝试使用rumps库
            import rumps
            print("使用rumps创建macOS托盘图标")

            class MacOSTray(rumps.App):
                def __init__(self, app):
                    super().__init__("性能监控", quit_button=None)
                    self.app = app

                    # 添加菜单项
                    self.menu = [
                        rumps.MenuItem("显示", callback=self.on_show),
                        rumps.MenuItem("设置", callback=self.on_settings),
                        None,
                        rumps.MenuItem("退出", callback=self.on_exit)
                    ]

                def on_show(self, sender):
                    self.app.root.after(0, self.app.restore_from_tray)

                def on_settings(self, sender):
                    self.app.root.after(0, self.app.open_config)

                def on_exit(self, sender):
                    self.app.root.after(0, self.app.exit_app)

            # 启动托盘
            self.macos_tray = MacOSTray(self)
            threading.Thread(target=self.macos_tray.run, daemon=True).start()
            print("rumps托盘图标创建成功")
        except ImportError:
            print("rumps未安装，尝试pystray")
            # 回退到pystray
            self.create_pystray_tray()
        except Exception as e:
            print(f"macOS托盘创建失败: {str(e)}")
            # 回退到tkinter
            self.create_tk_tray()

    def create_tk_tray(self):
        # Tkinter托盘回退方案
        print("使用Tkinter回退方案创建托盘菜单")
        self.show_tray_menu = True
        self.tray_menu = tk.Menu(self.root, tearoff=0)
        self.tray_menu.add_command(label="显示", command=self.restore_from_tray)
        self.tray_menu.add_command(label="设置", command=self.open_config)
        self.tray_menu.add_separator()
        self.tray_menu.add_command(label="退出", command=self.exit_app)

        # 绑定右键菜单
        self.root.bind("<Button-3>", self.show_tray_menu)
        # 添加任务栏图标
        try:
            self.root.iconbitmap(default=self.create_tray_icon())
        except:
            pass

    def show_tray_menu(self, event):
        # 显示Tkinter托盘菜单
        if self.show_tray_menu:
            try:
                self.tray_menu.tk_popup(event.x_root, event.y_root)
            finally:
                self.tray_menu.grab_release()

    def create_tray_icon(self):
        # 创建托盘图标文件
        try:
            import tempfile
            from PIL import Image, ImageDraw
            import base64
            import io

            # 如果已经有图标文件，直接使用
            icon_path = getattr(self, '_tray_icon_path', None)
            if icon_path and os.path.exists(icon_path):
                return icon_path

            # 创建简单的绿色方块图标
            img = Image.new('RGBA', (64, 64), (0, 0, 0, 0))
            draw = ImageDraw.Draw(img)
            draw.rectangle([(16, 16), (48, 48)], fill='green')

            # 如果是Windows或macOS，创建临时ICO文件
            if platform.system() == 'Windows':
                icon_path = os.path.join(tempfile.gettempdir(), "perfmon.ico")
                img.save(icon_path, format='ICO')
                self._tray_icon_path = icon_path
                return icon_path

            # Linux或其他系统使用PNG格式
            icon_path = os.path.join(tempfile.gettempdir(), "perfmon.png")
            img.save(icon_path, format='PNG')
            self._tray_icon_path = icon_path
            return icon_path

        except ImportError:
            # 如果PIL不可用，尝试创建base64编码的图标
            if platform.system() == 'Windows':
                # Windows ICO格式的base64
                icon_data = base64.b64decode(
                    "AAABAAEAICAAAAEAIACoEAAAFgAAACgAAAAgAAAAQAAAAAEAIAAAAAAAABAAACMuAAAjLgAAAA==")
                icon_path = os.path.join(tempfile.gettempdir(), "perfmon.ico")
                with open(icon_path, "wb") as f:
                    f.write(icon_data)
                return icon_path
            else:
                # PNG格式的base64
                icon_data = base64.b64decode(
                    "iVBORw0KGgoAAAANSUhEUgAAAEAAAABACAIAAAAlC+aJAAAACXBIWXMAAAsTAAALEwEAmpwYAAAB8UlEQVR42u2YsUoDQRCGX3JgYxEWFjYi2IlgFfoAr7W18iGsLYIgCKmDgviIgiAWF0QRi4AgIiK+QF6QhxArG1tB8BV8hpnMzd5etHfBvZvY+M/w78wsszuzsyuCIAhCCJqY8H1rDkZ6a2sH3U6mUoD8bO90KpXQbNTr5/3+fr2+02ymUq+4w1ar1e4mQ7u1jK0A8BZ6qgB9s4+Q5K5SJXwXzXrB+7y+XyF8F0wXQxG9T5NQfqY0HfHq6wjU3iKq4y5QH6d7jJbQ9mGd3Vr0i5k7e4z2+1w3Gx7aM0+8m2A2Q0fD0aV3C6fq4d1Kc1t3QJpUuQ1wQqB0pWqo4RzNc1wGvxLAL7MhI5p2uTZQ7O1Z9gRZQvqTpP9HlQ/0xR8Q4pVwQzK+SLdA2qDlI8pX0r4f3yXbZkC/KoA1X1D3h7v2e1fI0bOc5W+oQj0ZbDv/7gOQ1+1lXvFh4A6BQhTpYbXeHpXaHVG5w3oP3wP1oGfQKf9LdFvD7vPx1R3c3H9BZ5m1qj5A/p4z4ZQ+0AAAAAElFTkSuQmCC")
                icon_path = os.path.join(tempfile.gettempdir(), "perfmon.png")
                with open(icon_path, "wb") as f:
                    f.write(icon_data)
                return icon_path
        except Exception:
            # 所有方案都失败，返回None
            return None

    def restore_from_tray(self):
        # 从托盘恢复窗口
        self.root.deiconify()
        self.root.lift()
        self.root.focus_set()
        self.root.state('normal')

    def open_config(self):
        # 打开配置文件
        config_path = os.path.abspath('config.ini')
        print(f"打开配置文件: {config_path}")

        # 检查配置文件是否存在
        if not os.path.exists(config_path):
            print("配置文件不存在，创建默认配置")
            self.create_default_config()

        # 使用系统文本编辑器打开文件
        open_config_file(config_path)

    def create_default_config(self):
        # 创建默认配置文件
        config = configparser.ConfigParser()
        config['sender'] = {
            'computer_name': socket.gethostname(),
            'receiver_ip': '127.0.0.1',
            'receiver_port': '9999',
            'log_server_ip': '127.0.0.1',
            'log_server_port': '8888'
        }
        with open('config.ini', 'w') as configfile:
            config.write(configfile)

    def exit_app(self):
        # 退出应用程序
        self.running = False
        if self.after_id:
            self.root.after_cancel(self.after_id)
        self.root.destroy()
        os._exit(0)  # 强制退出所有线程

    def init_ui(self):
        # 初始化用户界面组件
        # 创建图表
        self.figure = Figure(figsize=(10, 6), facecolor='#1a1a1a')
        self.ax = self.figure.add_subplot(111)
        self.ax.set_facecolor('#1a1a1a')
        self.ax.tick_params(colors='white')
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
        # 获取系统性能指标
        # CPU使用率
        cpu = psutil.cpu_percent(interval=0.5)

        # 内存使用率
        mem = psutil.virtual_memory().percent

        # 磁盘使用率
        disk = psutil.disk_usage('/').percent if platform.system() != 'Windows' else psutil.disk_usage('C:').percent

        # 网络流量 - 计算差值
        net = psutil.net_io_counters()
        net_up = net.bytes_sent
        net_down = net.bytes_recv

        # 等待1秒后再次采样计算速率
        time.sleep(1)
        net2 = psutil.net_io_counters()
        net_up_speed = (net2.bytes_sent - net_up) / 1024  # KB/s
        net_down_speed = (net2.bytes_recv - net_down) / 1024  # KB/s

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
            'net_up': net_up_speed,
            'net_down': net_down_speed,
            'gpu': gpu_load
        }

    def update_ui(self, data):
        # 更新界面显示
        # 清除旧图表
        self.ax.clear()

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
        self.ax.legend(facecolor='#1a1a1a', labelcolor='white')
        self.canvas.draw()

        # 更新数值显示
        self.status_vars['CPU'].set(f"{data['cpu']:.1f}%")
        self.status_vars['内存'].set(f"{data['mem']:.1f}%")
        self.status_vars['磁盘'].set(f"{data['disk']:.1f}%")
        self.status_vars['上行'].set(f"{data['net_up']:.1f}KB/s")
        self.status_vars['下行'].set(f"{data['net_down']:.1f}KB/s")
        if GPU_ENABLED:
            gpu_text = f"{data['gpu']:.1f}%" if data['gpu'] else "N/A"
            self.status_vars['GPU'].set(gpu_text)

    def send_data(self):
        # 执行监控和数据发送
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
            self.root.after(0, lambda: self.update_ui(data))

        except Exception as e:
            print(f"数据采集/发送异常: {str(e)}")

        # 调度下一次执行
        if self.running:
            self.after_id = self.root.after(1000, self.send_data)

    def send_to_server(self, ip, port, data):
        # 网络发送方法
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(2)
                s.connect((ip, port))
                s.sendall(data)
        except Exception as e:
            print(f"连接错误 ({ip}:{port}): {str(e)}")

    def on_close(self):
        # 处理关闭事件
        if messagebox.askyesno(
                "退出确认",
                "确定要退出程序吗？",
                parent=self.root
        ):
            self.running = False
            self.root.destroy()
            sys.exit(0)

    def start_monitoring(self):
        # 启动监控循环
        self.send_data()
        self.root.mainloop()


if __name__ == "__main__":
    # Linux特定设置
    if platform.system() == 'Linux':
        # 禁用Gnome的加速抑制
        os.environ.pop('GTK_MODULES', None)
        # 确保XDG_RUNTIME_DIR存在
        if 'XDG_RUNTIME_DIR' not in os.environ:
            os.environ['XDG_RUNTIME_DIR'] = f'/run/user/{os.getuid()}'
        # 创建运行时目录（如果不存在）
        os.makedirs(os.environ['XDG_RUNTIME_DIR'], exist_ok=True)

    # 启动主程序
    monitor = PerformanceMonitor()