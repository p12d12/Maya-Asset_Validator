import maya.cmds as cmds
import maya.mel as mel
import os

from PySide6 import QtWidgets, QtCore
from maya import OpenMayaUI as omui
from shiboken6 import wrapInstance


EXPORT_ROOT = "EXPORT_ROOT"
PUBLISH_ROOT = r"D:\개발\TA\MayaAssetValidator\publish"

MESH_PREFIX = "GEO_"

KNOWN_MESH_PREFIXES = {
    MESH_PREFIX
}

TOLERANCE = 0.001

# -----------------------------------------------------------------------------

def get_maya_main_window():
    main_window_ptr = omui.MQtUtil.mainWindow()
    return wrapInstance(
        int(main_window_ptr),
        QtWidgets.QWidget
    )


def get_selected_meshes():
    selected = cmds.ls(selection=True)

    if not selected:
        print("[WARNING] No object selected")
        return []

    mesh_objects = []

    for obj in selected:
        shapes = cmds.listRelatives(
            obj,
            shapes=True,
            noIntermediate=True
        ) or []

        for shape in shapes:
            if cmds.nodeType(shape) == "mesh":
                mesh_objects.append(obj)
                break

    if not mesh_objects:
        print("[WARNING] No mesh selected")

    return mesh_objects


# 浮動小数点の誤差を許容して比較する
def is_close(value, target, tolerance=TOLERANCE):
    return abs(value - target) < tolerance

# -----------------------------------------------------------------------------
# Naming

def get_unique_name(base_name):
    if not cmds.objExists(base_name):
        return base_name

    index = 1

    while True:
        new_name = f"{base_name}_{index:02d}"

        if not cmds.objExists(new_name):
            return new_name

        index += 1


def validate_names():
    selected = get_selected_meshes()

    if not selected:
        return []

    problem_objects = []

    print("=== Naming Validation ===")

    for obj in selected:
        shapes = cmds.listRelatives(obj, shapes=True)

        if not shapes:
            continue

        shape = shapes[0]
        node_type = cmds.nodeType(shape)

        if node_type == "mesh":
            if obj.startswith(MESH_PREFIX):
                print(f"[OK] {obj}")
            else:
                print(f"[ERROR] {obj} - Missing {MESH_PREFIX} prefix")
                problem_objects.append(obj)

    return problem_objects


def fix_names(problem_objects):
    print("=== Fix Names ===")

    for obj in problem_objects:
        clean_name = remove_known_prefix(obj)
        base_name = f"{MESH_PREFIX}{clean_name}"

        new_name = get_unique_name(base_name)

        renamed = cmds.rename(obj, new_name)

        print(f"{obj} -> {renamed}")


# 接頭辞が重なる場合は、長いものを優先する
def remove_known_prefix(name):
    for prefix in sorted(
        KNOWN_MESH_PREFIXES,
        key=len,
        reverse=True
    ):
        if name.startswith(prefix):
            return name[len(prefix):]

    return name

# -----------------------------------------------------------------------------
# Transform

def validate_transforms():
    selected = get_selected_meshes()

    if not selected:
        return []

    transform_issues = []

    print("=== Transform Validation ===")

    for obj in selected:

        scale = cmds.getAttr(f"{obj}.scale")[0]
        rotation = cmds.getAttr(f"{obj}.rotate")[0]

        if all(is_close(v, 1.0) for v in scale):
            print(f"[OK] {obj} Scale")
        else:
            print(f"[ERROR] {obj} Scale: {scale}")
            transform_issues.append((obj, "Scale"))

        if all(is_close(v, 0.0) for v in rotation):
            print(f"[OK] {obj} Rotation")
        else:
            print(f"[ERROR] {obj} Rotation: {rotation}")
            transform_issues.append((obj, "Rotation"))

    return transform_issues


