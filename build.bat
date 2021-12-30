@echo off
cmd.exe /c pyinstaller --clean -y --dist dist\windows --workpath tmp build.spec
cmd.exe /c del  /f dist\windows\F95Checker\Qt5Bluetooth.dll
cmd.exe /c del  /f dist\windows\F95Checker\Qt5DBus.dll
cmd.exe /c del  /f dist\windows\F95Checker\Qt5Location.dll
cmd.exe /c del  /f dist\windows\F95Checker\Qt5Multimedia.dll
cmd.exe /c del  /f dist\windows\F95Checker\Qt5Nfc.dll
cmd.exe /c del  /f dist\windows\F95Checker\Qt5QmlWorkerScript.dll
cmd.exe /c del  /f dist\windows\F95Checker\Qt5Quick3D.dll
cmd.exe /c del  /f dist\windows\F95Checker\Qt5Quick3DAssetImport.dll
cmd.exe /c del  /f dist\windows\F95Checker\Qt5Quick3DRender.dll
cmd.exe /c del  /f dist\windows\F95Checker\Qt5Quick3DRuntimeRender.dll
cmd.exe /c del  /f dist\windows\F95Checker\Qt5Quick3DUtils.dll
cmd.exe /c del  /f dist\windows\F95Checker\Qt5QuickControls2.dll
cmd.exe /c del  /f dist\windows\F95Checker\Qt5QuickParticles.dll
cmd.exe /c del  /f dist\windows\F95Checker\Qt5QuickShapes.dll
cmd.exe /c del  /f dist\windows\F95Checker\Qt5QuickTemplates2.dll
cmd.exe /c del  /f dist\windows\F95Checker\Qt5QuickTest.dll
cmd.exe /c del  /f dist\windows\F95Checker\Qt5RemoteObjects.dll
cmd.exe /c del  /f dist\windows\F95Checker\Qt5Sensors.dll
cmd.exe /c del  /f dist\windows\F95Checker\Qt5SerialPort.dll
cmd.exe /c del  /f dist\windows\F95Checker\Qt5Sql.dll
cmd.exe /c del  /f dist\windows\F95Checker\Qt5Svg.dll
cmd.exe /c del  /f dist\windows\F95Checker\Qt5Test.dll
cmd.exe /c del  /f dist\windows\F95Checker\Qt5WebSockets.dll
cmd.exe /c del  /f dist\windows\F95Checker\Qt5XmlPatterns.dll
cmd.exe /c mkdir   dist\windows\F95Checker\lib
cmd.exe /c move /y dist\windows\F95Checker\aiohttp               dist\windows\F95Checker\lib
cmd.exe /c move /y dist\windows\F95Checker\multidict             dist\windows\F95Checker\lib
cmd.exe /c move /y dist\windows\F95Checker\tcl8                  dist\windows\F95Checker\lib
cmd.exe /c move /y dist\windows\F95Checker\yarl                  dist\windows\F95Checker\lib
cmd.exe /c move /y dist\windows\F95Checker\*.pyd                 dist\windows\F95Checker\lib
cmd.exe /c move /y dist\windows\F95Checker\api-ms-win-*          dist\windows\F95Checker\lib
cmd.exe /c move /y dist\windows\F95Checker\d3dcompiler_47.dll    dist\windows\F95Checker\lib
cmd.exe /c move /y dist\windows\F95Checker\libcrypto-1_1.dll     dist\windows\F95Checker\lib
cmd.exe /c move /y dist\windows\F95Checker\libcrypto-1_1-x64.dll dist\windows\F95Checker\lib
cmd.exe /c move /y dist\windows\F95Checker\libeay32.dll          dist\windows\F95Checker\lib
cmd.exe /c move /y dist\windows\F95Checker\libEGL.dll            dist\windows\F95Checker\lib
cmd.exe /c move /y dist\windows\F95Checker\libffi-7.dll          dist\windows\F95Checker\lib
cmd.exe /c move /y dist\windows\F95Checker\libGLESv2.dll         dist\windows\F95Checker\lib
cmd.exe /c move /y dist\windows\F95Checker\libssl-1_1.dll        dist\windows\F95Checker\lib
cmd.exe /c move /y dist\windows\F95Checker\libssl-1_1-x64.dll    dist\windows\F95Checker\lib
cmd.exe /c move /y dist\windows\F95Checker\MSVCP140.dll          dist\windows\F95Checker\lib
cmd.exe /c move /y dist\windows\F95Checker\MSVCP140_1.dll        dist\windows\F95Checker\lib
cmd.exe /c move /y dist\windows\F95Checker\opengl32sw.dll        dist\windows\F95Checker\lib
cmd.exe /c move /y dist\windows\F95Checker\ssleay32.dll          dist\windows\F95Checker\lib
cmd.exe /c move /y dist\windows\F95Checker\tcl86t.dll            dist\windows\F95Checker\lib
cmd.exe /c move /y dist\windows\F95Checker\tk86t.dll             dist\windows\F95Checker\lib
cmd.exe /c move /y dist\windows\F95Checker\ucrtbase.dll          dist\windows\F95Checker\lib
cmd.exe /c move /y dist\windows\F95Checker\VCRUNTIME140_1.dll    dist\windows\F95Checker\lib
cmd.exe /c move /y dist\windows\F95Checker\VCRUNTIME140.dll      dist\windows\F95Checker\lib
cmd.exe /c mkdir   dist\windows\F95Checker\modules
cmd.exe /c copy /y F95Checker.py                                 dist\windows\F95Checker
cmd.exe /c copy /y F95Checker.sh                                 dist\windows\F95Checker
cmd.exe /c copy /y requirements.txt                              dist\windows\F95Checker
cmd.exe /c copy /y update.py                                     dist\windows\F95Checker
cmd.exe /c copy /y update.exe                                    dist\windows\F95Checker
cmd.exe /c copy /y modules                                       dist\windows\F95Checker\modules
explorer.exe dist\windows\F95Checker
