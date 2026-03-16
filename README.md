# 무강대학교 AI 학사행정 서비스 Web App

FastAPI + Vanilla JS 기반의 AI 학사행정 웹 애플리케이션입니다.  
학생/교직원 로그인, 수강신청, 관리자 과목 관리, RAG 기반 학사 Q&A를 제공합니다.

---

## Quick Start

```bash
docker compose up -d --build
```

- Frontend: `http://localhost:8888`
- Backend Docs: `http://localhost:8000/docs`
- Health: `http://localhost:8000/api/health`

---

## 0) 실제 AWS 운영 정보 (2026-03-14 확인)

아래 값은 로컬 AWS CLI/Terraform output 기준 실조회 값입니다.  
민감정보(비밀번호, 액세스 키 원문)는 문서에 포함하지 않았습니다.

- AWS Account ID: `410947917751`
- IAM User(배포/운영): `arn:aws:iam::410947917751:user/mugang`
- Region: `ap-northeast-2` (Seoul)
- Terraform Active Color: `blue`
- Terraform Inactive Color: `green`
- Public Entry: `http://43.201.54.86/`
- API Docs: `http://43.201.54.86/docs`
- API Health: `http://43.201.54.86/api/health`
- 참고: Public IP는 변경될 수 있으며, 최신 값은 `terraform output proxy_public_ip`로 확인

---

## 1) 주요 기능

- 학번/사번 로그인 + 초기 비밀번호 변경(First Setup)
- 수강신청/취소/장바구니/정원 초과 대기열 처리
- 관리자 기능: 과목 생성/삭제, PDF 과목 업로드, 수강신청 일정 관리
- 학생 통계/관리자 통계 API 제공
- RAG 기반 챗봇 질의응답 (`/api/v1/chat/ask`)
- AI 과목 추천 API (`/api/v1/student/ai/recommend`)
- Docker 로컬 실행 + AWS Terraform 기반 Blue/Green 배포

---

## 2) 테스트 계정

점검 기준 계정(요청 반영):

- 학생: `201811047 / 123123123`
- 교직원(관리자): `staff / 123123123`

참고: 환경별 데이터 상태에 따라 first-setup 요구 여부는 달라질 수 있습니다.

---

## 3) 기술 스택

- Backend: Python 3.11, FastAPI, SQLAlchemy, Uvicorn
- Frontend: HTML/CSS/JavaScript (Vanilla), Nginx
- Auth: JWT + bcrypt
- DB:
  - PostgreSQL (메인 트랜잭션 DB, pgvector 확장 사용)
  - SQLite (로컬 fallback 옵션)
- AI: AWS Bedrock (임베딩/답변 생성)
- Infra: Docker, Docker Compose, Terraform, AWS (EC2/ASG/RDS/ECR/VPC)
- CI/CD: GitHub Actions

---

## 4) 저장소 구성 요약

이 저장소는 FastAPI 모놀리식 API 서버 + 정적 프론트엔드 조합입니다.  
수강신청 로직, 관리자 기능, RAG 문서 업로드/검색, 배포 인프라(Terraform)가 한 저장소에 포함돼 있습니다.

| 영역 | 실제 파일 | 역할 |
| --- | --- | --- |
| API 서버 | `backend/main.py` | 인증, 수강신청, 관리자, 챗봇, RAG API |
| 데이터 모델 | `backend/models.py` | 사용자/강의/수강/챗/RAG 테이블 ORM |
| DB 연결 | `backend/database.py` | `DATABASE_URL` 기반 엔진/세션 구성 |
| 학생 화면 | `frontend/pages/student/dashboard.html` | 수강신청 메인 UI |
| 프론트 로직 | `frontend/js/app.js` | 강의 조회/장바구니/신청 처리 |
| 챗봇 UI | `frontend/js/new_chatbot.js` | Q&A/추천 챗봇 상호작용 |
| 로컬 구성 | `docker-compose.yml` | frontend + backend + PostgreSQL(pgvector) |
| AWS 인프라 | `terraform/*.tf` | VPC, EC2 Blue/Green, RDS, ECR |
| 배포 자동화 | `.github/workflows/deploy.yml` | 이미지 빌드 + Blue/Green 배포 |

