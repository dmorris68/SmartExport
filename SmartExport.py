"""Smart Export add-in for Autodesk Fusion."""

import json
import os
import traceback

import adsk.core
import adsk.fusion

# Fusion loads Python add-ins as packages, while local tests load this as a
# standalone module. Support both contexts.
try:
    from .smart_export_core import (
        next_sequence,
        safe_stem,
        timestamp_filename,
        unique_path,
    )
except ImportError:
    from smart_export_core import (
        next_sequence,
        safe_stem,
        timestamp_filename,
        unique_path,
    )


CMD_ID = "dmorris68_SmartExport_Command"
CONTEXT_CMD_ID = "dmorris68_SmartExport_ContextCommand"
CMD_NAME = "Smart Export"
CMD_DESCRIPTION = "Export with a sequential version or saved-history timestamp."
FORMATS = ("STEP", "STL", "3MF", "IGES", "SAT", "SMT", "F3D", "OBJ", "USD")
EXTENSIONS = {
    "STEP": "step", "STL": "stl", "3MF": "3mf", "IGES": "iges",
    "SAT": "sat", "SMT": "smt", "F3D": "f3d", "OBJ": "obj", "USD": "usd",
}
SETTINGS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "settings.json")
LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "SmartExport.log")
handlers = []
controls = []
context_geometry = None
marking_menu_handler = None


def _log(message):
    """Write diagnostics that remain available after Fusion closes a dialog."""
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as stream:
            stream.write(f"{message}\n")
    except OSError:
        pass


def _load_settings():
    defaults = {"projects": {}, "format": "STEP", "mode": "Incrementing version"}
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as stream:
            saved = json.load(stream)
            defaults.update(saved)
            # Migrate the original single-folder setting without assigning it
            # to an unrelated Fusion project.
            defaults.pop("folder", None)
    except (OSError, ValueError, TypeError):
        pass
    if not isinstance(defaults.get("projects"), dict):
        defaults["projects"] = {}
    return defaults


def _save_settings(settings):
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as stream:
            json.dump(settings, stream, indent=2)
    except OSError:
        pass


def _selected_name(dropdown):
    item = dropdown.selectedItem
    return item.name if item else ""


def _history_epoch(document):
    if not document or not document.isSaved:
        return None
    data_file = document.dataFile
    return data_file.dateCreated if data_file else None


def _project_key(document):
    """Return the stable APS project ID for the active saved document."""
    try:
        if document and document.isSaved and document.dataFile:
            project = document.dataFile.parentProject
            if project:
                return project.id
    except RuntimeError:
        pass
    return None


def _project_folder(settings, document):
    project_id = _project_key(document)
    if project_id:
        folder = settings["projects"].get(project_id)
        if folder and os.path.isdir(folder):
            return folder
    return os.path.expanduser("~/Documents")


def _save_project_settings(settings, document, folder, format_name, mode):
    project_id = _project_key(document)
    if project_id:
        settings["projects"][project_id] = folder
    settings["format"] = format_name
    settings["mode"] = mode
    _save_settings(settings)


def _make_options(export_manager, design, geometry, format_name, filename):
    geometry = geometry or design.rootComponent
    if format_name == "STEP":
        return export_manager.createSTEPExportOptions(filename, geometry)
    if format_name == "STL":
        return export_manager.createSTLExportOptions(geometry, filename)
    if format_name == "3MF":
        return export_manager.createC3MFExportOptions(geometry, filename)
    if format_name == "IGES":
        return export_manager.createIGESExportOptions(filename, geometry)
    if format_name == "SAT":
        return export_manager.createSATExportOptions(filename, geometry)
    if format_name == "SMT":
        return export_manager.createSMTExportOptions(filename, geometry)
    if format_name == "F3D":
        return export_manager.createFusionArchiveExportOptions(filename, geometry)
    if format_name == "OBJ" and hasattr(export_manager, "createOBJExportOptions"):
        return export_manager.createOBJExportOptions(geometry, filename)
    if format_name == "USD" and hasattr(export_manager, "createUSDExportOptions"):
        return export_manager.createUSDExportOptions(filename, geometry)
    raise RuntimeError(f"{format_name} export is unavailable in this Fusion build.")


