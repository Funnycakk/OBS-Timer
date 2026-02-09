' OBS Timer Server - Silent Launcher (runs in background)
' Run this to start timer server without console window

Set objShell = CreateObject("WScript.Shell")
strPath = Left(WScript.ScriptFullName, InStrRev(WScript.ScriptFullName, "\"))
objShell.Run "python """ & strPath & "app.py"""", 0, False
