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
from .core import create_controller, set_color_on_selected, get_shapes_data_on_selected, set_shapes_data_on_selected, \
    replace_shapes_on_selected, select_all_ctrls, transform_selected_shapes, select_color, reset_all_ctrls, \
    reset_selected_transforms, duplicate_mirror_selected_transforms, select_mirror, add_mirror, \
    mirror_posing_on_selected

__folder__ = os.path.dirname(__file__)

class ShapeButton(QPushButton):

    def __init__(self, name, shapes_data):
        super().__init__()

        self.name = name
        self.shapes_data = shapes_data

        set_shapes_on_selected_func = lambda x: set_shapes_data_on_selected(self.shapes_data)
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

    def contextMenuEvent(self, event, /):
        menu = QMenu(self)

        select_action = QAction("Select", self)
        menu.addAction(select_action)

        select_action.triggered.connect(lambda: select_color(self.color_index))

        menu.exec_(event.globalPos())

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


class NameLine(QLineEdit):


    def contextMenuEvent(self, event):
        paste_selected_action = QAction('Paste Selected', self)
        paste_selected_action.triggered.connect(self.paste_selected)

        menu = self.createStandardContextMenu()
        menu.addSeparator()
        menu.addAction(paste_selected_action)

        menu.exec_(event.globalPos())

    def paste_selected(self):
        selection = cmds.ls(sl=True)

        if not selection:
            raise Exception('Nothing currently selected')

        text = selection[0]
        text = text.split('|')[-1]
        self.setText(text)


