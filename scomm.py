#! /usr/bin/env python3

import os,sys,json
import serial
import serial.tools.list_ports
import tkinter
import threading
import tkgen.gengui
import tkinter.scrolledtext
import tkinter.filedialog

import _locale
_locale._getdefaultlocale = (lambda *args: ['zh_CN', 'utf8'])

import time, datetime
def tsnow():
    return int(time.time()*1000)
def strnow():
    return datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
def tohex(b):
    return ' '.join(['%02X'%x for x in b])

def uint16(b):
    return b[0]*256+b[1]
def int16(b):
    d = (b[0]*256+b[1])
    return d>=0x80 and (d-0x10000) or d

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
        self.ckbtn_split = self.root.get('ckbtn-split')
        self.ckbtn_0d = self.root.get('ckbtn-0d')
        self.ckbtn_0a = self.root.get('ckbtn-0a')
        self.ckbtn_cycle = self.root.get('ckbtn-cycle')
        self.lastRecvTicks = 0
        self.lastCursor = "end"
        self.lastRecvData = b''
        self.wait_sendData = {'text':b'', 'rts':None, 'dtr':None}
        self._lock_dmesg = False
        self.event_init()
        self.dmesg_buff = []
    def setSendData(self, text=None, encoding=None, HEX=None, RTS=None, DTR=None):
        if type(text) == type(''):
            self.entry_sendText.var.set(text)
        if type(encoding) == type(''):
            self.entry_encoding.var.set(encoding)
        if type(HEX) == type(1):
            self.ckbtn_shex.var.set(HEX and 1 or 0)
        self.wait_sendData['rts'] = RTS
        self.wait_sendData['dtr'] = DTR
    def getSendData(self, cache=True):
        if not cache:
            if self.root.pack:
                self.log('send.data.pack:%s'%self.root.pack)
                self.setSendData(**self.root.pack)
                self.root.pack = None
            data = self.entry_sendText.var.get()
            encoding = self.entry_encoding.var.get()
            dat = self.ckbtn_shex.var.get() and bytes.fromhex(data) or data.encode(encoding, 'ignore')
            dat += self.ckbtn_0d.var.get() and b'\r' or b''
            dat += self.ckbtn_0a.var.get() and b'\n' or b''
            self.wait_sendData['text'] = dat
        return self.wait_sendData
    def getSendDataLoop(self):
        while True:
            self.getSendData(cache=False)
            time.sleep(1)
    def dmesg(self, cate, data):
        _err = 0
        while self._dmesg(cate, data):
            time.sleep(0.1)
            _err += 1
            if _err > 10:
                self.log('dmesg hang:[%s] %s'%(cate, str(data)))
                break
    def _dmesg(self, cate, data):
        if self._lock_dmesg: return True
        self._lock_dmesg = True
        MARK = lambda x:self.ckbtn_time.var.get() and x or ''
        text = MARK('[%s]'%strnow())
        encoding = self.entry_encoding.var.get()
        splitms = self.ckbtn_split.var.get() and int(self.entry_split.var.get().replace('ms','')) or 0
        ts = tsnow()
        _i0,fg='end','black'
        if cate == 'send' and self.ckbtn_sendshow.var.get():
            text += MARK('> ')
            text += self.ckbtn_rhex.var.get() and tohex(data) or data.decode(encoding, 'ignore')
            _i0 = self.text_recv.index('end')
            self.text_recv.insert('end', '\n%s'%text.translate({0:'<00>'}))
            self.lastRecvTicks = 0
            self.lastCursor = 'end'
            self.lastRecvData = b''
        elif cate == 'recv':
            if(ts-self.lastRecvTicks>splitms):
                self.lastCursor = self.text_recv.index('end')
                self.lastRecvData = data
                text += MARK('< ')
                text += self.ckbtn_rhex.var.get() and tohex(data) or data.decode(encoding, 'ignore')
                #self.text_recv.insert('end', '\n'+text)
            else:
                data = self.lastRecvData + data
                self.lastRecvData = data
                text += MARK('< ')
                text += self.ckbtn_rhex.var.get() and tohex(data) or data.decode(encoding, 'ignore')
                _i0 = self.lastCursor
                #self.text_recv.insert(_i0, '\n'+text)
            for cb in self.root.unpack.values():
                try:
                    if cb: text += eval(cb['value'],{'data':data, 'uint16':uint16,'int16':int16}) or ''
                except: pass
            self.text_recv.delete(_i0,'end')
            _i0 = self.text_recv.index('end')
            self.text_recv.insert(_i0, '\n%s'%text.translate({0:'<00>'}))
            self.lastRecvTicks = ts
            fg='blue'
        _i1 = self.text_recv.index('end')
        self.text_recv.tag_add('%s'%ts, _i0, _i1)
        self.text_recv.tag_config('%s'%ts,foreground=fg)
        self.text_recv.yview('end')
        self._lock_dmesg = False
        return False
    def serial_open(self):
        self.entry_baud.configure(state='disabled')
        self.combobox_port.configure(state='disabled')
        self.btn_onoff.configure(text='关闭串口')
        self.canvas_led.create_oval(4,4,19,19,fill='lightgreen')
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
    def save_recvtext(self):
        f = tkinter.filedialog.asksaveasfile(mode='w', defaultextension='.txt', initialfile='scommlog-%s'%tsnow())
        if f:
            f.write(self.text_recv.get('1.0','end'))
            f.close()
    def send_waitting(self):
        if self.ckbtn_cycle.var.get():
            ts = int(self.entry_cycle.var.get().replace('ms',''))/1000.0
            time.sleep(ts)
            return True
        return False
    def log(self, s):
        print('[sys.log]: %s'%s)
        self.label_status.var.set(len(str(s))>64 and (str(s)[:64]+' ...') or str(s))
    def save_cfg(self, dt):
        if type(dt) == type(''):
            dt = (dt.split('-')[-1], self.root.get(dt).var.get())
            if self.root.usercfg.get(dt[0]) == dt[1]: return
        with open('usercfg.json', 'wb+') as f:
            self.root.usercfg[dt[0]] = dt[1]
            encoding = self.root.get('entry-encoding').var.get()
            f.write(json.dumps(self.root.usercfg,indent=4,sort_keys=True).encode(encoding,'ignore'))
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
        self.comProgressStop = True
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

    def receiveDataLoop(self):
        self.com.flush()
        while not self.comProgressStop:
            try:
                if self.com.is_open:
                    data = self.com.read(self.com.in_waiting)
                    if data:
                        self.ui.log('%s: recv %s bytes: %s' % (self.com.port,len(data),str(data)))
                        self.ui.dmesg('recv', data)
                    time.sleep(0.05)
                else:
                    time.sleep(1)
            except Exception as e:
                self.ui.log('%s: receive trace: %s' % (self.com.port,str(e)))

    def sendDataLoop(self):
        while not self.comProgressStop:
            try:
                if self.com.is_open and self.ui.send_waitting():
                    _data = self.ui.getSendData(cache=True)
                    data = _data.get('text')
                    if data and len(data) > 0:
                        self.com.write(data)
                        self.sendCount += len(data)
                        self.ui.log('%s: send %s bytes: %s' % (self.com.port,len(data),str(data)))
                        self.ui.dmesg('send', data)
                else:
                    time.sleep(1)
            except Exception as e:
                self.ui.log('%s: send trace: %s' % (self.com.port,str(e)))

    def sendData(self):
        if not self.com.is_open:
            self.ui.log('Serial Port not open')
        else:
            _data = self.ui.getSendData(cache=False)
            rts = _data.get('rts')
            dtr = _data.get('dtr')
            data = _data.get('text')
            if type(rts) == type(True):
                self.com.rts = rts
                self.ui.log('%s: set rts=%s' % (self.com.port,rts))
                self.ui.setSendData(RTS=None)
            if type(dtr) == type(True):
                self.com.dtr = dtr
                self.ui.log('%s: set dtr=%s' % (self.com.port,dtr))
                self.ui.setSendData(DTR=None)
            if data and len(data) > 0:
                self.com.write(data)
                self.sendCount += len(data)
                self.ui.log('%s: send %s bytes: %s' % (self.com.port,len(data),str(data)))
                self.ui.dmesg('send', data)

    def openCloseSerialProcess(self):
        try:
            if self.com.is_open:
                self.comProgressStop = True
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
                    self.comProgressStop = False
                    self.receiveProcess = threading.Thread(target=self.receiveDataLoop)
                    self.receiveProcess.setDaemon(True)
                    self.receiveProcess.start()
                    self.sendProcess = threading.Thread(target=self.sendDataLoop)
                    self.sendProcess.setDaemon(True)
                    self.sendProcess.start()
                    self.sendProcess = threading.Thread(target=self.ui.getSendDataLoop)
                    self.sendProcess.setDaemon(True)
                    self.sendProcess.start()
                    # save usercfg
                    self.ui.save_cfg('entry-split')
                    self.ui.save_cfg('entry-cycle')
                    self.ui.save_cfg('entry-baud')
                    self.ui.save_cfg('entry-encoding')
                    self.ui.save_cfg('entry-uservar')
                except Exception as e:
                    self.com.close()
                    self.ui.serial_close()
                    self.comProgressStop = True
                    self.ui.log('%s: open failed' % (self.com.port))
        except Exception as e:
            self.ui.log('%s: openClose trace' % (self.com.port))

    def clearWin(self):
        self.ui.clear_recvtext()

    def saveFile(self):
        self.ui.save_recvtext()

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
        self.comProgressStop = True
        time.sleep(0.1)
        self.com.close()
        sys.exit(0)


