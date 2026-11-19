#!/usr/bin/env bash
# One time on the VPS: certificate (webroot) -> HTTPS conf behind the SNI router. Leaves every other site alone.
#   ./deploy/setup-domain.sh          (DOMAIN defaults to nyro.run; run ./deploy/deploy.sh first so the webroot exists)
set -euo pipefail
HOST=${HOST:-root@203.194.113.116}; D=${DOMAIN:-nyro.run}; IP=${HOST#*@}
cd "$(dirname "$0")/.."
GOT=$(dig +short A "$D" @1.1.1.1 | tail -1)
[ "$GOT" = "$IP" ] || { echo "$D -> '${GOT:-nothing}', not $IP yet. Wait for DNS, then run again."; exit 1; }
ssh -o BatchMode=yes "$HOST" "set -e; mkdir -p /var/www/nyro
  if [ ! -f /etc/letsencrypt/live/$D/fullchain.pem ]; then
    WWW=''; getent hosts www.$D >/dev/null && WWW='-d www.$D'
    certbot certonly --webroot -w /var/www/nyro -d $D \$WWW --non-interactive --agree-tos --register-unsafely-without-email
  fi
  test -s /etc/letsencrypt/live/$D/fullchain.pem
  cp -f /etc/nginx/conf.d/$D.conf /root/$D.conf.bak 2>/dev/null || true"
sed "s/__DOMAIN__/$D/g" deploy/nginx.conf.tpl | ssh -o BatchMode=yes "$HOST" "cat > /etc/nginx/conf.d/$D.conf
  if nginx -t; then systemctl reload nginx; else cp -f /root/$D.conf.bak /etc/nginx/conf.d/$D.conf; echo 'nginx test failed, old config restored'; exit 1; fi"
curl -s -o /dev/null -w "https %{http_code}\n" "https://$D/"
