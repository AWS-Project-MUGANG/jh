﻿# Docker 실행 가이드

## 기본: 로컬 PostgreSQL 모드
`docker-compose.yml`은 로컬 DB 기준입니다.

```powershell
docker compose up --build
```

접속:
- Frontend: http://localhost:8888
- Backend health: http://localhost:8000/api/health

종료:
```powershell
docker compose down
```

## AWS 터널 모드(잔재 보관)
AWS Bastion + RDS 터널이 필요할 때만 아래 파일을 사용합니다.

```powershell
docker compose -f docker-compose.aws.yml up --build
```

종료:
```powershell
docker compose -f docker-compose.aws.yml down
```

## 참고
- 로컬 모드 DB 계정: `mugang / mugang`
- 로컬 모드 DB URL: `postgresql://mugang:mugang@db:5432/mugang`

## [필수] AWS 배포용 (Production)
EC2 서버에서는 소스를 빌드하지 않고, ECR에 올라간 이미지를 다운받아 실행합니다.
배포 시에는 `docker-compose.prod.yml` 파일을 사용하세요.

```yaml
version: '3.8'

services:
  backend:
    # 깃허브 액션이 빌드해서 올린 ECR 이미지 주소
    image: 123456789012.dkr.ecr.ap-northeast-2.amazonaws.com/mugang-backend:latest
    ports:
      - "8000:8000"
    env_file:
      - .env  # 배포 시 EC2에 .env 파일을 별도로 생성해줘야 함

  frontend:
    image: 123456789012.dkr.ecr.ap-northeast-2.amazonaws.com/mugang-frontend:latest
    ports:
      - "80:80"
    depends_on:
      - backend
```
