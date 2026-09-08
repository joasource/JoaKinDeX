#!/usr/bin/env bash
# JoaKinDeX - Criado por Joaquim Ferreira Silva Neto <joaquimfsneto@gmail.com>
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
if [ -f "$DIR/joakindex" ]; then
    "$DIR/joakindex" "$@"
else
    "$DIR/joaclassificador-pdf" "$@"
fi
