# 바닐라 JS (가벼운 정적 웹 사이트)를 띄우기 위한 Nginx 설정
FROM nginx:alpine

# 기존 기본 Nginx HTML 페이지 삭제
RUN rm -rf /usr/share/nginx/html/*

# 생성해둔 HTML, CSS, JS 파일을 Nginx 기본 폴더로 복사
COPY . /usr/share/nginx/html/

# / 경로로 접속 시 로그인 페이지로 자동 리다이렉트 (선택 사항)
RUN echo 'server { listen 80; location / { root /usr/share/nginx/html; index pages/login.html student_main.html; } }' > /etc/nginx/conf.d/default.conf

# 외부 접근을 위한 포트 개방
EXPOSE 80

# Nginx 실행 명령어
CMD ["nginx", "-g", "daemon off;"]
