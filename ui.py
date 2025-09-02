import json

try:
    from PySide2.QtCore import *
    from PySide2.QtWidgets import *
    from PySide2.QtGui import *
    from shiboken2 import *
except:
    from PySide6.QtCore import *
    from PySide6.QtWidgets import *
    from PySide6.QtGui import *
    from shiboken6 import *

from maya import cmds

from .utils import DockableWidget
from .core import create_controller, set_color_on_selected, get_shapes_data, set_shapes_on_selected

__folder__ = os.path.dirname(__file__)

class ShapeButton(QPushButton):

    def __init__(self, name, shapes_data):
        super().__init__()

        self.name = name
        self.shapes_data = shapes_data

        set_shapes_on_selected_func = lambda x: set_shapes_on_selected(self.shapes_data)
        self.clicked.connect(set_shapes_on_selected_func)

        self.reload()

    def reload(self):
        self.setText(self.name)


class ColorButton(QPushButton):

    def __init__(self, color_index=None):
        super().__init__()

        self.color_index = color_index

        set_color_on_selected_func = lambda x: set_color_on_selected(self.color_index)
        self.clicked.connect(set_color_on_selected_func)

        self.reload()

    def reload(self):
        if self.color_index is None:
            self.setText('Reset Color')
        else:
            color_rbg_1 = cmds.colorIndex(self.color_index, q=True)
            color_rbg_255 = [int(x * 255) for x in color_rbg_1]

            color = QColor()
            color.setRgb(*color_rbg_255)

            palette = self.palette()
            palette.setColor(QPalette.ColorRole.Button, color)
            self.setPalette(palette)
            self.update()


class ControllerEditor(DockableWidget):

    def __init__(self):
        super().__init__()

        self.default_shapes_file = os.path.join(__folder__, 'default_shapes.json')
        self.default_shapes_data = dict()

        self.prefs_location = cmds.internalVar(userPrefDir=True)
        self.tool_prefs_location = os.path.join(self.prefs_location, 'controller_editor')
        self.shapes_file = os.path.join(self.tool_prefs_location, 'shapes.json')

        self.setWindowTitle('Controller Editor')

        # color
        colors_layout = QGridLayout()
        colors_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        column = 0
        row = 0
        for index in range(32):
            if index % 8 == 0:
                row += 1
                column = 0
            else:
                column += 1

            color_btn = ColorButton(index)
            colors_layout.addWidget(color_btn, row, column)

        reset_color_btn = ColorButton(None)

        color_layout = QVBoxLayout()
        color_layout.addWidget(reset_color_btn)
        color_layout.addLayout(colors_layout)

        # ctrl
        self.name_line = QLineEdit()
        self.name_line.setPlaceholderText('default')

        self.with_joint_check = QCheckBox()

        create_controller_func = lambda x: create_controller(
            self.name_line.text(),
            self.with_joint_check.isChecked()
        )

        create_btn = QPushButton('Create')
        create_btn.clicked.connect(create_controller_func)

        ctrl_layout = QFormLayout()
        ctrl_layout.addRow('name', self.name_line)
        ctrl_layout.addRow('with joint', self.with_joint_check)

        create_layout = QVBoxLayout()
        create_layout.addLayout(ctrl_layout)
        create_layout.addWidget(create_btn, alignment=Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignRight)

        # shape
        save_shape_btn = QPushButton('save')
        save_shape_btn.clicked.connect(self.save_selected_shapes)

        self.shape_name_line = QLineEdit()
        self.shape_name_line.setPlaceholderText('default')

        shape_btn_layout = QHBoxLayout()
        shape_btn_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
        shape_btn_layout.addWidget(self.shape_name_line)
        shape_btn_layout.addWidget(save_shape_btn)

        self.shapes_layout = QGridLayout()

        shape_layout = QVBoxLayout()
        shape_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        shape_layout.addLayout(self.shapes_layout)
        shape_layout.addStretch()
        shape_layout.addLayout(shape_btn_layout)

        # tabs
        tabs = {
            "create": create_layout,
            "color": color_layout,
            "shape": shape_layout
        }

        tab = QTabWidget()
        for name, layout in tabs.items():
            widget = QWidget()
            widget.setLayout(layout)

            tab.addTab(widget, name)

        # main layout
        main_layout = QVBoxLayout(self)
        main_layout.addWidget(tab)

        self.reload()

    def reload(self):

        with open(self.default_shapes_file, 'r') as f:
            self.default_shapes_data = json.load(f)

        self.reload_shapes_tab()

    def reload_shapes_tab(self):
        shapes_data = self.get_shapes_data_from_file()

        escape_count = 0
        while self.shapes_layout.count():
            if escape_count > 500:
                cmds.warning('Escape happened')
                break

            item = self.shapes_layout.takeAt(0)

            widget = item.widget()
            widget.deleteLater()

            escape_count += 1

        column = 0
        row = 0
        for index, (name, data) in enumerate(shapes_data.items()):
            if index % 3 == 0:
                row += 1
                column = 0
            else:
                column += 1

            shape_button = ShapeButton(name, data)
            self.shapes_layout.addWidget(shape_button, row, column)

    def get_shapes_data_from_file(self):
        if not os.path.isfile(self.shapes_file):
            return self.default_shapes_data

        with open(self.shapes_file, 'r') as f:
            return json.load(f)

    def save_shapes_data_in_file(self, name, data):
        shapes_data = self.get_shapes_data_from_file()
        shapes_data[name] = data

        shapes_file_location = os.path.dirname(self.shapes_file)
        if not os.path.isdir(shapes_file_location):
            os.mkdir(shapes_file_location)

        with open(self.shapes_file, 'w') as f:
            json.dump(shapes_data, f, indent=4)

    def save_selected_shapes(self):
        selection = cmds.ls(sl=True, type='transform')

        if len(selection) != 1:
            raise Exception(f'You should select exactly one transform. Got {len(selection)}')

        shape_name = self.shape_name_line.text() or self.shape_name_line.placeholderText()

        data = get_shapes_data(selection[0])
        self.save_shapes_data_in_file(shape_name, data)

        self.reload_shapes_tab()


def open_controller_editor():
    ControllerEditor.open_in_workspace()