def fix_transforms(transform_issues):
    print("=== Fix Transform ===")

    fixed_objects = []

    for obj, issue_type in transform_issues:
        if obj in fixed_objects:
            continue

        cmds.makeIdentity(
            obj,
            apply=True,
            translate=False,
            rotate=True,
            scale=True
        )

        fixed_objects.append(obj)

        print(f"[FIXED] {obj} Transform")

# -----------------------------------------------------------------------------
# Pivot

# ピボットの基準はワールド座標でのバウンディングボックス底面中央
def validate_pivots():
    selected = get_selected_meshes()

    if not selected:
        return []

    pivot_issues = []

    print("=== Pivot Validation ===")

    for obj in selected:

        bbox = cmds.exactWorldBoundingBox(obj)

        min_x, min_y, min_z = bbox[0], bbox[1], bbox[2]
        max_x, max_y, max_z = bbox[3], bbox[4], bbox[5]

        target_pivot = (
            (min_x + max_x) / 2,
            min_y,
            (min_z + max_z) / 2
        )

        current_pivot = cmds.xform(
            obj,
            query=True,
            worldSpace=True,
            rotatePivot=True
        )

        pivot_ok = all(
            is_close(current, target)
            for current, target in zip(current_pivot, target_pivot)
        )

        if pivot_ok:
            print(f"[OK] {obj} Pivot")

        else:
            print(f"[ERROR] {obj} Pivot")
            print(f"Current: {current_pivot}")
            print(f"Expected: {target_pivot}")

            pivot_issues.append((obj, "Pivot"))

    return pivot_issues


def fix_pivots(pivot_issues):
    print("=== Fix Pivots ===")

    fixed_objects = []

    for obj, issue_type in pivot_issues:
        if obj in fixed_objects:
            continue

        bbox = cmds.exactWorldBoundingBox(obj)

        min_x, min_y, min_z = bbox[0], bbox[1], bbox[2]
        max_x, max_y, max_z = bbox[3], bbox[4], bbox[5]

        target_pivot = (
            (min_x + max_x) / 2,
            min_y,
            (min_z + max_z) / 2
        )

        cmds.xform(
            obj,
            worldSpace=True,
            pivots=target_pivot
        )

        fixed_objects.append(obj)

        print(f"[FIXED] {obj} Pivot")

# -----------------------------------------------------------------------------
# Material / Texture

def validate_materials():
    selected = get_selected_meshes()

    if not selected:
        return []

    material_issues = []

    print("=== Material Validation ===")

    for obj in selected:
        shapes = cmds.listRelatives(obj, shapes=True)

        if not shapes:
            continue

        shape = shapes[0]

        if cmds.nodeType(shape) != "mesh":
            continue

        shading_groups = cmds.listConnections(
            shape,
            type="shadingEngine"
        ) or []

        custom_shading_groups = [
            sg
            for sg in shading_groups
            if sg != "initialShadingGroup"
        ]

        if custom_shading_groups:
            print(f"[OK] {obj} Custom Material Assigned")
        else:
            print(f"[ERROR] {obj} - No custom material")
            material_issues.append((obj, "Material"))

    return material_issues


def validate_textures():
    selected = get_selected_meshes()

    if not selected:
        return []

    texture_issues = []

    print("=== Texture Validation ===")

    for obj in selected:
        shapes = cmds.listRelatives(obj, shapes=True)

        if not shapes:
            continue

        shape = shapes[0]

        if cmds.nodeType(shape) != "mesh":
            continue

        shading_groups = cmds.listConnections(
            shape,
            type="shadingEngine"
        ) or []

        custom_shading_groups = [
            sg
            for sg in shading_groups
            if sg != "initialShadingGroup"
        ]

        file_nodes = []

        for shading_group in custom_shading_groups:
            history = cmds.listHistory(shading_group) or []

            for node in history:
                if cmds.nodeType(node) == "file":
                    file_nodes.append(node)

        if file_nodes:
            print(f"[OK] {obj} Texture: {file_nodes}")
        else:
            print(f"[ERROR] {obj} - No texture connected")
            texture_issues.append((obj, "Texture"))

    return texture_issues