현재 코드 기준 기본 운영 모델은 `Terraform + EC2 Blue/Green`입니다.

- 프록시 EC2(Nginx)가 외부 트래픽을 수신
- Blue/Green ASG를 교체하며 무중단에 가깝게 전환
- 앱 데이터는 RDS PostgreSQL에 저장
---

## 5) 환경 구분

| 환경 | 목적 | 런타임 | DB | 진입점 | 실행 기준 |
| --- | --- | --- | --- | --- | --- |
| `local` | 개인 개발/디버깅 | Docker Compose | 로컬 PostgreSQL 컨테이너 | `localhost:8888`(frontend), `localhost:8000`(API) | `docker compose up -d --build` |
| `aws-dev` | AWS 통합 검증 | EC2 + Docker | RDS PostgreSQL | `http://<proxy_public_ip>/` | `terraform apply` + Actions 배포 |
| `aws-prod-like` | 운영 시뮬레이션 | Blue/Green ASG | RDS PostgreSQL | Proxy Public IP | `deploy.yml` 워크플로 |

주의:

- 현재 저장소의 Kubernetes 매니페스트(`k8s/*`)는 보조 자료 수준이며, 실제 메인 배포는 Terraform 경로입니다.
- 애플리케이션의 핵심 트랜잭션 데이터는 PostgreSQL이 담당합니다.

---

## 6) 로컬 실행 (권장 시작점)

### 6-1. 실행

```bash
docker compose up -d --build
```

### 6-2. 접속

- 프론트: `http://localhost:8888`
- 백엔드 Swagger: `http://localhost:8000/docs`
- 헬스 체크: `http://localhost:8000/api/health`
- 로컬 검증 결과(2026-03-14): `8888`, `8000/docs`, `8000/api/health` 모두 `HTTP 200`

### 6-3. 종료

```bash
docker compose down
```

데이터 볼륨까지 삭제:

```bash
docker compose down -v
```

---

## 7) 백엔드 단독 실행 (옵션)

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

환경변수 예시:

```env
DATABASE_URL=postgresql://mugang:mugang@localhost:5432/mugang
```

---

## 8) AWS 인프라 실행 (Terraform)

### 8-1. 사전 준비

- AWS CLI 인증 완료
- Terraform 설치
- `terraform/terraform.tfvars` 준비 (`db_password`, `key_name` 등)
- Terraform backend S3 버킷 준비

### 8-2. 초기화/계획/적용

```bash
cd terraform
terraform init -backend-config="bucket=<TF_STATE_BUCKET>" -backend-config="key=mugang/terraform.tfstate" -backend-config="region=ap-northeast-2"
terraform plan
terraform apply -auto-approve
```

### 8-3. 출력 확인

```bash
terraform output
```

중요 출력:

- `proxy_public_ip`
- `rds_endpoint`
- `active_color`

---

## 8-4) 현재 AWS 리소스 스냅샷 (2026-03-14)

| 리소스 | 현재 상태 | 식별자/값 |
| --- | --- | --- |
| Proxy EC2 | Running | `i-06366a56aca980c24` / `43.201.54.86` / `10.0.1.84` |
| Blue App EC2 | Running | `i-0bfeb0b475a882908` / `10.0.2.11` |
| Green App EC2 | Stopped(Desired 0) | `mugang-green-asg` |
| ASG Blue | InService 1 | `mugang-blue-asg` |
| ASG Green | InService 0 | `mugang-green-asg` |
| RDS PostgreSQL | Available | `mugang-db.czui6uqasxf9.ap-northeast-2.rds.amazonaws.com:5432` |
| DynamoDB | ACTIVE (현재 미사용, 개발 예정) | `mugang-chat-history` (Terraform 정의만 존재, 향후 챗봇 이력 저장 연결 예정) |
| ECR Backend | Created | `410947917751.dkr.ecr.ap-northeast-2.amazonaws.com/mugang-backend` |
| ECR Frontend | Created | `410947917751.dkr.ecr.ap-northeast-2.amazonaws.com/mugang-frontend` |
| VPC | Active | `vpc-05f1b055c52e0bf88` |

