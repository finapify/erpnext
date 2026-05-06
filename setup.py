from setuptools import setup, find_packages

with open("requirements.txt") as f:
    install_requires = f.read().strip().split("\n")

setup(
    name="finapify_payments",
    version="0.1.0",
    description="Pay vendor bills via Finapify with OTP, async callbacks, and reconciliation",
    author="Finapify",
    author_email="developer@finapify.com",
    packages=find_packages(),
    zip_safe=False,
    include_package_data=True,
    install_requires=install_requires,
)
