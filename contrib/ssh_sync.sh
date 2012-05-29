#!/bin/bash

curl -H 'Content-Type: application/json' -X POST http://localhost:5984/_replicate -d '{"source":"'"$1"'", "target":"http://localhost:5985/'"$1"'"}'


