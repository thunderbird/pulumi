#!/bin/bash

### Usage
#
#     Run this script, supplying the arguments outlined below in this specific order:
#
#         ./quickstart.sh \
#             /path/to/project/root \        # The root of your code project where you want to set up a pulumi project
#             pulumi-state-s3-bucket-name \  # S3 bucket where you'll store your pulumi state files
#             project_name, \                # Name of your project as it will be known to pulumi
#             stack_name, \                  # Name of the first stack you want to create
#             [code_version]                 # Code version (git branch) that you want to pin. Optional; defaults to "main"
#
###

# Internalize some variables
CODE_PATH=$1
BUCKET_NAME=$2
PROJECT_NAME=$3
STACK_NAME=$4

# Figure out the directory this is being run from
REPO_DIR=$(realpath .)

# Determine preferred version of this module to use; default to main branch
if [ -z $5 ]; then
    CODE_VERSION="main"
else
    CODE_VERSION=$5
fi

# Ensure Pulumi is installed
if ! which pulumi &> /dev/null; then
    echo 'Installing Pulumi...'
    curl -fsSL https://get.pulumi.com | sh &> /dev/null
fi

# Validate the code path and enter that directory
if [ ! -e $CODE_PATH ]; then
    echo "Code path $CODE_PATH does not exist. Refusing to continue."
    exit 1
fi
echo "Entering $CODE_PATH"
pushd $CODE_PATH &> /dev/null

# Make a pulumi directory if we have to and get into it
echo "Setting up pulumi project directory"
if [ ! -e pulumi ]; then
    mkdir pulumi
elif [ ! -d pulumi ]; then
    echo "A file already exists called 'pulumi', and it is not a directory. Refusing to continue."
    exit 1
fi
cd pulumi

# Make sure there isn't already a Pulumi project here
if [ -f Pulumi.yaml ]; then
    echo "A Pulumi project already exists here. Refusing to continue."
    exit 1
fi

echo "Logging in to pulumi"
pulumi login s3://$BUCKET_NAME

echo "Setting up new pulumi project"
pulumi new aws-python --name $PROJECT_NAME --stack $STACK_NAME

echo "Setting up tb_pulumi"
echo "git+https://github.com/thunderbird/pulumi.git@$CODE_VERSION" > requirements.txt
pip install -r requirements.txt

cp $REPO_DIR/__main__.py.example ./__main__.py
cp $REPO_DIR/config.stack.yaml.example ./config.$STACK_NAME.yaml

virtualenv venv
./venv/bin/pip install -r requirements.txt

echo "Running a preview"
pulumi preview

popd &> /dev/null