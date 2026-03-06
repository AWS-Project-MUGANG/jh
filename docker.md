# 🐳 무강대학교 AI 학사행정 서비스 Docker 실행 가이드

본 문서는 팀원들이 로컬 환경에서 도커(Docker)를 사용하여 프로젝트를 실행하고 테스트할 수 있도록 돕는 가이드입니다.

---

## 1. 사전 준비 (Prerequisites)
시작하기 전에 팀원들의 컴퓨터에 다음 소프트웨어가 설치되어 있어야 합니다.

1. **Docker Desktop** 설치 및 실행
   - [공식 홈페이지](https://www.docker.com/products/docker-desktop/)에서 다운로드
   - 설치 후 반드시 **Docker Desktop 앱을 실행**해두어야 합니다.
2. **Git** 설치 (코드 공유를 위해 필요)

---

## 2. 프로젝트 내려받기 및 이동
프로젝트 최상위 디렉토리( `docker-compose.yml` 파일이 있는 위치)에서 터미널을 엽니다.

```bash
cd mugang_aws
```

---

## 3. 컨테이너 실행하기 (Docker Compose)
터미널에 아래 명령어를 입력하여 프론트엔드와 백엔드를 한꺼번에 실행합니다.

```powershell
# 이미지 빌드 및 컨테이너 실행
docker-compose up --build
```

> [!TIP]
> **--build** 옵션은 소스 코드가 변경되었을 때 이미지를 새로 만들기 위해 사용합니다. 최초 실행 이후 코드를 수정했다면 다시 이 명령어를 실행하세요.

---

## 4. 실행 확인 (Verification)
컨테이너가 정상적으로 정상적으로 올라왔다면 브라우저를 통해 접속할 수 있습니다.

*   **웹 서비스(프론트엔드)**: [http://localhost](http://localhost)
*   **API 서버(백엔드)**: [http://localhost:8000/api/health](http://localhost:8000/api/health)

### ✅ Docker Desktop에서 확인하는 법
1. Docker Desktop 앱의 **Containers** 탭으로 이동합니다.
2. `mugang_aws` 라는 그룹이 보이고, 왼쪽 화살표(`>`)를 눌렀을 때 아래 2개 서비스가 **초록색(Running)** 아이콘이면 성공입니다.
   - `mugang_aws-backend-1` (백엔드 서버)
   - `mugang_aws-frontend-1` (프론트엔드 서버)

---

## 5. 주의사항 및 트러블슈팅

### ⚠️ 포트 충돌 문제
만약 `Bind for 0.0.0.0:8000 failed` 같은 에러가 난다면, 이미 로컬에서 파이썬(`uvicorn`)을 실행 중인 것입니다. **기존에 띄워둔 서버를 종료**하고 다시 실행하세요.

### ⚠️ DB 데이터 (SQLite)
현재 로컬 테스트용 DB(`test.db`)는 컨테이너 실행 시 자동으로 연결됩니다. 데이터 초기화가 필요할 경우 `backend/test.db` 파일을 삭제하거나 컨테이너를 다시 빌드하세요.

---

## 6. 컨테이너 종료하기
작업이 끝났다면 터미널에서 `Ctrl + C`를 누르거나 아래 명령어를 입력하세요.

```powershell
docker-compose down
```