---

## 9) CI/CD (GitHub Actions)

현재 워크플로는 다음 흐름으로 구성됩니다.

- `.github/workflows/deploy.yml`
  - Frontend/Backend Docker 이미지 빌드
  - ECR 푸시
  - Terraform 기반 Blue/Green 전환
  - Proxy Nginx 업스트림 스위칭
- `.github/workflows/destroy.yml`
  - 수동 트리거로 전체 리소스 정리(`destroy` 확인값 필요)

배포 트리거:

- `main` 브랜치 push 시 자동 실행

---

## 10) 주요 API 엔드포인트

| 도메인 | 메서드 | 경로 |
| --- | --- | --- |
| Health | GET | `/api/health` |
| Auth | POST | `/api/v1/auth/login` |
| Auth | POST | `/api/v1/auth/first-setup` |
| Lecture | GET | `/api/v1/lectures` |
| Enrollment | POST | `/api/v1/enrollments` |
| Enrollment | DELETE | `/api/v1/enrollments/{enrollment_id}` |
| Student | GET | `/api/v1/student/{user_id}/stats` |
| AI | POST | `/api/v1/chat/ask` |
| AI | POST | `/api/v1/student/ai/recommend` |
| Admin | POST | `/api/v1/admin/courses/upload-pdf` |
| Admin | POST | `/api/v1/admin/enrollment-schedule` |
| Admin | GET | `/api/v1/admin/system-status` |

---

## 10-1) 발표용 데모 시나리오 (권장)

1. 로그인: 학생 계정(`201811047`)으로 로그인 후 대시보드 진입
2. 수강신청: 강의 필터 조회 후 장바구니 담기 및 신청
3. 챗봇 질의: `/api/v1/chat/ask` 기반으로 학사 질문 응답 확인
4. 관리자 기능: 과목/PDF 업로드 또는 수강신청 일정 설정 시연
5. 시스템 확인: `/api/v1/admin/system-status` 또는 `/api/health`로 마무리

---

## 11) 데이터베이스 구성

### 11-1. PostgreSQL (RDS / 로컬 컨테이너)

- 학사 핵심 데이터 저장
- SQLAlchemy ORM + pgvector 사용
- 로컬 Docker에서는 `pgvector/pgvector:pg16` 이미지 사용

### 11-2. DynamoDB (현재 미사용)

- Terraform에서 `mugang-chat-history` 테이블 정의 (`hash_key=session_id`, `range_key=timestamp`)
- 인프라 수준에만 존재하며, 애플리케이션 코드에서 실제로 연결하여 사용하지 않음
- 향후 챗봇 이력 저장 용도로 연결 예정

### 11-3. SQLite (Fallback)

- `DATABASE_URL` 미설정 시 개발 fallback으로 동작 가능
- 운영/검증 환경에서는 PostgreSQL 사용 권장

---

## 12) 아키텍처 다이어그램

### 12-0. 실제 사용 AWS 리소스

한눈에 보이도록 `리소스군 / 실제 서비스 / 역할` 기준으로 정리했습니다.

