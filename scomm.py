#!/usr/bin/env python3

import os
import sys
import json
import string
import serial
import serial.tools.list_ports
import tkinter
import tkinter.scrolledtext
import tkinter.filedialog
import tkgen.gengui
import threading
import time
import datetime
import queue
import logging
from typing import Optional, Dict, Any, List, Union

# 设置中文环境
import _locale
_locale._getdefaultlocale = (lambda *args: ['zh_CN', 'utf8'])

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 工具函数
def tsnow() -> int:
    """获取当前时间戳（毫秒）"""
    return int(time.time() * 1000)

def strnow() -> str:
    """获取当前时间字符串"""
    return datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]

def tohex(data: bytes) -> str:
    """将字节数据转换为十六进制字符串"""
    return ' '.join(f'{x:02X}' for x in data)

def human_string(data: bytes, is_hex: bool = False, encoding: str = 'utf-8') -> str:
    """将字节数据转换为可读字符串"""
    return tohex(data) if is_hex else data.decode(encoding, 'ignore')

def uint16(b: bytes) -> int:
    """从字节读取无符号16位整数"""
    return b[0] * 256 + b[1]

def int16(b: bytes) -> int:
    """从字节读取有符号16位整数"""
    d = b[0] * 256 + b[1]
    return d - 0x10000 if d >= 0x8000 else d


class ThreadSafeTextHandler:
    """线程安全的文本处理器"""
    
    def __init__(self, text_widget):
        self.text_widget = text_widget
        self.message_queue = queue.Queue()
        self.update_interval = 100  # 毫秒
        self.max_lines = 10000  # 最大行数限制
        self._start_updater()
    
    def _start_updater(self):
        """启动UI更新器"""
        self._update_text()
    
    def _update_text(self):
        """从队列中获取消息并更新UI"""
        try:
            while True:
                try:
                    message = self.message_queue.get_nowait()
                    self._safe_insert(message)
                except queue.Empty:
                    break
        except Exception as e:
            logger.error(f"更新文本时出错: {e}")
        
        # 继续定时更新
        self.text_widget.after(self.update_interval, self._update_text)
    
    def _safe_insert(self, message: str):
        """安全插入文本"""
        try:
            # 检查并限制文本长度
            lines = int(self.text_widget.index('end-1c').split('.')[0])
            if lines > self.max_lines:
                self.text_widget.delete('1.0', f'{lines - self.max_lines // 2}.0')
            
            self.text_widget.insert('end', message)
            self.text_widget.see('end')
        except Exception as e:
            logger.error(f"插入文本时出错: {e}")
    
    def put_message(self, message: str):
        """向队列中添加消息"""
        try:
            self.message_queue.put(message)
        except Exception as e:
            logger.error(f"添加消息到队列时出错: {e}")


