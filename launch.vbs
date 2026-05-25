Dim shell, dir
Set shell = CreateObject("WScript.Shell")
dir = CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName)
shell.Run "pythonw """ & dir & "\cliptype.py""", 0, False
