# AWS 배포 가이드

git push → 자동 배포가 되려면 아래 순서대로 설정이 필요합니다.

---

## 현재 상태 체크

| 항목 | 상태 |
|---|---|
| 코드 준비 (Terraform + GitHub Actions) | ✅ 완료 |
| S3 버킷 생성 (bootstrap) | ❌ 필요 |
| GitHub Secrets 등록 | ❌ 필요 |
| ECR import (기존 수동 생성한 경우) | ❌ 필요할 수 있음 |

---

## GitHub Actions가 내 AWS 계정을 아는 원리

`deploy.yml`에서 아래 부분이 AWS 인증을 처리합니다:

```yaml
- name: Configure AWS credentials
  uses: aws-actions/configure-aws-credentials@v4
  with:
    aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
    aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
    aws-region: ap-northeast-2
```

GitHub Secrets에 저장된 AWS 액세스 키를 실행 시 환경변수로 주입합니다.
AWS CLI/Terraform은 이 키로 어느 계정인지 인증합니다.

---

## 배포 전 설정 순서

### Step 1 — AWS IAM 액세스 키 발급

AWS 콘솔 → IAM → 사용자 → 보안 자격증명 → **액세스 키 만들기**

필요 권한: AdministratorAccess 또는 아래 서비스 권한
- EC2, ECR, RDS, S3, DynamoDB, SSM, AutoScaling, IAM, VPC, Terraform

> 발급된 **Access Key ID**와 **Secret Access Key**를 안전한 곳에 메모해두세요.

---

### Step 2 — S3 버킷 생성 (최초 1회, 로컬 터미널에서 실행)

Terraform 상태 파일을 저장할 S3 버킷을 만듭니다.
이 버킷은 메인 Terraform과 별도로 관리됩니다 (닭-달걀 문제 해결).

```bash
cd terraform/bootstrap

# 예제 파일 복사
cp terraform.tfvars.example terraform.tfvars
```

`terraform/bootstrap/terraform.tfvars`를 열어 버킷 이름을 수정합니다:

```hcl
bucket_name = "mugang-tf-state-20260312"  # 전역 유일한 이름으로 변경
```

> S3 버킷 이름은 전 세계에서 유일해야 합니다. 날짜나 이름을 붙여서 사용하세요.

```bash
terraform init
terraform apply
```

출력된 `bucket_name` 값을 메모해둡니다 (Step 3에서 사용).

---

### Step 3 — GitHub Secrets 5개 등록

GitHub 저장소 → **Settings → Secrets and variables → Actions → New repository secret**

| Secret 이름 | 값 |
|---|---|
| `AWS_ACCESS_KEY_ID` | Step 1에서 발급한 키 ID |
| `AWS_SECRET_ACCESS_KEY` | Step 1에서 발급한 시크릿 키 |
| `TF_STATE_BUCKET` | Step 2에서 출력된 버킷 이름 |
| `DB_PASSWORD` | `!!anrkd615` |
| `EC2_KEY_NAME` | `mugang-key` |

---

### Step 4 — ECR import (기존에 수동으로 ECR을 만든 경우만)

ECR 리포지토리를 이미 수동으로 만든 경우, Terraform 상태에 등록해야 합니다.
처음부터 시작하는 경우 이 단계는 건너뜁니다.

```bash
cd terraform

terraform init \
  -backend-config="bucket=<Step2에서만든버킷이름>" \
  -backend-config="key=mugang/terraform.tfstate" \
  -backend-config="region=ap-northeast-2"

terraform import aws_ecr_repository.frontend mugang-frontend
terraform import aws_ecr_repository.backend mugang-backend
```

---

### Step 5 — git push → 자동 배포 시작

```bash
git add .
git commit -m "배포 설정 완료"
git push origin main
```

push 후 GitHub Actions 탭에서 진행 상황을 확인할 수 있습니다.

**자동 배포 흐름:**
1. Docker 이미지 빌드 → ECR 푸시
2. Inactive 환경(Blue/Green)에 새 이미지 배포
3. 헬스체크 통과 확인
4. Proxy Nginx upstream 전환
5. 기존 환경 스케일다운

---

## 전체 삭제 (한 번에)

GitHub Actions → **destroy.yml** → 수동 실행 → `destroy` 입력

삭제 순서:
1. `terraform destroy` → EC2, RDS, DynamoDB, VPC, ECR 전부 삭제
2. S3 상태 버킷 자동 삭제

> ⚠️ 삭제 후 복구가 불가능합니다. 신중하게 실행하세요.

---

## 배포 후 접속 주소 확인

```bash
cd terraform
terraform output proxy_public_ip
```

출력된 IP로 브라우저에서 접속합니다: `http://<proxy_public_ip>`