class UIProcessor:
    """UI处理器"""
    
    def __init__(self, app):
        self.root = app
        self._setup_widgets()
        self._setup_variables()
        self._bind_events()
        
        # 初始化文本处理器
        self.text_handler = ThreadSafeTextHandler(self.text_recv)
        
        logger.info("UI处理器初始化完成")
    
    def _setup_widgets(self):
        """设置UI组件"""
        # 串口相关
        self.combobox_port = self.root.get('cbbox-com')
        self.entry_baud = self.root.get('entry-baud')
        self.btn_onoff = self.root.get('btn-onoff')
        self.canvas_led = self.root.get('canvas-led')
        
        # 数据显示相关
        self.text_recv = self.root.get('text-recv')
        self.label_status = self.root.get('label-status')
        
        # 复选框
        self.ckbtn_shex = self.root.get('ckbtn-shex')
        self.ckbtn_rhex = self.root.get('ckbtn-rhex')
        self.ckbtn_sendshow = self.root.get('ckbtn-sendshow')
        self.ckbtn_time = self.root.get('ckbtn-time')
        self.ckbtn_split = self.root.get('ckbtn-split')
        self.ckbtn_0d = self.root.get('ckbtn-0d')
        self.ckbtn_0a = self.root.get('ckbtn-0a')
        self.ckbtn_cycle = self.root.get('ckbtn-cycle')
        
        # 输入框
        self.entry_split = self.root.get('entry-split')
        self.entry_cycle = self.root.get('entry-cycle')
        self.entry_encoding = self.root.get('entry-encoding')
        self.entry_sendText = self.root.get('entry-sendText')
    
    def _setup_variables(self):
        """设置变量"""
        self.last_recv_ticks = 0
        self.last_recv_data = b''
        self.wait_send_data = {'text': b'', 'rts': None, 'dtr': None}
        
        # 状态标签变量
        self.status_var = tkinter.StringVar()
        self.label_status.config(textvariable=self.status_var)
    
    def _bind_events(self):
        """绑定事件"""
        self.combobox_port.bind("<<ComboboxSelected>>", 
                               lambda e: self.log(f"选择端口: {self.combobox_port.get()}"))
    
    def set_send_data(self, text: Optional[str] = None, encoding: Optional[str] = None, 
                     hex_flag: Optional[bool] = None, rts: Optional[bool] = None, 
                     dtr: Optional[bool] = None):
        """设置发送数据"""
        if text is not None:
            self.entry_sendText.var.set(text)
        if encoding is not None:
            self.entry_encoding.var.set(encoding)
        if hex_flag is not None:
            self.ckbtn_shex.var.set(1 if hex_flag else 0)
        
        self.wait_send_data.update({
            'rts': rts if rts is not None else self.wait_send_data['rts'],
            'dtr': dtr if dtr is not None else self.wait_send_data['dtr']
        })
    
    def get_send_data(self, cache: bool = True) -> Dict[str, Any]:
        """获取发送数据"""
        if not cache and self.root.pack:
            logger.info(f"发送数据包: {self.root.pack}")
            self.set_send_data(**self.root.pack)
            self.root.pack = None
        
        try:
            data = self.entry_sendText.var.get()
            encoding = self.entry_encoding.var.get()
            
            # 处理十六进制数据
            if self.ckbtn_shex.var.get():
                dat = bytes.fromhex(data) if data.strip() else b''
            else:
                dat = data.encode(encoding, 'ignore')
            
            # 添加行结束符
            if self.ckbtn_0d.var.get():
                dat += b'\r'
            if self.ckbtn_0a.var.get():
                dat += b'\n'
            
            self.wait_send_data['text'] = dat
        except Exception as e:
            logger.error(f"处理发送数据时出错: {e}")
            self.wait_send_data['text'] = b''
        
        return self.wait_send_data
    
    def dmesg(self, category: str, data: bytes):
        """显示消息（线程安全）"""
        try:
            if category == 'send' and not self.ckbtn_sendshow.var.get():
                return
            
            timestamp = f"[{strnow()}] " if self.ckbtn_time.var.get() else ""
            encoding = self.entry_encoding.var.get()
            
            if category == 'send':
                prefix = "> " if self.ckbtn_time.var.get() else ""
                content = human_string(data, self.ckbtn_shex.var.get(), encoding)
            else:  # recv
                prefix = "< " if self.ckbtn_time.var.get() else ""
                content = human_string(data, self.ckbtn_rhex.var.get(), encoding)
            
            message = f"\n{timestamp}{prefix}{content}"
            self.text_handler.put_message(message)
            
        except Exception as e:
            logger.error(f"显示消息时出错: {e}")
    
    def serial_open(self):
        """串口打开时的UI更新"""
        self.entry_baud.configure(state='disabled')
        self.combobox_port.configure(state='disabled')
        self.btn_onoff.configure(text='关闭串口')
        self.canvas_led.create_oval(4, 4, 19, 19, fill='lightgreen')
    
    def serial_close(self):
        """串口关闭时的UI更新"""
        self.entry_baud.configure(state='normal')
        self.combobox_port.configure(state='normal')
        self.btn_onoff.configure(text='打开串口')
        self.canvas_led.create_oval(4, 4, 19, 19, fill='red')
    
    def read_serial_port(self) -> str:
        """读取选择的串口"""
        return self.combobox_port.get()
    
    def read_serial_baud(self) -> int:
        """读取波特率"""
        try:
            return int(self.entry_baud.var.get())
        except ValueError:
            return 9600
    
    def set_serial_port_list(self, port_list: List[Any]):
        """设置串口列表"""
        current_text = self.combobox_port.get()
        ports = [str(port[0]) for port in port_list]
        
        self.combobox_port['values'] = ports
        
        if current_text in ports:
            self.combobox_port.set(current_text)
        elif ports:
            self.combobox_port.set(ports[-1])
    
    def clear_recv_text(self):
        """清空接收文本"""
        self.text_recv.delete('1.0', 'end')
    
    def save_recv_text(self):
        """保存接收文本"""
        try:
            filename = filedialog.asksaveasfilename(
                defaultextension='.txt',
                initialfile=f'scommlog-{tsnow()}'
            )
            if filename:
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(self.text_recv.get('1.0', 'end'))
                self.log(f"文件已保存: {filename}")
        except Exception as e:
            logger.error(f"保存文件时出错: {e}")
            self.log(f"保存失败: {e}")
    
    def should_send_cycle(self) -> bool:
        """检查是否应该循环发送"""
        return self.ckbtn_cycle.var.get()
    
    def get_cycle_interval(self) -> float:
        """获取循环发送间隔（秒）"""
        try:
            cycle_text = self.entry_cycle.var.get().replace('ms', '')
            return max(0.01, float(cycle_text) / 1000.0)  # 最小间隔10ms
        except ValueError:
            return 1.0
    
    def log(self, message: str):
        """记录状态消息"""
        logger.info(message)
        display_msg = message if len(message) <= 64 else message[:64] + ' ...'
        self.status_var.set(display_msg)
    
    def save_config(self, key: str, value: Any = None):
        """保存配置"""
        try:
            if value is None:
                # 从控件获取值
                value = self.root.get(key).var.get()
                config_key = key.split('-')[-1]
            else:
                config_key, value = key, value
            
            if self.root.usercfg.get(config_key) == value:
                return
            
            self.root.usercfg[config_key] = value
            
            with open('usercfg.json', 'w', encoding='utf-8') as f:
                json.dump(self.root.usercfg, f, indent=4, ensure_ascii=False)
                
        except Exception as e:
            logger.error(f"保存配置时出错: {e}")


