#!/usr/bin/env python3
"""仅点击 p2 位置的测试脚本"""

import sys
sys.path.insert(0, "src")

from qrmai.linux import LinuxMouse

mouse = LinuxMouse()

# p2 坐标来自 config.json
x, y = 1625, 509

print(f"移动并点击 p2 ({x}, {y}) ...")
mouse.move_click(x, y)
print("完成")

mouse.close()
