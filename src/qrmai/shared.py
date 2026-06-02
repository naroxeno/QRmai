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
        # OpenCV 视觉识别配置
        "auto_detect_p1p2": False,
        "template_threshold": 0.8,
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


# =============================================================================
# OpenCV 视觉识别 — P1 / P2 自动定位
# =============================================================================

_TEMPLATES_DIR = resource_path("templates_img")


def _get_template_path(name: str):
    """按优先级查找模板图：用户模板 > 开发者模板，均无则返回 None"""
    user_path = os.path.join(_TEMPLATES_DIR, f"{name}_user.png")
    dev_path = os.path.join(_TEMPLATES_DIR, f"{name}.png")

    if os.path.isfile(user_path):
        logger.info(f"[OpenCV] 使用用户模板: {user_path}")
        return user_path
    elif os.path.isfile(dev_path):
        logger.info(f"[OpenCV] 使用开发者模板: {dev_path}")
        return dev_path
    else:
        logger.warning(
            f"[OpenCV] 未找到模板图 {name}（已检查 {user_path} 和 {dev_path}）"
        )
        return None


def _image_to_bgr(image):
    """
    将多种输入格式统一转换为 OpenCV BGR ndarray。
    支持: ndarray / BytesIO / PIL Image / 文件路径 str
    """
    import numpy as np
    import cv2

    if isinstance(image, np.ndarray):
        arr = image
    elif isinstance(image, BytesIO):
        image.seek(0)
        arr = np.frombuffer(image.read(), dtype=np.uint8)
        arr = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    elif isinstance(image, str):
        arr = cv2.imread(image, cv2.IMREAD_COLOR)
    else:
        try:
            from PIL import Image
            if isinstance(image, Image.Image):
                arr = np.array(image.convert("RGB"))
                arr = cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)
            else:
                raise TypeError(f"不支持的图像类型: {type(image)}")
        except ImportError:
            raise TypeError(f"不支持的图像类型: {type(image)}")

    if arr is None or arr.size == 0:
        raise ValueError("图像数据为空")

    if len(arr.shape) == 2:
        arr = cv2.cvtColor(arr, cv2.COLOR_GRAY2BGR)
    elif arr.shape[2] == 4:
        arr = cv2.cvtColor(arr, cv2.COLOR_BGRA2BGR)

    return arr


