#!/bin/bash

LIBFILES="$(find ./manager_apiserver -name '*.py' | tr '\n' ' ')"

autopep8 -ia --ignore=E501 ${LIBFILES}
