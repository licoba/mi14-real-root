# 小米 14 一键 Root 助手

这是一个给小米 14（设备代号 `houji`）使用的 Root 辅助脚本。脚本会尽量把流程做成新手可跟随的一条线：检测手机状态、提示下载匹配 ROM、提取 `init_boot.img`、安装/使用 SukiSU 修补镜像、刷入当前槽位，并在重启后做基础验证。

## 重要提醒

刷写 `init_boot` 有风险。请确认：

- 手机是小米 14，设备代号是 `houji`。
- Bootloader 已解锁。
- ROM 版本必须和手机当前系统版本完全一致。
- 不要混用其他版本 ROM 的 `init_boot.img`。
- 脚本默认只刷当前槽位，不会同时刷 A/B 两个槽位。

## 文件说明

- `xiaomi14_onekey_root.py`：主脚本，交互式一键 Root 流程。
- `check_xiaomi14_bl.py`：Python 版 BL/设备状态检测脚本。
- `check_xiaomi14_bl.sh`：Shell 版 BL/设备状态检测脚本。

## 准备工作

1. 电脑已安装 Android platform-tools，并且 `adb`、`fastboot` 在 `PATH` 中。
2. 手机已开启 USB 调试，并在手机上允许电脑调试授权。
3. 手机 BL 已解锁。
4. 下载与手机当前系统版本完全一致的完整 fastboot 线刷包。
5. 项目目录里放置 SukiSU 安装包：

```text
SukiSU_v4.1.2_40545-release.apk
```

ROM 下载站提示：

```text
https://rom.oppo.help/
```

脚本会显示当前机型、设备代号、系统版本和槽位，并提示你用类似下面的关键词搜索：

```text
houji OS3.0.6.0.WNCCNXM
```

## 使用方法

在项目目录运行：

```bash
python3 xiaomi14_onekey_root.py
```

脚本会依次执行：

1. 检查 `adb`、`fastboot`。
2. 读取手机机型、设备代号、当前槽位、系统版本和 BL 状态。
3. 检查或安装 SukiSU v4.1.2。
4. 严格检测当前是否已经 Root：只有 SukiSU 已安装、`su -v` 可用、`su -c id` 返回 `uid=0` 时才会判定已 Root 并跳过刷写。
5. 显示 ROM 下载确认信息。
6. 要求你手动输入完整线刷包路径、解压目录路径，或 `init_boot.img` 路径。
7. 只提取 `init_boot.img`，不会完整解压整个 ROM。
8. 推送原始镜像到手机：

```text
/sdcard/Download/init_boot_stock.img
```

9. 提示你在手机 SukiSU 中修补这个镜像。
10. 自动拉回 `kernelsu_patched*.img`。
11. 最后确认输入 `ROOT` 后，刷入当前槽位的 `init_boot`。
12. 手机重启后等待 adb 返回，并做基础 root 状态验证。

## 单独检测 BL 状态

Python 版：

```bash
python3 check_xiaomi14_bl.py
```

Shell 版：

```bash
./check_xiaomi14_bl.sh
```

## Git 忽略说明

以下内容不会提交到 Git：

- APK 安装包
- 原始或修补后的 `.img` 镜像
- `root_work/` 工作目录
- Python 缓存文件

这些文件通常是本机下载或生成的产物，可能很大，也可能和具体设备状态相关。
