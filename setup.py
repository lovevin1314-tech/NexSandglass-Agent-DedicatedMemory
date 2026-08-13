from setuptools import setup, find_packages

if __name__ == "__main__":
    # 注意：此文件会被 Hermes memory-provider 加载器作为子模块 exec_module()
    # （遍历插件目录所有 *.py），模块级副作用（读文件、调 setup()）必须关进
    # __main__ 保护，否则 setuptools 会解析继承来的 sys.argv（如
    # ['main.py','gateway','run']）并抛 SystemExit 杀死整个网关进程。
    setup(
        name="nexsandglass",
        version="2.20.5",
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
