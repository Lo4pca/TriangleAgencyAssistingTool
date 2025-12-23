GLOBAL_STYLE_SHEET = """
    QDialog {
        background-color: #FFFFFF;
    }
    QLabel {
        color: #333333;
    }
    QLineEdit, QComboBox, QSpinBox {
        border: 1px solid #CCCCCC;
        padding: 4px;
        border-radius: 2px;
        min-height: 20px;
        color: #333333;
        background-color: #FFFFFF;
    }
    QComboBox QAbstractItemView {
        background-color: #FFFFFF;
        color: #333333;
        selection-background-color: #DDDDDD; 
        selection-color: #000000;
        border: 1px solid #CCCCCC;
    }
    .UnderlineInput {
        border: none;
        border-bottom: 2px solid #CCCCCC;
        background: transparent;
        border-radius: 0px;
        color: #333333;
        padding-bottom: 2px;
    }
    .HeaderLabel {
        font-size: 14pt;
        font-weight: bold;
    }
    .LabelA { color: #0055AA; font-weight: bold; font-size: 14pt; } 
    .LabelR { color: #E6B422; font-weight: bold; font-size: 14pt; } 
    .LabelC { color: #C41E3A; font-weight: bold; font-size: 14pt; } 
    
    .StatLabelRed { color: #C41E3A; font-size: 12pt; }
    
    .BlockHeader { font-weight: bold; font-size: 11pt; }
    .HeaderYellow { color: #E6B422; }
    .HeaderRed { color: #C41E3A; }
    
    .BlockDesc { 
        color: #999999; 
        margin-left: 15px; 
        font-size: 9pt;
    }
    
    /* 动态内容标题 */
    .BlockValueTitle {
        color: #000000;
        margin-left: 15px;
        font-size: 10pt;
        font-weight: bold;
        margin-top: 2px;
    }
    
    /* 动态内容描述 */
    .BlockValueDesc {
        color: #555555;
        margin-left: 15px;
        font-size: 9pt;
        font-style: italic;
        margin-bottom: 10px;
    }

    .QualityMainHeader {
        font-size: 20pt;
        font-weight: bold;
    }
    .QualityName {
        font-size: 11pt;
    }

    /* === 轨道复选框样式 === */
    QCheckBox.TrackBox {
        spacing: 5px;
    }
    QCheckBox.TrackBox::indicator {
        width: 18px;
        height: 18px;
        border: 2px solid #333333;
        border-radius: 2px;
        background-color: #FFFFFF;
    }
    QCheckBox.TrackBox::indicator:checked {
        background-color: #333333;
        image: none;
    }
    QCheckBox.TrackBox::indicator:hover {
        border-color: #888888;
    }
    
    /* 轨道标题 */
    .TrackName {
        font-size: 11pt;
        font-weight: bold;
        color: #000000;
    }
    /* 轨道描述 */
    .TrackDesc {
        font-size: 8pt;
        color: #666666;
        margin-bottom: 5px;
    }

    .TrackSectionTitle { font-size: 14pt; font-weight: bold; margin-top: 10px;}
    .TrackDescBox { border: 1px solid #CCCCCC; border-radius: 5px; padding: 5px; background-color: #F9F9F9; }
    .TrackRuleText { font-size: 9pt; color: #666666; }
    
    /* 自定义格子按钮 */
    QPushButton.TrackNode {
        border: 1px solid #AAAAAA;
        border-radius: 3px;
        background-color: #F0F0F0;
        font-size: 8pt;
        font-weight: bold;
        color: #333333;
    }
    /* 状态1: 标记 */
    QPushButton.TrackNode[state="1"] {
        background-color: #333333;
        color: #FFFFFF;
        border-color: #000000;
    }
    /* 状态2: 划掉 */
    QPushButton.TrackNode[state="2"] {
        background-color: #DDDDDD;
        color: #AAAAAA;
        text-decoration: line-through;
        border-style: dashed;
    }

    QTabBar::tab {
        color: black;
        background: #f0f0f0;
    }

    QTabBar::tab:selected {
        color: white;
        background: #3a7afe;
    }
"""