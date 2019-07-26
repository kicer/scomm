#! /usr/bin/env python3

import tkgen.gengui

if __name__ == '__main__':
    root = tkgen.gengui.TkJson('scomm.json', title='scomm串口调试助手')
    #root = tkgen.gengui.TkJson('rsa_ui.json', title='scomm串口调试助手')
    root.mainloop()
