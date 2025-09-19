from maya import cmds
from maya.api import OpenMaya

from .utils import chunk, hold_selection, get_mirror_name, get_mirror_matrix


@chunk
def create_controller(name, with_joint=True, lock_attrs=None, suffix='_ctl'):

    if not name:
        name = 'default'

    ctl_name = f'{name}{suffix}'

    if cmds.objExists(ctl_name):
        raise Exception(f'Ctl name {ctl_name!r} already exists')

    bfr_name = f'{name}_bfr'

    if cmds.objExists(bfr_name):
        raise Exception(f'Bfr name {bfr_name!r} already exists')

    # selection
    selection = cmds.ls(sl=True, long=True)

    # gizmo
    active_context = cmds.currentCtx()
    if active_context == 'RotateSuperContext':
        position = cmds.manipRotateContext('Rotate', position=True, q=True)
    elif active_context == 'moveSuperContext':
        position = cmds.manipMoveContext('Move', position=True, q=True)
    elif active_context == 'scaleSuperContext':
        position = cmds.manipScaleContext('Scale', position=True, q=True)
    else:
        cmds.warning(f'Unable to find position for context {active_context!r}')
        position = None

    if not position:
        position = 0, 0, 0

    # ctrl
    bfr = cmds.group(world=True, empty=True, name=bfr_name)
    ctl, = cmds.circle(constructionHistory=False, name=ctl_name, normal=(1, 0, 0))

    ctl_shape, = cmds.listRelatives(ctl, shapes=True, type='nurbsCurve', fullPath=True)
    cmds.setAttr(f'{ctl_shape}.overrideEnabled', True)
    cmds.setAttr(f'{ctl_shape}.overrideColor', 17)

    cmds.parent(ctl, bfr)

    # joint
    if with_joint:
        cmds.select(ctl)
        cmds.joint(name=f'{name}_jnt')

    # snap parent
    if selection:
        reference = selection[0]
        reference_is_component = '.' in reference

        if reference_is_component:
            cmds.xform(bfr, translation=position, worldSpace=True)
        else:
            cmds.matchTransform(bfr, reference, position=True, rotation=True, scale=False)

    # lock attrs
    if lock_attrs:
        for attr in lock_attrs:
            plug = f'{ctl}.{attr}'
            cmds.setAttr(plug, lock=True, keyable=False)

    cmds.select(bfr)

@chunk
@hold_selection
def transform_shapes(ctrl, rotation=None, scale=None):
    ctrl_shapes = cmds.listRelatives(ctrl, shapes=True, type='nurbsCurve', fullPath=True) or list()

    for ctrl_shape in ctrl_shapes:
        ctrl_cv_plug = f'{ctrl_shape}.cv[*]'
        cmds.select(ctrl_cv_plug)

        if rotation:
            cmds.rotate(
                *rotation,
                relative=True,
                objectCenterPivot=True,
                objectSpace=True,
            )

        if scale:
            cmds.scale(
                *scale,
                relative=True,
                objectCenterPivot=True,
                objectSpace=True,
            )

@chunk
def transform_selected_shapes(rotation=None, scale=None):
    selection = cmds.ls(sl=True, type='transform', long=True)

    for transform in selection:
        transform_shapes(transform, rotation, scale)

@chunk
def replace_shapes_on_selected():
    selection = cmds.ls(sl=True, type='transform', long=True)

    if len(selection) < 2:
        raise Exception(f'Selection ust contain at least two controllers. Got {len(selection)}')

    source = selection[0]
    destinations = selection[1:]

    shapes_data = get_shapes_data(source)
    for destination in destinations:
        set_shapes_data(destination, shapes_data)

@chunk
def set_color_on_selected(color_index):
    selection = cmds.ls(sl=True, long=True)

    if not selection:
        return

    for node in selection:
        set_color(node, color_index)

