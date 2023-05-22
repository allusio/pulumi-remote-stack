apt update -y
apt install -y python3-venv python3-pip
python3 -m pip install --upgrade pip==23.1.2
pip install pipx==1.2.0
pipx install build
/root/.local/bin/pyproject-build
pipx install twine
export TWINE_REPOSITORY_URL=$DEPLOYMENT_PYTHON_REPOSITORY
export TWINE_USERNAME=_json_key_base64
export TWINE_PASSWORD=$DEPLOYMENT_REPOSITORY_PUSH_CREDENTIALS_B64
/root/.local/bin/twine upload dist/*