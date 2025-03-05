from setuptools import setup, find_packages

setup(
    name="wattleflow",
    version="0.0.0.2",
    description="WattleFlow Workflow for Data Engineers",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    author="WattleFlow",
    author_email="wattleflow@outlook.com",
    url="https://github.com/wattleflow/wattleflow.git",
    license="Apache-2.0",
    packages=find_packages(where="src"),  # Pronalazi sve podpakete unutar src/
    package_dir={"": "src"},  # Označava src/ kao root za pakete
    include_package_data=True,  # Ako ima dodatne datoteke kao .json, .yaml, itd.
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3.13",
        "Operating System :: OS Independent",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Libraries",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "License :: OSI Approved :: Apache Software License",
    ],
    python_requires=">=3.9",
    install_requires=[
        "yaml"
    ],
    extras_require={
        # "dev": ["pytest", "black", "mypy"],
    },
)
