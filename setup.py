from setuptools import setup, find_packages

with open("requirements.txt") as f:
	install_requires = f.read().strip().split("\n")

from leave_accrual import __version__ as version

setup(
	name="leave_accrual",
	version=version,
	description="Custom Leave Accrual Policy for ERPNext HR",
	author="Antigravity",
	author_email="bot@example.com",
	packages=find_packages(),
	zip_safe=False,
	include_package_data=True,
	install_requires=install_requires
)
