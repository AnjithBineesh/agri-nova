"""Command-line entry point: python -m app.ml.train"""
from .training import train_all

if __name__ == "__main__":
    train_all(verbose=True)