class ExecuteHandler(adsk.core.CommandEventHandler):
    def __init__(self, geometry=None):
        super().__init__()
        self.geometry = geometry

    def notify(self, args):
        ui = adsk.core.Application.get().userInterface
        try:
            app = adsk.core.Application.get()
            design = adsk.fusion.Design.cast(app.activeProduct)
            document = app.activeDocument
            if not design or not document:
                raise RuntimeError("Open a Fusion design before using Smart Export.")

            inputs = args.command.commandInputs
            folder = inputs.itemById("folder").value.strip()
            format_name = _selected_name(inputs.itemById("format"))
            mode = _selected_name(inputs.itemById("mode"))
            if not os.path.isdir(folder):
                raise RuntimeError("Choose an existing export folder.")

            target = self.geometry
            stem = safe_stem(target.name if target else document.name)
            extension = EXTENSIONS[format_name]
            if mode == "Incrementing version":
                basename = next_sequence(folder, stem, extension)
                output = os.path.join(folder, basename)
            else:
                epoch = _history_epoch(document)
                if epoch is None:
                    raise RuntimeError(
                        "Timestamp naming requires a saved document history version. "
                        "Save the design, then run Smart Export again."
                    )
                basename = timestamp_filename(stem, extension, epoch)
                output = str(unique_path(os.path.join(folder, basename)))

            options = _make_options(
                design.exportManager, design, target, format_name, output
            )
            if not options or not design.exportManager.execute(options):
                raise RuntimeError("Fusion reported that the export failed.")

            _save_project_settings(
                _load_settings(), document, folder, format_name, mode
            )
            ui.messageBox(f"Exported:\n{output}", CMD_NAME)
        except Exception as exc:
            ui.messageBox(f"{exc}\n\n{traceback.format_exc()}", f"{CMD_NAME} failed")


class InputChangedHandler(adsk.core.InputChangedEventHandler):
    def notify(self, args):
        if args.input.id != "browse":
            return
        ui = adsk.core.Application.get().userInterface
        dialog = ui.createFolderDialog()
        dialog.title = "Choose Smart Export folder"
        current = args.inputs.itemById("folder").value
        if current and os.path.isdir(current):
            dialog.initialDirectory = current
        if dialog.showDialog() == adsk.core.DialogResults.DialogOK:
            args.inputs.itemById("folder").value = dialog.folder


class ValidateHandler(adsk.core.ValidateInputsEventHandler):
    def notify(self, args):
        folder = args.inputs.itemById("folder").value.strip()
        mode = _selected_name(args.inputs.itemById("mode"))
        document = adsk.core.Application.get().activeDocument
        args.areInputsValid = bool(
            os.path.isdir(folder)
            and (mode != "History timestamp" or _history_epoch(document) is not None)
        )


class CommandCreatedHandler(adsk.core.CommandCreatedEventHandler):
    def __init__(self, is_context=False):
        super().__init__()
        self.is_context = is_context

    def notify(self, args):
        try:
            settings = _load_settings()
            geometry = context_geometry if self.is_context else None
            command = args.command
            command.isExecutedWhenPreEmpted = False
            command.setDialogInitialSize(560, 360)
            command.setDialogMinimumSize(500, 330)
            inputs = command.commandInputs

            fmt = inputs.addDropDownCommandInput(
                "format", "Format", adsk.core.DropDownStyles.TextListDropDownStyle
            )
            available_formats = FORMATS
            if geometry and adsk.fusion.BRepBody.cast(geometry):
                available_formats = ("STL", "3MF", "OBJ")
            selected_format = settings["format"]
            if selected_format not in available_formats:
                selected_format = "STL"
            for name in available_formats:
                fmt.listItems.add(name, name == selected_format, "")

            mode = inputs.addDropDownCommandInput(
                "mode", "Filename", adsk.core.DropDownStyles.TextListDropDownStyle
            )
            for name in ("Incrementing version", "History timestamp"):
                mode.listItems.add(name, name == settings["mode"], "")

            document = adsk.core.Application.get().activeDocument
            inputs.addStringValueInput(
                "folder", "Export folder", _project_folder(settings, document)
            )
            inputs.addBoolValueInput("browse", "Browse…", False, "", False)
            note = inputs.addTextBoxCommandInput(
                "note", "", "Incrementing example: Part_v1.step\n\n"
                "Timestamp example: Part_2026-07-20_14-35-02.step", 3, True
            )
            note.isFullWidth = True

            for event, handler in (
                (command.execute, ExecuteHandler(geometry)),
                (command.inputChanged, InputChangedHandler()),
                (command.validateInputs, ValidateHandler()),
            ):
                event.add(handler)
                handlers.append(handler)
        except Exception:
            details = traceback.format_exc()
            _log(f"Command creation failed:\n{details}")
            adsk.core.Application.get().userInterface.messageBox(
                details, f"{CMD_NAME} command failed"
            )


