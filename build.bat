@echo off
cmd.exe /c pyinstaller --clean -y --dist dist\windows --workpath tmp build.spec
cmd.exe /c del  /f dist\windows\F95Checker\Qt5WebSockets.dll
cmd.exe /c del  /f dist\windows\F95Checker\Qt5Svg.dll
cmd.exe /c del  /f dist\windows\F95Checker\Qt5Quick.dll
cmd.exe /c del  /f dist\windows\F95Checker\Qt5QmlModels.dll
cmd.exe /c del  /f dist\windows\F95Checker\Qt5Qml.dll
cmd.exe /c del  /f dist\windows\F95Checker\Qt5Network.dll
cmd.exe /c del  /f dist\windows\F95Checker\Qt5DBus.dll
cmd.exe /c mkdir   dist\windows\F95Checker\lib
cmd.exe /c move /y dist\windows\F95Checker\aiohttp                          dist\windows\F95Checker\lib
cmd.exe /c move /y dist\windows\F95Checker\multidict                        dist\windows\F95Checker\lib
cmd.exe /c move /y dist\windows\F95Checker\tcl8                             dist\windows\F95Checker\lib
cmd.exe /c move /y dist\windows\F95Checker\yarl                             dist\windows\F95Checker\lib
cmd.exe /c move /y dist\windows\F95Checker\_asyncio.pyd                     dist\windows\F95Checker\lib
cmd.exe /c move /y dist\windows\F95Checker\_ctypes.pyd                      dist\windows\F95Checker\lib
cmd.exe /c move /y dist\windows\F95Checker\_hashlib.pyd                     dist\windows\F95Checker\lib
cmd.exe /c move /y dist\windows\F95Checker\_overlapped.pyd                  dist\windows\F95Checker\lib
cmd.exe /c move /y dist\windows\F95Checker\_queue.pyd                       dist\windows\F95Checker\lib
cmd.exe /c move /y dist\windows\F95Checker\_socket.pyd                      dist\windows\F95Checker\lib
cmd.exe /c move /y dist\windows\F95Checker\_ssl.pyd                         dist\windows\F95Checker\lib
cmd.exe /c move /y dist\windows\F95Checker\_tkinter.pyd                     dist\windows\F95Checker\lib
cmd.exe /c move /y dist\windows\F95Checker\_uuid.pyd                        dist\windows\F95Checker\lib
cmd.exe /c move /y dist\windows\F95Checker\_win32sysloader.pyd              dist\windows\F95Checker\lib
cmd.exe /c move /y dist\windows\F95Checker\api-ms-win-*                     dist\windows\F95Checker\lib
cmd.exe /c move /y dist\windows\F95Checker\d3dcompiler_47.dll               dist\windows\F95Checker\lib
cmd.exe /c move /y dist\windows\F95Checker\libcrypto-1_1.dll                dist\windows\F95Checker\lib
cmd.exe /c move /y dist\windows\F95Checker\libEGL.dll                       dist\windows\F95Checker\lib
cmd.exe /c move /y dist\windows\F95Checker\libffi-7.dll                     dist\windows\F95Checker\lib
cmd.exe /c move /y dist\windows\F95Checker\libGLESv2.dll                    dist\windows\F95Checker\lib
cmd.exe /c move /y dist\windows\F95Checker\libssl-1_1.dll                   dist\windows\F95Checker\lib
cmd.exe /c move /y dist\windows\F95Checker\MSVCP140.dll                     dist\windows\F95Checker\lib
cmd.exe /c move /y dist\windows\F95Checker\MSVCP140_1.dll                   dist\windows\F95Checker\lib
cmd.exe /c move /y dist\windows\F95Checker\opengl32sw.dll                   dist\windows\F95Checker\lib
cmd.exe /c move /y dist\windows\F95Checker\select.pyd                       dist\windows\F95Checker\lib
cmd.exe /c move /y dist\windows\F95Checker\tcl86t.dll                       dist\windows\F95Checker\lib
cmd.exe /c move /y dist\windows\F95Checker\tk86t.dll                        dist\windows\F95Checker\lib
cmd.exe /c move /y dist\windows\F95Checker\ucrtbase.dll                     dist\windows\F95Checker\lib
cmd.exe /c move /y dist\windows\F95Checker\unicodedata.pyd                  dist\windows\F95Checker\lib
cmd.exe /c move /y dist\windows\F95Checker\VCRUNTIME140_1.dll               dist\windows\F95Checker\lib
cmd.exe /c move /y dist\windows\F95Checker\VCRUNTIME140.dll                 dist\windows\F95Checker\lib
cmd.exe /c move /y dist\windows\F95Checker\win32api.pyd                     dist\windows\F95Checker\lib
cmd.exe /c move /y dist\windows\F95Checker\win32event.pyd                   dist\windows\F95Checker\lib
cmd.exe /c mkdir   dist\windows\F95Checker\modules
cmd.exe /c copy /y F95Checker.py                                            dist\windows\F95Checker
cmd.exe /c copy /y F95Checker.sh                                            dist\windows\F95Checker
cmd.exe /c copy /y requirements_linux.txt                                   dist\windows\F95Checker
cmd.exe /c copy /y requirements.txt                                         dist\windows\F95Checker
cmd.exe /c copy /y update.py                                                dist\windows\F95Checker
cmd.exe /c copy /y update.exe                                               dist\windows\F95Checker
cmd.exe /c copy /y modules                                                  dist\windows\F95Checker\modules
explorer.exe dist\windows\F95Checker
