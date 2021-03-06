# scomm串口调试助手(Mac/Linux/Windows)
一款跨平台串口调试助手，助力Mac/Linux/Windows平台下的嵌入式开发。


## 功能特色
1. 依托python，全平台运行
2. 接收数据，自定义脚本解析输出
3. 数据显示，自定义文本编码
4. 预置数据，快速编辑、一键发送
5. 预置变量，传递参数给预置数据
6. 接收数据，自定义分帧间隔
7. 串口开关状态灯指示
8. HEX格式、时间戳、循环发送、保存文件等


## 安装运行
```bash
# install python3
python scomm.py

# windows下安装py2exe可导出成exe文件
# pip install pyyaml pyserial py2exe
# python setup.py py2exe
```


## 运行环境
* python3.x
* tkinter
* pyserial
* pyyaml


## 解析脚本
鼠标右键/中键选择对应脚本，可以打开脚本编辑对话框。
程序中调用*eval*函数解析脚本并打印执行结果。

```python
# data为接收到的数据帧字节数组
# 注意数据帧可能有分片、组包的情况
# 可配合分帧间隔字段处理
#
# data内容按16进制转换，加空格后连接
' '.join(['%02X'%x for x in data])
```


## 数据编码
嵌入式环境下中文常用gbk编码，输入中文内容执行发送时，
会自动按照数据编码设定，编码后输出。

注意某些tcl/tk版本不兼容，可能无法输入中文，可通过快捷键编辑处理。


## 预置数据
鼠标右键/中键选择对应预置数据按钮，可以打开编辑对话框。
HEX格式请注意检测数据是否有效，程序中未对数据有效性作检查。

亦可按照字典形式设置流控等功能。

```json
# 设置RTS pin为高电平，同时发送hex字符串: 0x55 0xAA
# 注意：RTS/DTR引脚低电平有效
{"rts":0, "text":"55 AA", "hex":1}
```


## 预置变量
以逗号分割的字符串数组变量，传递给预置数据。
调用*eval*函数解析预置数据并发送执行结果。

```python
# data为预置变量字符数组
# 例如预置数据如下，选中HEX格式，预置变量设置为"1,3"
# 则对应要发送的数据解析为55 AA 03 F8 01 EE
"55 AA 03 F8 5A %02X EE" % int(data[0])
```


## 分帧间隔
电脑端系统驱动层有数据接收缓存，不能保证接收到的数据都是按数据帧分开的。
请合理设置分帧间隔字段，以确保数据显示符合预期。


## 常规选项

- HEX显示
    - 数据收发内容窗口的显示格式
- HEX发送
    - 按HEX格式解析要发送的数据，注意程序未对数据有效性作检查。
- 发送显示
    - 发送出去的数据是否显示
- 收发时间
    - 是否显示时间戳
- 循环发送
    - 按指定时间循环发送数据
