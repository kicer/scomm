#! /usr/bin/env python3

import os,json
import tkgen.gengui
import tkinter


def open_wm_data(root,btn):
    def _save_dfile():
        pass
    print('debug: toplevel=%s'%btn)
    root.toplevel('data.json', title='预置数据')
    _cfg = root.usercfg.get(btn)
    if _cfg:
        root.entry('entry-dfile').set(_cfg.get('title', btn))
        root.get('text-dsetting').insert('end', _cfg.get('value'))
        root.checkbox('ckbtn-dhex').set(_cfg.get('hex') and 1 or 0)
        root.button('btn-dsave', cmd=_save_dfile, focus=True)
def open_wm_pack(root,btn):
    print('debug: toplevel=%s'%btn)
    #root.toplevel('pack.json', title='组帧脚本')
def open_wm_unpack(root,btn):
    print('debug: toplevel=%s'%btn)
    #root.toplevel('unpack.json', title='解析脚本')


if __name__ == '__main__':
    root = tkgen.gengui.TkJson('scomm.json', title='scomm串口调试助手')

    cfg_file = 'app.json'
    root.usercfg = json.load(open(cfg_file)) if os.path.isfile(cfg_file) else {}

    # 预置数据回调函数
    for i in range(10):
        name = 'btn-data%02d'%(i+1)
        try:
            btn = root.get(name)
            root.button(name, lambda x=name: open_wm_data(root,x))
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
            root.button(name, lambda x=name: open_wm_pack(root,x))
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
            root.button(name, lambda x=name: open_wm_unpack(root,x))
            _cfg = root.usercfg.get(name)
            if _cfg and btn:
                btn.config(text=_cfg.get('title',name))
        except:
            pass

    root.configure(background='#e8e8e8')
    root.mainloop()
