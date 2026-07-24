# Smart Export for Autodesk Fusion

Current add-in version: **1.1.1**

Smart Export adds a **Smart Export** command to the Design workspace's Add-Ins
panel and an item to Fusion's File menu. It exports the active design with:

- an incrementing filename found by scanning the destination folder
  (`Part_v1.step`, `Part_v2.step`, …), or
- the local date/time of the active saved Fusion history version
  (`Part_2026-07-20_14-35-02.step`).

STEP, STL, and 3MF are first-class supported formats. IGES, SAT, SMT, F3D,
OBJ, and USD are also offered when the installed Fusion build exposes their
export API.

The command also appears when right-clicking a component, occurrence, or solid
body. Body exports offer the body-capable mesh formats STL, 3MF, and OBJ.
Component and occurrence exports offer the full format list.

Export folders are remembered independently for each saved Fusion cloud
project, using the project's stable Autodesk project ID. A project with no
saved folder starts in Documents and never inherits another project's folder.

The export dialog opens at a readable minimum size and shows the current naming
examples:

```text
Incrementing example: Part_v1.step

Timestamp example: Part_2026-07-20_14-35-02.step
```

## Install

1. Put this entire folder in Fusion's add-ins directory:
   - Windows: `%APPDATA%\Autodesk\Autodesk Fusion 360\API\AddIns\SmartExport`
   - macOS: `~/Library/Application Support/Autodesk/Autodesk Fusion 360/API/AddIns/SmartExport`
   The folder, entry-point, and manifest must have the same base name:
   `SmartExport/SmartExport.py` and `SmartExport/SmartExport.manifest`.
2. In Fusion, open **Utilities > Add-Ins > Scripts and Add-Ins**.
3. Select **SmartExport** under **Add-Ins**, enable **Run on Startup**, and click
   **Run**.

If startup fails, inspect `SmartExport.log` beside `SmartExport.py`. The log
records whether the command definition, toolbar control, and File-menu control
were created, along with any Python traceback.

Timestamp mode requires the document to have been saved. Its timestamp comes
from `Document.dataFile.dateCreated`, i.e. the active saved history entry.
If two versions have the same one-second timestamp, Smart Export appends `_2`,
`_3`, and so on instead of overwriting a file.

## Development checks

The naming code is intentionally independent from Fusion's `adsk` module:

```powershell
python -m unittest discover -s tests -v
```
