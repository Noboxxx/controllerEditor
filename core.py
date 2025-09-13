from maya import cmds

from .utils import chunk

@chunk
def create_controller(name, with_joint=True):

    if not name:
        name = 'default'

    ctl_name = f'{name}_ctl'

    if cmds.objExists(ctl_name):
        raise Exception(f'Ctl name {ctl_name!r} already exists')

    bfr_name = f'{name}_bfr'

    if cmds.objExists(bfr_name):
        raise Exception(f'Bfr name {bfr_name!r} already exists')

    # selection
    selection = cmds.ls(sl=True)

    # gizmo
    active_context = cmds.currentCtx()
    active_context = active_context.replace('SuperContext', '')
    active_context = active_context.title()

    try:
        position = cmds.manipMoveContext(active_context, q=True, p=True)
    except Exception as e:
        cmds.warning(e)
        position = 0, 0, 0

    print(active_context, position)

    # ctrl
    bfr = cmds.group(world=True, empty=True, name=bfr_name)
    ctl = cmds.circle(constructionHistory=False, name=ctl_name, normal=(1, 0, 0))

    ctl_shape, = cmds.listRelatives(ctl, shapes=True, type='nurbsCurve')
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

    cmds.select(bfr)


@chunk
def transform_shapes(ctrl, rotation=None, scale=None):
    held_selection = cmds.ls(sl=True)
    ctrl_shapes = cmds.listRelatives(ctrl, shapes=True, type='nurbsCurve') or list()

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

    cmds.select(held_selection)

@chunk
def transform_selected_shapes(rotation=None, scale=None):
    selection = cmds.ls(sl=True, type='transform')

    for transform in selection:
        transform_shapes(transform, rotation, scale)

@chunk
def replace_shapes_on_selected():
    selection = cmds.ls(sl=True, type='transform')

    if len(selection) < 2:
        raise Exception(f'Selection ust contain at least two controllers. Got {len(selection)}')

    source = selection[0]
    destinations = selection[1:]

    shapes_data = get_shapes_data(source)
    for destination in destinations:
        set_shapes_data(destination, shapes_data)

@chunk
def set_color_on_selected(color_index):
    selection = cmds.ls(sl=True)

    if not selection:
        return

    for node in selection:
        set_color(node, color_index)

@chunk
def select_color(color_index):
    curves = cmds.ls(type='nurbsCurve')

    override_ = color_index is not None

    to_select = list()
    for curve in curves:
        curve_override = cmds.getAttr(f'{curve}.overrideEnabled')
        curve_color_index = cmds.getAttr(f'{curve}.overrideColor')

        if curve_override == override_ and curve_color_index == color_index:
            transform, = cmds.listRelatives(curve, parent=True)
            to_select.append(transform)

    cmds.select(to_select)

@chunk
def set_color(node, color_index):
    if cmds.objectType(node, isAType='nurbsCurve'):
        shapes = [node]
    else:
        shapes = cmds.listRelatives(node, shapes=True, type='nurbsCurve')

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
def get_shapes_data(transform):
    held_selection = cmds.ls(sl=True)

    shapes = cmds.listRelatives(transform, shapes=True, type='nurbsCurve')

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

    cmds.select(held_selection  )
    return all_data

@chunk
def get_shapes_data_on_selected():
    selection = cmds.ls(sl=True, type='transform')

    if not selection:
        raise Exception('No transform selected')

    transform = selection[0]
    return get_shapes_data(transform)

@chunk
def set_shapes_data_on_selected(shapes_data):
    selection = cmds.ls(sl=True, type='transform')

    for transform in selection:
        set_shapes_data(transform, shapes_data)

    cmds.select(selection)

@chunk
def set_shapes_data(ctrl, shapes_data):
    held_selection = cmds.ls(sl=True)

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
    old_shapes = cmds.listRelatives(ctrl, shapes=True, type='nurbsCurve')
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
        new_shape, = cmds.listRelatives(new_curve, shapes=True, type='nurbsCurve')

        new_shape_name = f'{ctrl}Shape'
        if index > 0:
            new_shape_name = f'{new_shape_name}{index}'

        new_shape = cmds.rename(new_shape, new_shape_name)

        if index < len(old_colors):
            old_color = old_colors[index]
            set_color(new_shape, old_color)

        cmds.parent(new_shape, ctrl, relative=True, shape=True)

        cmds.delete(new_curve)

    cmds.select(held_selection)