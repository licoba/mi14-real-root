#!/usr/bin/env python3
import hashlib
import shutil
import subprocess
import sys
import tarfile
import time
import zipfile
from pathlib import Path


PHONE_STOCK_PATH = "/sdcard/Download/init_boot_stock.img"
ROM_DOWNLOAD_URL = "https://rom.oppo.help/"
SUKISU_APK = Path("SukiSU_v4.1.2_40545-release.apk")
SUKISU_VERSION_CODE = "40545"
SUKISU_PACKAGES = (
    "me.weishu.kernelsu",
    "io.github.sukisu.ultra",
    "com.sukisu.ultra",
)
PATCH_PATTERNS = (
    "/sdcard/Download/kernelsu_patched*.img",
    "/sdcard/Download/apatch_patched*.img",
    "/sdcard/Download/magisk_patched*.img",
    "/sdcard/Download/SukiSU*.img",
    "/sdcard/Download/sukisu*.img",
    "/sdcard/Download/*patched*.img",
)


def run(cmd, check=False):
    print(f"$ {' '.join(str(x) for x in cmd)}")
    proc = subprocess.run(
        [str(x) for x in cmd],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if proc.stdout.strip():
        print(proc.stdout.strip())
    if proc.stderr.strip():
        print(proc.stderr.strip())
    if check and proc.returncode != 0:
        raise SystemExit(f"命令失败: {' '.join(str(x) for x in cmd)}")
    return proc


def quiet(cmd):
    return subprocess.run(
        [str(x) for x in cmd],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def need_cmd(name):
    if not shutil.which(name):
        raise SystemExit(f"缺少命令: {name}。请安装 Android platform-tools，并确认它在 PATH 里。")


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def adb_prop(name):
    proc = quiet(["adb", "shell", "getprop", name])
    return proc.stdout.strip().replace("\r", "")


def fastboot_getvar(name):
    proc = quiet(["fastboot", "getvar", name])
    output = f"{proc.stdout}\n{proc.stderr}"
    for line in output.splitlines():
        line = line.strip()
        prefix = f"{name}:"
        if line.startswith(prefix):
            return line.split(":", 1)[1].strip()
    return ""


def adb_available():
    return quiet(["adb", "get-state"]).returncode == 0


def fastboot_available():
    proc = quiet(["fastboot", "devices"])
    return any(line.split() for line in proc.stdout.splitlines())


def check_phone(require_unlocked=True):
    need_cmd("adb")
    need_cmd("fastboot")
    run(["adb", "start-server"], check=True)

    if not adb_available():
        raise SystemExit("未检测到 adb 设备。请开机后打开 USB 调试，并在手机上允许调试授权。")

    model = adb_prop("ro.product.model")
    device = adb_prop("ro.product.device")
    slot = adb_prop("ro.boot.slot_suffix")
    flash_locked = adb_prop("ro.boot.flash.locked")
    verified = adb_prop("ro.boot.verifiedbootstate")
    build = adb_prop("ro.build.version.incremental")
    fingerprint = adb_prop("ro.build.fingerprint")

    print("设备状态:")
    print(f"  机型: {model or '未知'}")
    print(f"  设备代号: {device or '未知'}")
    print(f"  当前槽位: {slot or '未知'}")
    print(f"  系统版本: {build or '未知'}")
    print(f"  Verified Boot: {verified or '未知'}")
    print(f"  ro.boot.flash.locked: {flash_locked or '未知'}")

    if fingerprint:
        print(f"  fingerprint: {fingerprint}")

    if device and device != "houji":
        raise SystemExit(f"当前设备代号是 {device}，不是 Xiaomi 14/houji。为避免刷错机型，已停止。")

    if require_unlocked and flash_locked != "0":
        raise SystemExit("bootloader 看起来没有解锁。请先解锁 BL 后再继续。")

    return {
        "model": model,
        "device": device,
        "slot": slot.lstrip("_"),
        "build": build,
        "flash_locked": flash_locked,
    }


def package_installed(package_name):
    proc = quiet(["adb", "shell", "pm", "path", package_name])
    return proc.returncode == 0 and proc.stdout.strip().startswith("package:")


def find_installed_sukisu_package():
    for package_name in SUKISU_PACKAGES:
        if package_installed(package_name):
            return package_name

    proc = quiet(["adb", "shell", "pm", "list", "packages"])
    for line in proc.stdout.splitlines():
        package = line.replace("package:", "").strip()
        lower = package.lower()
        if "sukisu" in lower or "kernelsu" in lower:
            return package
    return ""


def package_version_code(package_name):
    proc = quiet(["adb", "shell", "dumpsys", "package", package_name])
    for line in proc.stdout.splitlines():
        line = line.strip()
        if line.startswith("versionCode="):
            return line.split("=", 1)[1].split()[0]
    return ""


def ensure_sukisu_installed():
    installed = find_installed_sukisu_package()
    if installed and package_version_code(installed) == SUKISU_VERSION_CODE:
        print(f"SukiSU v4.1.2 已安装: {installed}")
        return

    apk = SUKISU_APK.resolve()
    if not apk.exists():
        raise SystemExit(f"未找到 SukiSU 安装包: {apk}")

    if installed:
        current_version = package_version_code(installed) or "未知"
        print(f"检测到 SukiSU 版本不是 v4.1.2: {installed} versionCode={current_version}")
        print("正在卸载旧版本后安装 v4.1.2。")
        run(["adb", "uninstall", installed], check=True)
    else:
        print("手机未检测到 SukiSU。")

    print(f"正在安装: {apk.name}")
    run(["adb", "install", "-r", apk], check=True)
    installed = find_installed_sukisu_package()
    if installed and package_version_code(installed) == SUKISU_VERSION_CODE:
        print(f"SukiSU v4.1.2 安装完成: {installed}")
    else:
        print("SukiSU APK 已安装，但未能自动确认包名。请在手机桌面确认是否出现 SukiSU。")


def find_init_boot_in_dir(root):
    root = Path(root)
    matches = [p for p in root.rglob("init_boot.img") if p.is_file()]
    if not matches:
        return None
    matches.sort(key=lambda p: (0 if "/images/" in p.as_posix() else 1, len(p.as_posix())))
    return matches[0]


def safe_member_name(name):
    parts = Path(name).parts
    return not any(part in ("..", "") for part in parts) and not Path(name).is_absolute()


def extract_init_boot(rom_path, out_dir):
    rom_path = Path(rom_path).expanduser().resolve()
    out_dir = Path(out_dir).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "init_boot.img"

    if not rom_path.exists():
        raise SystemExit(f"找不到线刷包路径: {rom_path}")

    if rom_path.is_dir():
        found = find_init_boot_in_dir(rom_path)
        if not found:
            raise SystemExit(f"目录里没有找到 init_boot.img: {rom_path}")
        shutil.copy2(found, out_path)
        return out_path

    suffixes = "".join(rom_path.suffixes).lower()
    if suffixes.endswith((".tgz", ".tar.gz", ".tar")):
        with tarfile.open(rom_path, "r:*") as tf:
            candidates = [
                m for m in tf.getmembers()
                if m.isfile() and Path(m.name).name == "init_boot.img" and safe_member_name(m.name)
            ]
            if not candidates:
                raise SystemExit("线刷包里没有找到 init_boot.img。请确认下载的是完整 fastboot 线刷包。")
            candidates.sort(key=lambda m: (0 if "/images/" in m.name else 1, len(m.name)))
            src = tf.extractfile(candidates[0])
            if src is None:
                raise SystemExit("无法读取 init_boot.img。")
            with open(out_path, "wb") as f:
                shutil.copyfileobj(src, f)
            print(f"已从压缩包提取: {candidates[0].name}")
            return out_path

    if suffixes.endswith(".zip"):
        with zipfile.ZipFile(rom_path) as zf:
            candidates = [
                n for n in zf.namelist()
                if Path(n).name == "init_boot.img" and safe_member_name(n)
            ]
            if not candidates:
                raise SystemExit("ZIP 里没有找到 init_boot.img。请确认下载的是完整线刷包。")
            candidates.sort(key=lambda n: (0 if "/images/" in n else 1, len(n)))
            with zf.open(candidates[0]) as src, open(out_path, "wb") as f:
                shutil.copyfileobj(src, f)
            print(f"已从 ZIP 提取: {candidates[0]}")
            return out_path

    if rom_path.name == "init_boot.img":
        shutil.copy2(rom_path, out_path)
        return out_path

    raise SystemExit("不支持的文件类型。请传入线刷包 .tgz/.tar/.zip、解压后的目录，或 init_boot.img。")


def show_rom_download_prompt(state):
    model = state.get("model") or "未知"
    device = state.get("device") or "未知"
    build = state.get("build") or "未知"
    slot = state.get("slot") or "未知"

    print()
    print("ROM 下载确认")
    print("=" * 60)
    print(f"  机型: {model}")
    print(f"  设备代号: {device}")
    print(f"  当前系统版本: {build}")
    print(f"  当前槽位: {slot}")
    print()
    print("请下载与上面系统版本完全一致的完整 fastboot 线刷包。")
    print(f"下载站: {ROM_DOWNLOAD_URL}")
    print(f"建议搜索关键词: {device} {build}")
    print("例: houji OS3.0.6.0.WNCCNXM")
    print("=" * 60)

    confirm = input("已经下载好对应版本完整线刷包后，输入 YES 继续: ").strip()
    if confirm != "YES":
        raise SystemExit("已取消。请先下载对应版本完整线刷包。")


def confirm_rom_path_matches_state(rom_path, state):
    name = Path(rom_path).expanduser().name.lower()
    device = (state.get("device") or "").lower()
    build = (state.get("build") or "").lower()

    warnings = []
    if device and device not in name:
        warnings.append(f"路径名里没有设备代号 {device}")
    if build and build not in name:
        warnings.append(f"路径名里没有系统版本 {build}")

    if not warnings:
        return

    print()
    print("路径名提示:")
    for warning in warnings:
        print(f"  - {warning}")
    print("如果你输入的是已解压目录，或文件名被改过，这不一定是问题。")
    confirm = input("确认这个 ROM 就是当前手机对应版本，输入 YES 继续: ").strip()
    if confirm != "YES":
        raise SystemExit("已取消。请重新确认 ROM 路径。")


def push_stock_image(stock_img):
    run(["adb", "push", stock_img, PHONE_STOCK_PATH], check=True)
    print()
    print(f"已推送原始镜像到手机: {PHONE_STOCK_PATH}")
    print("现在请在手机上打开 SukiSU，选择修补/安装镜像文件，选这个 init_boot_stock.img。")
    print("修补完成后，保持手机连接，回到这里按回车继续。")
    input("按回车继续...")


def list_phone_patched_images():
    names = (
        "kernelsu_patched",
        "apatch_patched",
        "magisk_patched",
        "sukisu",
        "patched",
    )
    found = []
    proc = quiet(["adb", "shell", "find", "/sdcard/Download", "-maxdepth", "1", "-type", "f", "-name", "*.img", "-print"])
    for line in proc.stdout.splitlines():
        item = line.strip().replace("\r", "")
        filename = Path(item).name.lower()
        if item.endswith(".img") and filename != "init_boot_stock.img" and any(name in filename for name in names):
            found.append(item)
    found.sort(reverse=True)
    return found


def pull_patched_image(out_dir):
    found = list_phone_patched_images()
    if not found:
        raise SystemExit("没有在 /sdcard/Download 找到 magisk_patched/apatch_patched 镜像。请确认手机 App 已修补完成。")

    remote = found[0]
    local = Path(out_dir) / Path(remote).name
    run(["adb", "pull", remote, str(local)], check=True)
    print(f"已拉取修补镜像: {local}")
    print(f"SHA256: {sha256(local)}")
    return local


def reboot_fastboot():
    run(["adb", "reboot", "bootloader"], check=True)
    print("等待 fastboot 设备...")
    for _ in range(45):
        if fastboot_available():
            return
        time.sleep(1)
    raise SystemExit("等待 fastboot 超时。请确认手机已进入 fastboot 并且 USB 连接正常。")


def flash_image(patched_img, slot, flash_both=False, require_confirm=True):
    if not fastboot_available():
        raise SystemExit("未检测到 fastboot 设备。")

    unlocked = fastboot_getvar("unlocked")
    current_slot = fastboot_getvar("current-slot")
    print(f"fastboot unlocked: {unlocked or '未知'}")
    print(f"fastboot current-slot: {current_slot or '未知'}")
    if unlocked not in ("yes", "true"):
        raise SystemExit("fastboot 显示 BL 未解锁或无法确认，已停止刷写。")

    slot = (current_slot or slot or "").replace("_", "")
    if slot not in ("a", "b"):
        raise SystemExit(f"无法确认当前槽位: {slot or '未知'}")

    targets = [f"init_boot_{slot}"]
    if flash_both:
        targets = ["init_boot_a", "init_boot_b"]

    if require_confirm:
        print()
        print("即将刷写以下分区:")
        for target in targets:
            print(f"  {target} <- {patched_img}")
        print("确认条件: 修补镜像必须来自当前系统版本完全一致的 init_boot.img。")
        confirm = input("输入 ROOT 继续刷写，其他内容取消: ").strip()
        if confirm != "ROOT":
            raise SystemExit("已取消刷写。")

    for target in targets:
        run(["fastboot", "flash", target, patched_img], check=True)

    run(["fastboot", "reboot"], check=True)
    print("已重启。首次开机可能稍慢。")


def wait_for_android(timeout=180):
    print("等待手机重新开机并连接 adb...")
    start = time.time()
    while time.time() - start < timeout:
        if adb_available():
            boot_completed = adb_prop("sys.boot_completed")
            if boot_completed == "1":
                return True
        time.sleep(2)
    return False


def verify_after_flash(expected_slot):
    print()
    print("刷入后验证:")
    if not wait_for_android():
        print("  adb 等待超时。手机可能仍在开机，请手动确认。")
        return False

    slot = adb_prop("ro.boot.slot_suffix").lstrip("_")
    verified = adb_prop("ro.boot.verifiedbootstate")
    flash_locked = adb_prop("ro.boot.flash.locked")
    print(f"  当前槽位: {slot or '未知'}")
    print(f"  Verified Boot: {verified or '未知'}")
    print(f"  ro.boot.flash.locked: {flash_locked or '未知'}")

    if expected_slot and slot and slot != expected_slot:
        print(f"  警告: 当前槽位是 {slot}，刷入前记录的是 {expected_slot}。")

    su_version = quiet(["adb", "shell", "su", "-v"])
    if su_version.returncode == 0 and su_version.stdout.strip():
        print(f"  su 版本: {su_version.stdout.strip()}")
    else:
        print("  暂未从 adb shell 直接读取到 su 版本。")

    su_id = quiet(["adb", "shell", "su", "-c", "id"])
    output = (su_id.stdout + su_id.stderr).strip()
    if su_id.returncode == 0 and "uid=0" in output:
        print(f"  root 验证: 成功 ({output})")
        return True

    print("  root 验证: 还未确认成功。")
    print("  请打开 SukiSU，确认 root 管理器状态，并给 shell/ADB 授权后再测试。")
    if output:
        print(f"  su 输出: {output}")
    return False


def command_check():
    check_phone(require_unlocked=False)


def command_extract(rom, out_dir):
    out = extract_init_boot(rom, out_dir)
    print(f"输出: {out}")
    print(f"SHA256: {sha256(out)}")


def command_root(rom=None, patched=None, out="root_work", no_flash=False, flash_both=False):
    state = check_phone(require_unlocked=True)
    out_dir = Path(out).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    if patched:
        patched = Path(patched).expanduser().resolve()
        if not patched.exists():
            raise SystemExit(f"找不到修补镜像: {patched}")
    else:
        if not rom:
            raise SystemExit("没有提供线刷包路径。")
        stock = extract_init_boot(rom, out_dir)
        print(f"原始 init_boot: {stock}")
        print(f"SHA256: {sha256(stock)}")
        push_stock_image(stock)
        patched = pull_patched_image(out_dir)

    if no_flash:
        print("已选择只准备镜像，没有刷写。")
        print(f"修补镜像位置: {patched}")
        return

    reboot_fastboot()
    flash_image(patched, state.get("slot"), flash_both=flash_both)
    verify_after_flash(state.get("slot"))


def choose_rom_path(state):
    while True:
        try:
            value = input("请手动输入完整线刷包路径、解压目录路径，或 init_boot.img 路径: ").strip()
        except EOFError:
            raise SystemExit("未输入路径，已取消。")
        if value:
            path = Path(value).expanduser()
            confirm_rom_path_matches_state(path, state)
            return path
        print("路径不能为空。")


def latest_local_patched_image(out_dir):
    patterns = (
        "kernelsu_patched*.img",
        "apatch_patched*.img",
        "magisk_patched*.img",
        "*patched*.img",
    )
    candidates = []
    root = Path(out_dir)
    for pattern in patterns:
        candidates.extend(p for p in root.glob(pattern) if p.is_file())
    if not candidates:
        return None
    return sorted(candidates, key=lambda p: p.stat().st_mtime, reverse=True)[0]


def one_key_root():
    print("Xiaomi 14 一键 root")
    print("=" * 60)
    print("准备要求:")
    print("1. 手机已开机，USB 调试已授权。")
    print("2. BL 已解锁。")
    print("3. 已下载和当前手机系统版本完全一致的完整线刷包。")
    print("4. 项目目录里已有 SukiSU APK；手机没装时脚本会自动安装。")
    print("=" * 60)
    input("准备好后按回车开始...")
    print()

    state = check_phone(require_unlocked=True)
    ensure_sukisu_installed()
    out_dir = Path("root_work").resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    patched = latest_local_patched_image(out_dir)
    if patched:
        print(f"检测到已修补镜像，直接续跑: {patched}")
        print(f"SHA256: {sha256(patched)}")
    else:
        show_rom_download_prompt(state)
        rom = choose_rom_path(state)
        stock = extract_init_boot(rom, out_dir)
        print(f"原始 init_boot: {stock}")
        print(f"SHA256: {sha256(stock)}")
        push_stock_image(stock)
        patched = pull_patched_image(out_dir)

    print()
    print("最后确认:")
    print(f"  设备: {state.get('model') or '未知'} / {state.get('device') or '未知'}")
    print(f"  系统版本: {state.get('build') or '未知'}")
    print(f"  当前槽位: {state.get('slot') or '未知'}")
    print(f"  将刷入: {patched}")
    print()
    print("如果线刷包不是这个系统版本对应的包，请现在取消。")
    confirm = input("输入 ROOT 继续重启到 fastboot 并刷入，其他内容取消: ").strip()
    if confirm != "ROOT":
        raise SystemExit("已取消，没有刷写。")

    reboot_fastboot()
    flash_image(patched, state.get("slot"), flash_both=False, require_confirm=False)
    verify_after_flash(state.get("slot"))


def main():
    if len(sys.argv) != 1:
        print("本脚本禁止带参数运行。")
        print("请直接执行: python3 xiaomi14_onekey_root.py")
        raise SystemExit(2)
    one_key_root()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n已取消。")
        sys.exit(130)
