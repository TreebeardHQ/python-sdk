from setuptools import find_packages, setup

# Determine the package name and directory
package_name = "lumberjack"

setup(
    name=package_name,
    version="0.4.18",
    packages=find_packages(include=[package_name, f"{package_name}.*"]),
    description="Lumberjack logging library",
    author="George Mayer",
    author_email="george@treebeardhq.com",
    url="https://github.com/treebeardhq/lumberjack-sdk-python",
    python_requires=">=3.8",
    install_requires=[
        # Add your dependencies here
    ],
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
    ],
)