def _match_template_multiscale(
    screen,
    template_path,
    threshold=0.8,
    scales=(0.6, 0.8, 1.0, 1.2, 1.5),
):
    """
    多尺度模板匹配。在不同缩放比例下查找模板，返回最佳匹配的中心坐标。

    适应不同屏幕分辨率 / DPI 缩放下的 UI 元素尺寸差异。

    Returns:
        [x, y] 或 None
    """
    import cv2

    template = cv2.imread(template_path, cv2.IMREAD_COLOR)
    if template is None:
        logger.error(f"[OpenCV] 无法读取模板图: {template_path}")
        return None

    best_val = -1.0
    best_loc = None
    best_scale = 1.0
    best_size = template.shape[:2]

    for scale in scales:
        tw = int(template.shape[1] * scale)
        th = int(template.shape[0] * scale)
        if tw < 10 or th < 10 or tw > screen.shape[1] or th > screen.shape[0]:
            continue

        scaled = cv2.resize(template, (tw, th), interpolation=cv2.INTER_LINEAR)
        result = cv2.matchTemplate(screen, scaled, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(result)

        logger.debug(f"[OpenCV] 缩放 {scale:.1f}x -> max_val={max_val:.3f}")

        if max_val > best_val:
            best_val = max_val
            best_loc = max_loc
            best_scale = scale
            best_size = (th, tw)

    if best_loc is None or best_val < threshold:
        logger.warning(
            f"[OpenCV] 模板 {os.path.basename(template_path)} 匹配度不足 "
            f"(best={best_val:.3f} < {threshold})"
        )
        return None

    center_x = best_loc[0] + best_size[1] // 2
    center_y = best_loc[1] + best_size[0] // 2

    logger.info(
        f"[OpenCV] 匹配成功: {os.path.basename(template_path)} "
        f"-> [{center_x}, {center_y}] "
        f"(scale={best_scale:.1f}x, confidence={best_val:.3f})"
    )
    return [center_x, center_y]


def detect_p1p2(image, threshold=None):
    """
    从屏幕截图中自动识别 P1 / P2 的坐标。

    Args:
        image:     屏幕截图，支持 ndarray / BytesIO / PIL Image / 文件路径
        threshold: 匹配置信度阈值，默认使用 config 中的 template_threshold

    Returns:
        (p1, p2) — 各自为 [x, y] 或 None

    Example:
        p1, p2 = detect_p1p2(screenshot_bytes)
        # p1 = [1788, 654], p2 = [1427, 559]
    """
    if threshold is None:
        threshold = config.get("template_threshold", 0.8)

    screen = _image_to_bgr(image)
    logger.debug(
        f"[OpenCV] 开始识别 P1/P2，屏幕尺寸: {screen.shape[1]}x{screen.shape[0]}"
    )

    p1 = None
    p1_template = _get_template_path("p1")
    if p1_template:
        p1 = _match_template_multiscale(screen, p1_template, threshold)
    else:
        logger.warning("[OpenCV] 无 P1 模板图，跳过 P1 识别")

    p2 = None
    p2_template = _get_template_path("p2")
    if p2_template:
        p2 = _match_template_multiscale(screen, p2_template, threshold)
    else:
        logger.warning("[OpenCV] 无 P2 模板图，跳过 P2 识别")

    return p1, p2


def resolve_p1p2(capture_screen):
    """
    解析 P1/P2 点击坐标，供 qrmai_action 调用。

    优先级：
      1. config.json 中的 p1 / p2（非空时直接使用）
      2. OpenCV 自动识别

    Args:
        capture_screen: 平台截图函数，返回 BGR ndarray

    Returns:
        (p1, p2) — 各自为 [x, y]

    Raises:
        RuntimeError: 两种方式均无法获取坐标
    """
    p1_cfg = config.get("p1")
    p2_cfg = config.get("p2")

    # 检查 config 中是否有有效坐标（非 None、非空列表、长度为 2）
    p1_valid = (
        p1_cfg is not None
        and isinstance(p1_cfg, (list, tuple))
        and len(p1_cfg) == 2
        and all(isinstance(v, (int, float)) for v in p1_cfg)
    )
    p2_valid = (
        p2_cfg is not None
        and isinstance(p2_cfg, (list, tuple))
        and len(p2_cfg) == 2
        and all(isinstance(v, (int, float)) for v in p2_cfg)
    )

    if p1_valid and p2_valid:
        logger.info(f"[OpenCV] 使用 config 坐标: P1={p1_cfg}, P2={p2_cfg}")
        return list(p1_cfg), list(p2_cfg)

    # config 坐标不完整，尝试 OpenCV 识别
    logger.info(
        "[OpenCV] config 坐标不完整 (P1={}, P2={})，尝试自动识别".format(
            "有效" if p1_valid else "无效",
            "有效" if p2_valid else "无效",
        )
    )

    screen = capture_screen()
    detected_p1, detected_p2 = detect_p1p2(screen)

    if detected_p1 is None:
        if p1_valid:
            detected_p1 = list(p1_cfg)
            logger.warning(f"[OpenCV] P1 识别失败，回退到 config: {detected_p1}")
        else:
            raise RuntimeError(
                "无法获取 P1 坐标：config 为空且 OpenCV 识别失败，"
                "请在 config.json 中设置 p1 或添加模板图到 templates_img/"
            )

    if detected_p2 is None:
        if p2_valid:
            detected_p2 = list(p2_cfg)
            logger.warning(f"[OpenCV] P2 识别失败，回退到 config: {detected_p2}")
        else:
            raise RuntimeError(
                "无法获取 P2 坐标：config 为空且 OpenCV 识别失败，"
                "请在 config.json 中设置 p2 或添加模板图到 templates_img/"
            )

    logger.info(f"[OpenCV] 最终坐标: P1={detected_p1}, P2={detected_p2}")
    return detected_p1, detected_p2
