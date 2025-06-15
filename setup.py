from pathlib import Path
from setuptools import setup, find_packages

long_description = Path("README.md").read_text(encoding="utf-8")

setup(
    name="wattleflow",
    description="WattleFlow Workflow",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="WattleFlow",
    author_email="wattleflow@outlook.com",
    url="https://github.com/wattleflow/workflow.git",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    include_package_data=True,
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
    ],
    python_requires=">=3.9",
    setup_requires=["setuptools_scm"],
    use_scm_version=True,
    extras_require={},
)
