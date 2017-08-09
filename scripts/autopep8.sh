#!/bin/bash

LIBFILES="$(find ./manager_advhost -name '*.py' | tr '\n' ' ')"

autopep8 -ia --ignore=E501 ${LIBFILES}
