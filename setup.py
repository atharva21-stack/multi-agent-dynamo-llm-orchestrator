"""Setup configuration for agent-inference-stack."""
from setuptools import find_packages, setup

setup(
    name="agent-inference-stack",
    version="0.1.0",
    description="Multi-agent AI system with Dynamo token batching, vLLM inference, and Kubernetes orchestration",
    author="agent-inference-stack",
    author_email="dev@agent-inference-stack.ai",
    url="https://github.com/your-org/agent-inference-stack",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    python_requires=">=3.10",
    install_requires=[
        "fastapi>=0.104.0",
        "uvicorn[standard]>=0.24.0",
        "pydantic>=2.5.0",
        "pydantic-settings>=2.1.0",
        "redis[hiredis]>=5.0.0",
        "asyncpg>=0.29.0",
        "sqlalchemy[asyncio]>=2.0.0",
        "structlog>=23.2.0",
        "tenacity>=8.2.0",
        "pyyaml>=6.0",
        "python-dotenv>=1.0.0",
    ],
    entry_points={
        "console_scripts": [
            "agent-inference-stack=src.api.app:main",
        ],
    },
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
    ],
)
