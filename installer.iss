; ============================================================
; sgRNA Analyzer v2.1 安装包脚本 (Inno Setup)
;
; 编译方法:
;   1. 安装 Inno Setup (https://jrsoftware.org/isinfo.php)
;   2. 双击本文件或在 Inno Setup 中打开 -> Build -> Compile
;   3. 输出: dist\sgRNA_Analyzer_setup.exe
; ============================================================

#define MyAppName "sgRNA Analyzer"
#define MyAppVersion "2.1.0"
#define MyAppPublisher "许逸伦"
#define MyAppExeName "sgRNA_Analyzer.exe"

[Setup]
; 应用程序唯一标识（固定 GUID，勿改）
AppId={{7A4E9B2C-5F31-4D8A-9C64-2B1E8F6A3D57}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppVerName={#MyAppName} {#MyAppVersion}

; 默认安装目录: 用户可选（显示目录选择页）
DefaultDirName={autopf}\sgRNA Analyzer
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
; 始终显示"选择安装位置"页面，允许用户自定义目录
DisableDirPage=no

; 输出
OutputDir=dist
OutputBaseFilename=sgRNA_Analyzer_setup

; 压缩（LZMA2 强压缩，体积最小）
Compression=lzma2
SolidCompression=yes

; 现代向导风格
WizardStyle=modern

; 安装程序图标（软件 logo）
SetupIconFile=assets\app_icon.ico
; 控制面板"程序和功能"卸载条目显示的图标（卸载工具图标）
UninstallDisplayIcon={app}\uninstall_icon.ico

; 需要 Windows 7 及以上
MinVersion=6.1

[Languages]
Name: "chinesesimplified"; MessagesFile: "Languages\ChineseSimplified.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式"; GroupDescription: "附加任务："; Flags: unchecked

[Files]
; 打包整个 onedir 文件夹（含 _internal 依赖和 tools 捆绑工具）
Source: "dist\sgRNA_Analyzer\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
; 分发卸载图标（用于控制面板卸载条目显示）
Source: "assets\uninstall_icon.ico"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
; 主程序快捷方式（图标自动取 exe 内嵌的 app_icon）
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon
; 卸载快捷方式（用卸载工具图标）
Name: "{autoprograms}\卸载 {#MyAppName}"; Filename: "{app}\unins000.exe"; IconFilename: "{app}\uninstall_icon.ico"

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "立即启动 sgRNA Analyzer"; Flags: nowait postinstall skipifsilent

; Inno Setup 默认自动生成卸载程序 (unins000.exe) 并注册到
; 控制面板"程序和功能"，也会在卸载时自动清理安装的文件，
; 无需 [UninstallDelete] 段（该段会误删卸载程序自身）。
