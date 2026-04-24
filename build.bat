@echo off
echo Building AirPlay Streamer EXE...
echo.

REM Get customtkinter path
for /f "delims=" %%i in ('python -c "import customtkinter; import os; print(os.path.dirname(customtkinter.__file__))"') do set CTK_PATH=%%i

echo CustomTkinter path: %CTK_PATH%
echo.

pyinstaller --noconfirm --onedir --windowed ^
    --name "AirPlayStreamer" ^
    --add-data "%CTK_PATH%;customtkinter/" ^
    --hidden-import pyatv ^
    --hidden-import pyatv.protocols.raop ^
    --hidden-import pyatv.protocols.raop.protocols ^
    --hidden-import pyatv.protocols.raop.protocols.airplayv2 ^
    --hidden-import pyatv.protocols.raop.protocols.airplayv1 ^
    --hidden-import pyatv.protocols.airplay ^
    --hidden-import pyatv.protocols.airplay.auth ^
    --hidden-import pyatv.storage ^
    --hidden-import pyatv.storage.file_storage ^
    --hidden-import zeroconf ^
    --hidden-import zeroconf._utils ^
    --hidden-import ifaddr ^
    --hidden-import cryptography ^
    --hidden-import _cffi_backend ^
    --hidden-import miniaudio ^
    --hidden-import numpy ^
    --hidden-import pystray ^
    --hidden-import PIL ^
    --hidden-import pyaudiowpatch ^
    --hidden-import engineio ^
    --hidden-import chacha20poly1305_reuseable ^
    --hidden-import srptools ^
    --hidden-import mediafile ^
    --hidden-import tinytag ^
    --hidden-import google.protobuf ^
    --collect-all pyatv ^
    --collect-all zeroconf ^
    main.py

echo.
if %ERRORLEVEL% EQU 0 (
    echo BUILD SUCCESSFUL!
    echo EXE location: dist\AirPlayStreamer\AirPlayStreamer.exe
) else (
    echo BUILD FAILED!
)
pause
