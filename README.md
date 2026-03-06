# mugang_aws

# 터미널에서 SSH 켜기
cd c:/mugang_aws
ssh -i "mugang-key.pem" -L 5432:terraform-20260303070103185000000001.cba8sagacwbn.ap-northeast-2.rds.amazonaws.com:5432 ec2-user@3.34.141.17 -N


# backend
python -m uvicorn main:app --reload
uvicorn main:app --reload
uvicorn main:app --host 0.0.0.0 --port 8000

# frontend
python -m http.server 8080

# 교직원 로그인 정보
staff / 123123123
