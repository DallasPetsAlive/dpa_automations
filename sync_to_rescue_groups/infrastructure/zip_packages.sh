uv export --frozen --no-dev --no-editable -o requirements.txt
uv pip install \
   --no-installer-metadata \
   --no-compile-bytecode \
   --python-platform x86_64-manylinux2014 \
   --python 3.9 \
   --prefix packages \
   -r requirements.txt
mkdir -p python_layer/python
cp -r packages/lib python_layer/python/
