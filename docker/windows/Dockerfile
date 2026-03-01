# Windows Container 기반 개발 환경 구축 Dockerfile
# Base image: Windows Server Core with .NET Framework
FROM mcr.microsoft.com/windows/servercore:ltsc2022

# 레이블 추가
LABEL maintainer="dev@example.com"
LABEL description="Development environment with CMake, LLVM, Python, Git, Visual Studio Build Tools, and Node.js"

# 시스템 업데이트 및 기본 설정
SHELL ["powershell", "-Command", "$ErrorActionPreference = 'Stop'; $ProgressPreference = 'SilentlyContinue';"]

# Chocolatey 설치
RUN Set-ExecutionPolicy Bypass -Scope Process -Force; \
    [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor 3072; \
    iex ((New-Object System.Net.WebClient).DownloadString('https://chocolatey.org/install.ps1'))

# Chocolatey로 기본 개발 도구 설치
RUN choco install -y cmake --version=3.31.1
RUN choco install -y llvm --version=14.0.6
RUN choco install -y python --version=3.10.11
RUN choco install -y git
RUN choco install -y nodejs --version=14.6.0

# NVM (Node Version Manager) 설치
RUN $env:PATH = [System.Environment]::GetEnvironmentVariable('Path','Machine'); \
    Invoke-WebRequest -Uri "https://github.com/coreybutler/nvm-windows/releases/download/1.1.12/nvm-noinstall.zip" -OutFile "nvm.zip"; \
    Expand-Archive -Path "nvm.zip" -DestinationPath "C:\nvm"; \
    Remove-Item "nvm.zip"; \
    New-Item -ItemType Directory -Path 'C:\Program Files\nodejs' -Force | Out-Null

# NVM 환경 변수 설정
RUN [Environment]::SetEnvironmentVariable('NVM_HOME', 'C:\nvm', [EnvironmentVariableTarget]::Machine); \
    [Environment]::SetEnvironmentVariable('NVM_SYMLINK', 'C:\Program Files\nodejs', [EnvironmentVariableTarget]::Machine); \
    $env:PATH = [System.Environment]::GetEnvironmentVariable('Path','Machine'); \
    [Environment]::SetEnvironmentVariable('Path', $env:PATH + ';C:\nvm;C:\Program Files\nodejs', [EnvironmentVariableTarget]::Machine)

# Visual Studio Build Tools 설치 (대체 방법)
# Windows Container에서의 레이어 크기 문제를 고려하여 간단한 설치 방법 사용
RUN $ProgressPreference = 'SilentlyContinue'; \
    Invoke-WebRequest -Uri "https://aka.ms/vs/17/release/vs_buildtools.exe" -OutFile "vs_buildtools.exe"; \
    Start-Process -FilePath "vs_buildtools.exe" -ArgumentList "--quiet", "--wait", "--norestart", "--installPath", "C:\BuildTools" -NoNewWindow -Wait; \
    Remove-Item "vs_buildtools.exe"

# 환경 변수 설정
RUN [Environment]::SetEnvironmentVariable('GYP_MSVS_VERSION', '2022', [EnvironmentVariableTarget]::Machine); \
    [Environment]::SetEnvironmentVariable('VCINSTALLDIR', 'C:\BuildTools\VC', [EnvironmentVariableTarget]::Machine); \
    [Environment]::SetEnvironmentVariable('PYTHON', 'C:\Python310\python.exe', [EnvironmentVariableTarget]::Machine)

# NVM 설정 파일 생성
RUN Set-Content -Path 'C:\nvm\settings.txt' -Value @('root: C:\nvm','path: C:\Program Files\nodejs','arch: 64','proxy:','node_mirror: https://nodejs.org/dist/','npm_mirror: https://github.com/npm/cli/archive/') -Encoding ASCII

# NPM 설정
RUN npm config set msvs_version 2022 --global; \
    npm config set python "C:\Python310\python.exe"; \
    npm config set msbuild_path "C:\BuildTools\MSBuild\Current\Bin\MSBuild.exe"

# 작업 디렉토리 설정
WORKDIR C:\\workspace

# 기본 명령어
CMD ["powershell"]