# -----------------------------------------------------------------------------
# Hierarchy

def validate_hierarchy():
    selected = get_selected_meshes()

    if not selected:
        return []

    hierarchy_issues = []

    print("=== Hierarchy Validation ===")

    for obj in selected:
        parent = cmds.listRelatives(
            obj,
            parent=True,
            fullPath=False
        ) or []

        if not parent:
            print(f"[ERROR] {obj} No export root")
            hierarchy_issues.append((obj, "No Export Root"))
        elif parent[0] != EXPORT_ROOT:
            print(
                f"[ERROR] {obj} - Invalid parent: {parent[0]}"
            )
            hierarchy_issues.append((obj, "Invalid Parent"))

        else:
            print(f"[OK] {obj} Hierarchy")

    return hierarchy_issues

# -----------------------------------------------------------------------------
# Export / Publish

def validate_export_ready():
    selected = get_selected_meshes()

    print("=== Export Ready Validation ===")

    if not selected:
        print("[BLOCKED] No mesh selected")
        return False

    naming_issues = validate_names()
    transform_issues = validate_transforms()
    pivot_issues = validate_pivots()
    material_issues = validate_materials()
    texture_issues = validate_textures()
    hierarchy_issues = validate_hierarchy()

    all_issues = {
        "Naming": naming_issues,
        "Transform": transform_issues,
        "Pivot": pivot_issues,
        "Material": material_issues,
        "Texture": texture_issues,
        "Hierarchy": hierarchy_issues,
    }

    issue_count = sum(
        len(issues)
        for issues in all_issues.values()
    )

    print("=== Export Summary ===")

    for category, issues in all_issues.items():
        print(f"{category}: {len(issues)} issue(s)")

    if issue_count == 0:
        print("[READY] Asset is ready for export")
        return True

    print(f"[BLOCKED] {issue_count} issue(s) must be fixed")
    return False


def export_fbx():
    selected = get_selected_meshes()

    if not selected:
        print("[BLOCKED] No mesh selected")
        return False

    if not validate_export_ready():
        print("[BLOCKED] FBX export cancelled")
        return False

    export_path = cmds.fileDialog2(
        fileMode=0,
        caption="Export FBX",
        fileFilter="FBX Files (*.fbx)"
    )

    if not export_path:
        print("[CANCELLED] Export cancelled by user")
        return False

    path = export_path[0].replace("\\", "/")

    return run_fbx_export(path, selected)


def get_publish_path():
    selected = get_selected_meshes()

    if not selected:
        print("[BLOCKED] No mesh selected")
        return None

    if len(selected) > 1:
        print("[BLOCKED] Select only one asset for publishing")
        return None

    asset_name = selected[0]

    try:
        os.makedirs(
            PUBLISH_ROOT,
            exist_ok=True
        )

    except OSError as error:
        print(f"[ERROR] Invalid publish path: {error}")
        return None

    publish_path = os.path.join(
        PUBLISH_ROOT,
        f"{asset_name}.fbx"
    )

    publish_path = publish_path.replace("\\", "/")

    print(f"[PUBLISH PATH] {publish_path}")

    return publish_path


def publish_fbx():
    selected = get_selected_meshes()

    if not selected:
        print("[BLOCKED] No mesh selected")
        return False

    if not validate_export_ready():
        print("[BLOCKED] Publish cancelled")
        return False

    publish_path = get_publish_path()

    if not publish_path:
        return False

    if os.path.exists(publish_path):
        result = cmds.confirmDialog(
            title="Overwrite File",
            message=f"File already exists:\n{publish_path}\n\nOverwrite?",
            button=["Yes", "No"],
            defaultButton="No",
            cancelButton="No",
            dismissString="No"
        )

        if result != "Yes":
            print("[CANCELLED] Publish cancelled")
            return False

    return run_fbx_export(publish_path, selected)


