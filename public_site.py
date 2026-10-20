"""Vercel entrypoint: the interactive SIAS simulator, without database dependencies."""
from demo_app import create_demo_app

app = create_demo_app()
