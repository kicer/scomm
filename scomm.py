#! /usr/bin/env python3

import os,sys,json
import serial
import serial.tools.list_ports
import tkgen.gengui
import tkinter
import threading

import time, datetime
def tsnow():
    return int(time.time()*1000)
def strnow():
    return datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
def tohex(b):
    return ' '.join(['%02X'%x for x in b])

class UIproc():
    def __init__(self, app):
        self.root = app
        self.combobox_port = self.root.get('cbbox-com')
        self.entry_baud = self.root.get('entry-baud')
        self.entry_split = self.root.get('entry-split')
        self.entry_cycle = self.root.get('entry-cycle')
        self.entry_encoding = self.root.get('entry-encoding')
        self.entry_sendText = self.root.get('entry-sendText')
        self.btn_onoff = self.root.get('btn-onoff')
        self.canvas_led = self.root.get('canvas-led')
        self.label_status = self.root.get('label-status')
        self.ckbtn_shex = self.root.get('ckbtn-shex')
        self.ckbtn_rhex = self.root.get('ckbtn-rhex')
        self.ckbtn_sendshow = self.root.get('ckbtn-sendshow')
        self.ckbtn_time = self.root.get('ckbtn-time')
        self.text_recv = self.root.get('text-recv')
        self.entry_split = self.root.get('entry-split')
        self.lastRecvTicks = 0
        self.event_init()
    def getSendData(self):
        data = self.entry_sendText.var.get()
        encoding = self.entry_encoding.var.get()
        return self.ckbtn_shex.var.get() and bytes.fromhex(data) or data.encode(encoding, 'ignore')
    def dmesg(self, cate, data):
        text =  self.ckbtn_time.var.get() and '[%s]'%strnow() or ''
        encoding = self.entry_encoding.var.get()
        splitms = int(self.entry_split.var.get().replace('ms',''))
        if cate == 'send' and self.ckbtn_sendshow.var.get():
            text += '> '
            text += self.ckbtn_shex.var.get() and tohex(data) or data.decode(encoding, 'ignore')
            self.text_recv.insert('end', '\n'+text)
            self.lastRecvTicks = 0
        elif cate == 'recv':
            ts = tsnow()
            if(ts-self.lastRecvTicks>splitms):
                text += '< '
                text += self.ckbtn_rhex.var.get() and tohex(data) or data.decode(encoding, 'ignore')
                self.text_recv.insert('end', '\n'+text)
            else:
                text = self.ckbtn_rhex.var.get() and (' '+tohex(data)) or data.decode(encoding, 'ignore')
                self.text_recv.insert('end', text)
            self.lastRecvTicks = ts
    def serial_open(self):
        self.entry_baud.configure(state='disabled')
        self.combobox_port.configure(state='disabled')
        self.btn_onoff.configure(text='关闭串口')
        self.canvas_led.create_oval(4,4,19,19,fill='green')
    def serial_close(self):
        self.entry_baud.configure(state='normal')
        self.combobox_port.configure(state='normal')
        self.btn_onoff.configure(text='打开串口')
        self.canvas_led.create_oval(4,4,19,19,fill='red')
    def read_serial_port(self):
        return self.combobox_port.get()
    def read_serial_baud(self):
        return self.entry_baud.var.get()
    def set_serial_port_list(self, portList):
        currText = self.combobox_port.get()
        _ports = []
        for i in portList:
            _ports.append(str(i[0]))
        self.combobox_port['values'] = _ports
        if currText in _ports:
            self.combobox_port.set(currText)
        else:
            self.combobox_port.set(_ports[-1])
    def clear_recvtext(self):
        self.text_recv.delete('1.0','end')
    def log(self, s):
        print('[sys.log]: %s'%s)
        self.label_status.var.set(str(s))
    def event_init(self):
        self.combobox_port.bind("<<ComboboxSelected>>", lambda x:self.log(self.combobox_port.get()))