class SerialCommunicator:
    """串口通信器"""
    
    def __init__(self, app):
        self.ui = UIProcessor(app)
        self.com = serial.Serial()
        self.threads = []
        self.running = threading.Event()
        self.shutdown_event = threading.Event()
        
        # 统计信息
        self.send_count = 0
        self.recv_count = 0
        
        logger.info("串口通信器初始化完成")
    
    def detect_serial_ports(self):
        """检测串口"""
        if not hasattr(self, '_detecting') or not self._detecting:
            self._detecting = True
            thread = threading.Thread(target=self._detect_ports_process, daemon=True)
            thread.start()
            self.threads.append(thread)
    
    def _detect_ports_process(self):
        """检测串口进程"""
        try:
            port_list = list(serial.tools.list_ports.comports())
            if port_list:
                self.ui.log(f'发现 {len(port_list)} 个串口')
                self.ui.set_serial_port_list(port_list)
        except Exception as e:
            logger.error(f"检测串口时出错: {e}")
        finally:
            self._detecting = False
    
    def open_close_serial(self):
        """打开/关闭串口"""
        self.ui.log('串口操作中...')
        thread = threading.Thread(target=self._open_close_process, daemon=True)
        thread.start()
        self.threads.append(thread)
    
    def _open_close_process(self):
        """打开/关闭串口进程"""
        try:
            if self.com.is_open:
                # 关闭串口
                self._stop_communication()
                self.com.close()
                self.ui.serial_close()
                self.ui.log(f'{self.com.port}: 已关闭')
            else:
                # 打开串口
                if self._open_serial():
                    self._start_communication()
                    self._save_current_config()
        except Exception as e:
            logger.error(f"串口操作出错: {e}")
            self.ui.log(f'串口操作失败: {e}')
    
    def _open_serial(self) -> bool:
        """打开串口"""
        try:
            self.com.port = self.ui.read_serial_port()
            self.com.baudrate = self.ui.read_serial_baud()
            self.com.bytesize = 8
            self.com.parity = 'N'
            self.com.stopbits = 1
            self.com.timeout = 0.1  # 设置超时避免阻塞
            self.com.write_timeout = 1
            
            self.com.open()
            self.ui.serial_open()
            self.ui.log(f'{self.com.port}: 打开成功')
            return True
            
        except Exception as e:
            logger.error(f"打开串口失败: {e}")
            self.com.close()
            self.ui.serial_close()
            self.ui.log(f'{self.com.port}: 打开失败 - {e}')
            return False
    
    def _start_communication(self):
        """启动通信线程"""
        self.running.set()
        self.shutdown_event.clear()
        
        # 启动接收线程
        recv_thread = threading.Thread(target=self._receive_loop, daemon=True)
        recv_thread.start()
        self.threads.append(recv_thread)
        
        # 启动发送线程（如果需要循环发送）
        send_thread = threading.Thread(target=self._send_loop, daemon=True)
        send_thread.start()
        self.threads.append(send_thread)
    
    def _stop_communication(self):
        """停止通信线程"""
        self.running.clear()
        self.shutdown_event.set()
        
        # 等待线程结束
        for thread in self.threads[:]:
            if thread.is_alive():
                thread.join(timeout=1.0)
        
        self.threads.clear()
    
    def _receive_loop(self):
        """接收数据循环"""
        buffer = b''
        while self.running.is_set():
            try:
                if self.com.is_open:
                    data = self.com.read(self.com.in_waiting or 1)
                    if data:
                        buffer += data
                        self.recv_count += len(data)
                        
                        # 处理完整的数据包
                        if buffer:
                            self.ui.dmesg('recv', buffer)
                            self.ui.log(f'{self.com.port}: 接收 {len(buffer)} 字节')
                            buffer = b''
                
                time.sleep(0.01)  # 减少CPU占用
                
            except Exception as e:
                logger.error(f"接收数据错误: {e}")
                time.sleep(0.1)
    
    def _send_loop(self):
        """发送数据循环"""
        while self.running.is_set():
            try:
                if self.com.is_open and self.ui.should_send_cycle():
                    time.sleep(self.ui.get_cycle_interval())
                    self._send_data()
                else:
                    time.sleep(0.1)
                    
            except Exception as e:
                logger.error(f"发送循环错误: {e}")
                time.sleep(0.1)
    
    def send_data(self):
        """发送数据"""
        if not self.com.is_open:
            self.ui.log('串口未打开')
            return
        
        thread = threading.Thread(target=self._send_data, daemon=True)
        thread.start()
        self.threads.append(thread)
    
    def _send_data(self):
        """实际发送数据"""
        try:
            data_info = self.ui.get_send_data(cache=False)
            
            # 设置RTS/DTR
            if data_info['rts'] is not None:
                self.com.rts = data_info['rts']
                self.ui.log(f'{self.com.port}: RTS = {data_info["rts"]}')
            
            if data_info['dtr'] is not None:
                self.com.dtr = data_info['dtr']
                self.ui.log(f'{self.com.port}: DTR = {data_info["dtr"]}')
            
            # 发送数据
            data = data_info['text']
            if data:
                self.com.write(data)
                self.send_count += len(data)
                self.ui.log(f'{self.com.port}: 发送 {len(data)} 字节')
                self.ui.dmesg('send', data)
                
        except Exception as e:
            logger.error(f"发送数据错误: {e}")
            self.ui.log(f'发送失败: {e}')
    
    def clear_window(self):
        """清空窗口"""
        self.ui.clear_recv_text()
    
    def save_file(self):
        """保存文件"""
        self.ui.save_recv_text()
    
    def safe_exit(self):
        """安全退出"""
        logger.info("正在退出应用程序...")
        
        # 停止所有线程
        self.running.clear()
        self.shutdown_event.set()
        
        # 关闭串口
        if self.com.is_open:
            try:
                self.com.close()
                logger.info("串口已关闭")
            except Exception as e:
                logger.error(f"关闭串口时出错: {e}")
        
        # 等待一段时间让线程结束
        time.sleep(0.5)
        
        # 强制退出
        sys.exit(0)