@chunk
def select_color(color_index):
    curves = cmds.ls(type='nurbsCurve', long=True)

    override_ = color_index is not None

    to_select = list()
    for curve in curves:
        curve_override = cmds.getAttr(f'{curve}.overrideEnabled')
        curve_color_index = cmds.getAttr(f'{curve}.overrideColor')

        if curve_override == override_ and curve_color_index == color_index:
            transform, = cmds.listRelatives(curve, parent=True, fullPath=True)
            to_select.append(transform)

    cmds.select(to_select)

@chunk
def set_color(node, color_index):
    if cmds.objectType(node, isAType='nurbsCurve'):
        shapes = [node]
    else:
        shapes = cmds.listRelatives(node, shapes=True, type='nurbsCurve', fullPath=True)

    if not shapes:
        cmds.warning(f'No shape of type \'nurbsCurve\' found for node {node!r}')
        return

    for shape in shapes:
        if color_index is None:
            cmds.setAttr(f'{shape}.overrideEnabled', False)
            cmds.setAttr(f'{shape}.overrideColor', 0)
        else:
            cmds.setAttr(f'{shape}.overrideEnabled', True)
            cmds.setAttr(f'{shape}.overrideColor', color_index)

@chunk
@hold_selection
def get_shapes_data(transform):
    shapes = cmds.listRelatives(transform, shapes=True, type='nurbsCurve', fullPath=True)

    if not shapes:
        raise Exception('No shapes found to be saved')

    all_data = list()
    for shape in shapes:
        # form
        form = cmds.getAttr(f'{shape}.form')
        points = cmds.getAttr(f'{shape}.cv[*]')
        degree = cmds.getAttr(f'{shape}.degree')

        # knots
        curve_info = cmds.createNode('curveInfo')
        cmds.connectAttr(f'{shape}.local', f'{curve_info}.inputCurve')

        knots, = cmds.getAttr(f'{curve_info}.knots')

        cmds.delete(curve_info)

        # data
        data = dict()
        data['degree'] = degree
        data['form'] = form
        data['point'] = points
        data['knot'] = knots

        all_data.append(data)

    return all_data

@chunk
def get_shapes_data_on_selected():
    selection = cmds.ls(sl=True, type='transform', long=True)

    if not selection:
        raise Exception('No transform selected')

    transform = selection[0]
    return get_shapes_data(transform)

@chunk
def set_shapes_data_on_selected(shapes_data):
    selection = cmds.ls(sl=True, type='transform', long=True)

    for transform in selection:
        set_shapes_data(transform, shapes_data)

    cmds.select(selection)

@chunk
@hold_selection
def set_shapes_data(ctrl, shapes_data):
    # create
    new_curves = list()
    for shape_data in shapes_data:
        periodic = shape_data['form'] > 0
        points = shape_data['point'].copy()
        degree = shape_data['degree']
        knots = shape_data['knot']

        if periodic:
            for index in range(degree):
                points.append(points[index])

        curve = cmds.curve(
            periodic=periodic,
            point=points,
            degree=degree,
            knot=knots,
        )
        new_curves.append(curve)

    # remove
    old_shapes = cmds.listRelatives(ctrl, shapes=True, type='nurbsCurve', fullPath=True)
    old_colors = list()
    if old_shapes:
        for old_shape in old_shapes:
            if cmds.getAttr(f'{old_shape}.overrideEnabled'):
                old_color = cmds.getAttr(f'{old_shape}.overrideColor')
            else:
                old_color = None
            old_colors.append(old_color)

            cmds.delete(old_shape)

    # replace
    for index, new_curve in enumerate(new_curves):
        new_shape, = cmds.listRelatives(new_curve, shapes=True, type='nurbsCurve', fullPath=True)

        ctrl_name = ctrl.split('|')[-1]
        new_shape_name = f'{ctrl_name}Shape'
        if index > 0:
            new_shape_name = f'{new_shape_name}{index}'

        new_shape = cmds.rename(new_shape, new_shape_name)

        if index < len(old_colors):
            old_color = old_colors[index]
            set_color(new_shape, old_color)

        cmds.parent(new_shape, ctrl, relative=True, shape=True)

        cmds.delete(new_curve)


