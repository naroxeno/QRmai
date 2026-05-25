"""
QRmai 共享模块 — 平台无关的工具函数、日志、配置初始化
"""

import sys
import os
import json
import time
import logging
import hashlib
from io import BytesIO

# =============================================================================
# 平台检测
# =============================================================================
IS_WINDOWS = sys.platform == "win32"
IS_LINUX = sys.platform == "linux"

if not (IS_WINDOWS or IS_LINUX):
    raise RuntimeError(f"不支持的操作系统: {sys.platform}")


# =============================================================================
# 资源路径工具
# =============================================================================
def resource_path(relative_path):
    """获取资源文件的绝对路径"""
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


# =============================================================================
# 日志初始化
# =============================================================================
def setup_logging():
    """配置日志，将日志保存到logs文件夹"""
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    logs_dir = os.path.join(base_path, "logs")

    if not os.path.exists(logs_dir):
        os.makedirs(logs_dir)

    log_file = os.path.join(logs_dir, time.strftime("%Y-%m-%d") + ".log")

    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    if logger.handlers:
        logger.handlers.clear()

    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(logging.INFO)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    formatter = logging.Formatter(
        "%(asctime)s - %(levelname)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    )
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    return logger, logs_dir


# =============================================================================
# 日志实例
# =============================================================================
logger, logs_dir = setup_logging()
logger.info(f"日志系统初始化 - 平台: {sys.platform}")

# Werkzeug 日志也写入文件
werkzeug_logger = logging.getLogger("werkzeug")
werkzeug_logger.setLevel(logging.INFO)
werkzeug_handler = logging.FileHandler(
    os.path.join(logs_dir, time.strftime("%Y-%m-%d") + ".log"), encoding="utf-8"
)
werkzeug_handler.setLevel(logging.INFO)
werkzeug_formatter = logging.Formatter(
    "%(asctime)s - %(levelname)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
)
werkzeug_handler.setFormatter(werkzeug_formatter)
werkzeug_logger.addHandler(werkzeug_handler)


# =============================================================================
# 配置管理
# =============================================================================
def get_default_config():
    """获取默认配置项"""
    return {
        "p1": [1087, 799],
        "p2": [945, 682],
        "token": "qrmai",
        "host": "0.0.0.0",
        "port": 5000,
        "qr_route": "/qrmai",
        "cache_duration": 60,
        "standalone_mode": False,
        "decode": {"time": 10, "retry_count": 10},
        "skin_format": "new",
        "custom_skin_path": "./skin.png",
        "custom_skin_qrcode_size": 576,
        "custom_skin_qrcode_point": [106, 638],
        "dev_mode": False,
        # Linux 专用配置
        "wechat_bin": "/opt/wechat/wechat",
        "wechat_url_timeout": 30,
    }


def ensure_config_completeness(config):
    """确保配置项完整，缺失的项用默认值补全"""
    default_config = get_default_config()
    for key, default_value in default_config.items():
        if key not in config:
            config[key] = default_value
        elif isinstance(default_value, dict) and isinstance(config[key], dict):
            for sub_key, sub_default_value in default_value.items():
                if sub_key not in config[key]:
                    config[key][sub_key] = sub_default_value
    return config


# 加载配置
config = {}
config_path = resource_path("config.json")
if os.path.exists(config_path):
    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)

config = ensure_config_completeness(config)

if "version" not in config:
    try:
        config_version = hashlib.md5(
            (config["token"] + str(os.path.getmtime(config_path))).encode()
        ).hexdigest()
    except FileNotFoundError:
        config_version = hashlib.md5(
            (config["token"] + str(time.time())).encode()
        ).hexdigest()
    config["version"] = config_version


# =============================================================================
# 二维码图像生成（Windows/Linux 共用）
# =============================================================================
def apply_skin_to_qr(qr_data: str) -> BytesIO:
    """
    将解码得到的二维码数据生成二维码图像，如果有皮肤文件则叠加。
    返回包含 PNG 图像的 BytesIO 对象。
    """
    import qrcode
    from PIL import Image

    img_io = BytesIO()
    qr_img = qrcode.make(qr_data)

    import os as _os

    if "skin.png" in _os.listdir():
        if config["skin_format"] == "custom":
            skin = Image.open(config["custom_skin_path"])
        else:
            skin = Image.open("skin.png")
        qr_img = qr_img.convert("RGBA")

        width, height = qr_img.size
        for x in range(width):
            for y in range(height):
                r, g, b, a = qr_img.getpixel((x, y))
                if r > 200 and g > 200 and b > 200:
                    qr_img.putpixel((x, y), (255, 255, 255, 0))

        if config["skin_format"] == "custom":
            qrcode_size = int(config["custom_skin_qrcode_size"])
            resized_qr = qr_img.resize((qrcode_size, qrcode_size))
        else:
            resized_qr = qr_img.resize((576, 576))

        if config["skin_format"] == "new":
            skin.paste(resized_qr, (106, 638), mask=resized_qr)
        elif config["skin_format"] == "old":
            skin.paste(resized_qr, (106, 1060), mask=resized_qr)
        else:
            qrcode_point = (
                config["custom_skin_qrcode_point"][0],
                config["custom_skin_qrcode_point"][1],
            )
            skin.paste(resized_qr, qrcode_point, mask=resized_qr)

        skin.save(img_io, format="PNG")
    elif config["skin_format"] == "custom":
        skin = Image.open(config["custom_skin_path"])
        qr_img = qr_img.convert("RGBA")

        width, height = qr_img.size
        for x in range(width):
            for y in range(height):
                r, g, b, a = qr_img.getpixel((x, y))
                if r > 200 and g > 200 and b > 200:
                    qr_img.putpixel((x, y), (255, 255, 255, 0))

        qrcode_size = int(config["custom_skin_qrcode_size"])
        resized_qr = qr_img.resize((qrcode_size, qrcode_size))
        qrcode_point = (
            config["custom_skin_qrcode_point"][0],
            config["custom_skin_qrcode_point"][1],
        )
        skin.paste(resized_qr, qrcode_point, mask=resized_qr)
        skin.save(img_io, format="PNG")
    else:
        qr_img.save(img_io, format="PNG")

    img_io.seek(0)
    return img_io


def make_error_image(message: str) -> BytesIO:
    """创建包含错误信息的 PNG 图像"""
    from PIL import Image, ImageDraw, ImageFont

    img_io = BytesIO()
    im = Image.new("L", (200, 100), "#FFFFFF")
    font = ImageFont.load_default(size=23)
    draw = ImageDraw.Draw(im)
    draw.text((10, 10), message, font=font, fill="#000000")
    im.save(img_io, format="PNG")
    img_io.seek(0)
    return img_io