class TopWindow:
    """顶层窗口管理器"""
    
    def __init__(self, root):
        self.root = root
        self.root.unpack = {}
        self.root.pack = None
        
        self.win_data = None
        self.win_unpack = None
        
        logger.info("顶层窗口管理器初始化完成")
    
    def set_send_data(self, btn_name: str):
        """设置发送数据"""
        config = self.root.usercfg.get(btn_name, {})
        if not config:
            return
        
        try:
            value = config.get('value', '')
            
            # 尝试评估表达式
            try:
                user_vars = self.root.get('entry-uservar').var.get().split(',')
                value = eval(value, {"data": user_vars})
            except:
                pass
            
            # 准备发送数据包
            if isinstance(value, dict):
                self.root.pack = {
                    'text': value.get('text', ''),
                    'encoding': value.get('encoding'),
                    'hex_flag': value.get('hex'),
                    'rts': value.get('rts'),
                    'dtr': value.get('dtr')
                }
            else:
                self.root.pack = {
                    'text': str(value),
                    'hex_flag': config.get('hex')
                }
            
            # 触发发送
            self.root.get('btn-send').invoke()
            
        except Exception as e:
            logger.error(f"设置发送数据时出错: {e}")
    
    def set_unpack(self, btn_name: str):
        """设置解析脚本"""
        self.root.unpack[btn_name] = (
            self.root.get(btn_name).var.get() 
            and self.root.usercfg.get(btn_name) 
            or None
        )
    
    def save_config(self, btn_name: str, data: Dict[str, Any]):
        """保存配置"""
        self.root.save_cfg((btn_name, data))
        self.root.get(btn_name).configure(text=data.get('title', btn_name))
    
    def show_data_window(self, event):
        """显示数据配置窗口"""
        if self.win_data:
            self.win_data.destroy()
        
        self.win_data = self.root.toplevel('data.ui', title='预置数据')
        self.win_data.configure(bg='#e8e8e8')
        
        btn_name = event.widget._name
        config = self.root.usercfg.get(btn_name, {})
        
        # 设置控件值
        self.root.entry('entry-dfile').set(config.get('title', btn_name))
        self.root.get('text-dsetting').delete('1.0', 'end')
        self.root.get('text-dsetting').insert('end', config.get('value', ''))
        self.root.checkbox('ckbtn-dhex').set(config.get('hex', 0))
        
        # 绑定保存按钮
        self.root.button('btn-dsave', 
                        cmd=lambda: self._save_data_config(btn_name), 
                        focus=True)
    
    def _save_data_config(self, btn_name: str):
        """保存数据配置"""
        try:
            data = {
                'title': self.root.get('entry-dfile').var.get(),
                'value': self.root.get('text-dsetting').get('1.0', 'end-1c'),
                'hex': self.root.get('ckbtn-dhex').var.get()
            }
            self.save_config(btn_name, data)
            
            if self.win_data:
                self.win_data.destroy()
                self.win_data = None
                
        except Exception as e:
            logger.error(f"保存数据配置时出错: {e}")
    
    def show_unpack_window(self, event):
        """显示解析脚本窗口"""
        if self.win_unpack:
            self.win_unpack.destroy()
        
        self.win_unpack = self.root.toplevel('unpack.ui', title='解析脚本')
        self.win_unpack.configure(bg='#e8e8e8')
        
        btn_name = event.widget._name
        config = self.root.usercfg.get(btn_name, {})
        
        # 设置控件值
        self.root.entry('entry-ufile').set(config.get('title', btn_name))
        self.root.get('text-usetting').delete('1.0', 'end')
        self.root.get('text-usetting').insert('end', config.get('value', ''))
        
        # 绑定保存按钮
        self.root.button('btn-usave', 
                        cmd=lambda: self._save_unpack_config(btn_name), 
                        focus=True)
    
    def _save_unpack_config(self, btn_name: str):
        """保存解析脚本配置"""
        try:
            data = {
                'title': self.root.get('entry-ufile').var.get(),
                'value': self.root.get('text-usetting').get('1.0', 'end-1c')
            }
            self.save_config(btn_name, data)
            self.set_unpack(btn_name)
            
            if self.win_unpack:
                self.win_unpack.destroy()
                self.win_unpack = None
                
        except Exception as e:
            logger.error(f"保存解析脚本配置时出错: {e}")


