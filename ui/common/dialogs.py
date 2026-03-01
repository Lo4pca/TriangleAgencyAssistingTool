from PySide6.QtWidgets import QMessageBox, QDialog
def show_info(parent: QDialog, title: str, text: str):
    msg = QMessageBox(parent)
    msg.setWindowTitle(title)
    msg.setText(text)
    msg.setIcon(QMessageBox.Information)
    return msg.open()
#重复内容似乎过多
def show_warning(parent: QDialog, title: str, text: str):
    msg = QMessageBox(parent)
    msg.setWindowTitle(title)
    msg.setText(text)
    msg.setIcon(QMessageBox.Warning)
    return msg.exec()