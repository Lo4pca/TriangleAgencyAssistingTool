from PySide6.QtWidgets import QMessageBox, QWidget
def show_silent_info(parent: QWidget, title: str, text: str):
    msg = QMessageBox(parent)
    msg.setWindowTitle(title)
    msg.setText(text)
    # 使用 NoIcon 避免底层触发系统提示音
    msg.setIcon(QMessageBox.Icon.NoIcon) 
    return msg.open()
#重复内容似乎过多
def show_warning(parent: QWidget, title: str, text: str):
    msg = QMessageBox(parent)
    msg.setWindowTitle(title)
    msg.setText(text)
    msg.setIcon(QMessageBox.Warning)
    return msg.exec()