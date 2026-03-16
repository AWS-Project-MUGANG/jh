# AWS 배포 작업지시서 (Docker 우선, PostgreSQL on RDS)

## 목표
- 로컬 Docker로 먼저 기능 검증
- 이후 AWS RDS(PostgreSQL) + AWS 인프라로 전환
- AWS 리소스는 Terraform으로 자동 생성 (콘솔 수동 생성 최소화)

## 1) 내가 이미 처리한 항목
- Terraform RDS 비밀번호 하드코딩 제거
  - `terraform/rds.tf`에서 `password`를 `var.db_password`로 변경
  - `db_name`, `db_username`도 변수화
- `terraform/terraform.tfvars.example` 추가
  - 사용자 입력값 템플릿 제공
- `docker-compose.aws.yml`에서 SSH 터널/고정 DB 자격증명 제거
  - 이제 `backend/.env`의 `DATABASE_URL`만 사용
- `.gitignore`에 Terraform tfvars 비밀파일 제외 규칙 추가

## 2) 지금 사용자님이 해야 할 일 (순서대로)
1. `backend/.env` 확인/수정
   - 로컬 검증용:
     - `DATABASE_URL=postgresql://mugang:mugang@db:5432/mugang`
   - AWS RDS 연결용(전환 시):
     - `DATABASE_URL=postgresql://<user>:<password>@<rds-endpoint>:5432/mugang`

2. 로컬 Docker 검증
   - 실행: `docker-compose up --build`
   - 확인:
     - 프론트: `http://localhost:8888`
     - 백엔드: `http://localhost:8000/docs`

3. Terraform 변수 파일 생성
   - 파일 복사: `terraform/terraform.tfvars.example` -> `terraform/terraform.tfvars`
   - 값 입력:
     - `db_password`
     - `key_name` (현재 `compute.tf`의 EC2 리소스 사용 시 필요)

4. AWS 인프라 생성
   - 작업 디렉터리: `terraform/`
   - 실행:
     - `terraform init`
     - `terraform validate`
     - `terraform plan -out tfplan`
     - `terraform apply tfplan`

5. RDS 엔드포인트 확인 후 백엔드 연결값 교체
   - 출력 확인: `terraform output rds_endpoint`
   - `backend/.env`의 `DATABASE_URL`를 RDS 주소로 변경

## 3) 리소스를 직접 다 배포해야 하는지
- 아니요. 콘솔에서 하나씩 만들 필요 없습니다.
- Terraform `apply` 한 번으로 대부분 자동 생성됩니다.
- 직접 하는 작업은 주로 아래 3가지입니다:
  - AWS 자격증명 설정
  - 비밀값 입력(`db_password`, 앱 시크릿)
  - 적용 승인(`plan` 검토 후 `apply`)

## 4) 다음 단계 (내가 이어서 할 수 있는 작업)
- ECS Fargate + ECR 기준으로 Terraform 전환
  - EC2 직접 운영 대신 컨테이너 표준 배포로 단순화
- GitHub Actions로 CI/CD 자동화
  - 이미지 빌드/푸시(ECR)
  - ECS 서비스 롤링 배포
