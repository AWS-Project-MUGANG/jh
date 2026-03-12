terraform {
  # GitHub Actions에서 상태 파일을 공유하기 위한 S3 백엔드
  # 사전 작업: aws s3 mb s3://<버킷 이름> --region ap-northeast-2
  backend "s3" {
    # bucket / key / region 은 terraform init -backend-config 로 주입됩니다.
    encrypt = true
  }
}

provider "aws" {
  region = "ap-northeast-2" # 서울 리전
}