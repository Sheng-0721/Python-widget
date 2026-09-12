"""
Windows 桌面美化小组件
功能：隐藏快捷方式箭头、恢复Win10右键菜单、桌面美化软件导航
依赖：pip install customtkinter
运行：以管理员身份运行 python desktop_beautify.py
"""

import winreg
import sys
import platform
import subprocess
import webbrowser
import customtkinter as ctk
from tkinter import messagebox

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


# ==================== 注册表操作模块 ====================

class RegistryManager:
    """封装所有注册表读写操作，每个方法返回 (成功: bool, 消息: str)"""

    @staticmethod
    def _admin_check():
        """检查是否具有管理员权限"""
        try:
            import ctypes
            return ctypes.windll.shell32.IsUserAnAdmin() != 0
        except Exception:
            return False

    @staticmethod
    def get_windows_version():
        """获取Windows主版本号：10 或 11"""
        try:
            ver = platform.version()
            build = int(ver.split('.')[-1])
            return 11 if build >= 22000 else 10
        except Exception:
            return 0

    # ---------- 功能1：隐藏/显示快捷方式箭头 ----------

    @staticmethod
    def toggle_shortcut_arrow(hide: bool):
        """
        隐藏或显示桌面快捷方式右下角的小箭头。
        原理：在 HKCU\\...\\Shell Icons 下创建/删除字符串值 29，
        将其指向一个无箭头的图标资源；HKCU 路径无需管理员权限。
        """
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Explorer\Shell Icons"
        try:
            # 打开（或创建）目标键
            key = winreg.CreateKeyEx(
                winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE
            )
            if hide:
                # 将 29 号图标指向 imageres.dll 中的空白图标
                # imageres.dll,-1010 是一个透明图标资源，等价于“无箭头”
                winreg.SetValueEx(
                    key, "29", 0, winreg.REG_SZ,
                    r"%systemroot%\system32\imageres.dll,-1010"
                )
                msg = "快捷方式箭头已隐藏，请刷新桌面或重启资源管理器生效。"
            else:
                try:
                    winreg.DeleteValue(key, "29")
                except FileNotFoundError:
                    pass
                msg = "快捷方式箭头已恢复。"
            winreg.CloseKey(key)
            # 刷新资源管理器使更改立即生效
            RegistryManager._refresh_explorer()
            return True, msg
        except PermissionError:
            return False, "权限不足，请以管理员身份运行本程序。"
        except Exception as e:
            return False, f"操作失败：{e}"

    @staticmethod
    def is_shortcut_arrow_hidden():
        """检查当前是否已隐藏箭头"""
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Explorer\Shell Icons"
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_READ)
            value, _ = winreg.QueryValueEx(key, "29")
            winreg.CloseKey(key)
            return bool(value)
        except Exception:
            return False

    # ---------- 功能2：Win11 恢复 Win10 右键菜单 ----------

    @staticmethod
    def toggle_legacy_context_menu(enable: bool):
        """
        在 Win11 上启用/禁用 Win10 风格右键菜单。
        原理：创建/删除 CLSID {86ca1aa0-34aa-4e8b-a509-50c905bae2a2}
        的 InprocServer32 空值键，强制资源管理器加载旧版菜单。
        """
        clsid_path = (
            r"Software\Classes\CLSID"
            r"\{86ca1aa0-34aa-4e8b-a509-50c905bae2a2}\InprocServer32"
        )
        try:
            if enable:
                # 创建键并将默认值设为空字符串
                key = winreg.CreateKeyEx(
                    winreg.HKEY_CURRENT_USER, clsid_path, 0, winreg.KEY_SET_VALUE
                )
                winreg.SetValueEx(key, "", 0, winreg.REG_SZ, "")
                winreg.CloseKey(key)
                msg = "已启用 Win10 风格右键菜单，正在重启资源管理器..."
            else:
                # 递归删除整个 CLSID 键
                RegistryManager._delete_key_recursive(
                    winreg.HKEY_CURRENT_USER,
                    r"Software\Classes\CLSID"
                    r"\{86ca1aa0-34aa-4e8b-a509-50c905bae2a2}"
                )
                msg = "已恢复 Win11 新版右键菜单，正在重启资源管理器..."

            # 重启资源管理器使更改生效
            RegistryManager._restart_explorer()
            return True, msg
        except PermissionError:
            return False, "权限不足，请以管理员身份运行本程序。"
        except Exception as e:
            return False, f"操作失败：{e}"

    @staticmethod
    def is_legacy_menu_enabled():
        """检查 Win10 右键菜单是否已启用"""
        clsid_path = (
            r"Software\Classes\CLSID"
            r"\{86ca1aa0-34aa-4e8b-a509-50c905bae2a2}\InprocServer32"
        )
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, clsid_path, 0, winreg.KEY_READ)
            winreg.CloseKey(key)
            return True
        except FileNotFoundError:
            return False
        except Exception:
            return False

    # ---------- 内部工具方法 ----------

    @staticmethod
    def _delete_key_recursive(root, subkey):
        """递归删除注册表键及其所有子键"""
        try:
            key = winreg.OpenKey(root, subkey, 0, winreg.KEY_ALL_ACCESS)
            while True:
                try:
                    child = winreg.EnumKey(key, 0)
                    RegistryManager._delete_key_recursive(root, f"{subkey}\\{child}")
                except OSError:
                    break
            winreg.CloseKey(key)
            winreg.DeleteKey(root, subkey)
        except FileNotFoundError:
            pass

    @staticmethod
    def _refresh_explorer():
        """刷新资源管理器（不重启进程）"""
        try:
            subprocess.run(
                ["ie4uinit.exe", "-show"],
                capture_output=True, timeout=5
            )
        except Exception:
            pass

    @staticmethod
    def _restart_explorer():
        """重启资源管理器进程"""
        try:
            subprocess.run(
                ["taskkill", "/F", "/IM", "explorer.exe"],
                capture_output=True, timeout=5
            )
            subprocess.Popen(["explorer.exe"])
        except Exception:
            pass