def get_all_ctrls(suffix):
    ctrls = list()

    for transform in cmds.ls(type='transform'):
        if not transform.endswith(suffix):
            continue

        shapes = cmds.listRelatives(transform, shapes=True, type='nurbsCurve')

        if not shapes:
            continue

        ctrls.append(transform)

    return ctrls


@chunk
def select_all_ctrls(suffix):
    cmds.select(get_all_ctrls(suffix))

@chunk
def reset_all_ctrls(suffix):
    ctrls = get_all_ctrls(suffix)

    for ctrl in ctrls:
        reset_transform(ctrl)

@chunk
def reset_selected_transforms():
    selection = cmds.ls(sl=True, type='transform')

    for transform in selection:
        reset_transform(transform)

@chunk
def reset_transform(transform):
    user_attrs = cmds.listAttr(transform, userDefined=True) or list()
    trs_attrs = [
        'tx', 'ty', 'tz',
        'rx', 'ry', 'rz',
        'sx', 'sy', 'sz',
    ]

    for attr in trs_attrs + user_attrs:
        plug = f'{transform}.{attr}'

        # default value
        default_values = cmds.attributeQuery(attr, node=transform, listDefault=True)

        if default_values is None:
            continue

        # set attr
        try:
            cmds.setAttr(plug, *default_values)
        except Exception as e:
            cmds.warning(e)

@chunk
def duplicate_mirror_transform(transform):
    # side
    if '_L' in transform:
        source_side = '_L'
        destination_side = '_R'
    elif '_R' in transform:
        source_side = '_R'
        destination_side = '_L'
    else:
        source_side = None
        destination_side = None

    if not source_side:
        raise Exception(f'Transform {transform!r} is not sided transform')

    # matrix
    transform_matrix = cmds.xform(transform, q=True, matrix=True, worldSpace=True)
    mirror_matrix = get_mirror_matrix(transform_matrix)

    # mirror
    transform_copies = cmds.duplicate(transform, renameChildren=True)
    cmds.xform(transform_copies[0], matrix=mirror_matrix, worldSpace=True)

    # rename
    for trs in transform_copies:
        trs_new_name = trs.replace(source_side, destination_side)[:-1]
        cmds.rename(trs, trs_new_name)

@chunk
def duplicate_mirror_selected_transforms():
    selection = cmds.ls(sl=True, type='transform')

    for transform in selection:
        duplicate_mirror_transform(transform)

@chunk
def select_mirror():
    selection = cmds.ls(sl=True)

    mirror_selection = list()
    for item in selection:
        mirror_item = get_mirror_name(item) or item

        if not cmds.objExists(mirror_item):
            continue

        mirror_selection.append(mirror_item)

    cmds.select(mirror_selection)

@chunk
def add_mirror():
    selection = cmds.ls(sl=True)

    mirror_selection = list()
    for item in selection:
        mirror_item = get_mirror_name(item)

        if mirror_item is None or not cmds.objExists(mirror_item):
            continue

        mirror_selection.append(mirror_item)

    cmds.select(mirror_selection, add=True)

@chunk
def mirror_posing(transform):
    # side
    mirror_transform = get_mirror_name(transform)

    if mirror_transform is None or not cmds.objExists(mirror_transform):
        raise Exception(f'Transform {transform!r} has no mirror')

    # matrix
    matrix = cmds.xform(transform, q=True, matrix=True, worldSpace=True)
    mirror_matrix = get_mirror_matrix(matrix)

    cmds.xform(mirror_transform, matrix=mirror_matrix, worldSpace=True)

@chunk
def mirror_posing_on_selected():
    selection = cmds.ls(sl=True, type='transform')

    for transform in selection:
        mirror_posing(transform)