def run_fbx_export(path, objects):
    original_selection = cmds.ls(selection=True) or []

    try:
        if not cmds.pluginInfo(
            "fbxmaya",
            query=True,
            loaded=True
        ):
            cmds.loadPlugin("fbxmaya")

        cmds.select(objects, replace=True)

        mel.eval(
            f'FBXExport -f "{path}" -s;'
        )

        print(f"[SUCCESS] FBX Export: {path}")
        return True

    except Exception as error:
        print(f"[ERROR] FBX Export failed: {error}")
        return False

    # 書き出しの成否にかかわらず、元の選択状態に戻す
    finally:
        if original_selection:
            cmds.select(original_selection, replace=True)
        else:
            cmds.select(clear=True)

# -----------------------------------------------------------------------------
# UI

asset_validator_window = None


def show_ui():
    global asset_validator_window

    try:
        asset_validator_window.close()
        asset_validator_window.deleteLater()
    except:
        pass

    asset_validator_window = AssetValidatorUI()
    asset_validator_window.show()


class AssetValidatorUI(QtWidgets.QDialog):

    def __init__(self, parent=get_maya_main_window()):
        super().__init__(parent)

        self.setWindowTitle("Maya Asset Validator")
        self.setMinimumWidth(300)

        self.create_ui()

    def create_ui(self):
        self.setMinimumWidth(340)

        main_layout = QtWidgets.QVBoxLayout(self)

        # Title
        title = QtWidgets.QLabel("Maya Asset Validator")
        title_font = title.font()
        title_font.setBold(True)
        title_font.setPointSize(14)
        title.setFont(title_font)

        main_layout.addWidget(title)

        # Settings
        settings_group = QtWidgets.QGroupBox("Settings")
        settings_layout = QtWidgets.QFormLayout(settings_group)

        self.prefix_input = QtWidgets.QLineEdit(MESH_PREFIX)

        settings_layout.addRow("Mesh Prefix", self.prefix_input)

        main_layout.addWidget(settings_group)

        self.publish_path_input = QtWidgets.QLineEdit(PUBLISH_ROOT)

        browse_button = QtWidgets.QPushButton("Browse")
        browse_button.clicked.connect(self.browse_publish_path)

        publish_path_layout = QtWidgets.QHBoxLayout()
        publish_path_layout.addWidget(self.publish_path_input)
        publish_path_layout.addWidget(browse_button)

        settings_layout.addRow("Publish Path", publish_path_layout)

        # Validation
        validation_group = QtWidgets.QGroupBox("Validation")
        validation_layout = QtWidgets.QFormLayout(validation_group)

        self.naming_label = QtWidgets.QLabel("-")
        self.transform_label = QtWidgets.QLabel("-")
        self.pivot_label = QtWidgets.QLabel("-")
        self.material_label = QtWidgets.QLabel("-")
        self.texture_label = QtWidgets.QLabel("-")
        self.hierarchy_label = QtWidgets.QLabel("-")

        validation_layout.addRow("Naming", self.naming_label)
        validation_layout.addRow("Transform", self.transform_label)
        validation_layout.addRow("Pivot", self.pivot_label)
        validation_layout.addRow("Material", self.material_label)
        validation_layout.addRow("Texture", self.texture_label)
        validation_layout.addRow("Hierarchy", self.hierarchy_label)

        main_layout.addWidget(validation_group)

        # Actions
        action_group = QtWidgets.QGroupBox("Actions")
        action_layout = QtWidgets.QVBoxLayout(action_group)

        validate_button = QtWidgets.QPushButton("Validate")
        validate_button.clicked.connect(self.run_validation)

        auto_fix_button = QtWidgets.QPushButton("Auto Fix")
        auto_fix_button.clicked.connect(self.run_auto_fix)

        export_button = QtWidgets.QPushButton("Export FBX")
        export_button.clicked.connect(self.run_export)

        publish_button = QtWidgets.QPushButton("Publish")
        publish_button.clicked.connect(self.run_publish)

        action_layout.addWidget(validate_button)
        action_layout.addWidget(auto_fix_button)
        action_layout.addWidget(export_button)
        action_layout.addWidget(publish_button)

        main_layout.addWidget(action_group)

        # Status
        self.status_label = QtWidgets.QLabel("Status: Not Validated")

        status_font = self.status_label.font()
        status_font.setBold(True)
        self.status_label.setFont(status_font)

        main_layout.addSpacing(8)
        main_layout.addWidget(self.status_label)


    def update_settings(self):
        global MESH_PREFIX
        global PUBLISH_ROOT

        prefix = self.prefix_input.text().strip()
        publish_path = self.publish_path_input.text().strip()

        if not prefix:
            self.status_label.setText("Status: INVALID PREFIX")
            return False

        if not publish_path:
            self.status_label.setText("Status: INVALID PUBLISH PATH")
            return False

        # 設定変更後も旧接頭辞を置き換えられるよう保持する
        KNOWN_MESH_PREFIXES.add(MESH_PREFIX)
        KNOWN_MESH_PREFIXES.add(prefix)

        MESH_PREFIX = prefix
        PUBLISH_ROOT = publish_path

        return True


    def browse_publish_path(self):
        folder = cmds.fileDialog2(
            fileMode=3,
            caption="Select Publish Folder"
        )

        if folder:
            self.publish_path_input.setText(folder[0])


    def run_validation(self):
        if not self.update_settings():
            return

        selected = get_selected_meshes()

        if not selected:
            self.naming_label.setText("-")
            self.transform_label.setText("-")
            self.pivot_label.setText("-")
            self.material_label.setText("-")
            self.texture_label.setText("-")
            self.hierarchy_label.setText("-")

            self.status_label.setText("Status: NO MESH SELECTED")
            return

        print("=== UI Validate ===")

        naming_issues = validate_names()
        transform_issues = validate_transforms()
        pivot_issues = validate_pivots()
        material_issues = validate_materials()
        texture_issues = validate_textures()
        hierarchy_issues = validate_hierarchy()

        self.naming_label.setText(
            "OK" if not naming_issues else "ISSUE"
        )

        self.transform_label.setText(
            "OK" if not transform_issues else "ISSUE"
        )

        self.pivot_label.setText(
            "OK" if not pivot_issues else "ISSUE"
        )

        self.material_label.setText(
            "OK" if not material_issues else "ISSUE"
        )

        self.texture_label.setText(
            "OK" if not texture_issues else "ISSUE"
        )

        self.hierarchy_label.setText(
            "OK" if not hierarchy_issues else "ISSUE"
        )

        all_issues = (
            naming_issues
            + transform_issues
            + pivot_issues
            + material_issues
            + texture_issues
            + hierarchy_issues
        )

        if not all_issues:
            self.status_label.setText("Status: READY")
        else:
            self.status_label.setText("Status: BLOCKED")

    def run_auto_fix(self):
        if not self.update_settings():
            return

        print("=== UI Auto Fix ===")

        naming_issues = validate_names()

        if naming_issues:
            fix_names(naming_issues)

        transform_issues = validate_transforms()

        if transform_issues:
            fix_transforms(transform_issues)

        pivot_issues = validate_pivots()

        if pivot_issues:
            fix_pivots(pivot_issues)

        self.run_validation()

    def run_export(self):
        if not self.update_settings():
            return

        result = export_fbx()

        if result:
            self.status_label.setText("Status: EXPORTED")
        else:
            self.status_label.setText("Status: EXPORT BLOCKED")


    def run_publish(self):
        if not self.update_settings():
            return

        result = publish_fbx()

        if result:
            self.status_label.setText("Status: PUBLISHED")
        else:
            self.status_label.setText("Status: PUBLISH BLOCKED")

show_ui()