# ==================== 美化软件数据 ====================

BEAUTIFY_SOFTWARE = [
    {
        "name": "TranslucentTB",
        "desc": "任务栏透明/毛玻璃效果，轻量高效",
        "url": "https://github.com/TranslucentTB/TranslucentTB",
    },
    {
        "name": "Rainmeter",
        "desc": "桌面小部件与皮肤引擎，极客美化首选",
        "url": "https://www.rainmeter.net/",
    },
    {
        "name": "Lively Wallpaper",
        "desc": "开源动态壁纸，支持视频/网页/GIF壁纸",
        "url": "https://www.rocksdanister.com/lively/",
    },
    {
        "name": "RoundedTB",
        "desc": "任务栏圆角、边距与分段自定义",
        "url": "https://github.com/RoundedTB/RoundedTB",
    },
    {
        "name": "ExplorerPatcher",
        "desc": "恢复 Win10 开始菜单、任务栏与右键菜单",
        "url": "https://github.com/valinet/ExplorerPatcher",
    },
    {
        "name": "StartAllBack",
        "desc": "Win11 开始菜单/任务栏经典化（付费）",
        "url": "https://www.startallback.com/",
    },
    {
        "name": "Classic Shell",
        "desc": "经典开始菜单替代方案",
        "url": "http://www.classicshell.net/",
    },
    {
        "name": "MyDockFinder",
        "desc": "仿 macOS Dock 与顶部菜单栏",
        "url": "https://www.mydockfinder.com/",
    },
    {
        "name": "致美化",
        "desc": "中文主题/美化资源综合站",
        "url": "https://zhutix.com/",
    },
    {
        "name": "WindowBlinds",
        "desc": "Stardock 系统主题美化（付费）",
        "url": "https://www.stardock.com/products/windowblinds/",
    },
]


# ==================== 主界面 ====================

class BeautifyApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("桌面美化助手")
        self.geometry("520x620")
        self.resizable(False, False)

        # 窗口居中
        self.update_idletasks()
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        x = (sw - 520) // 2
        y = (sh - 620) // 2
        self.geometry(f"520x620+{x}+{y}")

        self._build_ui()
        self._refresh_status()

    # ---------- UI 构建 ----------

    def _build_ui(self):
        # 标题
        title = ctk.CTkLabel(
            self, text="🖥  桌面美化助手",
            font=ctk.CTkFont(size=22, weight="bold")
        )
        title.pack(pady=(24, 4))

        subtitle = ctk.CTkLabel(
            self, text="一键优化 Windows 桌面视觉体验",
            font=ctk.CTkFont(size=12), text_color="gray"
        )
        subtitle.pack(pady=(0, 16))

        # 系统信息
        win_ver = RegistryManager.get_windows_version()
        ver_text = f"当前系统：Windows {win_ver}" if win_ver else "无法检测系统版本"
        self.sys_label = ctk.CTkLabel(
            self, text=ver_text, font=ctk.CTkFont(size=12), text_color="#4A9EFF"
        )
        self.sys_label.pack(pady=(0, 12))

        # ---- 功能卡片区域 ----
        card_frame = ctk.CTkFrame(self, corner_radius=12)
        card_frame.pack(fill="x", padx=24, pady=(0, 12))

        # 卡片1：隐藏快捷方式箭头
        self._build_feature_row(
            card_frame,
            icon="🔗",
            title="隐藏快捷方式箭头",
            desc="移除桌面图标右下角的小箭头",
            btn_text="切换",
            command=self._on_toggle_arrow,
            row=0
        )

        # 卡片2：Win10 右键菜单
        self._build_feature_row(
            card_frame,
            icon="📋",
            title="Win10 风格右键菜单",
            desc="替换 Win11 新版右键菜单为经典样式",
            btn_text="切换",
            command=self._on_toggle_context_menu,
            row=1,
            disabled=(win_ver != 11)
        )

        # ---- 美化软件推荐区域 ----
        soft_frame = ctk.CTkFrame(self, corner_radius=12)
        soft_frame.pack(fill="both", expand=True, padx=24, pady=(0, 16))

        soft_title = ctk.CTkLabel(
            soft_frame, text="  ✨ 推荐美化软件",
            font=ctk.CTkFont(size=14, weight="bold"), anchor="w"
        )
        soft_title.pack(fill="x", padx=12, pady=(10, 6))

        # 滚动区域
        scroll = ctk.CTkScrollableFrame(soft_frame, height=200)
        scroll.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        for sw in BEAUTIFY_SOFTWARE:
            self._build_software_item(scroll, sw)

    def _build_feature_row(self, parent, icon, title, desc, btn_text,
                           command, row, disabled=False):
        """构建单个功能卡片行"""
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.pack(fill="x", padx=16, pady=8)

        left = ctk.CTkFrame(frame, fg_color="transparent")
        left.pack(side="left", fill="x", expand=True)

        ctk.CTkLabel(
            left, text=f"{icon}  {title}",
            font=ctk.CTkFont(size=14, weight="bold"), anchor="w"
        ).pack(anchor="w")

        ctk.CTkLabel(
            left, text=desc,
            font=ctk.CTkFont(size=11), text_color="gray", anchor="w"
        ).pack(anchor="w")

        btn = ctk.CTkButton(
            frame, text=btn_text, width=70, height=32,
            command=command,
            state="disabled" if disabled else "normal"
        )
        btn.pack(side="right")

        if disabled:
            ctk.CTkLabel(
                left, text="（仅 Win11 可用）",
                font=ctk.CTkFont(size=10), text_color="#FF6B6B", anchor="w"
            ).pack(anchor="w")

    def _build_software_item(self, parent, sw):
        """构建单条美化软件信息"""
        item = ctk.CTkFrame(parent, corner_radius=8, fg_color=("#2B2B2B", "#1E1E1E"))
        item.pack(fill="x", pady=3, padx=4)

        left = ctk.CTkFrame(item, fg_color="transparent")
        left.pack(side="left", fill="x", expand=True, padx=10, pady=6)

        ctk.CTkLabel(
            left, text=sw["name"],
            font=ctk.CTkFont(size=13, weight="bold"), anchor="w"
        ).pack(anchor="w")

        ctk.CTkLabel(
            left, text=sw["desc"],
            font=ctk.CTkFont(size=10), text_color="gray", anchor="w"
        ).pack(anchor="w")

        ctk.CTkButton(
            item, text="官网", width=52, height=28,
            fg_color="#3A7BD5", hover_color="#2E6BC0",
            command=lambda u=sw["url"]: webbrowser.open(u)
        ).pack(side="right", padx=8)

    # ---------- 事件处理 ----------

    def _on_toggle_arrow(self):
        currently_hidden = RegistryManager.is_shortcut_arrow_hidden()
        hide = not currently_hidden  # 当前隐藏则恢复，反之则隐藏

        success, msg = RegistryManager.toggle_shortcut_arrow(hide)
        if success:
            self._refresh_status()
            messagebox.showinfo("操作成功", msg)
        else:
            messagebox.showerror("操作失败", msg)

    def _on_toggle_context_menu(self):
        currently = RegistryManager.is_legacy_menu_enabled()
        enable = not currently

        success, msg = RegistryManager.toggle_legacy_context_menu(enable)
        if success:
            self._refresh_status()
            messagebox.showinfo("操作成功", msg)
        else:
            messagebox.showerror("操作失败", msg)

    def _refresh_status(self):
        """刷新界面上的状态显示（通过标题栏提示）"""
        arrow_hidden = RegistryManager.is_shortcut_arrow_hidden()
        legacy = RegistryManager.is_legacy_menu_enabled()

        status_parts = []
        if arrow_hidden:
            status_parts.append("箭头已隐藏")
        if legacy:
            status_parts.append("经典右键菜单")
        if status_parts:
            self.title(f"桌面美化助手  [{' | '.join(status_parts)}]")
        else:
            self.title("桌面美化助手")


# ==================== 入口 ====================

if __name__ == "__main__":
    # 检查是否为 Windows 系统
    if sys.platform != "win32":
        print("本程序仅支持 Windows 系统。")
        sys.exit(1)

    app = BeautifyApp()
    app.mainloop()