def main():
    """主函数"""
    #try:
    if True:
        # 导入UI生成库
        
        # 创建主窗口
        tkinter.ScrolledText = tkinter.scrolledtext.ScrolledText
        root = tkgen.gengui.TkJson('app.ui', title='scomm串口调试助手')
        
        # 初始化通信器
        comm = SerialCommunicator(root)
        window_manager = TopWindow(root)
        
        # 加载用户配置
        if os.path.isfile('usercfg.json'):
            with open('usercfg.json', 'r', encoding='utf-8') as f:
                root.usercfg = json.load(f)
        else:
            root.usercfg = {}
        
        root.save_cfg = comm.ui.save_config
        
        # 设置预置数据按钮
        _setup_data_buttons(root, window_manager)
        
        # 设置解析脚本按钮
        _setup_unpack_buttons(root, window_manager)
        
        # 设置UI控件
        _setup_ui_controls(root, comm)
        
        # 设置窗口属性
        root.configure(bg='#e8e8e8')
        root.lift()  # 置顶窗口
        
        # 设置关闭协议
        root.protocol("WM_DELETE_WINDOW", lambda: comm.safe_exit())
        
        # 启动串口检测
        comm.detect_serial_ports()
        
        # 启动主循环
        logger.info("应用程序启动完成")
        root.mainloop()
        
    #except Exception as e:
    else:
        logger.error(f"应用程序启动失败: {e}")
        sys.exit(1)


