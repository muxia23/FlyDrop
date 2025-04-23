# main.py

from utils.network import DeviceDiscovery

def on_new_device(ip, name):
    print(f"发现设备：{name} ({ip})")

if __name__ == '__main__':
    device_name = input("请输入当前设备名：")
    discovery = DeviceDiscovery(device_name, on_new_device)
    discovery.start()

    try:
        while True:
            pass  # 保持运行
    except KeyboardInterrupt:
        discovery.stop()
        print("已停止设备发现。")