class SerComm():
    #root = None

    def __init__(self, app):
        self.ui = UIproc(app)
        self.com = serial.Serial()
        self.thread = None
        self.alive = threading.Event()
        self.setting = None
        self.isDetectSerialPort = False
        self.receiveProgressStop = True
        self.sendCount = 0
        self.recvCount = 0

    def detectSerialPort(self):
        if not self.isDetectSerialPort:
            self.isDetectSerialPort = True
            t = threading.Thread(target=self.detectSerialPortProcess)
            t.setDaemon(True)
            t.start()

    def openCloseSerial(self):
        self.ui.log('Serial Port waitting...')
        t = threading.Thread(target=self.openCloseSerialProcess)
        t.setDaemon(True)
        t.start()

    def receiveData(self):
        while not self.receiveProgressStop:
            #try:
            if True:
                data = self.com.read(self.com.in_waiting)
                if data:
                    self.ui.log('recv1: %s' % strnow()) 
                    self.ui.dmesg('recv', data)
                    self.ui.log('%s: receive: %s' % (self.com.port,str(data)))
                time.sleep(0.050)
            #except Exception as e:
            else:
                self.ui.log('%s: receive trace: %s' % (self.com.port,str(e)))

    def sendData(self):
        #try:
        if True:
            if not self.com.is_open:
                self.ui.log('Serial Port not open')
            else:
                data = self.ui.getSendData()
                if data and len(data) > 0:
                    self.com.write(data)
                    self.sendCount += len(data)
                    self.ui.dmesg('send', data)
                    self.ui.log('%s: send %s bytes: %s...' % (self.com.port,len(data),str(data)[:16]))
                    # scheduled send
                    #if self.sendSettingsScheduledCheckBox.isChecked():
                    #    if not self.isScheduledSending:
                    #        t = threading.Thread(target=self.scheduledSend)
                    #        t.setDaemon(True)
                    #        t.start()
        #except Exception as e:
        #    self.ui.log('%s: send trace: %s' % (self.com.port,str(e)))

    def openCloseSerialProcess(self):
        try:
            if self.com.is_open:
                self.receiveProgressStop = True
                self.com.close()
                self.ui.serial_close()
                self.ui.log('%s: closed' % self.com.port)
            else:
                try:
                    self.com.baudrate = int(self.ui.read_serial_baud())
                    self.com.port = self.ui.read_serial_port()
                    self.com.bytesize = 8
                    self.com.parity = 'N'
                    self.com.stopbits = 1
                    self.com.timeout = 0
                    self.com.write_timeout = 0
                    self.com.inter_byte_timeout = 0
                    self.com.open()
                    self.ui.serial_open()
                    self.ui.log('%s: open success' % self.com.port)
                    self.receiveProgressStop = False
                    self.receiveProcess = threading.Thread(target=self.receiveData)
                    self.receiveProcess.setDaemon(True)
                    self.receiveProcess.start()
                except Exception as e:
                    self.com.close()
                    self.ui.serial_close()
                    self.receiveProgressStop = True
                    self.ui.log('%s: open failed: %s' % (self.com.port,str(e)))
        except Exception as e:
            self.ui.log('%s: openClose trace: %s' % (self.com.port,str(e)))

    def clearWin(self):
        self.ui.clear_recvtext()

    def sendFile(self):
        pass

    def findSerialPort(self):
        self.port_list = list(serial.tools.list_ports.comports())
        return self.port_list

    def detectSerialPortProcess(self):
        while(1):
            portList = self.findSerialPort()
            if len(portList)>0:
                self.ui.log('detectSerialPort = %s' % len(portList))
                self.ui.set_serial_port_list(portList)
                break
            time.sleep(1)
        self.isDetectSerialPort = False

    def safe_exit(self):
        self.com.close()
        sys.exit(0)


