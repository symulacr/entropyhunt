from __future__ import annotations

from setuptools import find_packages, setup


package_name = "entropy_hunt_ros2"


setup(
    name=package_name,
    version="0.1.0",
    packages=find_packages(include=[package_name, f"{package_name}.*"]),
    package_dir={"": "."},
    include_package_data=True,
    install_requires=["setuptools"],
    zip_safe=True,
    description="ROS 2 operator and drone nodes for Entropy Hunt",
    entry_points={
        "console_scripts": [
            "drone_node = entropy_hunt_ros2.drone_node:main",
            "operator_node = entropy_hunt_ros2.operator_node:main",
        ]
    },
)
