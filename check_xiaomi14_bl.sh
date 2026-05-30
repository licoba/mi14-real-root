#!/usr/bin/env bash
set -euo pipefail

need_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "缺少命令: $1"
    echo "请先安装 Android platform-tools，并确认 adb/fastboot 在 PATH 里。"
    exit 1
  fi
}

line() {
  printf '%s\n' "------------------------------------------------------------"
}

need_cmd adb
need_cmd fastboot

line
echo "Xiaomi 14 bootloader/root 前置状态检测"
line

echo "[1/4] 检查 adb 连接..."
adb start-server >/dev/null
adb_devices="$(adb devices | awk 'NR > 1 && $1 != "" {print $1 " " $2}')"

if [[ -z "${adb_devices}" ]]; then
  echo "未检测到 adb 设备。"
  echo "如果手机已开机：打开 USB 调试，插线后在手机上允许调试授权。"
else
  echo "${adb_devices}"
fi

line
echo "[2/4] 读取当前 Android 状态..."
if adb get-state >/dev/null 2>&1; then
  model="$(adb shell getprop ro.product.model 2>/dev/null | tr -d '\r' || true)"
  device="$(adb shell getprop ro.product.device 2>/dev/null | tr -d '\r' || true)"
  slot="$(adb shell getprop ro.boot.slot_suffix 2>/dev/null | tr -d '\r' || true)"
  verified="$(adb shell getprop ro.boot.verifiedbootstate 2>/dev/null | tr -d '\r' || true)"
  flash_locked="$(adb shell getprop ro.boot.flash.locked 2>/dev/null | tr -d '\r' || true)"

  echo "机型: ${model:-未知}"
  echo "设备代号: ${device:-未知}"
  echo "当前槽位: ${slot:-未知}"
  echo "Verified Boot: ${verified:-未知}"
  echo "ro.boot.flash.locked: ${flash_locked:-未知}"

  case "${flash_locked}" in
    0) echo "adb 侧判断: bootloader 大概率已解锁。" ;;
    1) echo "adb 侧判断: bootloader 仍是锁定状态。" ;;
    *) echo "adb 侧无法明确判断 bootloader 状态，继续用 fastboot 检查。" ;;
  esac
else
  echo "adb 当前不可用，可能设备在 fastboot 模式或未授权。"
fi

line
echo "[3/4] 检查 fastboot 状态..."
echo "如果手机现在是正常开机状态，脚本不会自动重启。"
echo "要做 fastboot 检测，请手动执行：adb reboot bootloader"
echo "进入 fastboot 后重新运行本脚本。"

fastboot_devices="$(fastboot devices 2>/dev/null | awk '$1 != "" {print $1}')"
if [[ -z "${fastboot_devices}" ]]; then
  echo "未检测到 fastboot 设备。"
else
  echo "检测到 fastboot 设备:"
  echo "${fastboot_devices}"
  unlocked="$(fastboot getvar unlocked 2>&1 | awk -F ': ' '/unlocked:/ {print $2}' | tr -d '\r' | tail -1 || true)"
  secure="$(fastboot getvar secure 2>&1 | awk -F ': ' '/secure:/ {print $2}' | tr -d '\r' | tail -1 || true)"
  current_slot="$(fastboot getvar current-slot 2>&1 | awk -F ': ' '/current-slot:/ {print $2}' | tr -d '\r' | tail -1 || true)"

  echo "fastboot unlocked: ${unlocked:-未知}"
  echo "fastboot secure: ${secure:-未知}"
  echo "fastboot current-slot: ${current_slot:-未知}"

  case "${unlocked}" in
    yes|true) echo "fastboot 侧判断: bootloader 已解锁。" ;;
    no|false) echo "fastboot 侧判断: bootloader 未解锁。" ;;
    *) echo "fastboot 侧无法明确判断 bootloader 状态。" ;;
  esac
fi

line
echo "[4/4] root 前提醒"
cat <<'EOF'
Xiaomi 14 root 通常流程:
1. 确认 BL 已解锁。
2. 下载与你手机当前系统版本完全一致的官方 ROM。
3. 从 ROM 里提取 init_boot.img。新机型通常修补 init_boot，不是 boot。
4. 用 Magisk/APatch 在手机上修补 init_boot.img。
5. 进 fastboot 后先临时测试:
   fastboot boot patched_init_boot.img
6. 能正常开机且 root 正常后，再刷入当前槽位:
   fastboot flash init_boot patched_init_boot.img

不要混用不同版本 ROM 的 init_boot.img；不要在没确认槽位和版本时直接刷。
EOF
line
