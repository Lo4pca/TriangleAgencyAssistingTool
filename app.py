import sys
from PySide6.QtWidgets import QApplication

from core.config_manager import ConfigManager
from ui.startup.role_select import RoleSelectDialog
from ui.startup.game_select import GameSelectDialog
from ui.main.pl_window import PLMainWindow

def main() -> None:
    """应用程序的主入口点，管理身份与游戏状态"""
    app = QApplication(sys.argv)
    config_mgr = ConfigManager()

    while True:
        role = config_mgr.get_role()
        
        # 1. 身份选择阶段
        if not role:
            role_dialog = RoleSelectDialog()
            if role_dialog.exec():
                role = role_dialog.selected_role
                config_mgr.set_role(role)
            else:
                sys.exit(0)

        # 2. 游戏选择阶段
        game_dialog = GameSelectDialog(role)
        result = game_dialog.exec()
        
        if result == 0: 
            # 用户点击了“返回切换身份”
            config_mgr.set_role(None)
            continue
            
        game_name = game_dialog.selected_game
        if not game_name:
            continue

        # 3. 启动对应主窗口
        main_window = None
        if role == "PL":
            main_window = PLMainWindow(game_name)
        elif role == "GM":
            from ui.main.gm_window import GMMainWindow
            main_window = GMMainWindow(game_name)
        
        # 进入 Qt 事件循环
        if main_window:
            main_window.show()
            app.exec()
            sys.exit(0) 

if __name__ == "__main__":
    main()