def _setup_data_buttons(root, window_manager):
    """设置预置数据按钮"""
    for i in range(20):
        btn_name = f'btn-data{i+1:02d}'
        try:
            btn = root.get(btn_name)
            if btn:
                root.button(btn_name, cmd=lambda x=btn_name: window_manager.set_send_data(x))
                btn.bind('<Button-2>', window_manager.show_data_window)
                btn.bind('<Button-3>', window_manager.show_data_window)
                
                # 设置按钮文本
                config = root.usercfg.get(btn_name)
                if config:
                    btn.configure(text=config.get('title', btn_name))
                    
        except Exception as e:
            logger.debug(f"设置按钮 {btn_name} 时出错: {e}")


def _setup_unpack_buttons(root, window_manager):
    """设置解析脚本按钮"""
    var = tkinter.IntVar()
    for i in range(20):
        btn_name = f'btn-unpack{i+1:02d}'
        try:
            btn = root.get(btn_name)
            if btn:
                btn.var = var
                root.button(btn_name, cmd=lambda x=btn_name: window_manager.set_unpack(x))
                btn.bind('<Button-2>', window_manager.show_unpack_window)
                btn.bind('<Button-3>', window_manager.show_unpack_window)
                
                # 设置按钮文本
                config = root.usercfg.get(btn_name)
                if config:
                    btn.configure(text=config.get('title', btn_name))
                
                root.checkbox(btn_name).set(0)
                
        except Exception as e:
            logger.debug(f"设置解析按钮 {btn_name} 时出错: {e}")


def _setup_ui_controls(root, comm):
    """设置UI控件"""
    # 初始化LED
    root.get('canvas-led').create_oval(4, 4, 19, 19, fill='gray')
    
    # 设置复选框默认值
    checkboxes = {
        'ckbtn-rhex': 0, 'ckbtn-shex': 0, 'ckbtn-0d': 0, 'ckbtn-0a': 0,
        'ckbtn-split': 1, 'ckbtn-cycle': 0, 'ckbtn-time': 1, 'ckbtn-sendshow': 1
    }
    
    for name, value in checkboxes.items():
        root.checkbox(name).set(value)
    
    # 设置输入框默认值
    entries = {
        'entry-split': '99ms',
        'entry-cycle': '1024ms', 
        'entry-baud': '9600',
        'entry-encoding': 'utf8',
        'entry-uservar': ''
    }
    
    for name, default in entries.items():
        root.entry(name).set(root.usercfg.get(name.split('-')[-1], default))
    
    # 绑定按钮事件
    root.button('btn-scan', cmd=lambda: comm.detect_serial_ports())
    root.button('btn-onoff', cmd=lambda: comm.open_close_serial())
    root.button('btn-send', cmd=lambda: comm.send_data())
    root.button('btn-clear', cmd=lambda: comm.clear_window())
    root.button('btn-savefile', cmd=lambda: comm.save_file())
    
    # 绑定发送文本框回车事件
    root.entry('entry-sendText', key='<Return>', cmd=lambda e: comm.send_data()).set('')


if __name__ == '__main__':
    main()