| 리소스군 | 실제 서비스 | 역할 |
| --- | --- | --- |
| 네트워크 | VPC, Public/Private Subnet, IGW, NAT, Route Table, Security Group | 외부/내부 트래픽 분리, 라우팅, 포트 제어 |
| 컴퓨팅 | EC2 Proxy, Launch Template(Blue/Green), ASG(Blue/Green) | 프록시 라우팅, 무중단 배포, 앱 실행 |
| 데이터 | RDS PostgreSQL, DynamoDB(`mugang-chat-history`, 현재 미사용) | 핵심 트랜잭션 저장 / DynamoDB는 Terraform 인프라 정의만 존재하며 추후 챗봇 이력 저장 용도로 연결 개발 예정 |
| 이미지/상태 | ECR(frontend/backend), S3(Terraform backend state) | 컨테이너 이미지 저장, 인프라 상태 관리 |
| 접근/운영 | IAM Role/Profile/Policy, SSM(Session/RunCommand) | 권한 제어, 원격 점검/명령 수행 |
| CI/CD/AI | GitHub Actions, Bedrock Runtime | 자동 배포 파이프라인, LLM/임베딩 호출 |

### 12-1. AWS 인프라 아키텍처 (요약)

```mermaid
flowchart LR
    USER[User Browser] --> PROXY[EC2 Proxy Nginx]
    PROXY --> BLUE[Blue App EC2]
    PROXY -. switch .-> GREEN[Green App EC2]

    BLUE --> RDS[(RDS PostgreSQL)]
    GREEN --> RDS
    BLUE -. 미사용 개발예정 .-> DDB[(DynamoDB)]
    GREEN -. 미사용 개발예정 .-> DDB

    GHA[GitHub Actions] --> ECR[(ECR)]
    GHA --> S3[(S3 Terraform State)]
    ECR --> BLUE
    ECR --> GREEN
    SSM[SSM] --> PROXY
    SSM --> BLUE
    SSM --> GREEN
```

### 12-2. AWS 인프라 아키텍처 (상세)

