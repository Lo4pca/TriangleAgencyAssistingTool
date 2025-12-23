from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, 
    QLabel, QSpinBox, QScrollArea, QFrame
)
from PySide6.QtCore import Qt
from models.static_data import (
    TRACK_LABELS, COMPETENCY_RANKS_TOP, COMPETENCY_RANKS_BOTTOM
)
from ui.common.widgets import create_label, HLine, TrackNode

class TrackSectionWidget(QWidget):
    def __init__(self, title, title_class, labels_map, state_list, 
                 desc_left, desc_right, ranks_top=None, ranks_bottom=None, 
                 color="#333333", parent=None):
        super().__init__(parent)
        self.nodes = []
        self.init_ui(title, title_class, labels_map, state_list, 
                     desc_left, desc_right, ranks_top, ranks_bottom, color)

    def init_ui(self, title, title_class, labels_map, state_list, 
                desc_left, desc_right, ranks_top, ranks_bottom, color):
        layout = QVBoxLayout(self)
        layout.setSpacing(5)
        layout.setContentsMargins(0, 0, 0, 0)

        # 1. 标题
        title_lbl = QLabel(title)
        title_lbl.setProperty("class", f"TrackSectionTitle {title_class}")
        layout.addWidget(title_lbl)

        # 2. 轨道网格逻辑
        grid_widget = QWidget()
        track_grid = QGridLayout(grid_widget)
        track_grid.setSpacing(5)

        ROWS, COLS = 2, 15
        ROW_OFFSET = 1 if ranks_top else 0

        track_grid.addWidget(self._create_arrow("right", color), ROW_OFFSET, 0)
        track_grid.addWidget(self._create_arrow("left", color), ROW_OFFSET + 1, 0)
        
        if ranks_top:
            for col_idx, rank_name in ranks_top.items():
                lbl = QLabel(rank_name)
                lbl.setStyleSheet("color: #999999; font-size: 8pt;")
                lbl.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignBottom)
                track_grid.addWidget(lbl, 0, col_idx + 1)
                
        if ranks_bottom:
            row_idx = ROW_OFFSET + 2
            for col_idx, rank_name in ranks_bottom.items():
                lbl = QLabel(rank_name)
                lbl.setStyleSheet("color: #999999; font-size: 8pt;")
                lbl.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
                track_grid.addWidget(lbl, row_idx, col_idx + 1)

        for i in range(ROWS * COLS):
            label_text = labels_map.get(i, "")
            node = TrackNode(label_text)
            if i < len(state_list):
                node.set_state(state_list[i])

            is_first_row = (i < COLS)
            if is_first_row:
                r, c = ROW_OFFSET, i + 1
            else:
                r, c = ROW_OFFSET + 1, (2 * COLS) - i 
            
            track_grid.addWidget(node, r, c)
            self.nodes.append(node)

        layout.addWidget(grid_widget)

        # 3. 描述文本区域
        desc_container = self._create_desc_box(desc_left, desc_right)
        layout.addWidget(desc_container)

    def _create_arrow(self, direction, color):
        text = "▶" if direction == "right" else "◀"
        lbl = QLabel(text)
        lbl.setStyleSheet(f"color: {color}; font-size: 20pt; font-weight: bold;")
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setFixedSize(30, 30)
        return lbl

    def _create_desc_box(self, left_text, right_text):
        container = QWidget()
        container.setProperty("class", "TrackDescBox")
        container.setStyleSheet(".TrackDescBox { background-color: #F9F9F9; border-radius: 4px; }")
        layout = QHBoxLayout(container)
        l_lbl = QLabel(left_text)
        l_lbl.setWordWrap(True)
        r_lbl = QLabel(right_text)
        r_lbl.setWordWrap(True)
        
        layout.addWidget(l_lbl, 1)
        v_line = QFrame()
        v_line.setFrameShape(QFrame.VLine)
        v_line.setFrameShadow(QFrame.Sunken)
        layout.addWidget(v_line)
        layout.addWidget(r_lbl, 1)
        return container

    def get_track_data(self):
        return [n.get_state() for n in self.nodes]

