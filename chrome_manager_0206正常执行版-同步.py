#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import os
from PIL import Image, ImageDraw, ImageFont
from PyQt6.QtWidgets import (QApplication, QWidget, QPushButton, QVBoxLayout,
                            QFileDialog, QListWidget, QLineEdit, QLabel, QHBoxLayout,
                            QSpinBox, QCheckBox, QMessageBox, QAbstractItemView,
                            QDialog, QTableWidget, QTableWidgetItem, QHeaderView, QComboBox,
                            QListWidgetItem, QRadioButton)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QMetaObject, Q_ARG, QObject, QTimer
import shutil
import subprocess
import json
import re,time
import logging
from datetime import datetime
import traceback
from pynput import keyboard
from PyQt6.QtCore import QTimer

os.environ['QT_MAC_WANTS_LAYER'] = '1'  # 解决MacOS图形层问题
os.environ['PYNPUT_BACKEND'] = 'darwin'  # 强制使用macOS原生后端

def safe_gui_update(widget, method, *args):
    QMetaObject.invokeMethod(
        widget,
        method,
        Qt.ConnectionType.QueuedConnection,
        *args
    )

# 在文件开头添加日志配置
def setup_logger():
    """配置日志系统"""
    # 创建logs目录（如果不存在）
    log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')
    os.makedirs(log_dir, exist_ok=True)
    
    # 创建日志文件名（使用当前时间）
    log_file = os.path.join(log_dir, f'chrome_sync_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log')
    
    # 配置日志格式
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    
    # 配置文件处理器
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setFormatter(formatter)
    
    # 配置控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    
    # 获取根日志记录器
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)
    
    # 添加处理器
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    logging.info(f"日志文件创建在: {log_file}")
    return logger

# 打印环境信息
print(f"Python 路径: {sys.executable}")
print(f"当前工作目录: {os.getcwd()}")
print(f"PYTHONPATH: {os.environ.get('PYTHONPATH', 'Not set')}")

try:
    print("开始导入模块...")
    
    # 尝试导入 PIL
    try:
        from PIL import Image, ImageDraw, ImageFont
        print("PIL 导入成功")
    except ImportError as e:
        print(f"PIL 导入失败: {e}")
        sys.exit(1)

    # 尝试导入 PyQt6
    try:
        from PyQt6.QtWidgets import (QApplication, QWidget, QPushButton, QVBoxLayout,
                                    QFileDialog, QListWidget, QLineEdit, QLabel, QHBoxLayout,
                                    QSpinBox, QCheckBox, QMessageBox, QAbstractItemView,
                                    QDialog, QTableWidget, QTableWidgetItem, QHeaderView, QComboBox,
                                    QListWidgetItem, QRadioButton)
        from PyQt6.QtCore import Qt, QThread, pyqtSignal, QMetaObject, Q_ARG
        print("PyQt6 导入成功")
    except ImportError as e:
        print(f"PyQt6 导入失败: {e}")
        sys.exit(1)

    import shutil
    import subprocess
    import json
    import re
    
    print("所有模块导入成功")

