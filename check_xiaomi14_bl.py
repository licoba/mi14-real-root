#!/usr/bin/env python3
import shutil
import subprocess
import sys


def run(cmd, check=False):
    proc = subprocess.run(
        cmd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if check and proc.returncode != 0:
        raise SystemExit(proc.stderr.strip() or proc.stdout.strip() or f"命令失败: {' '.join(cmd)}")
    return proc


def need_cmd(name):
    if not shutil.which(name):
        print(f"缺少命令: {name}")
        print("请先安装 Android platform-tools，并确认 adb/fastboot 在 PATH 里。")
        raise SystemExit(1)


def adb_prop(name):
    proc = run(["adb", "shell", "getprop", name])
    return proc.stdout.strip().replace("\r", "")


def fastboot_getvar(name):
    proc = run(["fastboot", "getvar", name])
    output = f"{proc.stdout}\n{proc.stderr}"
    for line in output.splitlines():
        line = line.strip()
        prefix = f"{name}:"
        if line.startswith(prefix):
            return line.split(":", 1)[1].strip()
    return ""


def line():
    print("-" * 60)


def main():
    need_cmd("adb")
    need_cmd("fastboot")

    line()
    print("Xiaomi 14 bootloader/root 前置状态检测")
    line()

    print("[1/4] 检查 adb 连接...")
    run(["adb", "start-server"])
    adb_devices = []
    proc = run(["adb", "devices"])
    for raw in proc.stdout.splitlines()[1:]:
        parts = raw.split()
        if len(parts) >= 2:
            adb_devices.append((parts[0], parts[1]))

    if adb_devices:
        for serial, state in adb_devices:
            print(f"{serial} {state}")
    else:
        print("未检测到 adb 设备。")
        print("如果手机已开机：打开 USB 调试，插线后在手机上允许调试授权。")

    line()
    print("[2/4] 读取当前 Android 状态...")
    adb_state = run(["adb", "get-state"])
    if adb_state.returncode == 0:
        model = adb_prop("ro.product.model")
        device = adb_prop("ro.product.device")
        slot = adb_prop("ro.boot.slot_suffix")
        verified = adb_prop("ro.boot.verifiedbootstate")
        flash_locked = adb_prop("ro.boot.flash.locked")

        print(f"机型: {model or '未知'}")
        print(f"设备代号: {device or '未知'}")
        print(f"当前槽位: {slot or '未知'}")
        print(f"Verified Boot: {verified or '未知'}")
        print(f"ro.boot.flash.locked: {flash_locked or '未知'}")

        if flash_locked == "0":
            print("adb 侧判断: bootloader 大概率已解锁。")
        elif flash_locked == "1":
            print("adb 侧判断: bootloader 仍是锁定状态。")
        else:
            print("adb 侧无法明确判断 bootloader 状态，继续用 fastboot 检查。")
    else:
        print("adb 当前不可用，可能设备在 fastboot 模式或未授权。")

    line()
    print("[3/4] 检查 fastboot 状态...")
    print("如果手机现在是正常开机状态，脚本不会自动重启。")
    print("要做 fastboot 检测，请手动执行：adb reboot bootloader")
    print("进入 fastboot 后重新运行本脚本。")

    fb = run(["fastboot", "devices"])
    fastboot_devices = [line.split()[0] for line in fb.stdout.splitlines() if line.split()]
    if not fastboot_devices:
        print("未检测到 fastboot 设备。")
    else:
        print("检测到 fastboot 设备:")
        for serial in fastboot_devices:
            print(serial)
        unlocked = fastboot_getvar("unlocked")
        secure = fastboot_getvar("secure")
        current_slot = fastboot_getvar("current-slot")
        print(f"fastboot unlocked: {unlocked or '未知'}")
        print(f"fastboot secure: {secure or '未知'}")
        print(f"fastboot current-slot: {current_slot or '未知'}")
        if unlocked in ("yes", "true"):
            print("fastboot 侧判断: bootloader 已解锁。")
        elif unlocked in ("no", "false"):
            print("fastboot 侧判断: bootloader 未解锁。")
        else:
            print("fastboot 侧无法明确判断 bootloader 状态。")

    line()
    print("[4/4] root 前提醒")
    print(
        """Xiaomi 14 root 通常流程:
1. 确认 BL 已解锁。
2. 下载与你手机当前系统版本完全一致的官方线刷包。
3. 从线刷包里提取 init_boot.img。新机型通常修补 init_boot，不是 boot。
4. 用 Magisk/APatch 在手机上修补 init_boot.img。
5. 进 fastboot 后先临时测试能否启动，确认正常后再刷入当前槽位。

不要混用不同版本 ROM 的 init_boot.img；不要在没确认槽位和版本时直接刷。"""
    )
    line()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n已取消。")
        sys.exit(130)
