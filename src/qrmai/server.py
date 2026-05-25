# Flask框架相关模块
from flask import (
    Flask,
    render_template,
    request,
    Response,
    session,
    redirect,
    url_for,
    jsonify,
)
from functools import wraps
from io import BytesIO
from uuid import uuid4
import sys
import time
import json
import os

IS_LINUX = sys.platform == "linux"

# 初始化Flask应用
app = Flask(__name__)
app.secret_key = str(uuid4())  # 在生产环境中应该使用更安全的密钥

# 缓存相关全局变量
request_lock = False  # 请求锁，防止并发访问
last_qr_bytes = None  # 上次生成的二维码字节数据
last_qr_time = 0  # 上次生成二维码的时间戳

# 以下变量由 main.py 通过 init() 注入
_config = None
_logger = None
_qrmai_action = None


def init(qrmai_action, config, logger, template_folder):
    """初始化 server 模块，注入来自 main.py 的依赖"""
    global _qrmai_action, _config, _logger
    _qrmai_action = qrmai_action
    _config = config
    _logger = logger
    app.template_folder = template_folder


def require_auth(f):
    """装饰器：要求用户认证"""

    @wraps(f)
    def decorated_function(*args, **kwargs):
        # 检查基础认证状态
        if "authenticated" not in session:
            return redirect(url_for("login"))

        # 检查配置版本是否匹配（增强安全性）
        if "config_version" not in session or session["config_version"] != _config.get(
            "version"
        ):
            # 配置已更改，需要重新登录
            session.pop("authenticated", None)
            session.pop("config_version", None)
            return redirect(url_for("login"))

        return f(*args, **kwargs)

    return decorated_function


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        token = request.form.get("token")
        if token and token == _config["token"]:
            session["authenticated"] = True
            # 存储配置版本信息到session中，用于增强安全性
            session["config_version"] = _config.get("version")
            _logger.info(f"来自{request.remote_addr}的成功登录请求")
            return {"success": True}
        else:
            _logger.info(f"来自{request.remote_addr}的登录请求失败")
            return {"success": False}
    _logger.info(f"{request.remote_addr}尝试进入登录页面")
    return render_template("login.html")


@app.route("/logout", methods=["POST"])
def logout():
    session.pop("authenticated", None)
    return "", 204


@app.route("/settings", methods=["GET", "POST"])
@require_auth
def settings():
    if request.method == "POST":
        # 读取POST参数并更新config
        token_updated = False
        old_token = _config["token"]

        # 处理所有表单字段，包括布尔值字段
        # 首先处理布尔值字段，确保未选中的开关也能正确处理
        boolean_fields = ["standalone_mode"]
        for field in boolean_fields:
            if field in _config:
                # 检查表单中是否包含该字段
                _config[field] = field in request.form and request.form[
                    field
                ].lower() in ("true", "1", "yes", "on")

        # 处理其他字段
        for key, value in request.form.items():
            # 跳过已处理的布尔值字段
            if key in boolean_fields:
                continue

            if key in _config:
                # 尝试将字符串转换为对应类型（int/float/list）
                if isinstance(_config[key], bool):
                    _config[key] = value.lower() in ("true", "1", "yes", "on")
                elif isinstance(_config[key], int):
                    _config[key] = int(value)
                elif isinstance(_config[key], float):
                    _config[key] = float(value)
                elif isinstance(_config[key], list) and "," in value:
                    _config[key] = [
                        int(v) if v.isdigit() else v for v in value.split(",")
                    ]
                else:
                    _config[key] = value
                # 检查是否更新了token
                if key == "token" and value != old_token:
                    token_updated = True
            elif key == "qr_route":  # 处理新的配置项
                _config[key] = value
                # 二维码路由路径更改，需要更新路由
                # 注意：在当前请求中无法动态修改路由，需要重启服务

        # 保存更新后的config到文件
        with open("config.json", "w", encoding="utf-8") as f:
            json.dump(_config, f, ensure_ascii=False, indent=4)
        # 如果token被更新，需要更新配置版本信息
        if token_updated:
            import hashlib
            import time as _time

            try:
                config_version = hashlib.md5(
                    (_config["token"] + str(os.path.getmtime("config.json"))).encode()
                ).hexdigest()
            except FileNotFoundError:
                config_version = hashlib.md5(
                    (_config["token"] + str(_time.time())).encode()
                ).hexdigest()
            _config["version"] = config_version
            # 更新session中的配置版本信息
            session["config_version"] = config_version
        return "配置已更新", 200
    # GET请求时返回设置页面
    return render_template("settings.html", config=_config, is_linux=IS_LINUX)


@app.route("/check_update", methods=["POST"])
@require_auth
def check_update():
    """检查更新的路由"""
    try:
        # 导入updater模块
        import updater

        # 检查是否有新版本
        has_update, latest_release = updater.is_new_version_available()

        if has_update and latest_release:
            return jsonify(
                {
                    "has_update": True,
                    "version": latest_release["version"],
                    "name": latest_release["name"],
                    "published_at": latest_release["published_at"],
                    "body": latest_release["body"],
                }
            )
        else:
            return jsonify({"has_update": False, "message": "当前已是最新版本"})
    except Exception as e:
        return jsonify({"error": True, "message": f"检查更新时出错: {str(e)}"}), 500


@app.route("/_qrmai", endpoint="qrmai")
def qrmai():
    """
    处理二维码路由请求的函数
    包含身份验证、缓存机制和并发控制
    """
    # 验证token，如果与配置不符则返回403错误
    if request.args.get("token") != _config["token"]:
        return Response("403 Forbidden", status=403)

    # 引入全局变量
    global request_lock, last_qr_bytes, last_qr_time

    # 获取当前时间戳
    current_time = time.time()

    # 获取缓存持续时间，默认60秒
    cache_duration = _config.get("cache_duration", 60)

    # 如果有正在进行的请求，等待直到请求完成
    while request_lock:
        time.sleep(0.5)
        _logger.info("等待请求完成...")

    # 检查缓存是否有效（存在且未过期）
    if last_qr_bytes and (current_time - last_qr_time) < cache_duration:
        # 返回缓存的二维码图像
        return Response(BytesIO(last_qr_bytes), mimetype="image/png")

    # 设置请求锁，防止并发访问
    request_lock = True
    try:
        # 执行二维码获取操作
        img_io = _qrmai_action()
        img_io.seek(0)  # 将指针移到开始位置

        # 更新缓存数据
        last_qr_bytes = img_io.getvalue()
        last_qr_time = current_time

        # 返回新生成的二维码图像
        return Response(BytesIO(last_qr_bytes), mimetype="image/png")
    finally:
        # 释放请求锁
        request_lock = False


@app.route("/manual_update", methods=["POST"])
@require_auth
def manual_update():
    """手动更新的路由"""
    try:
        # 导入updater模块
        import updater

        # 检查是否有新版本并执行更新
        has_update, latest_release = updater.is_new_version_available()

        if has_update and latest_release:
            # 执行更新
            success = updater.check_and_update()

            if success:
                # 更新成功，返回200状态码
                return "", 200
            else:
                # 更新失败
                return jsonify({"error": True, "message": "更新失败"}), 500
        else:
            # 无更新可用，返回204状态码
            return "", 204
    except Exception as e:
        return jsonify({"error": True, "message": f"手动更新时出错: {str(e)}"}), 500
