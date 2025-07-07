# Fly Drop

基于 python 的局域网跨平台文件传输和粘贴板共享系统

## 使用说明
clone到本地后，先在backend文件夹下启动main.py，后在frontend文件夹下启动main.py

## ToDoList：
1.window环境测试
2.设置页面编写
3.粘贴板共享

（目前只测试了 mac 系统之间的互通）

## 常见问题
1.为什么别人发现不了我的设备？
可能是因为局域网路由器设置了内网隔离，导致 udp 广播无法正确被接受
