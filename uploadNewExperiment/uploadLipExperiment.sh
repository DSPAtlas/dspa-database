#!/bin/bash

# Check if folder path and VM username are provided
if [ -z "$1" ] || [ -z "$2" ]; then
  echo "Usage: ./mybash.sh /path/to/folder vm_username"
  exit 1
fi

FOLDER_TO_UPLOAD="$1"
VM_USER="$2"
VM_HOST="sysbc-lx-s03.ethz.ch" 

# Upload local data and scripts
scp -r "$FOLDER_TO_UPLOAD" "$VM_USER@$VM_HOST:/tmp/upload"
scp -r ./src "$VM_USER@$VM_HOST:/tmp/src"


# Run scripts on VM in the virtual environment
ssh "$VM_USER@$VM_HOST" bash -c "'
  export MYSQL_USER=root
  export MYSQL_PASSWORD=dspa
  export MYSQL_HOST=127.0.0.1
  export MYSQL_PORT=3307
  export MYSQL_DATABASE=dynaprotdbv2
  export PYTHONUNBUFFERED=1

  chmod -R u+rx /tmp/src

  source /home/ekrismer/dynaprot-venv/bin/activate

  python /tmp/src/metadata.py /tmp/upload/$(basename "$FOLDER_TO_UPLOAD")
  python /tmp/src/proteinScores.py
  

  # Clean up uploaded data folder
  rm -rf /tmp/upload/$(basename "$FOLDER_TO_UPLOAD")
  echo \"🧹 Upload folder cleaned up from VM.\"
'"