```mermaid
graph TB
    subgraph Internet["🌐 Internet"]
        User["👤 사용자 (브라우저)"]
        GHA["⚙️ GitHub Actions\nCI/CD Pipeline"]
    end

    subgraph AWS_Region["☁️ AWS ap-northeast-2 (Seoul)"]

        subgraph ECR["📦 Amazon ECR"]
            ECR_BE["mugang-backend\n(Docker Image)"]
            ECR_FE["mugang-frontend\n(Docker Image)"]
        end

        subgraph VPC["🔒 VPC (10.0.0.0/16)"]

            subgraph Public_Subnet["Public Subnet (AZ-a)"]
                NGW["🔀 NAT Gateway"]
                ProxyEC2["🖥️ Proxy EC2 (t3.micro)\nNginx Reverse Proxy\nPublic IP: 43.201.54.86\n:80"]
            end

            subgraph Private_Subnet_A["Private Subnet AZ-a"]
                BlueASG["🔵 Blue ASG (t3.medium)\n[ACTIVE]\nDocker: backend:8000\n        frontend:80"]
            end

            subgraph Private_Subnet_C["Private Subnet AZ-c"]
                GreenASG["🟢 Green ASG (t3.medium)\n[STANDBY]\nDocker: backend:8000\n        frontend:80"]
            end

            subgraph Data_Layer["Data Layer (Private)"]
                RDS["🗄️ Amazon RDS\nPostgreSQL 15.12\ndb.t3.micro / 20GB\nmugang-db"]
                DDB["📋 DynamoDB\nmugang-chat-history\n(PAY_PER_REQUEST)"]
            end

            subgraph EC2_Internal["EC2 Instance (Blue/Green)"]
                direction TB
                Nginx_FE["Nginx\n:80\n정적 파일 서빙\n/api/* → backend:8000"]
                FastAPI["FastAPI\n:8000\nPython 3.11\nUvicorn"]
            end
        end

        subgraph Bedrock["🤖 AWS Bedrock (us-east-1)"]
            Titan["amazon.titan-embed-text-v1\n(1536-dim 임베딩)"]
            Claude["anthropic.claude-v2\n(RAG 답변 생성)"]
        end

        SSM["🔧 AWS SSM\n(Blue/Green 전환 명령)"]
        S3_TF["🪣 S3\nTerraform State Backend"]
    end

    subgraph Docker_Compose["🐳 Docker (로컬 개발)"]
        direction LR
        DC_FE["frontend\n(Nginx Alpine :8888)"]
        DC_BE["backend\n(Uvicorn :8000)"]
        DC_DB["PostgreSQL + pgvector\n(:5432)"]
    end

    subgraph Backend_Internals["⚡ FastAPI 내부 구조"]
        direction TB
        Auth["🔐 Auth\n/api/v1/auth/*\nJWT + bcrypt"]
        Lectures["📚 Lectures\n/api/v1/lectures/*"]
        Enrollments["📝 Enrollments\n/api/v1/enrollments/*\n수강신청 + 대기열"]
        RAG["🧠 RAG\n/admin/rag/*\n문서 임베딩 검색"]
        Chat["💬 Chat\n/chat/ask\nRAG Q&A"]
        Admin["👨‍💼 Admin\n/admin/*\n성적/공지/일정"]
    end

    subgraph DB_Schema["🗃️ PostgreSQL Schema (pgvector)"]
        direction LR
        T1["user_tb"]
        T2["lecture_tb"]
        T3["enroll_tb"]
        T4["rag_docs_tb\n(벡터 임베딩)"]
        T5["grade_tb"]
        T6["chat_session_tb"]
        T7["schedule_tb"]
    end

    %% 사용자 → AWS 흐름
    User -->|"HTTP :80"| ProxyEC2
    ProxyEC2 -->|"Nginx upstream\n(active color)"| BlueASG
    ProxyEC2 -.->|"Standby"| GreenASG

    %% EC2 내부
    BlueASG --- Nginx_FE
    Nginx_FE -->|"/api/* proxy_pass"| FastAPI
    FastAPI --- Backend_Internals
    FastAPI -->|"SQLAlchemy ORM"| RDS
    RDS --- DB_Schema

    %% Bedrock 연동
    RAG -->|"boto3 임베딩 요청"| Titan
    Chat -->|"boto3 답변 생성"| Claude

    %% DynamoDB
    Chat -.->|"(예정)"| DDB

    %% Private → Internet
    BlueASG -->|"아웃바운드"| NGW
    GreenASG -->|"아웃바운드"| NGW
    NGW --> Internet

    %% CI/CD
    GHA -->|"docker push"| ECR_BE
    GHA -->|"docker push"| ECR_FE
    GHA -->|"SSM 명령"| SSM
    SSM -->|"upstream 전환"| ProxyEC2
    ECR_BE -->|"pull"| BlueASG
    ECR_FE -->|"pull"| BlueASG

    %% Terraform state
    GHA -->|"tfstate"| S3_TF

    %% 로컬 개발
    DC_FE --- DC_BE
    DC_BE --- DC_DB

    %% 스타일
    classDef aws fill:#FF9900,color:#000,stroke:#FF9900
    classDef docker fill:#0DB7ED,color:#fff,stroke:#0DB7ED
    classDef db fill:#3C873A,color:#fff,stroke:#3C873A
    classDef ai fill:#8B5CF6,color:#fff,stroke:#8B5CF6
    classDef nginx fill:#009900,color:#fff,stroke:#009900

    class RDS,DDB,S3_TF,ECR,ECR_BE,ECR_FE,SSM db
    class Bedrock,Titan,Claude ai
    class ProxyEC2,BlueASG,GreenASG aws
    class Docker_Compose,DC_FE,DC_BE,DC_DB docker
    class Nginx_FE nginx
```

### 12-3. 서비스 아키텍처 (논리 구성)

```mermaid
flowchart LR
    U[User] --> WEB[Web UI\nNginx + HTML/CSS/JS]
    WEB --> API[FastAPI API Layer]

    subgraph DOMAIN[Application Domain]
        AUTH[Auth\nLogin/First Setup/JWT]
        ENROLL[Enrollment\n강의조회/장바구니/신청/취소]
        ADMIN[Admin\n과목관리/일정관리/서버관리]
        RAG[RAG/Chat\n문서업로드/벡터검색/추천]
    end

    API --> AUTH
    API --> ENROLL
    API --> ADMIN
    API --> RAG

    AUTH --> PG[(PostgreSQL + pgvector)]
    ENROLL --> PG
    ADMIN --> PG
    RAG --> PG
    RAG --> BEDROCK[AWS Bedrock Runtime]
    API -. 미사용 개발예정 .-> DDB[(DynamoDB)]
```

