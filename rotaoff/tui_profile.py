"""profile 组：配置、字段、扫码登录。"""

import os
import sys

from rotaoff import data, library, output, select, store, tasks, ui
from rotaoff.i18n import help_block, t
from rotaoff.store import RotaOffError


from rotaoff.tui_common import _open_path
from rotaoff.tui_help import _want_help, help_text

def _mask(token) -> str:
    text = str(token or "")
    return f"{text[:6]}…" if len(text) > 6 else text


def show_profiles() -> None:
    users = store.load_users()
    active = store.active_profile_name()
    if not users:
        ui.info("还没有任何配置，用 profile new <名称> 建一个，或直接 login 扫码。")
        return
    rows = []
    for name, profile in users.items():
        verified, key = store.verify_profile(profile)
        rows.append([
            ("* " if name == active else "  ") + name,
            str(profile.get("serverCode") or "-"),
            _mask(profile.get("objectID")),
            _mask(profile.get("sessionToken")),
            t(key, profile.get("locale", "zh-CN")),
        ])
    ui.table(["配置", "服务器", "objectID", "sessionToken", "状态"], rows,
             aligns=["left", "center", "left", "left", "left"])


def cmd_profile(args) -> None:
    if _want_help(args):
        print(help_text("profile"))
        return
    if args[0].lower() in ("show", "list", "ls"):
        show_profiles()
        return
    if args[0].lower() == "login":
        cmd_login(args[1:])
        return

    action = args[0]
    if action == "use" and len(args) >= 2:
        store.set_active_profile(args[1])
        ui.ok(f"当前配置: {args[1]}")
        return
    if action == "new" and len(args) >= 2:
        store.create_profile(args[1])
        store.set_active_profile(args[1])
        ui.ok(f"已新建并切换到配置: {args[1]}")
        return
    if action == "set" and len(args) >= 3:
        key, value = args[1], " ".join(args[2:])
        field, verified, message_key = store.set_profile_field(key, value)
        if verified:
            ui.ok(f"已保存: {field} = {value}")
        else:
            ui.warn(f"已保存: {field} = {value}（还缺: {t(message_key, store.profile_locale())}）")
        return
    ui.warn("用法: profile | profile use <名> | profile new <名> | profile set <字段> <值>")


def cmd_login(args) -> None:
    from rotaeno.api import taptap_auth

    server = (args[0] if args else "cn").lower()
    if server not in store.SERVER_CODES:
        raise RotaOffError(t("unavailable-server-code", server_code=server))

    login = taptap_auth.TapTapLogin(server=server, device_id=store.active_profile_name())
    qrcode = login.get_qrcode(needImage=True)
    ui.info(f"二维码已保存: {qrcode['image']}")
    _open_path(qrcode["image"])
    ui.info("请用 TapTap 在 60 秒内扫码登录…（Ctrl+C 可放弃）")

    try:
        info = login.get_objectid_and_sessiontoken(qrcode_data=qrcode, show_qrcode=False)
    except TimeoutError:
        raise RotaOffError(
            t("login-timed-out-please-retrieve-taptap-login-qrcode-again")
        )

    store.set_profile_field("serverCode", server)
    store.set_profile_field("objectID", info["objectID"])
    _, verified, message_key = store.set_profile_field("sessionToken", info["sessionToken"])
    message = t(message_key, store.profile_locale())
    ui.ok(message) if verified else ui.warn(message)