class TopWin():
    def __init__(self, root):
        self.root = root
        self.root.unpack = {}
        self.root.pack = None
        self.WinData = None
        self.WinPack = None
        self.WinUnpack = None
    def set_send_data(self, btn):
        _cfg = self.root.usercfg.get(btn, {})
        if _cfg:
            val = _cfg.get('value')
            try:
                val = eval(val, {"data":self.root.get('entry-uservar').var.get().split(',')})
            except: pass
            if type(val) == type({}):
                self.root.pack = {
                        'text':val.get('text'),
                        'encoding':val.get('encoding'),
                        'HEX':val.get('hex')
                }
                if 'rts' in val:
                    self.root.pack['RTS'] = bool(val.get('rts'))
                if 'dtr' in val:
                    self.root.pack['DTR'] = bool(val.get('dtr'))
            else:
                self.root.pack = {'text':val,'HEX':_cfg.get('hex')}
            self.root.get('btn-send').invoke()
    def set_unpack(self, btn):
        self.root.unpack[btn] = self.root.get(btn).var.get() and self.root.usercfg.get(btn) or None
    def save_cfg(self, btn, dat):
        self.root.save_cfg((btn,dat))
        self.root.get(btn).configure(text=dat.get('title'))
    def win_data(self, event):
        def _save(w):
            dat = {'title':self.root.get('entry-dfile').var.get()}
            dat['value'] = self.root.get('text-dsetting').get('1.0','end -1 chars')
            dat['hex'] = self.root.get('ckbtn-dhex').var.get() and 1 or 0
            self.save_cfg(w,dat)
            self.WinData.destroy()
        if self.WinData: self.WinData.destroy()
        self.WinData = self.root.toplevel('data.ui', title='预置数据')
        self.WinData.configure(bg='#e8e8e8')
        btn = event.widget._name
        _cfg = self.root.usercfg.get(btn, {})
        self.root.entry('entry-dfile').set(_cfg.get('title', btn))
        self.root.get('text-dsetting').insert('end', _cfg.get('value',''))
        self.root.checkbox('ckbtn-dhex').set(_cfg.get('hex') and 1 or 0)
        self.root.button('btn-dsave', cmd=lambda x=btn:_save(x), focus=True)
    def win_unpack(self, event):
        def _save(w):
            dat = {'title':self.root.get('entry-ufile').var.get()}
            dat['value'] = self.root.get('text-usetting').get('1.0','end -1 chars')
            self.save_cfg(w,dat)
            self.set_unpack(w)
            self.WinUnpack.destroy()
        if self.WinUnpack: self.WinUnpack.destroy()
        self.WinUnpack = self.root.toplevel('unpack.ui', title='解析脚本')
        self.WinUnpack.configure(bg='#e8e8e8')
        btn = event.widget._name
        _cfg = self.root.usercfg.get(btn, {})
        self.root.entry('entry-ufile').set(_cfg.get('title', btn))
        self.root.get('text-usetting').insert('end', _cfg.get('value',''))
        self.root.button('btn-usave', cmd=lambda x=btn:_save(x), focus=True)


