
# build 환경 구성

## install tools 
- cmake 3.31
- llvm 14.0.5
- python 3.10
- git
- Visual Studio 2022 Professional
- nvm-setup 1.1.12

## nvm 14.6.0 버전 설치
nvm install 14.6.0

### 설치된 버전 확인 및 사용 설정
nvm use 14.6.0

### 현재 버전 확인
node -v

#### VS 버전을 2022로 고정
npm config set msvs_version 2022 --global

### Professional 버전용 MSBuild.exe 경로 설정
npm config set msbuild_path "C:\Program Files\Microsoft Visual Studio\2022\Professional\Msbuild\Current\Bin\MSBuild.exe"

### Python 경로 설정 (Python이 설치된 실제 경로로 입력)
npm config set python "C:\Program Files\Python310"

환경 변수 등록
시스템 환경 변수에도 다음 내용을 추가하면 더 안정적입니다.
변수명: GYP_MSVS_VERSION / 값: 2022
변수명: VCINSTALLDIR / 값: C:\Program Files\Microsoft Visual Studio\2022\Community\VC

### 