class ControllerEditor(DockableWidget):

    def __init__(self):
        super().__init__()

        self.copied_shapes = None
        self.ctrl_suffix = '_ctl'

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
        new_range = (
            13, 4, 12, 10, 11, 16, 20, 0,
            14, 23, 27, 26, 7, 28, 19, 31,
            6, 15, 18, 29, 5, 8, 9, 30,
            17, 25, 22, 21, 24, 1, 2, 3,
        )
        for index, color_index in enumerate(new_range):
            if index % 8 == 0:
                row += 1
                column = 0
            else:
                column += 1

            color_btn = ColorButton(color_index)
            colors_layout.addWidget(color_btn, row, column)

        reset_color_btn = ColorButton(None)

        color_layout = QVBoxLayout()
        color_layout.addWidget(reset_color_btn)
        color_layout.addLayout(colors_layout)

        self.name_line = NameLine()
        self.name_line.setPlaceholderText('default')

        self.with_joint_check = QCheckBox()
        self.with_joint_check.setChecked(True)

        def create_controller_func():
            lock_attrs = list()
            for attribute_, attribute_data_ in self.attributes_checks.items():
                if isinstance(attribute_data_, QCheckBox):
                    state = attribute_data_.isChecked()
                    if not state:
                        lock_attrs.append(attribute_)
                else:
                    for axis_, checkbox in attribute_data_.items():
                        state = checkbox.isChecked()
                        if not state:
                            full_attribute = f'{attribute_}{axis_.title()}'
                            lock_attrs.append(full_attribute)

            name = self.name_line.text() or self.name_line.placeholderText()
            with_joint = self.with_joint_check.isChecked()

            create_controller(name, with_joint, lock_attrs, self.ctrl_suffix)

        create_btn = QPushButton('Create')
        create_btn.clicked.connect(create_controller_func)

        create_ctrl_params_layout = QFormLayout()
        create_ctrl_params_layout.addRow('name', self.name_line)
        create_ctrl_params_layout.addRow('with joint', self.with_joint_check)

        self.attributes_checks = dict()

        attributes = {
            'translate': {
                'default': True,
                'vector': True
            },
            'rotate': {
                'default': True,
                'vector': True
            },
            'scale': {
                'default': True,
                'vector': True
            },
            'visibility': {
                'default': False,
                'vector': False
            },
        }

        for attribute, attribute_data in attributes.items():
            self.attributes_checks[attribute] = dict()

            attribute_layout = QHBoxLayout()
            attribute_layout.setContentsMargins(QMargins(0, 0, 0, 0))
            attribute_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)

            vector = attribute_data.get('vector', False)
            default = attribute_data.get('default', False)

            if vector:
                for axis in ('x', 'y', 'z'):
                    attr_check = QCheckBox(axis)
                    attr_check.setChecked(default)

                    self.attributes_checks[attribute][axis] = attr_check

                    attribute_layout.addWidget(attr_check)
            else:
                attr_check = QCheckBox()
                attr_check.setChecked(default)

                self.attributes_checks[attribute] = attr_check

                attribute_layout.addWidget(attr_check)

            w = QWidget()
            w.setLayout(attribute_layout)
            create_ctrl_params_layout.addRow(attribute, w)

        create_ctrl_layout = QVBoxLayout()
        create_ctrl_layout.addLayout(create_ctrl_params_layout)
        create_ctrl_layout.addWidget(create_btn, alignment=Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignRight)

        select_all_ctrls_btn = QPushButton('Select All Ctrls')
        select_all_ctrls_btn.setIcon(QIcon(':aselect.png'))
        def select_all_ctrls_func():
            select_all_ctrls(self.ctrl_suffix)
        select_all_ctrls_btn.clicked.connect(select_all_ctrls_func)

        select_mirror_btn = QPushButton('Select Mirror')
        select_mirror_btn.setIcon(QIcon(':aselect.png'))
        select_mirror_btn.clicked.connect(select_mirror)

        add_mirror_btn = QPushButton('Add Mirror')
        add_mirror_btn.setIcon(QIcon(':aselect.png'))
        add_mirror_btn.clicked.connect(add_mirror)

        reset_all_ctrls_btn = QPushButton('Reset All Ctrls')
        reset_all_ctrls_btn.setIcon(QIcon(':clockwise.png'))
        def reset_all_ctrls_func():
            reset_all_ctrls(self.ctrl_suffix)
        reset_all_ctrls_btn.clicked.connect(reset_all_ctrls_func)

        reset_selected_btn = QPushButton('Reset Selected')
        reset_selected_btn.setIcon(QIcon(':clockwise.png'))
        reset_selected_btn.clicked.connect(reset_selected_transforms)

        duplicate_mirror_btn = QPushButton('Duplicate Mirror')
        duplicate_mirror_btn.setIcon(QIcon(':polyMirrorGeometry.png'))
        duplicate_mirror_btn.clicked.connect(duplicate_mirror_selected_transforms)

        mirror_posing_btn = QPushButton('Mirror Posing')
        mirror_posing_btn.setIcon(QIcon(':polyMirrorGeometry.png'))
        mirror_posing_btn.clicked.connect(mirror_posing_on_selected)

        utils_layout = QGridLayout()
        utils_layout.addWidget(reset_selected_btn, 0, 0)
        utils_layout.addWidget(reset_all_ctrls_btn, 0, 1)
        utils_layout.addWidget(duplicate_mirror_btn, 1, 0)
        utils_layout.addWidget(mirror_posing_btn, 1, 1)
        utils_layout.addWidget(select_all_ctrls_btn, 2, 0)
        utils_layout.addWidget(select_mirror_btn, 3, 0)
        utils_layout.addWidget(add_mirror_btn, 3, 1)

        create_label = QLabel('Create')
        create_label.setStyleSheet('font-weight: bold;')

        utils_label = QLabel('Utils')
        utils_label.setStyleSheet('font-weight: bold;')

        ctrl_layout = QVBoxLayout()
        ctrl_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        ctrl_layout.addWidget(utils_label)
        ctrl_layout.addLayout(utils_layout)
        ctrl_layout.addWidget(create_label)
        ctrl_layout.addLayout(create_ctrl_layout)

        # shape
        def copy_func():
            self.copied_shapes = get_shapes_data_on_selected()
        self.copy_btn = QPushButton('copy')
        self.copy_btn.clicked.connect(copy_func)

        def past_func():
            if not self.copied_shapes:
                raise Exception('Nothing found to be pasted.')
            set_shapes_data_on_selected(self.copied_shapes)
        self.paste_btn = QPushButton('paste')
        self.paste_btn.clicked.connect(past_func)

        scale_up_btn = QPushButton('scale up')
        scale_up_btn.clicked.connect(lambda: transform_selected_shapes(scale=(1.2, 1.2, 1.2)))

        scale_down_btn = QPushButton('scale down')
        scale_down_btn.clicked.connect(lambda: transform_selected_shapes(scale=(.8, .8, .8)))

        rotate_x_btn = QPushButton('rotate X')
        rotate_x_btn.clicked.connect(lambda: transform_selected_shapes(rotation=(45, 0, 0)))

        rotate_y_btn = QPushButton('rotate Y')
        rotate_y_btn.clicked.connect(lambda: transform_selected_shapes(rotation=(0, 45, 0)))

        rotate_z_btn = QPushButton('rotate Z')
        rotate_z_btn.clicked.connect(lambda: transform_selected_shapes(rotation=(0, 0, 45)))

        transform_layout = QGridLayout()
        transform_layout.addWidget(scale_up_btn, 0, 0)
        transform_layout.addWidget(scale_down_btn, 0, 1)
        transform_layout.addWidget(rotate_x_btn, 1, 0)
        transform_layout.addWidget(rotate_y_btn, 1, 1)
        transform_layout.addWidget(rotate_z_btn, 1, 2)

        replace_btn = QPushButton('replace')
        replace_btn.clicked.connect(replace_shapes_on_selected)

        copy_paste_layout = QHBoxLayout()
        copy_paste_layout.addWidget(replace_btn)
        copy_paste_layout.addWidget(self.copy_btn)
        copy_paste_layout.addWidget(self.paste_btn)

        save_shape_btn = QPushButton('save')
        save_shape_btn.clicked.connect(self.save_selected_shapes)

        self.shape_name_line = QLineEdit()
        self.shape_name_line.setPlaceholderText('default')

        shape_save_layout = QHBoxLayout()
        shape_save_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
        shape_save_layout.addWidget(self.shape_name_line)
        shape_save_layout.addWidget(save_shape_btn)

        self.shapes_layout = QGridLayout()

        shape_layout = QVBoxLayout()
        shape_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        shape_layout.addWidget(QLabel('Transform'))
        shape_layout.addLayout(transform_layout)
        shape_layout.addWidget(QLabel('Copy'))
        shape_layout.addLayout(copy_paste_layout)
        shape_layout.addWidget(QLabel('Replace'))
        shape_layout.addLayout(shape_save_layout)
        shape_layout.addLayout(self.shapes_layout)

        # tabs
        tabs = {
            'ctrl': ctrl_layout,
            'color': color_layout,
            'shape': shape_layout
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
        shape_name = self.shape_name_line.text() or self.shape_name_line.placeholderText()
        data = get_shapes_data_on_selected()

        self.save_shapes_data_in_file(shape_name, data)

        self.reload_shapes_tab()


def open_controller_editor():
    ControllerEditor.open_in_workspace()