if __name__ == '__main__':
    tkinter.ScrolledText = tkinter.scrolledtext.ScrolledText
    root = tkgen.gengui.TkJson('app.ui', title='scomm串口调试助手')
    comm = SerComm(root)
    wm = TopWin(root)
    # 读取用户数据文件
    root.usercfg = json.load(open('usercfg.json')) if os.path.isfile('usercfg.json') else {}
    root.save_cfg = comm.ui.save_cfg
    # 预置数据回调函数
    for i in range(20):
        name = 'btn-data%02d'%(i+1)
        try:
            btn = root.get(name)
            root.button(name, cmd=lambda x=name: wm.set_send_data(x))
            btn.bind('<Button-2>', wm.win_data)
            btn.bind('<Button-3>', wm.win_data)
            _cfg = root.usercfg.get(name)
            if _cfg and btn:
                btn.configure(text=_cfg.get('title',name))
        except:
            pass
    # 解析脚本回调函数
    var = tkinter.IntVar()
    for i in range(20):
        name = 'btn-unpack%02d'%(i+1)
        try:
            btn = root.get(name)
            root.button(name, cmd=lambda x=name: wm.set_unpack(x))
            btn.bind('<Button-2>', wm.win_unpack)
            btn.bind('<Button-3>', wm.win_unpack)
            btn.var = var
            _cfg = root.usercfg.get(name)
            if _cfg and btn:
                btn.configure(text=_cfg.get('title',name))
            root.checkbox(name).set(0)
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
    root.entry('entry-split').set(root.usercfg.get('split','99ms'))
    root.entry('entry-cycle').set(root.usercfg.get('cycle','1024ms'))
    root.entry('entry-baud').set(root.usercfg.get('baud','9600'))
    root.entry('entry-encoding').set(root.usercfg.get('encoding','gbk'))
    root.entry('entry-uservar').set(root.usercfg.get('uservar',''))
    root.entry('entry-sendText', key='<Return>', cmd=lambda x:comm.sendData()).set('')
    root.button('btn-scan', cmd=lambda:comm.detectSerialPort())
    root.button('btn-onoff', cmd=lambda:comm.openCloseSerial())
    root.button('btn-send', cmd=lambda:comm.sendData())
    root.button('btn-clear', cmd=lambda:comm.clearWin())
    root.button('btn-savefile', cmd=lambda:comm.saveFile())
    _stvar = tkinter.StringVar()
    root.label('label-status').textvariable=_stvar
    root.label('label-status').var =_stvar
    #root.get('text-recv').configure(state=tkinter.DISABLED)
    # 其他设置
    root.configure(bg='#e8e8e8')
    root.lift() # 把主窗口置于最前面
    #root.wm_state('zoomed') # 最大化窗口
    root.protocol("WM_DELETE_WINDOW", lambda:comm.safe_exit())
    # 启动任务
    comm.detectSerialPort()
    root.mainloop()