class TopWin():
    def __init__(self, root):
        self.root = root
    def set_send_data(self, btn):
        _cfg = self.root.usercfg.get(btn, {})
        if _cfg:
            val = _cfg.get('value')
            self.root.get('entry-sendText').var.set(val)
            self.root.get('ckbtn-shex').var.set(_cfg.get('hex') and 1 or 0)
            self.root.get('btn-send').invoke()
    def win_data(self, event):
        def _save_dfile():
            pass
        self.root.toplevel('data.json', title='预置数据').configure(bg='#e8e8e8')
        btn = event.widget._name
        _cfg = self.root.usercfg.get(btn, {})
        self.root.entry('entry-dfile').set(_cfg.get('title', btn))
        self.root.get('text-dsetting').insert('end', _cfg.get('value',''))
        self.root.checkbox('ckbtn-dhex').set(_cfg.get('hex') and 1 or 0)
        self.root.button('btn-dsave', cmd=_save_dfile, focus=True)
        self.root.button('btn-dsend', cmd=lambda x=btn:self.set_send_data(x))
    def win_pack(self, btn):
        pass
        #root.toplevel('pack.json', title='组帧脚本').configure(bg='#e8e8e8')
    def win_unpack(self, btn):
        pass
        #root.toplevel('unpack.json', title='解析脚本').configure(bg='#e8e8e8')


if __name__ == '__main__':
    root = tkgen.gengui.TkJson('scomm.json', title='scomm串口调试助手')
    comm = SerComm(root)
    wm = TopWin(root)
    # 读取用户数据文件
    cfg_file = 'app.json'
    root.usercfg = json.load(open(cfg_file)) if os.path.isfile(cfg_file) else {}
    # 预置数据回调函数
    for i in range(10):
        name = 'btn-data%02d'%(i+1)
        try:
            btn = root.get(name)
            root.button(name, lambda x=name: wm.set_send_data(x))
            btn.bind('<Button-2>', wm.win_data)
            btn.bind('<Button-3>', wm.win_data)
            _cfg = root.usercfg.get(name)
            if _cfg and btn:
                btn.config(text=_cfg.get('title',name))
        except:
            pass
    # 组帧脚本回调函数
    for i in range(10):
        name = 'btn-pack%02d'%(i+1)
        try:
            btn = root.get(name)
            root.button(name, lambda x=name: wm.win_pack(root,x))
            _cfg = root.usercfg.get(name)
            if _cfg and btn:
                btn.config(text=_cfg.get('title',name))
        except:
            pass
    # 解析脚本回调函数
    for i in range(10):
        name = 'btn-unpack%02d'%(i+1)
        try:
            btn = root.get(name)
            root.button(name, lambda x=name: wm.win_unpack(root,x))
            _cfg = root.usercfg.get(name)
            if _cfg and btn:
                btn.config(text=_cfg.get('title',name))
        except:
            pass
    # UI相关设置
    root.get('canvas-led').create_oval(4,4,19,19,fill='gray')
    root.checkbox('ckbtn-rhex').set(0)
    root.checkbox('ckbtn-shex').set(0)
    root.checkbox('ckbtn-0d').set(0)
    root.checkbox('ckbtn-0a').set(0)
    root.checkbox('ckbtn-split').set(1)
    root.checkbox('ckbtn-cycle').set(0)
    root.checkbox('ckbtn-time').set(1)
    root.checkbox('ckbtn-sendshow').set(1)
    root.entry('entry-split').set('50ms')
    root.entry('entry-cycle').set('1000ms')
    root.entry('entry-baud').set('9600')
    root.entry('entry-encoding').set('gbk')
    root.entry('entry-sendText', key='<Return>', cmd=lambda x:comm.sendData()).set('')
    root.button('btn-scan', cmd=lambda:comm.detectSerialPort())
    root.button('btn-onoff', cmd=lambda:comm.openCloseSerial())
    root.button('btn-send', cmd=lambda:comm.sendData())
    root.button('btn-clear', cmd=lambda:comm.clearWin())
    root.button('btn-sendfile', cmd=lambda:comm.sendFile())
    _stvar = tkinter.StringVar()
    root.label('label-status').textvariable=_stvar
    root.label('label-status').var =_stvar
    # 其他设置
    root.configure(bg='#e8e8e8')
    root.lift() # 把主窗口置于最前面
    #root.wm_state('zoomed') # 最大化窗口
    root.protocol("WM_DELETE_WINDOW", lambda:comm.safe_exit())
    # 启动任务
    comm.detectSerialPort()
    root.mainloop()
