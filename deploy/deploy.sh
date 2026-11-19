#!/usr/bin/env bash
# Deploy the Nyro landing (site/) to the VPS. Static only: the app itself runs on the user's machine (npx nyro-agent web).
# Usage (from the nyro-agent/ folder):  ./deploy/deploy.sh      (DOMAIN defaults to nyro.run)
# First time only, after the A records point at the VPS:  ./deploy/setup-domain.sh
set -euo pipefail
HOST=${HOST:-root@203.194.113.116}
DOMAIN=${DOMAIN:-nyro.run}
cd "$(dirname "$0")/.."
test -f site/index.html
ssh -o BatchMode=yes "$HOST" "mkdir -p /var/www/nyro"
rsync -az --delete --exclude '.DS_Store' -e "ssh -o BatchMode=yes" site/ "$HOST:/var/www/nyro/"
ssh -o BatchMode=yes "$HOST" "chmod -R a+rX /var/www/nyro"
curl -s -o /dev/null -w "https %{http_code}\n" "https://$DOMAIN/" || echo "https not set up yet: run ./deploy/setup-domain.sh"
echo "deployed → https://$DOMAIN"
