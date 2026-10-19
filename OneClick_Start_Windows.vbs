Set WshShell = CreateObject("WScript.Shell")
WshShell.CurrentDirectory = CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName)
' 优先尝试无黑框模式启动桌面控制台
On Error Resume Next
WshShell.Run "pythonw app_launcher.py", 0, False
If Err.Number <> 0 Then
    WshShell.Run "python app_launcher.py", 0, False
End If