class WorkLifeBalanceTab(QWidget):
    def __init__(self, character_data, parent=None):
        super().__init__(parent)
        self.data = character_data
        
        # 初始化为 30 个格子
        self.competency_states = self.data.get("wl_competency_track", [0]*30)
        self.reality_states = self.data.get("wl_reality_track", [0]*30)
        self.anomaly_states = self.data.get("wl_anomaly_track", [0]*30)
        
        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout()
        main_layout.setSpacing(20)
        main_layout.setContentsMargins(20, 20, 20, 20)
        
        # ==========================
        # 1. 顶部计数器区域
        # ==========================
        top_panel = QHBoxLayout()
        top_panel.setAlignment(Qt.AlignmentFlag.AlignTop)
        
        # --- 左侧：规则说明 ---
        rule_layout = QVBoxLayout()
        rule_layout.setSpacing(5)
        
        # 红色规则框
        rule_box = QLabel("每标记一个格子，将另外两个轨道的最末格划掉")
        rule_box.setStyleSheet("""
            background-color: #C41E3A; 
            color: white; 
            padding: 12px; 
            border-radius: 6px; 
            font-weight: bold;
            font-size: 10pt;
        """)
        rule_box.setWordWrap(True)
        rule_layout.addWidget(rule_box)
        
        # 灰色小字
        sub_rule = QLabel("每次任务后用可用时间标记一个格子，然后访问标记对应的受限文档")
        sub_rule.setStyleSheet("color: #666666; font-size: 9pt;")
        sub_rule.setWordWrap(True)
        rule_layout.addWidget(sub_rule)
        
        top_panel.addLayout(rule_layout, 2) # 权重2
        
        # --- 中间：MVP ---
        mvp_layout = QVBoxLayout()
        mvp_layout.setSpacing(5)
        mvp_header = create_label("MVP 获得次数", "HeaderRed", "color: #C41E3A;")
        mvp_header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        mvp_layout.addWidget(mvp_header)
        
        self.mvp_spin = QSpinBox()
        self.mvp_spin.setValue(self.data.get("mvp_count", 0))
        self.mvp_spin.setMinimumHeight(35)
        self.mvp_spin.setStyleSheet("font-size: 14pt; border: 2px solid #C41E3A; border-radius: 4px;")
        self.mvp_spin.setAlignment(Qt.AlignmentFlag.AlignCenter)
        mvp_layout.addWidget(self.mvp_spin)
        
        mvp_desc = QLabel("由嘉奖最多的玩家获得")
        mvp_desc.setStyleSheet("color: #666666; font-size: 8pt;")
        mvp_desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        mvp_layout.addWidget(mvp_desc)
        
        top_panel.addLayout(mvp_layout, 1)
        
        # --- 右侧：观察期 ---
        probation_layout = QVBoxLayout()
        probation_layout.setSpacing(5)
        probation_header = create_label("观察期 获得次数", "HeaderA", "color: #000044; font-weight:bold;")
        probation_header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        probation_layout.addWidget(probation_header)
        
        self.probation_spin = QSpinBox()
        self.probation_spin.setValue(self.data.get("probation_count", 0))
        self.probation_spin.setMinimumHeight(35)
        self.probation_spin.setStyleSheet("font-size: 14pt; border: 2px solid #000044; border-radius: 4px;")
        self.probation_spin.setAlignment(Qt.AlignmentFlag.AlignCenter)
        probation_layout.addWidget(self.probation_spin)
        
        probation_desc = QLabel("由处分最多的玩家获得")
        probation_desc.setStyleSheet("color: #666666; font-size: 8pt;")
        probation_desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        probation_layout.addWidget(probation_desc)
        
        top_panel.addLayout(probation_layout, 1)
        
        main_layout.addLayout(top_panel)
        main_layout.addWidget(HLine())
        
        # ==========================
        # 2. 轨道区域 (滚动)
        # ==========================
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setSpacing(40)
        
        # --- 公司职能轨道 ---
        self.competency_section = TrackSectionWidget(
            title="公 司 职 能 轨 迹",
            title_class="HeaderRed",
            labels_map=TRACK_LABELS["competency"],
            state_list=self.competency_states,
            desc_left="每次标记公司职能，增加一项素质保证的上限1点，最多到9。然后获得3嘉奖",
            desc_right="每次获得MVP时，可标记一个公司职能格子且不需要划掉其他轨迹的格子",
            ranks_top=COMPETENCY_RANKS_TOP,
            ranks_bottom=COMPETENCY_RANKS_BOTTOM,
            color="#C41E3A"
        )
        scroll_layout.addWidget(self.competency_section)

        # --- 现实身份轨道 ---
        self.reality_section = TrackSectionWidget(
            title="现 实 身 份 轨 迹",
            title_class="HeaderYellow",
            labels_map=TRACK_LABELS["reality"],
            state_list=self.reality_states,
            desc_left="每次标记现实身份，可增加一条关系轨迹的一点关系。然后每有一条网络化的关系轨迹可重复增加一次关系",
            desc_right="若你既没获得MVP也没获得观察期，可标记一个现实身份格子且不需要划掉其他轨迹的格子",
            color="#E6B422"
        )
        scroll_layout.addWidget(self.reality_section)

        # --- 异常共鸣轨道 ---
        self.anomaly_section = TrackSectionWidget(
            title="异 常 共 鸣 轨 迹", 
            title_class="LabelA", 
            labels_map=TRACK_LABELS["anomaly"], 
            state_list=self.anomaly_states,
            desc_left="每次标记异常能力，选择一项：\n▶ 练习：将一项异常技能标记上已练习\n▶ 被了解：取消勾选的已练习标记，并从已练习的异常技能里选一个向你的队友提问技能问题。勾选票数最多的那个答案并获得解锁的技能\n(消耗一点时间解锁H4我就告诉你这是什么意思！)",
            desc_right="每次你获得观察期时，可标记一个异常共鸣格子且不需要划掉其他轨迹的格子",
            color="#0055AA"
        )
        scroll_layout.addWidget(self.anomaly_section)
        
        scroll.setWidget(scroll_content)
        main_layout.addWidget(scroll)
        
        self.setLayout(main_layout)

    def get_data(self):
        return {
            "mvp_count": self.mvp_spin.value(),
            "probation_count": self.probation_spin.value(),
            "wl_competency_track": self.competency_section.get_track_data(),
            "wl_reality_track": self.reality_section.get_track_data(),
            "wl_anomaly_track": self.anomaly_section.get_track_data()
        }