### 12-4. 챗봇 질의 흐름

```mermaid
sequenceDiagram
    participant U as User
    participant FE as Frontend
    participant API as FastAPI
    participant DB as PostgreSQL
    participant BR as AWS Bedrock

    U->>FE: 질문 입력
    FE->>API: POST /api/v1/chat/ask
    API->>DB: 세션/메시지 저장
    API->>DB: RAG 문서 벡터 검색
    API->>BR: 문맥 기반 답변 생성 요청
    BR-->>API: 생성 응답
    API->>DB: assistant 답변 저장
    API-->>FE: reply + sources
```

---

## 13) 주요 경로

- Backend API: `backend/main.py`
- Backend Model: `backend/models.py`
- Backend DB: `backend/database.py`
- Frontend Entry: `frontend/index.html`
- Frontend Main JS: `frontend/js/app.js`
- Frontend Chatbot JS: `frontend/js/new_chatbot.js`
- Local Compose: `docker-compose.yml`
- AWS Compose(보조 실행): `docker-compose.aws.yml`
- Terraform: `terraform/*.tf`
- K8s(참고): `k8s/*.yaml`
- Deploy Workflow: `.github/workflows/deploy.yml`

---

## 14) 운영 체크 포인트

- 배포 후 `http://43.201.54.86/api/health` 응답 확인
- 배포 후 `http://43.201.54.86/docs` Swagger 확인
- Blue/Green 활성 색상은 `terraform output active_color`로 확인
- DB 접속은 RDS private 구조이므로 SSM 포트포워딩 사용

---

## 15) 향후 개선 후보

- DynamoDB 챗봇 이력 저장 경로를 백엔드 코드에 연결(현재 인프라 정의만 존재, 미사용)
- Alembic 기반 마이그레이션 도입
- 테스트 자동화(pytest + API 시나리오)
- Kubernetes 매니페스트와 Terraform 운영 모델 중 하나로 표준화

---

## 16) 제출용 화면 캡처 (앱)

아래 이미지는 `images/` 폴더에 저장한 수동 캡처본입니다.

1. 로그인 화면 (점검 계정 입력)  
![app-login](images/app-login.png)

2. 학생 대시보드(수강신청 + 사이드바 + 챗봇)  
![app-student-dashboard](images/app-student-dashboard.png)

3. 학생 시간표 화면  
![app-student-timetable](images/app-student-timetable.png)

4. 관리자 과목 개설 관리 화면  
![app-admin-course-management](images/app-admin-course-management.png)

5. 관리자 수강신청 일정 관리 화면  
![app-admin-enrollment-schedule](images/app-admin-enrollment-schedule.png)

6. 관리자 AI 학사 규정(RAG) 업데이트 화면  
![app-admin-rag-update](images/app-admin-rag-update.png)

7. 관리자 서버 모니터링 화면  
![app-admin-server-management](images/app-admin-server-management.png)

---

## 17) 제출용 화면 캡처 (AWS)

경로: `images/`

1. EC2 인스턴스 목록  
![aws-ec2-instances](images/aws-ec2-instances.png)

2. RDS 인스턴스 상세  
![aws-rds-detail](images/aws-rds-detail.png)

3. ECR 리포지토리 목록  
![aws-ecr-repositories](images/aws-ecr-repositories.png)

4. ECR backend 이미지 태그 상세  
![aws-ecr-backend-images](images/aws-ecr-backend-images.png)

---

## 18) 제출용 화면 캡처 (CI/CD)

경로: `images/`

1. GitHub Actions 배포 성공 및 단계 로그  
![cicd-github-actions-success](images/cicd-github-actions-success.png)







