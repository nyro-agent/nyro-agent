# __DOMAIN__: static landing (site/), behind the SNI router on :443 like the other sites on this VPS
server {
    listen 80;
    listen [::]:80;
    server_name __DOMAIN__ www.__DOMAIN__;
    location /.well-known/acme-challenge/ { root /var/www/nyro; }
    location / { return 301 https://__DOMAIN__$request_uri; }
}

server {
    listen 127.0.0.1:8443 ssl proxy_protocol;
    server_name __DOMAIN__ www.__DOMAIN__;
    ssl_certificate /etc/letsencrypt/live/__DOMAIN__/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/__DOMAIN__/privkey.pem;
    root /var/www/nyro;
    index index.html;

    if ($host = www.__DOMAIN__) { return 301 https://__DOMAIN__$request_uri; }

    location /assets/ { expires 1d; add_header Cache-Control "public"; }
    location / { add_header Cache-Control "no-cache"; try_files $uri $uri/ =404; }
    error_page 404 /404.html;
}
