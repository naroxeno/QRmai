#!/usr/bin/env python3
"""Linux 鼠标移动测试脚本

测试 LinuxMouse 的 move_to / click / move_click 功能。

用法:
    python test_mouse.py           # 交互模式，逐步测试
    python test_mouse.py --auto    # 自动模式，间隔 1 秒连续执行
"""

import argparse
import logging
import sys
import time

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("test_mouse")


def load_linuxmouse():
    """从 qrmai.linux 动态加载 LinuxMouse 类"""
    from qrmai.linux import LinuxMouse
    return LinuxMouse


def interactive_test():
    """交互式逐步测试"""
    LinuxMouse = load_linuxmouse()
    mouse = LinuxMouse()

    print("=" * 60)
    print("  LinuxMouse 测试 (交互模式)")
    print("  每步执行后按 Enter 继续，Ctrl+C 退出")
    print("=" * 60)

    tests = [
        ("move_to 左上角 (100, 100)", lambda: mouse.move_to(100, 100)),
        ("move_to 右上角 (1820, 100)", lambda: mouse.move_to(1820, 100)),
        ("move_to 右下角 (1820, 980)", lambda: mouse.move_to(1820, 980)),
        ("move_to 左下角 (100, 980)", lambda: mouse.move_to(100, 980)),
        ("move_to 回中心 (960, 540)", lambda: mouse.move_to(960, 540)),
        ("click 单击 (当前位置)", lambda: mouse.click()),
        ("move_click 组合 (960, 300)", lambda: mouse.move_click(960, 300)),
        ("move_click 组合 (960, 540)", lambda: mouse.move_click(960, 540)),
    ]

    try:
        for desc, action in tests:
            print(f"\n>>> {desc}")
            input("    按 Enter 执行...")
            action()
            print("    完成 ✓")
    except KeyboardInterrupt:
        print("\n\n中断测试")
    finally:
        mouse.close()
        print("已关闭鼠标设备")


def auto_test():
    """自动连续测试"""
    LinuxMouse = load_linuxmouse()
    mouse = LinuxMouse()

    print("=" * 60)
    print("  LinuxMouse 测试 (自动模式)")
    print("  每步间隔 1 秒，观察鼠标移动轨迹")
    print("=" * 60)

    # 四角 + 中心
    sequence = [
        (100, 100),   # 左上
        (1820, 100),  # 右上
        (1820, 980),  # 右下
        (100, 980),   # 左下
        (100, 100),   # 回到左上
        (960, 540),   # 中心
    ]

    try:
        for i, (x, y) in enumerate(sequence):
            print(f"[{i + 1}/{len(sequence)}] 移动到 ({x}, {y})")
            mouse.move_to(x, y)
            time.sleep(0.8)

        print("\n执行 2 次 move_click...")
        mouse.move_click(500, 540)
        time.sleep(1)
        mouse.move_click(1420, 540)

        print("\n✓ 自动测试完成")
    except KeyboardInterrupt:
        print("\n\n中断测试")
    finally:
        mouse.close()
        print("已关闭鼠标设备")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="LinuxMouse 鼠标移动测试")
    parser.add_argument(
        "--auto", action="store_true", help="自动模式，无需手动确认每步"
    )
    args = parser.parse_args()

    if not sys.platform.startswith("linux"):
        print("错误: 此测试仅支持 Linux 平台", file=sys.stderr)
        sys.exit(1)

    if args.auto:
        auto_test()
    else:
        interactive_test()
