PYTHON="${PYTHON:-$(command -v python3.14 || command -v python3)}"
PYTHONPATH=$PYTHONPATH:~/DofusFashionistaVanced/fashionistapulp "$PYTHON" wipe_solution_cache.py
cd fashionsite
"$PYTHON" -m django compilemessages
sudo systemctl restart httpd

