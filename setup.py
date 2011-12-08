from setuptools import setup, find_packages

setup(
    name = 'deployment',
    version = '0.1',
    author = 'Marc DellaVolpe',
    description = 'Standard deployment tasks',
    packages = find_packages(),
    install_requires=[
        "Fabric"
    ],
    include_package_data=True,
    zip_safe=False
)