except Exception as e:
    print(f"发生错误: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# 添加用户的 Python 包路径
user_site_packages = os.path.expanduser('~/Library/Python/3.9/lib/python/site-packages')
if user_site_packages not in sys.path:
    sys.path.append(user_site_packages)

# 配置默认Chrome主程序路径
DEFAULT_CHROME_PATH = "/Applications/Google Chrome.app"  ##n cong nali fuzhi 
DEFAULT_STORAGE_PATH = "/Volumes/"  #mubiao dizhi

class ProxyConfigDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("代理配置")
        self.setModal(True)
        
        # 创建布局
        layout = QVBoxLayout()
        
        # 创建代理配置表格
        self.proxy_table = QTableWidget()
        self.proxy_table.setColumnCount(2)  # 只需要两列：浏览器名和代理配置
        self.proxy_table.setHorizontalHeaderLabels(["浏览器", "代理配置 (IP:port:username:password)"])
        
        # 设置表格列宽
        header = self.proxy_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        
        # 添加表格到布局
        layout.addWidget(self.proxy_table)
        
        # 添加说明标签
        help_label = QLabel("格式说明：IP:端口:用户名:密码")
        layout.addWidget(help_label)
        
        # 创建按钮布局
        button_layout = QHBoxLayout()
        
        # 创建保存和取消按钮
        save_button = QPushButton("保存")
        cancel_button = QPushButton("取消")
        
        save_button.clicked.connect(self.accept)
        cancel_button.clicked.connect(self.reject)
        
        button_layout.addWidget(save_button)
        button_layout.addWidget(cancel_button)
        
        # 添加按钮布局
        layout.addLayout(button_layout)
        
        # 设置对话框布局
        self.setLayout(layout)
        
        # 设置窗口大小
        self.resize(600, 400)

    def get_proxy_config(self):
        """获取表格中的代理配置"""
        config = {}
        for row in range(self.proxy_table.rowCount()):
            browser = self.proxy_table.item(row, 0)
            proxy = self.proxy_table.item(row, 1)
            
            if browser and proxy and proxy.text().strip():
                browser_name = browser.text()
                proxy_str = proxy.text().strip()
                # 验证格式
                parts = proxy_str.split(':')
                if len(parts) == 4:
                    config[browser_name] = proxy_str
        
        return config

class ListenerManager(QObject):
    error_occurred = pyqtSignal(str)
    sync_active = False

    def __init__(self, parent=None):
        super().__init__(parent)
        self.listener = None
        self.timer = QTimer()
        self.timer.timeout.connect(self.check_permissions)

    def start_listening(self):
        """启动监听的核心方法"""
        try:
            # 初始化监听器（示例代码，需替换实际逻辑）
            self.listener = SomeListener()  # 替换为实际的监听对象
            self.timer.start(1000)  # 启动定时检查（1秒间隔）
        except Exception as e:
            self.error_occurred.emit(f"启动监听失败: {str(e)}")

    def process_events(self):
        """处理累积的事件"""
        if self.mouse_listener:
            self.mouse_listener._run_until()
        if self.keyboard_listener:
            self.keyboard_listener._run_until()
    def show_permission_alert(self):
        # 显示系统级权限提示
        alert = NSAlert.alloc().init()
        alert.setMessageText_("需要辅助功能权限")
        alert.setInformativeText_("请前往系统设置 > 隐私与安全 > 辅助功能 中启用本程序的权限")
        alert.runModal()
    
    def check_accessibility_permission(self):
        """检查辅助功能权限"""
        options = kAXTrustedCheckOptionPrompt.takeUnretainedValue()
        return AXIsProcessTrustedWithOptions({options: True})

    def stop_listening(self):
        """停止监听的方法"""
        self.timer.stop()
        if self.listener:
            self.listener.close()
            self.listener = None

    def on_mouse_move(self, x, y):
        """处理鼠标移动事件"""
        if not self.sync_active:
            return
        try:
            self.logger.debug(f"处理鼠标移动: ({x}, {y})")
            # 获取主窗口的位置和大小
            cmd = f"""
            osascript -e '
            tell application "System Events"
                tell process "{self.main_window["name"]}"
                    get position and size of window 1
                end tell
            end tell'
            """
            result = subprocess.check_output(cmd, shell=True).decode('utf-8')
            main_pos = [int(x) for x in result.strip().split(', ')]
            
            # 计算相对位置
            rel_x = (x - main_pos[0]) / main_pos[2]
            rel_y = (y - main_pos[1]) / main_pos[3]
            
            # 同步到其他窗口
            for window in self.selected_windows:
                if window != self.main_window:
                    self.move_mouse_to_window(window, rel_x, rel_y)
        except Exception as e:
            self.logger.error(f"鼠标移动同步失败: {e}", exc_info=True)
            self.error_occurred.emit(str(e))

    def on_mouse_click(self, x, y, button, pressed):
        """处理鼠标点击事件"""
        if not self.sync_active:
            return
        try:
            for window in self.selected_windows:
                if window != self.main_window:
                    self.click_at_window(window, x, y, button, pressed)
        except Exception as e:
            self.logger.error(f"鼠标点击同步失败: {e}", exc_info=True)
            self.error_occurred.emit(str(e))

    def on_mouse_scroll(self, x, y, dx, dy):
        """处理鼠标滚动事件"""
        if not self.sync_active:
            return
        try:
            for window in self.selected_windows:
                if window != self.main_window:
                    self.scroll_window(window, dx, dy)
        except Exception as e:
            self.logger.error(f"鼠标滚动同步失败: {e}", exc_info=True)
            self.error_occurred.emit(str(e))

    def on_key_press(self, key):
        """处理键盘按下事件"""
        if not self.sync_active:
            return
        try:
            for window in self.selected_windows:
                if window != self.main_window:
                    self.send_key_to_window(window, key, True)
        except Exception as e:
            self.logger.error(f"键盘按下同步失败: {e}", exc_info=True)
            self.error_occurred.emit(str(e))

    def on_key_release(self, key):
        """处理键盘释放事件"""
        if not self.sync_active:
            return
        try:
            for window in self.selected_windows:
                if window != self.main_window:
                    self.send_key_to_window(window, key, False)
        except Exception as e:
            self.logger.error(f"键盘释放同步失败: {e}", exc_info=True)
            self.error_occurred.emit(str(e))

    def move_mouse_to_window(self, window, rel_x, rel_y):
        """将鼠标移动到指定窗口的相对位置"""
        try:
            # 获取目标窗口的位置和大小
            cmd = f"""
            osascript -e '
            tell application "System Events"
                tell process "{window["name"]}"
                    get position and size of window 1
                end tell
            end tell'
            """
            result = subprocess.check_output(cmd, shell=True).decode('utf-8')
            win_pos = [int(x) for x in result.strip().split(', ')]
            
            # 计算实际坐标
            abs_x = win_pos[0] + (win_pos[2] * rel_x)
            abs_y = win_pos[1] + (win_pos[3] * rel_y)
            
            # 使用 AppleScript 移动鼠标
            move_cmd = f"""
            osascript -e '
            tell application "System Events"
                set mousePosition to {{{int(abs_x)}, {int(abs_y)}}}
                click at mousePosition
            end tell'
            """
            subprocess.run(move_cmd, shell=True)
            
        except Exception as e:
            self.logger.error(f"移动鼠标失败: {e}", exc_info=True)
            self.error_occurred.emit(str(e))

    def click_at_window(self, window, x, y, button, pressed):
        """在指定窗口的位置模拟鼠标点击"""
        try:
            # 获取目标窗口的位置和大小
            cmd = f"""
            osascript -e '
            tell application "System Events"
                tell process "{window["name"]}"
                    get position and size of window 1
                end tell
            end tell'
            """
            result = subprocess.check_output(cmd, shell=True).decode('utf-8')
            win_pos = [int(x) for x in result.strip().split(', ')]
            
            # 计算相对位置
            rel_x = (x - win_pos[0]) / win_pos[2]
            rel_y = (y - win_pos[1]) / win_pos[3]
            
            # 计算目标窗口中的实际坐标
            abs_x = win_pos[0] + (win_pos[2] * rel_x)
            abs_y = win_pos[1] + (win_pos[3] * rel_y)
            
            if pressed:  # 只在按下时点击
                # 使用 AppleScript 模拟点击
                click_cmd = f"""
                osascript -e '
                tell application "System Events"
                    tell process "{window["name"]}"
                        set frontmost to true
                        click at {{{int(abs_x)}, {int(abs_y)}}}
                    end tell
                end tell'
                """
                subprocess.run(click_cmd, shell=True)
            
        except Exception as e:
            self.logger.error(f"点击操作失败: {e}", exc_info=True)
            self.error_occurred.emit(str(e))

    def scroll_window(self, window, dx, dy):
        """在指定窗口模拟滚动"""
        try:
            # 使用 AppleScript 模拟滚动
            scroll_cmd = f"""
            osascript -e '
            tell application "System Events"
                tell process "{window["name"]}"
                    set frontmost to true
                    scroll direction {"down" if dy > 0 else "up"}
                end tell
            end tell'
            """
            subprocess.run(scroll_cmd, shell=True)
            
        except Exception as e:
            self.logger.error(f"滚动操作失败: {e}", exc_info=True)
            self.error_occurred.emit(str(e))

    def send_key_to_window(self, window, key, pressed):
        """向指定窗口发送键盘事件"""
        try:
            if pressed:
                # 将 pynput 键值转换为 AppleScript 键值
                key_str = str(key)
                if hasattr(key, 'char'):
                    key_str = key.char
                elif hasattr(key, 'name'):
                    key_str = key.name
                
                # 使用 AppleScript 模拟按键
                key_cmd = f"""
                osascript -e '
                tell application "System Events"
                    tell process "{window["name"]}"
                        set frontmost to true
                        keystroke "{key_str}"
                    end tell
                end tell'
                """
                subprocess.run(key_cmd, shell=True)
                
        except Exception as e:
            self.logger.error(f"键盘操作失败: {e}", exc_info=True)
            self.error_occurred.emit(str(e))

    def check_permissions(self):
        """这里实现具体的权限检查逻辑"""
        # 示例检查代码：
        try:
            # 检查系统权限的代码...
            if not has_permission():
                self.error_occurred.emit("缺少必要权限")
        except Exception as e:
            self.error_occurred.emit(str(e))

class SyncManagerDialog(QDialog):
    def __init__(self, running_windows, parent=None):
        super().__init__(parent)
        self.running_windows = running_windows
        self.sync_active = False
        self.listener_thread = None
        self.logger = logging.getLogger(__name__)
        self.initUI()

    def initUI(self):
        self.setWindowTitle("同步管理")
        self.setModal(True)
        layout = QVBoxLayout()
        
        # 创建窗口列表
        self.window_list = QTableWidget()
        self.window_list.setColumnCount(3)
        self.window_list.setHorizontalHeaderLabels(["选择", "窗口名称", "主控窗口"])
        self.window_list.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        
        # 添加窗口到列表
        self.window_list.setRowCount(len(self.running_windows))
        for row, window in enumerate(self.running_windows):
            # 选择框
            select_checkbox = QTableWidgetItem()
            select_checkbox.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
            select_checkbox.setCheckState(Qt.CheckState.Checked)
            self.window_list.setItem(row, 0, select_checkbox)
            
            # 窗口名称
            name_item = QTableWidgetItem(window['name'])
            self.window_list.setItem(row, 1, name_item)
            
            # 主控窗口单选框
            main_radio = QRadioButton()
            self.window_list.setCellWidget(row, 2, main_radio)
            if row == 0:  # 默认选择第一个窗口作为主控
                main_radio.setChecked(True)
        
        layout.addWidget(self.window_list)
        
        # 控制按钮
        button_layout = QHBoxLayout()
        
        self.select_all_btn = QPushButton("全选")
        self.select_all_btn.clicked.connect(self.toggle_select_all)
        
        self.start_sync_btn = QPushButton("开始同步")
        self.start_sync_btn.clicked.connect(self.toggle_sync)
        
        button_layout.addWidget(self.select_all_btn)
        button_layout.addWidget(self.start_sync_btn)
        
        layout.addLayout(button_layout)
        self.setLayout(layout)
        
    def toggle_select_all(self):
        state = Qt.CheckState.Checked if self.select_all_btn.text() == "全选" else Qt.CheckState.Unchecked
        for row in range(self.window_list.rowCount()):
            self.window_list.item(row, 0).setCheckState(state)
        self.select_all_btn.setText("取消全选" if state == Qt.CheckState.Checked else "全选")
    
    def toggle_sync(self):
        if not self.sync_active:
            # 获取选中的窗口和主控窗口
            selected_windows = []
            main_window = None
            
            for row in range(self.window_list.rowCount()):
                if self.window_list.item(row, 0).checkState() == Qt.CheckState.Checked:
                    window = self.running_windows[row]
                    selected_windows.append(window)
                    if self.window_list.cellWidget(row, 2).isChecked():
                        main_window = window
            
            if not main_window:
                QMessageBox.warning(self, "警告", "请选择一个主控窗口！")
                return
            
            if len(selected_windows) < 2:
                QMessageBox.warning(self, "警告", "请至少选择两个窗口进行同步！")
                return
            
            self.start_sync(main_window, selected_windows)
        else:
            self.stop_sync()

    def start_sync(self, main_window, selected_windows):
        """使用单线程事件循环方式启动"""
        try:
            # 创建监听管理器（在主线程）
            self.listener_manager = ListenerManager(self)
            self.listener_manager.error_occurred.connect(self.handle_error)
            self.listener_manager.start_listening()
            
            self.sync_active = True
            self.start_sync_btn.setText("停止同步")
            QMessageBox.information(self, "提示", "同步已开始！")
            
        except Exception as e:
            self.logger.error(f"启动失败: {e}")
            QMessageBox.critical(self, "错误", f"启动失败: {str(e)}")

    def handle_error(self, error_msg):
        """确保错误处理在主线程执行"""
        self.logger.error(f"处理错误: {error_msg}")
        QMessageBox.critical(self, "错误", error_msg)
        self.stop_sync()

    def stop_sync(self):
        """停止窗口同步"""
        try:
            self.sync_active = False
            self.start_sync_btn.setText("开始同步")
            self.logger.info("同步已完全停止")
            QMessageBox.information(self, "提示", "同步已停止！")
            
        except Exception as e:
            self.logger.error(f"停止同步失败: {e}")
            QMessageBox.critical(self, "错误", f"停止同步失败: {str(e)}")

    def closeEvent(self, event):
        """窗口关闭时安全停止监听"""
        if hasattr(self, 'sync_manager') and self.sync_manager.sync_active:
            self.sync_manager.stop_sync()
        super().closeEvent(event)

class ChromeManager(QWidget):
    def __init__(self):
        super().__init__()
        self.groups = {}
        self.icon_size = 1024  # ICNS 文件的标准尺寸
        self.font_size = 400   # 序号文字大小
        self.font_path = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
        self.initUI()
        self.load_groups()
        self.load_existing_copies()

    def initUI(self):
        self.setWindowTitle("Mac Chrome 多开管理")
        self.setGeometry(300, 300, 600, 500)

        layout = QVBoxLayout()

        # 选择Chrome主程序
        self.chrome_path_input = QLineEdit(DEFAULT_CHROME_PATH)
        self.select_chrome_btn = QPushButton("选择Chrome主程序")
        self.select_chrome_btn.clicked.connect(self.select_chrome)

        # 选择存储路径
        self.storage_path_input = QLineEdit(DEFAULT_STORAGE_PATH)
        self.select_storage_btn = QPushButton("选择存储路径")
        self.select_storage_btn.clicked.connect(self.select_storage)

        # 设置副本前缀和数量
        self.prefix_input = QLineEdit("chrome")
        self.copy_count_spin = QSpinBox()
        self.copy_count_spin.setRange(1, 9900)
        self.copy_count_spin.setValue(5)

        self.create_copies_btn = QPushButton("创建浏览器副本")
        self.create_copies_btn.clicked.connect(self.create_copies)

        # 浏览器副本列表
        self.browser_list = QListWidget()
        self.browser_list.setSelectionMode(QAbstractItemView.SelectionMode.MultiSelection)

        # 添加全选和加载按钮的水平布局
        button_layout = QHBoxLayout()
        self.select_all_btn = QPushButton("全选")
        self.select_all_btn.clicked.connect(self.toggle_select_all)
        self.load_copies_btn = QPushButton("加载浏览器副本")
        self.load_copies_btn.clicked.connect(self.load_existing_copies)
        
        button_layout.addWidget(self.select_all_btn)
        button_layout.addWidget(self.load_copies_btn)

        # 添加分组相关控件
        group_layout = QHBoxLayout()
        
        # 分组下拉框
        self.group_combo = QComboBox()
        self.group_combo.currentTextChanged.connect(self.on_group_selected)
        
        # 分组操作按钮
        self.add_to_group_btn = QPushButton("加入分组")
        self.add_to_group_btn.clicked.connect(self.add_to_group)
        
        self.remove_from_group_btn = QPushButton("移出分组")
        self.remove_from_group_btn.clicked.connect(self.remove_from_group)
        
        self.delete_group_btn = QPushButton("删除分组")
        self.delete_group_btn.clicked.connect(self.delete_group)

        group_layout.addWidget(QLabel("选择分组:"))
        group_layout.addWidget(self.group_combo)
        group_layout.addWidget(self.add_to_group_btn)
        group_layout.addWidget(self.remove_from_group_btn)
        group_layout.addWidget(self.delete_group_btn)

        # 将新的控件添加到主布局
        layout.addLayout(group_layout)

        # 加载浏览器副本按钮
        self.load_copies_btn = QPushButton("加载浏览器副本")
        self.load_copies_btn.clicked.connect(self.load_existing_copies)

        # 启动浏览器
        self.start_browser_btn = QPushButton("启动选中的浏览器")
        self.start_browser_btn.clicked.connect(self.start_selected)

        # 自动排列按钮
        self.arrange_btn = QPushButton("自动排列窗口")
        self.arrange_btn.clicked.connect(self.arrange_windows)

        # 代理配置按钮
        self.proxy_config_btn = QPushButton("代理配置")
        self.proxy_config_btn.clicked.connect(self.show_proxy_config)

        # 添加窗口同步按钮
        self.sync_windows_btn = QPushButton("窗口同步")
        self.sync_windows_btn.clicked.connect(self.show_sync_manager)

        layout.addWidget(QLabel("Chrome 主程序路径:"))
        layout.addWidget(self.chrome_path_input)
        layout.addWidget(self.select_chrome_btn)
        layout.addWidget(QLabel("存储路径:"))
        layout.addWidget(self.storage_path_input)
        layout.addWidget(self.select_storage_btn)
        layout.addWidget(QLabel("浏览器副本前缀:"))
        layout.addWidget(self.prefix_input)
        layout.addWidget(QLabel("创建数量:"))
        layout.addWidget(self.copy_count_spin)
        layout.addWidget(self.create_copies_btn)
        layout.addWidget(QLabel("浏览器副本:"))
        layout.addLayout(button_layout)
        layout.addWidget(self.browser_list)
        layout.addWidget(self.start_browser_btn)
        layout.addWidget(self.arrange_btn)
        layout.addWidget(self.proxy_config_btn)
        layout.addWidget(self.sync_windows_btn)

        self.setLayout(layout)

        # 添加定时器保证列表持续排序
        self.sort_timer = QTimer()
        self.sort_timer.timeout.connect(lambda: self.browser_list.sortItems(Qt.SortOrder.AscendingOrder))
        self.sort_timer.start(500)  # 每500毫秒检查一次排序

    def select_chrome(self):
        path, _ = QFileDialog.getOpenFileName(self, "选择 Chrome 主程序", "", "App Files (*.app)")
        if path:
            self.chrome_path_input.setText(path)

    def select_storage(self):
        path = QFileDialog.getExistingDirectory(self, "选择存储路径")
        if path:
            self.storage_path_input.setText(path)

    def create_modified_icon(self, number, output_path):
        """创建带序号的图标"""
        try:
            # 创建一个新的图像，使用浅蓝色背景
            background_color = (135, 206, 250)  # 浅蓝色 RGB 值
            image = Image.new('RGBA', (self.icon_size, self.icon_size), background_color)
            
            # 创建绘图对象
            draw = ImageDraw.Draw(image)
            
            # 加载字体
            font = ImageFont.truetype(self.font_path, self.font_size)
            
            # 计算文本大小
            text = str(number)
            text_bbox = draw.textbbox((0, 0), text, font=font)
            text_width = text_bbox[2] - text_bbox[0]
            text_height = text_bbox[3] - text_bbox[1]
            
            # 计算文本位置（居中）
            x = (self.icon_size - text_width) // 2
            y = (self.icon_size - text_height) // 2
            
            # 绘制文本阴影
            shadow_offset = 3
            shadow_color = (70, 130, 180, 150)  # 深蓝色半透明阴影
            draw.text((x + shadow_offset, y + shadow_offset), text, 
                     font=font, fill=shadow_color)
            
            # 绘制主文本
            text_color = (25, 25, 112)  # 深蓝色文本
            draw.text((x, y), text, font=font, fill=text_color)
            
            # 保存为ICNS格式
            image.save(output_path, format='ICNS')
            return True
            
        except Exception as e:
            print(f"创建图标时出错: {e}")
            return False

    def extract_number(self, app_path):
        """从应用程序路径中提取序号"""
        match = re.search(r'(\d{4})\.app$', app_path)
        if match:
            return match.group(1)
        return None

    def create_copies(self):
        """修改创建副本的方法，使用4位数字命名"""
        count = self.copy_count_spin.value()
        storage_path = self.storage_path_input.text()
        chrome_path = self.chrome_path_input.text()

        if not os.path.exists(chrome_path):
            QMessageBox.warning(self, "错误", "Chrome 主程序路径无效！")
            return

        if not os.path.exists(storage_path):
            QMessageBox.warning(self, "错误", "存储路径无效！")
            return

        # 获取当前目录下最大的浏览器序号
        max_number = 0
        for item in os.listdir(storage_path):
            if item.endswith('.app') and item[:4].isdigit():
                try:
                    number = int(item[:4])
                    max_number = max(max_number, number)
                except ValueError:
                    continue
        
        print(f"当前最大序号: {max_number}")
        start_number = max_number + 1
        
        # 获取主Chrome的配置目录
        main_chrome_path = os.path.expanduser("~/Library/Application Support/Google/Chrome/Default")
        print(f"主Chrome配置目录: {main_chrome_path}")

        # 需要复制的插件相关目录
        extension_items = [
            "Extensions",
            "Local Extension Settings",
            "Extension State",
            "Extension Scripts",
            "Extension Rules"
        ]

        for i in range(count):
            current_number = start_number + i
            clone_name = f"{current_number:04d}.app"
            clone_path = os.path.join(storage_path, clone_name)
            
            print(f"\n开始创建浏览器副本: {clone_name}")
            
            if os.path.exists(clone_path):
                print(f"跳过已存在的副本: {clone_name}")
                continue

            # 复制Chrome应用
            shutil.copytree(chrome_path, clone_path)
            print(f"复制Chrome应用完成: {clone_path}")
            
            # 修改图标
            icon_path = os.path.join(clone_path, "Contents", "Resources", "app.icns")
            if self.create_modified_icon(current_number, icon_path):
                print(f"修改图标成功: {clone_name}")
            else:
                print(f"修改图标失败: {clone_name}")
            
            # 创建配置目录
            config_path = os.path.join(clone_path, "config")
            default_path = os.path.join(config_path, "Default")
            os.makedirs(default_path, exist_ok=True)
            print(f"创建配置目录: {default_path}")

            # 复制插件相关文件
            print("开始复制插件相关文件...")
            for item in extension_items:
                src_path = os.path.join(main_chrome_path, item)
                dst_path = os.path.join(default_path, item)
                
                if os.path.exists(src_path):
                    try:
                        if os.path.isdir(src_path):
                            print(f"复制目录: {item}")
                            shutil.copytree(src_path, dst_path)
                        else:
                            print(f"复制文件: {item}")
                            shutil.copy2(src_path, dst_path)
                        print(f"成功复制: {item}")
                    except Exception as e:
                        print(f"复制 {item} 失败: {e}")
                else:
                    print(f"源路径不存在，跳过: {item}")

            # 设置权限
            try:
                chrome_binary = os.path.join(clone_path, "Contents", "MacOS", "Google Chrome")
                os.chmod(clone_path, 0o755)
                os.chmod(chrome_binary, 0o755)
                print("设置权限成功")
            except Exception as e:
                print(f"设置权限失败: {e}")

            # 添加到列表
            list_item = QListWidgetItem(clone_path)
            list_item.setFlags(list_item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            list_item.setCheckState(Qt.CheckState.Unchecked)
            self.browser_list.addItem(list_item)
            print(f"创建浏览器副本完成: {clone_name}\n")

        print("所有浏览器副本创建完成")

    def load_groups(self):
        """加载保存的分组信息"""
        try:
            groups_file = os.path.join(os.path.dirname(__file__), "groups.json")
            if os.path.exists(groups_file):
                with open(groups_file, 'r') as f:
                    self.groups = json.load(f)
                    self.update_group_combo()
        except Exception as e:
            print(f"加载分组信息失败: {e}")

    def save_groups(self):
        """保存分组信息"""
        try:
            groups_file = os.path.join(os.path.dirname(__file__), "groups.json")
            with open(groups_file, 'w') as f:
                json.dump(self.groups, f, indent=4)
        except Exception as e:
            QMessageBox.warning(self, "错误", f"保存分组信息失败: {e}")

    def update_group_combo(self):
        """更新分组下拉框"""
        current_text = self.group_combo.currentText()
        self.group_combo.clear()
        self.group_combo.addItem("全部")
        self.group_combo.addItems(sorted(self.groups.keys()))
        if current_text and current_text in self.groups:
            self.group_combo.setCurrentText(current_text)

    def add_to_group(self):
        """将选中的浏览器添加到分组"""
        selected_items = [self.browser_list.item(i) for i in range(self.browser_list.count())
                         if self.browser_list.item(i).checkState() == Qt.CheckState.Checked]
        
        if not selected_items:
            QMessageBox.warning(self, "警告", "请先选择要加入分组的浏览器！")
            return

        # 创建分组选择对话框
        dialog = QDialog(self)
        dialog.setWindowTitle("选择或创建分组")
        layout = QVBoxLayout()

        # 分组选择
        group_combo = QComboBox()
        group_combo.addItems(sorted(self.groups.keys()))
        group_combo.setEditable(True)
        
        buttons = QHBoxLayout()
        ok_button = QPushButton("确定")
        cancel_button = QPushButton("取消")
        
        buttons.addWidget(ok_button)
        buttons.addWidget(cancel_button)
        
        layout.addWidget(QLabel("选择已有分组或输入新分组名称:"))
        layout.addWidget(group_combo)
        layout.addLayout(buttons)
        
        dialog.setLayout(layout)
        
        ok_button.clicked.connect(dialog.accept)
        cancel_button.clicked.connect(dialog.reject)
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            group_name = group_combo.currentText().strip()
            if not group_name:
                QMessageBox.warning(self, "错误", "分组名称不能为空！")
                return
                
            # 创建或更新分组
            if group_name not in self.groups:
                self.groups[group_name] = []
            
            # 添加选中的浏览器到分组
            for item in selected_items:
                browser_path = item.text()
                if browser_path not in self.groups[group_name]:
                    self.groups[group_name].append(browser_path)
            
            self.save_groups()
            self.update_group_combo()
            self.on_group_selected(self.group_combo.currentText())

    def remove_from_group(self):
        """从当前分组中移除选中的浏览器"""
        current_group = self.group_combo.currentText()
        if current_group == "全部" or current_group not in self.groups:
            return

        selected_items = [self.browser_list.item(i) for i in range(self.browser_list.count())
                         if self.browser_list.item(i).checkState() == Qt.CheckState.Checked]
        
        if not selected_items:
            QMessageBox.warning(self, "警告", "请先选择要移除的浏览器！")
            return

        for item in selected_items:
            browser_path = item.text()
            if browser_path in self.groups[current_group]:
                self.groups[current_group].remove(browser_path)

        self.save_groups()
        self.on_group_selected(current_group)

    def delete_group(self):
        """删除当前选中的分组"""
        current_group = self.group_combo.currentText()
        if current_group == "全部" or current_group not in self.groups:
            return

        if self.groups[current_group]:
            reply = QMessageBox.question(self, "确认删除",
                                       f"分组 '{current_group}' 中包含 {len(self.groups[current_group])} 个浏览器，确定要删除吗？",
                                       QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.No:
                return

        del self.groups[current_group]
        self.save_groups()
        self.update_group_combo()
        self.on_group_selected("全部")

    def on_group_selected(self, group_name):
        """当选择分组时更新浏览器列表"""
        self.browser_list.clear()
        
        if group_name == "全部":
            # 显示所有浏览器
            storage_path = self.storage_path_input.text()
            if os.path.exists(storage_path):
                for item in os.listdir(storage_path):
                    if item.endswith(".app"):
                        list_item = QListWidgetItem(os.path.join(storage_path, item))
                        list_item.setFlags(list_item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                        list_item.setCheckState(Qt.CheckState.Unchecked)
                        self.browser_list.addItem(list_item)
        elif group_name in self.groups:
            # 显示分组内的浏览器
            for browser_path in self.groups[group_name]:
                if os.path.exists(browser_path):
                    list_item = QListWidgetItem(browser_path)
                    list_item.setFlags(list_item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                    list_item.setCheckState(Qt.CheckState.Unchecked)
                    self.browser_list.addItem(list_item)

    def load_existing_copies(self):
        """加载现有的浏览器副本"""
        storage_path = self.storage_path_input.text()
        if not os.path.exists(storage_path):
            return

        self.browser_list.clear()
        for item in os.listdir(storage_path):
            if item.endswith(".app"):
                clone_path = os.path.join(storage_path, item)
                list_item = QListWidgetItem(clone_path)
                list_item.setFlags(list_item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                list_item.setCheckState(Qt.CheckState.Unchecked)
                self.browser_list.addItem(list_item)

    def start_selected(self):
        """启动选中的Chrome副本"""
        print("开始启动浏览器...")
        
        selected_items = [self.browser_list.item(i) for i in range(self.browser_list.count())
                         if self.browser_list.item(i).checkState() == Qt.CheckState.Checked]
        
        if not selected_items:
            QMessageBox.warning(self, "警告", "请先选择要启动的浏览器！")
            return

        # 加载代理配置
        try:
            config_path = os.path.join(os.path.dirname(__file__), "proxy_config.json")
            with open(config_path, 'r') as f:
                proxy_config = json.load(f)
                print("成功加载代理配置文件")
        except Exception as e:
            print(f"无法加载代理配置: {e}")
            proxy_config = {}

        for item in selected_items:
            clone_path = item.text()
            app_name = os.path.basename(clone_path)
            print(f"\n准备启动浏览器: {clone_path}")
            
            # 检查路径是否存在
            if not os.path.exists(clone_path):
                print(f"错误: 找不到浏览器路径 {clone_path}")
                QMessageBox.warning(self, "错误", f"找不到浏览器: {clone_path}")
                continue
            
            # 检查执行文件是否存在
            chrome_binary = os.path.join(clone_path, "Contents", "MacOS", "Google Chrome")
            if not os.path.exists(chrome_binary):
                print(f"错误: 找不到浏览器执行文件 {chrome_binary}")
                QMessageBox.warning(self, "错误", f"找不到浏览器执行文件: {chrome_binary}")
                continue

            try:
                # 基本启动命令
                cmd = [chrome_binary]
                
                # 添加配置目录
                config_dir = os.path.join(clone_path, "config")
                cmd.append(f"--user-data-dir={config_dir}")
                
                # 如果有代理配置，直接添加代理参数
                if app_name in proxy_config:
                    proxy_str = proxy_config[app_name]
                    parts = proxy_str.split(':')
                    if len(parts) == 4:
                        ip, port, username, password = parts  # 直接使用配置的顺序
                        cmd.extend([
                            f"--proxy-server=http://{ip}:{port}",  # 只使用IP和端口
                            "--proxy-bypass-list=<-loopback>",  # 允许访问本地地址
                        ])
                        print(f"使用代理: http://{ip}:{port}")
                
                # 添加其他必要参数
                cmd.extend([
                    "--no-first-run",
                    "--no-default-browser-check",
                    "--disable-gpu-shader-disk-cache",
                    "--disable-restore-session-state"
                ])
                
                # 启动浏览器
                print(f"执行命令: {' '.join(cmd)}")
                process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    start_new_session=True
                )
                
                # 检查进程是否成功启动
                time.sleep(1)
                if process.poll() is not None:
                    stdout, stderr = process.communicate()
                    print(f"进程输出: {stdout.decode()}")
                    print(f"错误输出: {stderr.decode()}")
                    raise Exception(f"浏览器启动失败: {stderr.decode()}")
                else:
                    print(f"浏览器启动成功: {app_name}")
                    
            except Exception as e:
                error_msg = str(e)
                print(f"启动失败: {error_msg}")
                QMessageBox.warning(self, "错误", f"启动浏览器失败: {error_msg}")
                continue

    def show_proxy_config(self):
        """显示代理配置界面"""
        # 获取选中的浏览器副本
        selected_items = [self.browser_list.item(i) for i in range(self.browser_list.count())
                         if self.browser_list.item(i).checkState() == Qt.CheckState.Checked]
        
        # 获取选中浏览器的名称列表
        selected_browsers = [os.path.basename(item.text()) for item in selected_items]
        
        if not selected_browsers:
            QMessageBox.warning(self, "警告", "请先选择要配置的浏览器！")
            return
        
        try:
            # 加载现有配置
            config_path = os.path.join(os.path.dirname(__file__), "proxy_config.json")
            if os.path.exists(config_path):
                with open(config_path, 'r') as f:
                    proxy_config = json.load(f)
            else:
                proxy_config = {}
            
            # 创建代理配置对话框
            dialog = ProxyConfigDialog(self)
            
            # 设置表格的行数为选中的浏览器数量
            dialog.proxy_table.setRowCount(len(selected_browsers))
            
            # 填充表格数据
            for row, browser_name in enumerate(selected_browsers):
                # 设置浏览器名称
                name_item = QTableWidgetItem(browser_name)
                dialog.proxy_table.setItem(row, 0, name_item)
                
                # 如果有现有配置，填充代理信息
                if browser_name in proxy_config:
                    proxy_str = proxy_config[browser_name]
                    dialog.proxy_table.setItem(row, 1, QTableWidgetItem(proxy_str))
            
            # 显示对话框
            if dialog.exec() == QDialog.DialogCode.Accepted:
                # 获取新的配置
                new_config = dialog.get_proxy_config()
                
                # 保存配置
                with open(config_path, 'w') as f:
                    json.dump(new_config, f, indent=4)
                
                QMessageBox.information(self, "成功", "代理配置已保存")
                
        except Exception as e:
            QMessageBox.critical(self, "错误", f"加载代理配置失败: {str(e)}")

    def arrange_windows(self):
        # 实现自动排列窗口的逻辑
        selected_items = []
        for i in range(self.browser_list.count()):
            item = self.browser_list.item(i)
            if item.checkState() == Qt.CheckState.Checked:
                selected_items.append(item)

        if not selected_items:
            QMessageBox.warning(self, "错误", "请先选择要排列的浏览器副本！")
            return

        # 获取当前显示器分辨率（物理像素）
        screen_width = int(subprocess.check_output(
            "system_profiler SPDisplaysDataType | awk -F': ' '/Resolution/{print $2}' | head -n 1 | cut -d' ' -f1",
            shell=True).decode().strip())
        screen_height = int(subprocess.check_output(
            "system_profiler SPDisplaysDataType | awk -F': ' '/Resolution/{print $2}' | head -n 1 | cut -d' ' -f3",
            shell=True).decode().strip())

        # 转换为逻辑像素
        logical_width = screen_width // 2
        logical_height = screen_height // 2

        selected_paths = [item.text() for item in selected_items]
        num_windows = len(selected_paths)
        
        # 自动计算最佳行列数
        def calculate_grid(n):
            if n <= 4:  # 4个或更少窗口使用单行
                return 1, n
            elif n <= 6:  # 5-6个窗口使用2行
                return 2, (n + 1) // 2
            elif n <= 9:  # 7-9个窗口使用3行
                return 3, (n + 2) // 3
            else:  # 10个或更多窗口使用4行
                return 4, (n + 3) // 4

        rows, cols = calculate_grid(num_windows)
        
        # 计算窗口尺寸和位置
        margin_x = 10  # 水平边距
        margin_y = 25  # 垂直边距（顶部留更多空间）
        spacing_x = 5  # 水平间距
        spacing_y = 5  # 垂直间距
        
        # 计算单个窗口的尺寸
        usable_width = logical_width - (2 * margin_x)
        usable_height = logical_height - (2 * margin_y)
        window_width = (usable_width - (spacing_x * (cols - 1))) // cols
        window_height = (usable_height - (spacing_y * (rows - 1))) // rows

        print(f"Physical Screen: {screen_width}x{screen_height}")
        print(f"Logical Screen: {logical_width}x{logical_height}")
        print(f"Grid: {rows}x{cols}")
        print(f"Window size: {window_width}x{window_height}")

        # 为每个窗口创建单独的AppleScript
        for index, clone_path in enumerate(selected_paths):
            # 计算行列位置
            row = index // cols
            col = index % cols
            
            # 计算窗口位置
            x_pos = margin_x + col * (window_width + spacing_x)
            y_pos = margin_y + row * (window_height + spacing_y)
            
            app_name = os.path.basename(clone_path).replace(".app", "")
            
            window_script = f'''
            tell application "{app_name}"
                activate
                delay 0.5
                set bounds of window 1 to {{{x_pos}, {y_pos}, {x_pos + window_width}, {y_pos + window_height}}}
            end tell
            '''
            
            print(f"Arranging {app_name} at position ({row},{col}): x={x_pos}, y={y_pos}")
            
            try:
                subprocess.run(["osascript", "-e", window_script], check=True)
                print(f"Successfully arranged {app_name}")
                
            except subprocess.CalledProcessError as e:
                print(f"Error arranging {app_name}: {e}")
                print("AppleScript content:")
                print(window_script)
                continue

        print("Window arrangement completed")

    def show_sync_manager(self):
        # 确保窗口创建在主线程
        if QThread.currentThread() != self.thread():
            QMetaObject.invokeMethod(self, "show_sync_manager", Qt.ConnectionType.QueuedConnection)
            return
        
        # 主线程执行实际窗口创建
        running_windows = self.get_running_chrome_windows()
        if not running_windows:
            QMessageBox.warning(self, "警告", "没有检测到正在运行的Chrome窗口！")
            return
        
        self.sync_manager = SyncManagerDialog(running_windows, self)
        self.sync_manager.show()

    def get_running_chrome_windows(self):
        """获取所有正在运行的Chrome窗口"""
        running_windows = []
        seen_apps = set()  # 用于跟踪已经添加的应用
        
        try:
            print("开始获取Chrome窗口信息...")
            
            # 使用 ps 命令获取进程信息
            ps_cmd = "ps aux | grep 'Google Chrome' | grep -v grep"
            ps_result = subprocess.check_output(ps_cmd, shell=True).decode('utf-8')
            print(f"PS 命令结果: {ps_result}")
            
            # 从 ps 结果中提取 Chrome 实例信息
            for line in ps_result.split('\n'):
                if '/Contents/MacOS/Google Chrome' in line:
                    for i in range(self.browser_list.count()):
                        item = self.browser_list.item(i)
                        if item and os.path.exists(item.text()):
                            app_name = os.path.basename(item.text())
                            # 检查是否已经添加过这个应用
                            if app_name not in seen_apps and app_name in line:
                                window_info = {
                                    'path': item.text(),
                                    'name': app_name,
                                    'process_info': line.strip()
                                }
                                running_windows.append(window_info)
                                seen_apps.add(app_name)  # 标记这个应用已经被添加
                                print(f"找到运行中的Chrome窗口: {app_name}")
            
            if not running_windows:
                print("未检测到运行中的Chrome窗口")
            else:
                print(f"共检测到 {len(running_windows)} 个运行中的Chrome窗口")
                
        except Exception as e:
            print(f"获取运行中的Chrome窗口失败: {e}")
            print("错误详情:")
            import traceback
            traceback.print_exc()
        
        return running_windows

    def toggle_select_all(self):
        """切换全选状态（仅影响当前显示的列表）"""
        current_text = self.select_all_btn.text()
        new_state = Qt.CheckState.Checked if current_text == "全选" else Qt.CheckState.Unchecked
        new_text = "取消全选" if current_text == "全选" else "全选"
        
        for i in range(self.browser_list.count()):
            item = self.browser_list.item(i)
            item.setCheckState(new_state)
        
        self.select_all_btn.setText(new_text)

def excepthook(exc_type, exc_value, exc_tb):
    tb = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
    print(f"Uncaught exception:\n{tb}")
    QApplication.quit()

sys.excepthook = excepthook

if __name__ == "__main__":
    try:
        logger = setup_logger()
        logger.info("程序启动")
        
        # 设置更详细的全局异常处理
        def handle_exception(exc_type, exc_value, exc_traceback):
            if issubclass(exc_type, KeyboardInterrupt):
                sys.__excepthook__(exc_type, exc_value, exc_traceback)
                return
                
            # 记录详细的错误信息
            import traceback
            error_msg = ''.join(traceback.format_exception(exc_type, exc_value, exc_traceback))
            logger.critical("未捕获的异常:\n%s", error_msg)
            
            # 如果是在 Qt 线程中发生的异常，确保显示错误对话框
            from PyQt6.QtCore import QThread
            if isinstance(exc_value, Exception) and QThread.currentThread().objectName() != 'main':
                logger.error("线程中发生异常")
                # 在主线程中显示错误对话框
                from PyQt6.QtWidgets import QMessageBox
                from PyQt6.QtCore import QTimer
                QTimer.singleShot(0, lambda: QMessageBox.critical(None, 
                    "错误", 
                    f"程序发生错误:\n{str(exc_value)}\n\n详细信息已记录到日志文件"))
        
        # 设置线程异常处理
        import threading
        threading.excepthook = lambda args: handle_exception(
            args.exc_type, args.exc_value, args.exc_traceback)
        
        # 设置全局异常处理
        sys.excepthook = handle_exception
        
        # 启用 Qt 的异常捕获
        from PyQt6.QtCore import qInstallMessageHandler
        def qt_message_handler(mode, context, message):
            logger.debug(f"Qt消息 ({mode}): {message}")
        qInstallMessageHandler(qt_message_handler)
        
        logger.info("异常处理器设置完成")
        
        app = QApplication(sys.argv)
        window = ChromeManager()
        window.show()
        
        # 设置应用程序异常处理
        app.setQuitOnLastWindowClosed(True)
        
        exit_code = app.exec()
        logger.info(f"程序退出，退出码: {exit_code}")
        sys.exit(exit_code)
        
    except Exception as e:
        print(f"程序发生严重错误: {e}")
        logger.critical(f"程序发生严重错误: {e}", exc_info=True)
        
        # 尝试显示错误对话框
        try:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.critical(None, "严重错误", f"程序发生严重错误:\n{str(e)}")
        except:
            pass
            
        sys.exit(1)