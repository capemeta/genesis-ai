#!/bin/sh
set -eu

ROOT_PATH_VALUE="${ROOT_PATH:-/}"

if [ -z "$ROOT_PATH_VALUE" ]; then
  ROOT_PATH_VALUE="/"
fi

case "$ROOT_PATH_VALUE" in
  /*) ;;
  *) ROOT_PATH_VALUE="/$ROOT_PATH_VALUE" ;;
esac

while [ "$ROOT_PATH_VALUE" != "/" ] && [ "${ROOT_PATH_VALUE%/}" != "$ROOT_PATH_VALUE" ]; do
  ROOT_PATH_VALUE="${ROOT_PATH_VALUE%/}"
done

if [ "$ROOT_PATH_VALUE" = "/" ]; then
  export NGINX_ROOT_PATH_PREFIX=""
  export NGINX_ROOT_PATH_SLASH="/"
  export NGINX_ROOT_PATH_EXACT="/__genesis_root_redirect_disabled__"
else
  export NGINX_ROOT_PATH_PREFIX="$ROOT_PATH_VALUE"
  export NGINX_ROOT_PATH_SLASH="$ROOT_PATH_VALUE/"
  export NGINX_ROOT_PATH_EXACT="$ROOT_PATH_VALUE"
fi