class MarkingMenuHandler(adsk.core.MarkingMenuEventHandler):
    def notify(self, args):
        global context_geometry
        try:
            context_geometry = None
            for entity in args.selectedEntities:
                if (adsk.fusion.BRepBody.cast(entity)
                        or adsk.fusion.Occurrence.cast(entity)
                        or adsk.fusion.Component.cast(entity)):
                    context_geometry = entity
                    break
            if not context_geometry:
                return
            definition = (
                adsk.core.Application.get().userInterface.commandDefinitions
                .itemById(CONTEXT_CMD_ID)
            )
            if definition:
                args.linearMarkingMenu.controls.addCommand(definition)
        except Exception:
            _log(f"Context menu failed:\n{traceback.format_exc()}")


def run(context):
    global marking_menu_handler
    _log("Starting Smart Export 1.1.1")
    app = adsk.core.Application.get()
    ui = app.userInterface if app else None
    try:
        if not ui:
            raise RuntimeError("Fusion user interface is unavailable.")
        old = ui.commandDefinitions.itemById(CMD_ID)
        if old:
            old.deleteMe()
        definition = ui.commandDefinitions.addButtonDefinition(
            CMD_ID, CMD_NAME, CMD_DESCRIPTION
        )
        created = CommandCreatedHandler(False)
        definition.commandCreated.add(created)
        handlers.append(created)

        old_context = ui.commandDefinitions.itemById(CONTEXT_CMD_ID)
        if old_context:
            old_context.deleteMe()
        context_definition = ui.commandDefinitions.addButtonDefinition(
            CONTEXT_CMD_ID, CMD_NAME, "Export the selected component or body."
        )
        context_created = CommandCreatedHandler(True)
        context_definition.commandCreated.add(context_created)
        handlers.append(context_created)

        marking_menu_handler = MarkingMenuHandler()
        ui.markingMenuDisplaying.add(marking_menu_handler)
        handlers.append(marking_menu_handler)
        _log("Registered component/body context-menu handler.")

        workspace = ui.workspaces.itemById("FusionSolidEnvironment")
        panel = workspace.toolbarPanels.itemById("SolidScriptsAddinsPanel") if workspace else None
        if panel:
            control = panel.controls.addCommand(definition)
            control.isPromoted = True
            controls.append(control)
            _log("Added Design workspace toolbar control.")
        else:
            _log("Warning: SolidScriptsAddinsPanel was not found.")

        qat = ui.toolbars.itemById("QAT")
        file_menu = qat.controls.itemById("FileSubMenuCommand") if qat else None
        if file_menu:
            menu_control = file_menu.controls.addCommand(
                definition, "ThreeDprintCmdDef", True
            )
            if menu_control:
                controls.append(menu_control)
                _log("Added File menu control.")
        else:
            _log("Warning: FileSubMenuCommand was not found.")
        _log("Smart Export started successfully.")
    except Exception:
        details = traceback.format_exc()
        _log(f"Startup failed:\n{details}")
        if ui:
            ui.messageBox(details, f"{CMD_NAME} load failed")


def stop(context):
    global marking_menu_handler
    ui = adsk.core.Application.get().userInterface
    try:
        if marking_menu_handler:
            ui.markingMenuDisplaying.remove(marking_menu_handler)
            if marking_menu_handler in handlers:
                handlers.remove(marking_menu_handler)
            marking_menu_handler = None
            _log("Removed context-menu event handler.")
        for control in reversed(controls):
            if control and control.isValid:
                control.deleteMe()
        controls.clear()
        for command_id in (CMD_ID, CONTEXT_CMD_ID):
            definition = ui.commandDefinitions.itemById(command_id)
            if definition:
                definition.deleteMe()
        handlers.clear()
    except Exception:
        ui.messageBox(traceback.format_exc(), f"{CMD_NAME} unload failed")
