from setuptools import setup, find_packages

setup(
    name="nexsandglass",
    version="2.11.1",
    description="沙漏记忆系统 — 纯本地零依赖L3思考层",
    long_description=open("README.md", encoding="utf-8").read(),
    long_description_content_type="text/markdown",
    url="https://github.com/lovevin1314-tech/NexSandglass-Agent-DedicatedMemory",
    author="NeuroBase",
    license="MIT",
    packages=find_packages(),
    py_modules=[f[:-3] for f in __import__('os').listdir('.') if f.endswith('.py') and not f.startswith('_')],
    python_requires=">=3.10",
)
