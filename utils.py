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

import random
import string

import inspect
from maya import OpenMayaUI, cmds

class Chunk(object):

    def __init__(self, name='untitled'):
        self.name = str(name)

    def __enter__(self):
        cmds.undoInfo(openChunk=True, chunkName=self.name)

    def __exit__(self, exc_type, exc_val, exc_tb):
        cmds.undoInfo(closeChunk=True)

def chunk(func):
    def wrapper(*args, **kwargs):
        with Chunk(name=func.__name__):
            return func(*args, **kwargs)

    return wrapper

def get_maya_main_window():
    pointer = OpenMayaUI.MQtUtil.mainWindow()
    return wrapInstance(int(pointer), QMainWindow)


class Seperator(QFrame):

    def __init__(self, orientation=Qt.Horizontal):
        super().__init__()

        if orientation == Qt.Horizontal:
            self.setFrameShape(self.HLine)
        elif orientation == Qt.Vertical:
            self.setFrameShape(self.VLine)
        else:
            raise ValueError(f'Unknown orientation {orientation!r}')

        self.setFrameShadow(self.Plain)


class DockableWidget(QWidget):

    def __init__(self, parent=None):
        if parent is None:
            parent = get_maya_main_window()
        super().__init__(parent)

        self.id = ''.join(random.choice(string.ascii_uppercase) for _ in range(4))

        class_name = self.__class__.__name__
        object_name = f'{class_name}_{self.id}'

        self.setObjectName(object_name)

    @classmethod
    def open_in_workspace(cls, workspace_name=None):
        # widget
        widget = cls()
        widget_pointer = OpenMayaUI.MQtUtil.findControl(widget.objectName())

        # workspace
        if workspace_name is None:
            # create workspace control
            workspace_name = cmds.workspaceControl(
                f'{widget.objectName()}_workspaceControl',
                initialWidth=widget.width(),
                initialHeight=widget.height(),
                label=widget.windowTitle(),
            )

            # ui script
            module_name = inspect.getmodule(widget).__name__
            class_name = widget.__class__.__name__

            command = f'import {module_name}; {module_name}.{class_name}.open_in_workspace({workspace_name!r})'
            command = f'cmds.evalDeferred({command!r}, lowestPriority=True)'

            cmds.workspaceControl(workspace_name, e=True, uiScript=command)

        workspace_control = OpenMayaUI.MQtUtil.findControl(workspace_name)

        # parent widget to workspace control
        OpenMayaUI.MQtUtil.addWidgetToMayaLayout(int(widget_pointer), int(workspace_control))

        return widget
