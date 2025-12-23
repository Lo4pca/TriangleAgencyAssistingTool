import sys
from PySide6.QtWidgets import QApplication

from core.config_manager import ConfigManager
from ui.startup.role_select import RoleSelectDialog
from ui.startup.game_select import GameSelectDialog
from ui.main.pl_window import PLMainWindow

def main():
    app = QApplication(sys.argv)
    config_mgr = ConfigManager()

    while True:
        role = config_mgr.get_role()
        
        if not role:
            role_dialog = RoleSelectDialog()
            if role_dialog.exec():
                role = role_dialog.selected_role
                config_mgr.set_role(role)
            else:
                sys.exit(0)

        game_dialog = GameSelectDialog(role)
        result = game_dialog.exec()
        
        if result == 0: 
            config_mgr.set_role(None)
            continue
            
        game_name = game_dialog.selected_game
        if not game_name:
            continue # 理论上 on_confirm 会拦截，但双保险

        # 3. 启动主窗口
        main_window = None
        if role == "PL":
            main_window = PLMainWindow(game_name)
        elif role == "GM":
            from ui.main.gm_window import GMMainWindow
            main_window = GMMainWindow(game_name)
        
        if main_window:
            main_window.show()
            app.exec()
            sys.exit(0) 

if __name__ == "__main__":
    main()