# 바닐라 JS (가벼운 정적 웹 사이트)를 띄우기 위한 Nginx 설정
FROM nginx:alpine

# 기존 기본 Nginx HTML 페이지 삭제
RUN rm -rf /usr/share/nginx/html/*

# 생성해둔 HTML, CSS, JS 파일을 Nginx 기본 폴더로 복사
COPY . /usr/share/nginx/html/

# Nginx 설정: 정확한 로그인 페이지 연결 및 API 프록시
RUN echo 'server { \
    listen 80; \
    root /usr/share/nginx/html; \
    # 정적 파일 우선 확인, 없으면 404
    location / { \
        try_files $uri $uri/ =404; \
    } \
    # 루트 접속 시 로그인 페이지로 명시적 리다이렉트
    location = / { \
        return 301 /pages/auth/login.html; \
    } \
    location /api { \
        proxy_pass http://backend:8000; \
        proxy_set_header Host $host; \
        proxy_set_header X-Real-IP $remote_addr; \
    } \
    # CSS, JS 등 폴더 단축 경로 허용 여부 \
    location /css/ { alias /usr/share/nginx/html/css/; } \
    location /js/ { alias /usr/share/nginx/html/js/; } \
    location /pages/ { alias /usr/share/nginx/html/pages/; } \
    # 사용자 편의를 위한 단축 경로 (pages 폴더 생략본 허용) \
    location /student/ { alias /usr/share/nginx/html/pages/student/; } \
    location /admin/ { alias /usr/share/nginx/html/pages/admin/; } \
    location /auth/ { alias /usr/share/nginx/html/pages/auth/; } \
}' > /etc/nginx/conf.d/default.conf

# 외부 접근을 위한 포트 개방
EXPOSE 80

# Nginx 실행 명령어
CMD ["nginx", "-g", "daemon off;"]
