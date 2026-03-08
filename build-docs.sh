#!/usr/bin/env bash

# install deps and build
pip install .[dev]
cd docs
make clean html |& tee make.log

# we are in GHA and not on main, fail build on error
if [ "$GITHUB_ACTIONS" = "true" ]; then
  if [ "$GITHUB_REF_NAME" != "main" ]; then
    set +e
    grep '\(ERROR\|WARNING\)' make.log
    if [ $? -eq 0 ]; then
      echo "Problems found in docs build"
      exit 1
    else
      exit 0
    fi
  fi
fi

# We are in main branch in github actions, create archive
if [ "$GITHUB_ACTIONS" = "true" ]; then
  if [ "$GITHUB_REF_NAME" = "main" ]; then
      # GHA does `set -e` for us, but we expect the grep below to fail. Thus, we must `set +e` here.
      echo "This is the main branch. Create Archive."
      cd _build/html
      tar -cvjf ../../../docs.tbz ./*
  fi
fi
