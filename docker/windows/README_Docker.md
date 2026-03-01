# Windows Container 개발 환경

이 Dockerfile은 Windows Container 기반으로 개발 환경을 구축하는 방법을 제공합니다.

## 포함된 개발 도구

- **CMake 3.31.1**: 빌드 시스템
- **LLVM 14.0.6**: 컴파일러 도구 체인
- **Python 3.10.11**: 파이썬 환경
- **Git**: 버전 관리
- **Node.js 14.6.0**: JavaScript 런타임
- **Visual Studio Build Tools 2022**: C++ 빌드 환경
- **NVM**: Node.js 버전 관리

## 사용 방법

### 1. Docker 이미지 빌드

```bash
docker-compose build
```

### 2. 컨테이너 실행

```bash
docker-compose up -d
```

### 3. 컨테이너에 접속

```bash
docker exec -it windows-dev-env powershell
```

### 4. 개발 환경 확인

컨테이너 내부에서 다음 명령어로 설치된 도구 확인:

```powershell
# CMake 버전 확인
cmake --version

# Python 버전 확인
python --version

# Node.js 버전 확인
node --version

# Git 버전 확인
git --version

# MSBuild 경로 확인
Get-Command msbuild
```

## 주요 환경 변수

- `GYP_MSVS_VERSION=2022`: Node.js 빌드 시 Visual Studio 버전 지정
- `VCINSTALLDIR`: Visual Studio C++ 컴파일러 경로
- `PYTHON`: Python 실행 파일 경로

## 빌드 예제

컨테이너 내부에서 간단한 빌드 테스트:

```powershell
# Node.js native 모듈 빌드 테스트
cd C:\workspace
npm install
node-gyp configure
node-gyp build
```

## 주의사항

- Windows Container는 Windows 호스트에서만 실행 가능
- 이미지 크기가 크므로 넉넉한 디스크 공간 필요
- 첫 빌드 시 다소 시간이 소요될 수 있음

## 삭제
docker image prune -f
docker rmi -f $(docker images -q)

docker build -t dev-env .
